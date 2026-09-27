import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    backend: str = "sqlite"
    database_path: Path = Path("data/crawler.sqlite3")
    region: str = "us-east-1"
    table_name: str = "url_data"
    bucket_name: str = "crawler-html"
    endpoint_url: str | None = None

    def __post_init__(self) -> None:
        if self.backend not in {"sqlite", "aws"}:
            raise ValueError("STORAGE_BACKEND must be sqlite or aws")

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            backend=os.getenv("STORAGE_BACKEND", "sqlite"),
            database_path=Path(os.getenv("DATABASE_PATH", "data/crawler.sqlite3")),
            region=os.getenv("AWS_DEFAULT_REGION", "us-east-1"),
            table_name=os.getenv("DYNAMODB_TABLE", "url_data"),
            bucket_name=os.getenv("S3_BUCKET", "crawler-html"),
            endpoint_url=os.getenv("AWS_ENDPOINT_URL") or None,
        )
