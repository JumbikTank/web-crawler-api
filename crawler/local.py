"""Persistent local adapters exposing the same API as DynamoDB and S3 services."""

import asyncio
import hashlib
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from time import time
from typing import Any

from crawler.models import RawHtmlData, UrlData


class SQLiteStorage:
    def __init__(self, path: Path) -> None:
        self.path = path

    @contextmanager
    def connection(self) -> Iterator[sqlite3.Connection]:
        db = sqlite3.connect(self.path, timeout=5)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    def initialize(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connection() as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.executescript("""
                CREATE TABLE IF NOT EXISTS urls (
                    url TEXT PRIMARY KEY,
                    s3_link TEXT,
                    content_hash TEXT,
                    last_crawled_time INTEGER
                );
                CREATE INDEX IF NOT EXISTS idx_urls_hash ON urls(content_hash, url);
                CREATE TABLE IF NOT EXISTS html (
                    content_hash TEXT PRIMARY KEY,
                    content TEXT NOT NULL
                );
            """)

    async def create_url_data(self, url_data: UrlData) -> dict[str, Any]:
        def write() -> dict[str, Any]:
            item = {
                "url": url_data.url,
                "s3_link": url_data.s3_link,
                "content_hash": url_data.content_hash,
                "last_crawled_time": (
                    int(time())
                    if url_data.last_crawled_time is None
                    else url_data.last_crawled_time
                ),
            }
            with self.connection() as db:
                db.execute(
                    "INSERT INTO urls VALUES (:url, :s3_link, :content_hash, :last_crawled_time) "
                    "ON CONFLICT(url) DO UPDATE SET s3_link=excluded.s3_link, "
                    "content_hash=excluded.content_hash, "
                    "last_crawled_time=excluded.last_crawled_time",
                    item,
                )
            return item

        return await asyncio.to_thread(write)

    async def get_url_data(self, url: str) -> dict[str, Any] | None:
        def read() -> dict[str, Any] | None:
            with self.connection() as db:
                row = db.execute("SELECT * FROM urls WHERE url=?", (url,)).fetchone()
                return dict(row) if row else None

        return await asyncio.to_thread(read)

    async def list_urls(
        self, limit: int, after: str | None, content_hash: str | None
    ) -> tuple[list[dict[str, Any]], str | None]:
        def read() -> tuple[list[dict[str, Any]], str | None]:
            query = "SELECT * FROM urls WHERE url > ?"
            parameters: list[Any] = [after or ""]
            if content_hash is not None:
                query += " AND content_hash = ?"
                parameters.append(content_hash)
            query += " ORDER BY url LIMIT ?"
            parameters.append(limit + 1)
            with self.connection() as db:
                rows = db.execute(query, parameters).fetchall()
                items = [dict(row) for row in rows[:limit]]
                return items, items[-1]["url"] if len(rows) > limit else None

        return await asyncio.to_thread(read)

    async def delete_url(self, url: str) -> bool:
        def delete() -> bool:
            with self.connection() as db:
                return db.execute("DELETE FROM urls WHERE url=?", (url,)).rowcount > 0

        return await asyncio.to_thread(delete)

    async def stats(self) -> dict[str, int]:
        def read() -> dict[str, int]:
            with self.connection() as db:
                row = db.execute(
                    "SELECT COUNT(*) AS total_urls, COUNT(content_hash) AS with_content, "
                    "COUNT(DISTINCT content_hash) AS unique_contents FROM urls"
                ).fetchone()
                return dict(row)

        return await asyncio.to_thread(read)

    async def save_html(self, raw_html: RawHtmlData) -> str:
        content_hash = hashlib.sha256(raw_html.html_content.encode()).hexdigest()

        def write() -> None:
            with self.connection() as db:
                db.execute(
                    "INSERT OR IGNORE INTO html VALUES (?, ?)",
                    (content_hash, raw_html.html_content),
                )

        await asyncio.to_thread(write)
        return f"sqlite://html/{content_hash}"

    async def get_html(self, content_hash: str) -> str | None:
        def read() -> str | None:
            with self.connection() as db:
                row = db.execute(
                    "SELECT content FROM html WHERE content_hash=?", (content_hash,)
                ).fetchone()
                return str(row["content"]) if row else None

        return await asyncio.to_thread(read)
