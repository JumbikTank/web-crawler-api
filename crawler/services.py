import hashlib
from time import time
from typing import Any

import aioboto3

from crawler.models import RawHtmlData, UrlData


class DynamoDBService:
    def __init__(self, table_name: str, region: str = "us-east-1") -> None:
        self.table_name = table_name
        self.region = region
        self.session = aioboto3.Session()

    async def create_url_data(self, url_data: UrlData) -> dict[str, Any]:
        async with self.session.resource("dynamodb", region_name=self.region) as dynamo:
            table = await dynamo.Table(self.table_name)
            item: dict[str, Any] = {
                "url": url_data.url,
                "s3_link": url_data.s3_link,
                "content_hash": url_data.content_hash,
                "last_crawled_time": url_data.last_crawled_time or int(time()),
            }
            await table.put_item(Item=item)
            return item

    async def get_url_data(self, url: str) -> dict[str, Any] | None:
        async with self.session.resource("dynamodb", region_name=self.region) as dynamo:
            table = await dynamo.Table(self.table_name)
            response = await table.get_item(Key={"url": url})
            item: dict[str, Any] | None = response.get("Item")
            return item


class S3Service:
    def __init__(self, bucket_name: str, region: str = "us-east-1") -> None:
        self.bucket_name = bucket_name
        self.region = region
        self.session = aioboto3.Session()

    async def save_html(self, raw_html: RawHtmlData) -> str:
        content_hash = hashlib.sha256(raw_html.html_content.encode()).hexdigest()
        s3_key = f"html/{content_hash}.html"

        async with self.session.client("s3", region_name=self.region) as s3:
            await s3.put_object(
                Bucket=self.bucket_name,
                Key=s3_key,
                Body=raw_html.html_content.encode(),
                ContentType="text/html",
            )

        return f"s3://{self.bucket_name}/{s3_key}"
