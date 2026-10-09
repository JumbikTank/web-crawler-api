import asyncio
import ipaddress
import socket
from dataclasses import dataclass
from time import monotonic
from urllib.parse import urljoin, urlsplit

import aiohttp
from aiohttp.abc import ResolveResult
from aiohttp.resolver import ThreadedResolver
from protego import Protego

from crawler.models import validate_url

USER_AGENT = "StudyCrawler/1.0"
MAX_HTML_BYTES = 1_048_576


class DownloadError(Exception):
    def __init__(self, code: str, detail: str, http_status: int | None = None) -> None:
        super().__init__(detail)
        self.code = code
        self.detail = detail
        self.http_status = http_status


def check_address(address: str) -> None:
    ip = ipaddress.ip_address(address)
    if not ip.is_global or ip.is_multicast or ip.is_unspecified:
        raise DownloadError("unsafe_url", "Разрешены только публичные IP-адреса")


class PublicResolver(ThreadedResolver):
    async def resolve(
        self, host: str, port: int = 0, family: socket.AddressFamily = socket.AF_INET
    ) -> list[ResolveResult]:
        addresses = await super().resolve(host, port, family)
        for address in addresses:
            check_address(address["host"])
        return addresses


@dataclass
class FetchResponse:
    status: int
    body: str
    content_type: str
    location: str | None = None


@dataclass
class DownloadedPage:
    final_url: str
    html: str
    http_status: int


class Downloader:
    def __init__(self) -> None:
        self.session: aiohttp.ClientSession | None = None
        self.slots = asyncio.Semaphore(4)
        self.host_locks: dict[str, asyncio.Lock] = {}
        self.last_request: dict[str, float] = {}
        self.robots: dict[str, tuple[float, Protego]] = {}

    async def start(self) -> None:
        self.session = aiohttp.ClientSession(
            connector=aiohttp.TCPConnector(resolver=PublicResolver(), ttl_dns_cache=60, limit=4),
            timeout=aiohttp.ClientTimeout(total=10, connect=5),
            headers={"User-Agent": USER_AGENT, "Accept-Encoding": "identity"},
            auto_decompress=False,
            trust_env=False,
            cookie_jar=aiohttp.DummyCookieJar(),
        )

    async def close(self) -> None:
        if self.session is not None:
            await self.session.close()

    @staticmethod
    def check_url(url: str) -> str:
        try:
            validate_url(url)
            parts = urlsplit(url)
            host = parts.hostname or ""
            try:
                ipaddress.ip_address(host)
            except ValueError:
                if host.lower() == "localhost" or host.lower().endswith(".localhost"):
                    raise DownloadError("unsafe_url", "Локальные адреса запрещены") from None
            else:
                check_address(host)
            authority = f"[{host}]" if ":" in host else host.encode("idna").decode().lower()
            default_port = 443 if parts.scheme == "https" else 80
            if parts.port is not None and parts.port != default_port:
                authority += f":{parts.port}"
            return f"{parts.scheme}://{authority}"
        except ValueError as exc:
            raise DownloadError("invalid_url", "Некорректный HTTP(S)-адрес") from exc

    async def _request(self, url: str, max_bytes: int, delay: float = 1.0) -> FetchResponse:
        origin = self.check_url(url)
        if len(self.host_locks) >= 1024 and origin not in self.host_locks:
            expired = [
                host
                for host, lock in self.host_locks.items()
                if not lock.locked() and self.last_request.get(host, 0) + 60 <= monotonic()
            ]
            for host in expired:
                self.host_locks.pop(host)
                self.last_request.pop(host, None)
            if len(self.host_locks) >= 1024:
                raise DownloadError("busy", "Слишком много активных доменов; повторите позже")
        lock = self.host_locks.setdefault(origin, asyncio.Lock())
        async with lock:
            await asyncio.sleep(max(0, self.last_request.get(origin, 0) + delay - monotonic()))
            assert self.session is not None
            try:
                async with self.session.get(url, allow_redirects=False) as response:
                    if response.headers.get("Content-Encoding", "identity").lower() != "identity":
                        raise DownloadError("encoding", "Сервер не поддержал несжатый ответ")
                    if response.content_length is not None and response.content_length > max_bytes:
                        raise DownloadError("too_large", "Ответ превышает допустимый размер")
                    chunks = bytearray()
                    async for chunk in response.content.iter_chunked(16_384):
                        chunks.extend(chunk)
                        if len(chunks) > max_bytes:
                            raise DownloadError("too_large", "Ответ превышает допустимый размер")
                    try:
                        body = chunks.decode(response.charset or "utf-8", errors="replace")
                    except LookupError:
                        body = chunks.decode("utf-8", errors="replace")
                    return FetchResponse(
                        response.status,
                        body,
                        response.content_type,
                        response.headers.get("Location"),
                    )
            finally:
                self.last_request[origin] = monotonic()

    async def _robots(self, origin: str) -> Protego:
        cached = self.robots.get(origin)
        if cached and cached[0] > monotonic():
            return cached[1]
        url = origin + "/robots.txt"
        for _ in range(6):
            response = await self._request(url, 524_288)
            if response.status in {301, 302, 303, 307, 308} and response.location:
                url = urljoin(url, response.location)
                continue
            if response.status in {404, 410}:
                rules = Protego.parse("")
            elif response.status >= 400:
                raise DownloadError(
                    "robots_unavailable", "robots.txt не разрешает обход", response.status
                )
            else:
                rules = Protego.parse(response.body)
            if len(self.robots) >= 1024:
                self.robots.pop(next(iter(self.robots)))
            self.robots[origin] = (monotonic() + 3600, rules)
            return rules
        raise DownloadError("redirect_limit", "Слишком много перенаправлений robots.txt")

    async def fetch(self, url: str) -> DownloadedPage:
        try:
            async with self.slots, asyncio.timeout(30):
                for _ in range(6):
                    origin = self.check_url(url)
                    rules = await self._robots(origin)
                    if not rules.can_fetch(url, USER_AGENT):
                        raise DownloadError("robots_denied", "URL запрещён правилами robots.txt")
                    delay = max(1.0, rules.crawl_delay(USER_AGENT) or 0)
                    rate = rules.request_rate(USER_AGENT)
                    if rate and rate.requests > 0:
                        delay = max(delay, rate.seconds / rate.requests)
                    response = await self._request(url, MAX_HTML_BYTES, delay)
                    if response.status in {301, 302, 303, 307, 308} and response.location:
                        url = urljoin(url, response.location)
                        continue
                    if response.status != 200:
                        raise DownloadError(
                            "http_error", "Сайт вернул ошибку HTTP", response.status
                        )
                    if response.content_type not in {"text/html", "application/xhtml+xml"}:
                        raise DownloadError("content_type", "По адресу находится не HTML")
                    if not response.body or len(response.body.encode()) > MAX_HTML_BYTES:
                        raise DownloadError("html_size", "HTML пуст или превышает 1 МиБ в UTF-8")
                    return DownloadedPage(url, response.body, response.status)
                raise DownloadError("redirect_limit", "Слишком много перенаправлений страницы")
        except TimeoutError as exc:
            raise DownloadError("timeout", "Истекло время скачивания") from exc
        except (aiohttp.ClientError, OSError) as exc:
            raise DownloadError("network_error", "Не удалось подключиться к сайту") from exc
