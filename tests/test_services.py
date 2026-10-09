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

        assert result.startswith("s3://test_bucket/html/")
        assert result.endswith(".html")
        hash_part = result.split("/")[-1].replace(".html", "")
        assert len(hash_part) == 64


@pytest.mark.asyncio
async def test_dynamo_pagination_filter_and_delete() -> None:
    service = DynamoDBService("test_table", endpoint_url="http://localhost:4566")
    with patch.object(service.session, "resource") as resource:
        table = AsyncMock()
        resource.return_value.__aenter__.return_value.Table.return_value = table
        table.scan.return_value = {"Items": [], "LastEvaluatedKey": {"url": "https://next.example"}}
        items, cursor = await service.list_urls(5, "https://previous.example", "a" * 64)
        assert items == []
        assert cursor == "https://next.example"
        table.scan.assert_awaited_once_with(
            Limit=5,
            ConsistentRead=True,
            ExclusiveStartKey={"url": "https://previous.example"},
            FilterExpression="content_hash = :hash",
            ExpressionAttributeValues={":hash": "a" * 64},
        )
        table.delete_item.return_value = {"Attributes": {"url": "https://next.example"}}
        assert await service.delete_url("https://next.example")
        table.delete_item.return_value = {}
        assert not await service.delete_url("https://next.example")


@pytest.mark.asyncio
async def test_dynamo_stats_across_pages() -> None:
    service = DynamoDBService("test_table")
    with patch.object(service.session, "resource") as resource:
        table = AsyncMock()
        resource.return_value.__aenter__.return_value.Table.return_value = table
        table.scan.side_effect = [
            {"Items": [{"content_hash": "a" * 64}, {}], "LastEvaluatedKey": {"url": "https://a"}},
            {"Items": [{"content_hash": "a" * 64}, {"content_hash": "b" * 64}]},
        ]
        assert await service.stats() == {
            "total_urls": 4,
            "with_content": 3,
            "unique_contents": 2,
        }
        assert table.scan.await_count == 2
        assert table.scan.call_args_list[0].kwargs == {"Limit": 100, "ConsistentRead": True}


@pytest.mark.asyncio
async def test_s3_read_and_missing_object() -> None:
    from botocore.exceptions import ClientError

    service = S3Service("test_bucket")
    with patch.object(service.session, "client") as client:
        s3 = AsyncMock()
        client.return_value.__aenter__.return_value = s3
        body = AsyncMock()
        body.__aenter__.return_value.read.return_value = "Привет".encode()
        s3.get_object.return_value = {"Body": body}
        assert await service.get_html("a" * 64) == "Привет"
        s3.get_object.assert_awaited_once_with(Bucket="test_bucket", Key=f"html/{'a' * 64}.html")
        s3.get_object.side_effect = ClientError({"Error": {"Code": "NoSuchKey"}}, "GetObject")
        assert await service.get_html("b" * 64) is None
        s3.get_object.side_effect = ClientError({"Error": {"Code": "AccessDenied"}}, "GetObject")
        with pytest.raises(ClientError):
            await service.get_html("b" * 64)
