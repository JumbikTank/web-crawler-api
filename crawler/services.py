import hashlib
from time import time
from typing import Any

import aioboto3
from botocore.config import Config
from botocore.exceptions import ClientError

from crawler.models import RawHtmlData, UrlData

AWS_CONFIG = Config(connect_timeout=3, read_timeout=5, retries={"max_attempts": 2})


class DynamoDBService:
    def __init__(
        self, table_name: str, region: str = "us-east-1", endpoint_url: str | None = None
    ) -> None:
        self.table_name = table_name
        self.region = region
        self.session = aioboto3.Session()
        self.endpoint_url = endpoint_url

    def _resource(self) -> Any:
        return self.session.resource(
            "dynamodb", region_name=self.region, endpoint_url=self.endpoint_url, config=AWS_CONFIG
        )

    async def create_url_data(self, url_data: UrlData) -> dict[str, Any]:
        async with self._resource() as dynamo:
            table = await dynamo.Table(self.table_name)
            item: dict[str, Any] = {
                "url": url_data.url,
                "s3_link": url_data.s3_link,
                "content_hash": url_data.content_hash,
                "last_crawled_time": (
                    int(time())
                    if url_data.last_crawled_time is None
                    else url_data.last_crawled_time
                ),
            }
            await table.put_item(Item=item)
            return item

    async def get_url_data(self, url: str) -> dict[str, Any] | None:
        async with self._resource() as dynamo:
            table = await dynamo.Table(self.table_name)
            response = await table.get_item(Key={"url": url}, ConsistentRead=True)
            item: dict[str, Any] | None = response.get("Item")
            return item

    async def list_urls(
        self, limit: int, after: str | None, content_hash: str | None
    ) -> tuple[list[dict[str, Any]], str | None]:
        options: dict[str, Any] = {"Limit": limit, "ConsistentRead": True}
        if after is not None:
            options["ExclusiveStartKey"] = {"url": after}
        if content_hash is not None:
            options["FilterExpression"] = "content_hash = :hash"
            options["ExpressionAttributeValues"] = {":hash": content_hash}
        async with self._resource() as dynamo:
            table = await dynamo.Table(self.table_name)
            result = await table.scan(**options)
        return result["Items"], result.get("LastEvaluatedKey", {}).get("url")

    async def delete_url(self, url: str) -> bool:
        async with self._resource() as dynamo:
            table = await dynamo.Table(self.table_name)
            result = await table.delete_item(Key={"url": url}, ReturnValues="ALL_OLD")
        return bool(result.get("Attributes"))

    async def stats(self) -> dict[str, int]:
        total = with_content = 0
        hashes: set[str] = set()
        after = None
        while True:
            items, after = await self.list_urls(100, after, None)
            total += len(items)
            for item in items:
                if item.get("content_hash"):
                    with_content += 1
                    hashes.add(item["content_hash"])
            if after is None:
                break
        return {"total_urls": total, "with_content": with_content, "unique_contents": len(hashes)}


class S3Service:
    def __init__(
        self, bucket_name: str, region: str = "us-east-1", endpoint_url: str | None = None
    ) -> None:
        self.bucket_name = bucket_name
        self.region = region
        self.session = aioboto3.Session()
        self.endpoint_url = endpoint_url

    def _client(self) -> Any:
        return self.session.client(
            "s3", region_name=self.region, endpoint_url=self.endpoint_url, config=AWS_CONFIG
        )

    async def save_html(self, raw_html: RawHtmlData) -> str:
        content_hash = hashlib.sha256(raw_html.html_content.encode()).hexdigest()
        s3_key = f"html/{content_hash}.html"

        async with self._client() as s3:
            await s3.put_object(
                Bucket=self.bucket_name,
                Key=s3_key,
                Body=raw_html.html_content.encode(),
                ContentType="text/html",
            )

        return f"s3://{self.bucket_name}/{s3_key}"

    async def get_html(self, content_hash: str) -> str | None:
        async with self._client() as s3:
            try:
                result = await s3.get_object(
                    Bucket=self.bucket_name, Key=f"html/{content_hash}.html"
                )
            except ClientError as exc:
                if exc.response["Error"]["Code"] == "NoSuchKey":
                    return None
                raise
            async with result["Body"] as stream:
                body = await stream.read()
                return bytes(body).decode("utf-8")
