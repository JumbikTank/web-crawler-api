from litestar import Litestar, post, get
from litestar.datastructures import State
from litestar.openapi import OpenAPIConfig

from crawler.models import UrlData, RawHtmlData
from crawler.services import DynamoDBService, S3Service


@post("/urls", summary="Create URL data", description="Save URL metadata to DynamoDB")
async def create_url(data: UrlData, state: State) -> dict:
    dynamo_service: DynamoDBService = state.dynamo_service
    result = await dynamo_service.create_url_data(data)
    return result


@get("/urls/{url:str}", summary="Get URL data", description="Retrieve URL metadata from DynamoDB")
async def get_url(url: str, state: State) -> dict:
    dynamo_service: DynamoDBService = state.dynamo_service
    result = await dynamo_service.get_url_data(url)
    return result or {}


@post("/html", summary="Save HTML to S3", description="Store raw HTML content in S3 bucket")
async def save_html(data: RawHtmlData, state: State) -> dict:
    s3_service: S3Service = state.s3_service
    s3_link = await s3_service.save_html(data)
    return {"s3_link": s3_link, "url": data.url}


def create_app() -> Litestar:
    initial_state = State({
        "dynamo_service": DynamoDBService(table_name="url_data"),
        "s3_service": S3Service(bucket_name="crawler-html"),
    })

    return Litestar(
        route_handlers=[create_url, get_url, save_html],
        state=initial_state,
        openapi_config=OpenAPIConfig(
            title="Web Crawler API",
            version="0.1.0",
        ),
    )


app = create_app()
