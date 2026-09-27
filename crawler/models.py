from typing import Annotated
from urllib.parse import urlsplit

from msgspec import Meta, Struct

Url = Annotated[str, Meta(min_length=1, max_length=2048)]
ContentHash = Annotated[str, Meta(pattern=r"^[a-f0-9]{64}$", min_length=64, max_length=64)]


def validate_url(url: str) -> str:
    try:
        parsed = urlsplit(url)
        port = parsed.port
        valid = (
            0 < len(url) <= 2048
            and parsed.scheme in {"http", "https"}
            and bool(parsed.hostname)
            and parsed.username is None
            and parsed.password is None
            and not any(char.isspace() or ord(char) < 32 for char in url)
            and (port is None or 1 <= port <= 65535)
        )
    except ValueError:
        valid = False
    if not valid:
        raise ValueError("URL должен быть HTTP(S)-адресом без логина и пароля, до 2048 символов")
    return url


class UrlData(Struct, forbid_unknown_fields=True):
    url: Url
    s3_link: str | None = None
    content_hash: ContentHash | None = None
    last_crawled_time: Annotated[int, Meta(ge=0)] | None = None

    def __post_init__(self) -> None:
        validate_url(self.url)


class RawHtmlData(Struct, forbid_unknown_fields=True):
    url: Url
    html_content: Annotated[str, Meta(min_length=1, max_length=1_048_576)]

    def __post_init__(self) -> None:
        validate_url(self.url)
        if len(self.html_content.encode()) > 1_048_576:
            raise ValueError("HTML не должен превышать 1 МиБ в UTF-8")


class UrlBatch(Struct, forbid_unknown_fields=True):
    urls: Annotated[list[Url], Meta(min_length=1, max_length=100)]

    def __post_init__(self) -> None:
        for url in self.urls:
            validate_url(url)


class CrawlRequest(Struct, forbid_unknown_fields=True):
    urls: Annotated[list[Url], Meta(min_length=1, max_length=20)]

    def __post_init__(self) -> None:
        for url in self.urls:
            validate_url(url)
