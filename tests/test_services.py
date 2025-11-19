from unittest.mock import AsyncMock, patch

import pytest

from crawler.models import RawHtmlData, UrlData
from crawler.services import DynamoDBService, S3Service


@pytest.mark.asyncio
async def test_dynamo_create_url_data() -> None:
    service = DynamoDBService(table_name="test_table")
    url_data = UrlData(url="https://example.com", content_hash="abc123")

    with patch.object(service.session, "resource") as mock_resource:
        mock_table = AsyncMock()
        mock_table.put_item = AsyncMock()
        mock_dynamo = AsyncMock()
        mock_dynamo.Table = AsyncMock(return_value=mock_table)
        mock_resource.return_value.__aenter__.return_value = mock_dynamo

        result = await service.create_url_data(url_data)

        assert result["url"] == "https://example.com"
        assert result["content_hash"] == "abc123"


@pytest.mark.asyncio
async def test_dynamo_get_url_data() -> None:
    """Test getting URL data from DynamoDB when it exists."""
    service = DynamoDBService(table_name="test_table")

    with patch.object(service.session, "resource") as mock_resource:
        mock_table = AsyncMock()
        mock_table.get_item = AsyncMock(
            return_value={
                "Item": {
                    "url": "https://example.com",
                    "content_hash": "abc123",
                    "s3_link": "s3://bucket/html/abc123.html",
                }
            }
        )
        mock_dynamo = AsyncMock()
        mock_dynamo.Table = AsyncMock(return_value=mock_table)
        mock_resource.return_value.__aenter__.return_value = mock_dynamo

        result = await service.get_url_data("https://example.com")

        assert result is not None
        assert result["url"] == "https://example.com"
        assert result["content_hash"] == "abc123"


@pytest.mark.asyncio
async def test_dynamo_get_url_data_not_found() -> None:
    """Test getting URL data from DynamoDB when it doesn't exist."""
    service = DynamoDBService(table_name="test_table")

    with patch.object(service.session, "resource") as mock_resource:
        mock_table = AsyncMock()
        mock_table.get_item = AsyncMock(return_value={})
        mock_dynamo = AsyncMock()
        mock_dynamo.Table = AsyncMock(return_value=mock_table)
        mock_resource.return_value.__aenter__.return_value = mock_dynamo

        result = await service.get_url_data("https://notfound.com")

        assert result is None


@pytest.mark.asyncio
async def test_s3_save_html() -> None:
    service = S3Service(bucket_name="test_bucket")
    raw_html = RawHtmlData(url="https://example.com", html_content="<html></html>")

    with patch.object(service.session, "client") as mock_client:
        mock_s3 = AsyncMock()
        mock_s3.put_object = AsyncMock()
        mock_client.return_value.__aenter__.return_value = mock_s3

        result = await service.save_html(raw_html)

        assert result.startswith("s3://test_bucket/html/")
        assert result.endswith(".html")


@pytest.mark.asyncio
async def test_s3_save_html_with_content() -> None:
    """Test S3 save with actual HTML content and verify hash."""
    service = S3Service(bucket_name="test_bucket")
    html_content = "<html><body><h1>Test Page</h1></body></html>"
    raw_html = RawHtmlData(url="https://example.com", html_content=html_content)

    with patch.object(service.session, "client") as mock_client:
        mock_s3 = AsyncMock()
        mock_s3.put_object = AsyncMock()
        mock_client.return_value.__aenter__.return_value = mock_s3

        result = await service.save_html(raw_html)

        # Verify the S3 key contains a valid SHA-256 hash
        assert result.startswith("s3://test_bucket/html/")
        assert result.endswith(".html")
        # SHA-256 hash is 64 characters
        hash_part = result.split("/")[-1].replace(".html", "")
        assert len(hash_part) == 64
