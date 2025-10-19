from msgspec import Struct


class UrlData(Struct):
    url: str
    s3_link: str | None = None
    content_hash: str | None = None
    last_crawled_time: int | None = None


class RawHtmlData(Struct):
    url: str
    html_content: str
