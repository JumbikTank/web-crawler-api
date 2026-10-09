import asyncio
import socket
import sqlite3
from collections.abc import AsyncIterator
from pathlib import Path
from time import monotonic
from unittest.mock import AsyncMock, patch

import aiohttp
import pytest
from aiohttp import web
from aiohttp.abc import AbstractResolver, ResolveResult
from litestar.testing import AsyncTestClient

from crawler.app import create_app
from crawler.config import Settings
from crawler.downloader import (
    DownloadedPage,
    Downloader,
    DownloadError,
    FetchResponse,
    PublicResolver,
)
from crawler.extraction import extract_text


async def test_crawl_stores_only_requested_urls(tmp_path: Path) -> None:
    app = create_app(Settings(database_path=tmp_path / "crawl.sqlite3"))
    html = '<h1>Привет &amp; мир</h1><a href="https://unrequested.example">Link</a><script>bad()</script>'
    fetch = AsyncMock(
        side_effect=[
            DownloadedPage("https://one.example/final", html, 200),
            DownloadError("http_error", "Not found", 404),
        ]
    )
    async with AsyncTestClient(app=app) as client:
        with patch.object(app.state.downloader, "fetch", fetch):
            response = await client.post(
                "/crawl",
                json={
                    "urls": [
                        "https://one.example",
                        "https://two.example",
                        "https://one.example",
                    ]
                },
            )
        assert response.status_code == 200
        result = response.json()
        assert (result["saved"], result["failed"]) == (1, 1)
        assert result["items"][0]["final_url"] == "https://one.example/final"
        assert result["items"][1]["http_status"] == 404
        assert [call.args[0] for call in fetch.await_args_list] == [
            "https://one.example",
            "https://two.example",
        ]
        text = await client.get("/text", params={"url": "https://one.example"})
        assert text.json()["text"] == "Привет & мир Link"
        assert (await client.get("/html", params={"url": "https://one.example"})).json()[
            "html_content"
        ] == html
        assert (await client.get("/stats")).json()["total_urls"] == 1
        assert (
            await client.get("/text", params={"url": "https://missing.example"})
        ).status_code == 404
        for urls in [[], ["https://example.com"] * 21, ["invalid"]]:
            assert (await client.post("/crawl", json={"urls": urls})).status_code == 400


async def test_crawl_storage_error_is_per_url(tmp_path: Path) -> None:
    app = create_app(Settings(database_path=tmp_path / "crawl.sqlite3"))
    async with AsyncTestClient(app=app) as client:
        with (
            patch.object(
                app.state.downloader,
                "fetch",
                AsyncMock(
                    return_value=DownloadedPage(
                        "https://example.com",
                        "<p>ok</p>",
                        200,
                    )
                ),
            ),
            patch.object(app.state.s3_service, "save_html", AsyncMock(side_effect=sqlite3.Error())),
        ):
            response = await client.post("/crawl", json={"urls": ["https://example.com"]})
        assert response.json()["items"][0]["error"] == "storage_error"


@pytest.mark.parametrize(
    ("html", "expected"),
    [
        ("", ""),
        ("<p>one<p>two", "one two"),
        ("<div>Текст&nbsp;☀</div>", "Текст ☀"),
        (
            "<head><title>secret</title></head><body><p>Hello</p><style>bad</style>"
            "<script>bad()</script><noscript>bad</noscript><template>bad</template></body>",
            "Hello",
        ),
        ("<a href='https://example.com'>link</a><!-- comment -->", "link"),
    ],
)
def test_native_html_extraction(html: str, expected: str) -> None:
    assert extract_text(html) == expected


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1",
        "http://[::1]",
        "http://10.0.0.1",
        "http://169.254.169.254/latest",
        "http://localhost",
        "http://app.localhost",
        "file:///etc/passwd",
        "http://[ff02::1]",
        "http://[::ffff:127.0.0.1]",
    ],
)
def test_private_addresses_rejected(url: str) -> None:
    with pytest.raises(DownloadError):
        Downloader.check_url(url)


def test_public_literal_address() -> None:
    assert Downloader.check_url("https://1.1.1.1/") == "https://1.1.1.1"


async def test_resolver_checks_actual_connection_addresses() -> None:
    resolver = PublicResolver()
    for address in ["127.0.0.1", "192.168.1.1", "::1"]:
        with patch(
            "aiohttp.resolver.ThreadedResolver.resolve",
            AsyncMock(
                return_value=[
                    {
                        "hostname": "public.test",
                        "host": address,
                        "port": 80,
                        "family": socket.AF_INET,
                        "proto": 0,
                        "flags": 0,
                    }
                ]
            ),
        ):
            with pytest.raises(DownloadError, match="публичные"):
                await resolver.resolve("public.test", 80)
    with patch(
        "aiohttp.resolver.ThreadedResolver.resolve",
        AsyncMock(
            return_value=[
                {
                    "hostname": "public.test",
                    "host": "1.1.1.1",
                    "port": 80,
                    "family": socket.AF_INET,
                    "proto": 0,
                    "flags": 0,
                }
            ]
        ),
    ):
        assert (await resolver.resolve("public.test", 80))[0]["host"] == "1.1.1.1"
    await resolver.close()


async def test_robots_and_redirects() -> None:
    downloader = Downloader()
    requests = AsyncMock(
        side_effect=[
            FetchResponse(
                200,
                "User-agent: *\nDisallow: /blocked\nAllow: /blocked/open\n"
                "Crawl-delay: 2\nRequest-rate: 1/3",
                "text/plain",
            ),
            FetchResponse(302, "", "text/html", "/blocked/open"),
            FetchResponse(200, "<p>allowed</p>", "text/html"),
        ]
    )
    with patch.object(downloader, "_request", requests):
        result = await downloader.fetch("https://site.example/start")
        assert result.final_url == "https://site.example/blocked/open"
        assert requests.await_args_list[1].args[2] == 3
        with pytest.raises(DownloadError, match="robots.txt"):
            await downloader.fetch("https://site.example/blocked")
    assert requests.await_count == 3


@pytest.mark.parametrize(
    ("response", "code"),
    [
        (FetchResponse(500, "error", "text/html"), "http_error"),
        (FetchResponse(200, "binary", "application/pdf"), "content_type"),
        (FetchResponse(200, "", "text/html"), "html_size"),
        (FetchResponse(200, "я" * 524_289, "text/html"), "html_size"),
    ],
)
async def test_download_rejects_invalid_pages(response: FetchResponse, code: str) -> None:
    downloader = Downloader()
    with patch.object(
        downloader,
        "_request",
        AsyncMock(
            side_effect=[
                FetchResponse(404, "", "text/plain"),
                response,
            ]
        ),
    ):
        with pytest.raises(DownloadError) as error:
            await downloader.fetch("https://example.com")
    assert error.value.code == code


async def test_robots_errors_limits_and_cache_expiry() -> None:
    downloader = Downloader()
    with patch.object(
        downloader,
        "_request",
        AsyncMock(
            return_value=FetchResponse(
                503,
                "",
                "text/plain",
            )
        ),
    ):
        with pytest.raises(DownloadError) as error:
            await downloader.fetch("https://example.com")
        assert error.value.code == "robots_unavailable"
    with patch.object(
        downloader,
        "_request",
        AsyncMock(
            return_value=FetchResponse(
                301,
                "",
                "text/plain",
                "/robots.txt",
            )
        ),
    ):
        with pytest.raises(DownloadError) as error:
            await downloader.fetch("https://example.com")
        assert error.value.code == "redirect_limit"
    requests = AsyncMock(
        side_effect=[
            FetchResponse(302, "", "text/plain", "/robots-real.txt"),
            FetchResponse(200, "User-agent: *\nDisallow:", "text/plain"),
            *[FetchResponse(301, "", "text/html", "/loop") for _ in range(6)],
        ]
    )
    with patch.object(downloader, "_request", requests):
        with pytest.raises(DownloadError) as error:
            await downloader.fetch("https://example.com/loop")
        assert error.value.code == "redirect_limit"
    rules = downloader.robots["https://example.com"][1]
    downloader.robots = {f"https://site{i}.example": (0, rules) for i in range(1024)}
    with patch.object(
        downloader, "_request", AsyncMock(return_value=FetchResponse(404, "", "text/plain"))
    ):
        await downloader._robots("https://new.example")
    assert len(downloader.robots) == 1024


@pytest.mark.parametrize(
    ("exception", "code"),
    [
        (TimeoutError(), "timeout"),
        (aiohttp.ClientConnectionError(), "network_error"),
    ],
)
async def test_network_errors(exception: Exception, code: str) -> None:
    with patch.object(Downloader, "_request", AsyncMock(side_effect=exception)):
        with pytest.raises(DownloadError) as error:
            await Downloader().fetch("https://example.com")
        assert error.value.code == code


async def test_redirect_cannot_target_private_network() -> None:
    requests = AsyncMock(
        side_effect=[
            FetchResponse(404, "", "text/plain"),
            FetchResponse(302, "", "text/html", "http://127.0.0.1/secret"),
        ]
    )
    with patch.object(Downloader, "_request", requests):
        with pytest.raises(DownloadError) as error:
            await Downloader().fetch("https://example.com")
    assert error.value.code == "unsafe_url"
    assert requests.await_count == 2


class FixtureResolver(AbstractResolver):
    """Only used by the controlled HTTP fixture; never selected by application configuration."""

    async def resolve(
        self, host: str, port: int = 0, family: socket.AddressFamily = socket.AF_INET
    ) -> list[ResolveResult]:
        return [
            {
                "hostname": host,
                "host": "127.0.0.1",
                "port": port,
                "family": socket.AF_INET,
                "proto": 0,
                "flags": 0,
            }
        ]

    async def close(self) -> None:
        pass


@pytest.fixture
async def http_fixture() -> AsyncIterator[tuple[Downloader, str, list[str]]]:
    calls: list[str] = []

    async def handle(request: web.Request) -> web.StreamResponse:
        calls.append(request.path)
        if request.path == "/robots.txt":
            return web.Response(status=404)
        if request.path == "/large":
            return web.Response(body=b"x" * 1_048_577, content_type="text/html")
        if request.path == "/stream":
            response = web.StreamResponse(headers={"Content-Type": "text/html"})
            await response.prepare(request)
            await response.write(b"x" * 1_048_577)
            await response.write_eof()
            return response
        if request.path == "/compressed":
            return web.Response(body=b"test", headers={"Content-Encoding": "gzip"})
        if request.path == "/charset":
            return web.Response(
                body=b"hello", headers={"Content-Type": "text/html; charset=not-real"}
            )
        return web.Response(
            text="<h1>Local test</h1><a href='/unrequested'>link</a>", content_type="text/html"
        )

    app = web.Application()
    app.router.add_get("/{path:.*}", handle)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 0)
    await site.start()
    port = runner.addresses[0][1]
    downloader = Downloader()
    downloader.session = aiohttp.ClientSession(
        connector=aiohttp.TCPConnector(resolver=FixtureResolver()),
        auto_decompress=False,
    )
    try:
        yield downloader, f"http://fixture.test:{port}", calls
    finally:
        await downloader.close()
        await runner.cleanup()


async def test_real_http_download_without_recursive_requests(
    http_fixture: tuple[Downloader, str, list[str]],
) -> None:
    downloader, origin, calls = http_fixture
    result = await downloader.fetch(origin + "/page")
    assert result.http_status == 200
    assert extract_text(result.html) == "Local test link"
    assert calls == ["/robots.txt", "/page"]


async def test_http_stream_limits_and_encoding(
    http_fixture: tuple[Downloader, str, list[str]],
) -> None:
    downloader, origin, _ = http_fixture
    for path, code in [
        ("/large", "too_large"),
        ("/stream", "too_large"),
        ("/compressed", "encoding"),
    ]:
        with pytest.raises(DownloadError) as error:
            await downloader._request(origin + path, 1_048_576, delay=0)
        assert error.value.code == code
    assert (await downloader._request(origin + "/charset", 1_048_576, delay=0)).body == "hello"


async def test_bounded_domain_state(http_fixture: tuple[Downloader, str, list[str]]) -> None:
    downloader, origin, _ = http_fixture
    downloader.host_locks = {str(i): asyncio.Lock() for i in range(1024)}
    downloader.last_request = dict.fromkeys(downloader.host_locks, monotonic())
    with pytest.raises(DownloadError) as error:
        await downloader._request(origin, 100)
    assert error.value.code == "busy"
    downloader.last_request = dict.fromkeys(downloader.host_locks, monotonic() - 61)
    assert (await downloader._request(origin, 1000)).status == 200


def test_origin_normalizes_default_ports_and_unicode_domains() -> None:
    assert Downloader.check_url("https://EXAMPLE.com:443/path") == "https://example.com"
    assert Downloader.check_url("http://example.com:8080/path") == "http://example.com:8080"
    assert Downloader.check_url("https://пример.рф/") == "https://xn--e1afmkfd.xn--p1ai"


async def test_global_download_concurrency_limit() -> None:
    active = peak = 0

    async def respond(url: str, max_bytes: int, delay: float = 1.0) -> FetchResponse:
        nonlocal active, peak
        active += 1
        peak = max(peak, active)
        await asyncio.sleep(0.005)
        active -= 1
        if url.endswith("/robots.txt"):
            return FetchResponse(404, "", "text/plain")
        return FetchResponse(200, "<p>ok</p>", "text/html")

    downloader = Downloader()
    with patch.object(downloader, "_request", respond):
        results = await asyncio.gather(
            *[downloader.fetch(f"https://site{i}.example/page") for i in range(12)]
        )
    assert len(results) == 12
    assert 1 < peak <= 4


async def test_origin_delay_applies_between_requests(
    http_fixture: tuple[Downloader, str, list[str]],
) -> None:
    downloader, origin, _ = http_fixture
    await downloader._request(origin + "/first", 1000, delay=0)
    start = monotonic()
    await downloader._request(origin + "/second", 1000, delay=0.05)
    assert monotonic() - start >= 0.045
