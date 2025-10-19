import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from crawler.models import UrlData, RawHtmlData
from crawler.services import DynamoDBService, S3Service


@pytest.mark.asyncio
async def test_dynamo_create_url_data():
    service = DynamoDBService(table_name="test_table")
    url_data = UrlData(url="https://example.com", content_hash="abc123")

    with patch.object(service.session, 'resource') as mock_resource:
        mock_table = AsyncMock()
        mock_table.put_item = AsyncMock()
        mock_dynamo = AsyncMock()
        mock_dynamo.Table = AsyncMock(return_value=mock_table)
        mock_resource.return_value.__aenter__.return_value = mock_dynamo

        result = await service.create_url_data(url_data)

        assert result["url"] == "https://example.com"
        assert result["content_hash"] == "abc123"


@pytest.mark.asyncio
async def test_s3_save_html():
    service = S3Service(bucket_name="test_bucket")
    raw_html = RawHtmlData(url="https://example.com", html_content="<html></html>")

    with patch.object(service.session, 'client') as mock_client:
        mock_s3 = AsyncMock()
        mock_s3.put_object = AsyncMock()
        mock_client.return_value.__aenter__.return_value = mock_s3

        result = await service.save_html(raw_html)

        assert result.startswith("s3://test_bucket/html/")
        assert result.endswith(".html")
