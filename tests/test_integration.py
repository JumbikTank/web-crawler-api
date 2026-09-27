"""API tests against a real, isolated SQLite database; no storage mocks."""

import asyncio
import base64
import hashlib
import sqlite3
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from litestar.testing import AsyncTestClient

from crawler.app import create_app
from crawler.config import Settings
from crawler.local import SQLiteStorage


@pytest.fixture
async def client(tmp_path: Path) -> AsyncIterator[AsyncTestClient[Any]]:
    app = create_app(Settings(database_path=tmp_path / "crawler.sqlite3"))
    async with AsyncTestClient(app=app) as test_client:
        yield test_client


async def test_url_lifecycle(client: AsyncTestClient[Any]) -> None:
    url = "https://example.com/page?x=1&y=2"
    result = await client.post("/urls", json={"url": url})
    assert result.status_code == 201
    assert result.json()["last_crawled_time"] > 0
    fetched = await client.get("/url-data", params={"url": url})
    assert fetched.json() == result.json()
    updated = await client.post("/urls", json={"url": url, "last_crawled_time": 0})
    assert updated.json()["last_crawled_time"] == 0
    assert (await client.get("/stats")).json()["total_urls"] == 1
    assert (await client.delete("/url-data", params={"url": url})).status_code == 204
    assert (await client.get("/url-data", params={"url": url})).status_code == 404
    assert (await client.delete("/url-data", params={"url": url})).status_code == 404


async def test_html_roundtrip_dedup_and_filter(client: AsyncTestClient[Any]) -> None:
    html = '<html><h1>Привет</h1><script>alert("x")</script></html>'
    digest = hashlib.sha256(html.encode()).hexdigest()
    for url in ["https://a.example/", "https://b.example/"]:
        saved = await client.post("/html", json={"url": url, "html_content": html})
        assert saved.status_code == 201
        assert saved.json()["content_hash"] == digest
        assert saved.json()["s3_link"] == f"sqlite://html/{digest}"
        read = await client.get("/html", params={"url": url})
        assert read.status_code == 200
        assert read.headers["content-type"].startswith("application/json")
        assert read.json()["html_content"] == html
    await client.post("/urls", json={"url": "https://empty.example/"})
    filtered = await client.get("/urls", params={"content_hash": digest, "limit": 1})
    assert len(filtered.json()["items"]) == 1
    next_page = await client.get(
        "/urls", params={"content_hash": digest, "cursor": filtered.json()["next_cursor"]}
    )
    assert len(next_page.json()["items"]) == 1
    assert next_page.json()["next_cursor"] is None
    assert (await client.get("/stats")).json() == {
        "total_urls": 3,
        "with_content": 2,
        "unique_contents": 1,
    }
    local: SQLiteStorage = client.app.state.s3_service
    with local.connection() as db:
        assert db.execute("SELECT COUNT(*) FROM html").fetchone()[0] == 1
    await client.delete("/url-data", params={"url": "https://a.example/"})
    assert (await client.get("/html", params={"url": "https://b.example/"})).status_code == 200


async def test_replacing_html_keeps_other_urls(client: AsyncTestClient[Any]) -> None:
    for url in ["https://a.example", "https://b.example"]:
        await client.post("/html", json={"url": url, "html_content": "old"})
    await client.post("/html", json={"url": "https://a.example", "html_content": "new"})
    assert (await client.get("/html", params={"url": "https://a.example"})).json()[
        "html_content"
    ] == "new"
    assert (await client.get("/html", params={"url": "https://b.example"})).json()[
        "html_content"
    ] == "old"


async def test_batch_and_pagination(client: AsyncTestClient[Any]) -> None:
    await client.post("/html", json={"url": "https://a.example", "html_content": "saved"})
    result = await client.post(
        "/urls/batch",
        json={
            "urls": [
                "https://c.example",
                "https://a.example",
                "https://b.example",
                "https://a.example",
            ]
        },
    )
    assert result.status_code == 201
    assert result.json()["count"] == 3
    assert result.json()["items"][1]["content_hash"] == hashlib.sha256(b"saved").hexdigest()
    page1 = (await client.get("/urls", params={"limit": 2})).json()
    page2 = (await client.get("/urls", params={"limit": 2, "cursor": page1["next_cursor"]})).json()
    assert [item["url"] for item in page1["items"] + page2["items"]] == [
        "https://a.example",
        "https://b.example",
        "https://c.example",
    ]
    assert page2["next_cursor"] is None


@pytest.mark.parametrize(
    "url",
    [
        "",
        "ftp://example.com",
        "not-a-url",
        "https://",
        "https://a b",
        "https://user:pass@host",
        "https://host:99999",
        "https://[invalid",
        "https://host/\npath",
        "https://" + "a" * 2048,
    ],
)
async def test_invalid_urls(client: AsyncTestClient[Any], url: str) -> None:
    assert (await client.post("/urls", json={"url": url})).status_code == 400
    assert (await client.get("/url-data", params={"url": url})).status_code == 400


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"url": "https://example.com", "unknown": 1},
        {"url": "https://example.com", "content_hash": "abc"},
        {"url": "https://example.com", "last_crawled_time": -1},
    ],
)
async def test_invalid_metadata(client: AsyncTestClient[Any], payload: dict[str, Any]) -> None:
    assert (await client.post("/urls", json=payload)).status_code == 400


@pytest.mark.parametrize(
    "params",
    [
        {"limit": 0},
        {"limit": 101},
        {"limit": "abc"},
        {"cursor": "%%%"},
        {"cursor": base64.urlsafe_b64encode(b"not-a-url").decode()},
        {"content_hash": "abc"},
    ],
)
async def test_invalid_list_params(client: AsyncTestClient[Any], params: dict[str, Any]) -> None:
    assert (await client.get("/urls", params=params)).status_code == 400


async def test_batch_validation_before_writes(client: AsyncTestClient[Any]) -> None:
    for urls in [[], ["https://example.com"] * 101, ["https://valid.example", "invalid"]]:
        assert (await client.post("/urls/batch", json={"urls": urls})).status_code == 400
    assert (await client.get("/stats")).json()["total_urls"] == 0


async def test_html_size_limits(client: AsyncTestClient[Any]) -> None:
    for html in ["", "x" * 1_048_577, "я" * 524_289]:
        response = await client.post(
            "/html", json={"url": "https://example.com", "html_content": html}
        )
        assert response.status_code == 400
    response = await client.post(
        "/html", json={"url": "https://example.com", "html_content": "я" * 524_288}
    )
    assert response.status_code == 201
    response = await client.post(
        "/html", content=b"x" * (8 * 1024 * 1024 + 1), headers={"content-type": "application/json"}
    )
    assert response.status_code == 413


async def test_missing_html(client: AsyncTestClient[Any]) -> None:
    url = "https://example.com"
    assert (await client.get("/html", params={"url": url})).status_code == 404
    await client.post("/urls", json={"url": url})
    assert (await client.get("/html", params={"url": url})).status_code == 404
    await client.post("/urls", json={"url": url, "content_hash": "a" * 64})
    assert (await client.get("/html", params={"url": url})).status_code == 404
    local: SQLiteStorage = client.app.state.dynamo_service
    with local.connection() as db:
        db.execute("UPDATE urls SET content_hash='legacy-invalid'")
    assert (await client.get("/html", params={"url": url})).status_code == 404


async def test_restart_persistence(tmp_path: Path) -> None:
    settings = Settings(database_path=tmp_path / "persist.sqlite3")
    url = "https://example.com"
    async with AsyncTestClient(app=create_app(settings)) as first:
        await first.post("/html", json={"url": url, "html_content": "persistent"})
    async with AsyncTestClient(app=create_app(settings)) as second:
        response = await second.get("/html", params={"url": url})
        assert response.json()["html_content"] == "persistent"


async def test_concurrent_writes(client: AsyncTestClient[Any]) -> None:
    responses = await asyncio.gather(
        *[
            client.post("/html", json={"url": f"https://example.com/{i}", "html_content": "same"})
            for i in range(20)
        ]
    )
    assert all(response.status_code == 201 for response in responses)
    assert (await client.get("/stats")).json() == {
        "total_urls": 20,
        "with_content": 20,
        "unique_contents": 1,
    }


async def test_storage_failure_is_503(client: AsyncTestClient[Any]) -> None:
    service = client.app.state.dynamo_service
    with patch.object(
        service, "get_url_data", AsyncMock(side_effect=sqlite3.OperationalError("secret"))
    ):
        response = await client.get("/url-data", params={"url": "https://example.com"})
    assert response.status_code == 503
    assert "secret" not in response.text


async def test_health_and_openapi(client: AsyncTestClient[Any]) -> None:
    assert (await client.get("/health")).json() == {"status": "ok"}
    schema = await client.get("/schema/openapi.json")
    assert schema.status_code == 200
    assert set(schema.json()["paths"]) >= {
        "/urls",
        "/url-data",
        "/urls/batch",
        "/html",
        "/stats",
        "/health",
    }


def test_configuration(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "configured.sqlite3"))
    monkeypatch.setenv("STORAGE_BACKEND", "aws")
    monkeypatch.setenv("AWS_ENDPOINT_URL", "http://localhost:4566")
    settings = Settings.from_env()
    assert settings.database_path == tmp_path / "configured.sqlite3"
    app = create_app(settings)
    assert app.state.dynamo_service.endpoint_url == "http://localhost:4566"
    with pytest.raises(ValueError, match="STORAGE_BACKEND"):
        Settings(backend="invalid")


async def test_local_list_latency(client: AsyncTestClient[Any]) -> None:
    """NFR-4: in-process HTTP API, 1000 records, one client, 50 reads after warm-up."""
    from time import perf_counter

    storage: SQLiteStorage = client.app.state.dynamo_service
    with storage.connection() as db:
        db.executemany(
            "INSERT INTO urls(url) VALUES (?)",
            [(f"https://example.com/{i:04d}",) for i in range(1000)],
        )
    for _ in range(5):
        assert (await client.get("/urls", params={"limit": 20})).status_code == 200
    durations = []
    for _ in range(50):
        started = perf_counter()
        response = await client.get("/urls", params={"limit": 20})
        durations.append((perf_counter() - started) * 1000)
        assert response.status_code == 200
        assert len(response.json()["items"]) == 20
    p95_ms = sorted(durations)[47]
    print(f"Local API p95: {p95_ms:.2f} ms")
    assert p95_ms < 200, f"Local API p95={p95_ms:.2f} ms exceeds 200 ms"


async def test_cursor_for_long_unicode_url(client: AsyncTestClient[Any]) -> None:
    prefix = "https://example.com/"
    urls = [prefix + "漢" * 1500 + suffix for suffix in ("a", "b")]
    for url in urls:
        assert (await client.post("/urls", json={"url": url})).status_code == 201
    first = (await client.get("/urls", params={"limit": 1})).json()
    assert len(first["next_cursor"]) > 4096
    second = await client.get("/urls", params={"limit": 1, "cursor": first["next_cursor"]})
    assert second.status_code == 200
    assert second.json()["items"][0]["url"] == urls[1]


async def test_hash_with_trailing_newline_is_rejected(client: AsyncTestClient[Any]) -> None:
    digest = "a" * 64 + "\n"
    assert (
        await client.post(
            "/urls",
            json={
                "url": "https://example.com",
                "content_hash": digest,
            },
        )
    ).status_code == 400
    assert (await client.get("/urls", params={"content_hash": digest})).status_code == 400
