import asyncio
import base64
import binascii
import hashlib
import logging
import re
import sqlite3
from typing import Annotated, Any

from botocore.exceptions import BotoCoreError, ClientError
from litestar import Litestar, Request, Response, delete, get, post
from litestar.datastructures import State
from litestar.exceptions import NotFoundException, ValidationException
from litestar.openapi import OpenAPIConfig
from litestar.params import Parameter

from crawler.config import Settings
from crawler.local import SQLiteStorage
from crawler.models import RawHtmlData, UrlBatch, UrlData, validate_url
from crawler.services import DynamoDBService, S3Service

MetadataStorage = SQLiteStorage | DynamoDBService
HtmlStorage = SQLiteStorage | S3Service
logger = logging.getLogger(__name__)


def checked_url(url: str) -> str:
    try:
        return validate_url(url)
    except ValueError as exc:
        raise ValidationException(detail=str(exc)) from exc


@post("/urls", summary="Создать или заменить метаданные URL")
async def create_url(data: UrlData, state: State) -> dict[str, Any]:
    service: MetadataStorage = state.dynamo_service
    return await service.create_url_data(data)


@get("/url-data", summary="Получить метаданные URL")
async def get_url(url: str, state: State) -> dict[str, Any]:
    service: MetadataStorage = state.dynamo_service
    result = await service.get_url_data(checked_url(url))
    if result is None:
        raise NotFoundException(detail="URL не найден")
    return result


@get("/urls", summary="Список URL с пагинацией и фильтром по SHA-256")
async def list_urls(
    state: State,
    limit: Annotated[int, Parameter(ge=1, le=100)] = 20,
    cursor: Annotated[str | None, Parameter(max_length=16384)] = None,
    content_hash: Annotated[
        str | None, Parameter(pattern=r"^[a-f0-9]{64}$", min_length=64, max_length=64)
    ] = None,
) -> dict[str, Any]:
    after = None
    if cursor is not None:
        try:
            after = base64.b64decode(cursor, altchars=b"-_", validate=True).decode()
            checked_url(after)
        except (ValueError, binascii.Error) as exc:
            raise ValidationException(detail="Некорректный cursor") from exc
    service: MetadataStorage = state.dynamo_service
    items, next_url = await service.list_urls(limit, after, content_hash)
    next_cursor = base64.urlsafe_b64encode(next_url.encode()).decode() if next_url else None
    return {"items": items, "next_cursor": next_cursor}


@delete("/url-data", summary="Удалить метаданные URL")
async def delete_url(url: str, state: State) -> None:
    service: MetadataStorage = state.dynamo_service
    if not await service.delete_url(checked_url(url)):
        raise NotFoundException(detail="URL не найден")


@post("/urls/batch", summary="Пакетно зарегистрировать до 100 URL")
async def create_batch(data: UrlBatch, state: State) -> dict[str, Any]:
    service: MetadataStorage = state.dynamo_service
    items = []
    for url in dict.fromkeys(data.urls):
        # Re-importing a known URL must not erase previously saved HTML metadata.
        item = await service.get_url_data(url)
        items.append(item if item is not None else await service.create_url_data(UrlData(url)))
    return {"items": items, "count": len(items)}


@post("/html", summary="Сохранить HTML и связать его с URL")
async def save_html(data: RawHtmlData, state: State) -> dict[str, Any]:
    content_hash = hashlib.sha256(data.html_content.encode()).hexdigest()
    html_service: HtmlStorage = state.s3_service
    metadata_service: MetadataStorage = state.dynamo_service
    link = await html_service.save_html(data)
    return await metadata_service.create_url_data(
        UrlData(url=data.url, s3_link=link, content_hash=content_hash)
    )


@get("/html", summary="Прочитать сохранённый HTML по URL")
async def get_html(url: str, state: State) -> dict[str, str]:
    metadata_service: MetadataStorage = state.dynamo_service
    html_service: HtmlStorage = state.s3_service
    metadata = await metadata_service.get_url_data(checked_url(url))
    if not metadata or not metadata.get("content_hash"):
        raise NotFoundException(detail="HTML для URL не найден")
    content_hash = str(metadata["content_hash"])
    if not re.fullmatch(r"[a-f0-9]{64}", content_hash):
        raise NotFoundException(detail="HTML для URL не найден")
    html = await html_service.get_html(content_hash)
    if html is None:
        raise NotFoundException(detail="HTML для URL не найден")
    return {"url": url, "content_hash": content_hash, "html_content": html}


@get("/stats", summary="Статистика URL и уникального содержимого")
async def stats(state: State) -> dict[str, int]:
    service: MetadataStorage = state.dynamo_service
    return await service.stats()


@get("/health", summary="Проверка работы HTTP-сервера", sync_to_thread=False)
def health() -> dict[str, str]:
    return {"status": "ok"}


def storage_error(request: Request[Any, Any, Any], exc: Exception) -> Response[dict[str, Any]]:
    # Do not include URLs, request bodies, credentials or internal exception details.
    logger.error("Storage unavailable: %s", type(exc).__name__)
    return Response(
        {"status_code": 503, "detail": "Хранилище временно недоступно"}, status_code=503
    )


def create_app(settings: Settings | None = None) -> Litestar:
    settings = settings or Settings.from_env()
    startup = []
    if settings.backend == "sqlite":
        local = SQLiteStorage(settings.database_path)

        async def initialize() -> None:
            await asyncio.to_thread(local.initialize)

        startup.append(initialize)
        metadata: MetadataStorage = local
        html: HtmlStorage = local
    else:
        metadata = DynamoDBService(settings.table_name, settings.region, settings.endpoint_url)
        html = S3Service(settings.bucket_name, settings.region, settings.endpoint_url)

    return Litestar(
        route_handlers=[
            create_url,
            get_url,
            list_urls,
            delete_url,
            create_batch,
            save_html,
            get_html,
            stats,
            health,
        ],
        state=State({"dynamo_service": metadata, "s3_service": html}),
        on_startup=startup,
        request_max_body_size=8 * 1024 * 1024,
        exception_handlers={
            sqlite3.Error: storage_error,
            BotoCoreError: storage_error,
            ClientError: storage_error,
        },
        openapi_config=OpenAPIConfig(title="Web Crawler API", version="0.1.0"),
    )


app = create_app()
