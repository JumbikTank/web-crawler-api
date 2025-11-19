from unittest.mock import AsyncMock

import pytest
from litestar import Litestar
from litestar.datastructures import State
from litestar.testing import AsyncTestClient

from crawler.app import create_url, get_url, save_html


@pytest.mark.asyncio
async def test_create_url_endpoint() -> None:
    """Test POST /urls endpoint."""
    mock_dynamo = AsyncMock()
    mock_dynamo.create_url_data.return_value = {
        "url": "https://example.com",
        "content_hash": "abc123",
        "s3_link": "s3://bucket/html/abc123.html",
        "last_crawled_time": 1234567890,
    }

    app = Litestar(
        route_handlers=[create_url],
        state=State({"dynamo_service": mock_dynamo}),
    )

    async with AsyncTestClient(app=app) as client:
        response = await client.post(
            "/urls",
            json={
                "url": "https://example.com",
                "content_hash": "abc123",
                "s3_link": "s3://bucket/html/abc123.html",
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["url"] == "https://example.com"
        assert data["content_hash"] == "abc123"


@pytest.mark.asyncio
async def test_get_url_endpoint_found() -> None:
    """Test GET /url-data endpoint when URL exists."""
    mock_dynamo = AsyncMock()
    mock_dynamo.get_url_data.return_value = {
        "url": "https://example.com",
        "content_hash": "abc123",
        "s3_link": "s3://bucket/html/abc123.html",
        "last_crawled_time": 1234567890,
    }

    app = Litestar(
        route_handlers=[get_url],
        state=State({"dynamo_service": mock_dynamo}),
    )

    async with AsyncTestClient(app=app) as client:
        response = await client.get("/url-data?url=https://example.com")

        assert response.status_code == 200
        data = response.json()
        assert data["url"] == "https://example.com"
        assert data["content_hash"] == "abc123"


@pytest.mark.asyncio
async def test_get_url_endpoint_not_found() -> None:
    """Test GET /url-data endpoint when URL doesn't exist."""
    mock_dynamo = AsyncMock()
    mock_dynamo.get_url_data.return_value = None

    app = Litestar(
        route_handlers=[get_url],
        state=State({"dynamo_service": mock_dynamo}),
    )

    async with AsyncTestClient(app=app) as client:
        response = await client.get("/url-data?url=https://notfound.com")

        assert response.status_code == 200
        data = response.json()
        assert data == {}


@pytest.mark.asyncio
async def test_save_html_endpoint() -> None:
    """Test POST /html endpoint."""
    mock_s3 = AsyncMock()
    mock_s3.save_html.return_value = "s3://bucket/html/abc123.html"

    app = Litestar(
        route_handlers=[save_html],
        state=State({"s3_service": mock_s3}),
    )

    async with AsyncTestClient(app=app) as client:
        response = await client.post(
            "/html",
            json={
                "url": "https://example.com",
                "html_content": "<html><body>Test</body></html>",
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["url"] == "https://example.com"
        assert data["s3_link"] == "s3://bucket/html/abc123.html"


@pytest.mark.asyncio
async def test_create_app() -> None:
    """Test application factory function."""
    from crawler.app import create_app

    app = create_app()

    assert app is not None
    assert app.openapi_config is not None
    assert app.openapi_config.title == "Web Crawler API"
    assert app.openapi_config.version == "0.1.0"
