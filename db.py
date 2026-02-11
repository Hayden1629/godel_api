"""
Database layer for Godel CLI
Abstract backend with SQLite implementation (swap to PostgreSQL later)
"""

import asyncio
import json
import logging
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import aiosqlite

logger = logging.getLogger("godel.db")

DB_PATH = Path(__file__).parent / "godel.db"

# ---------------------------------------------------------------------------
# Abstract interface
# ---------------------------------------------------------------------------

class DatabaseBackend(ABC):
    """Interface that any storage backend must implement."""

    @abstractmethod
    async def init(self):
        """Create tables / run migrations."""
        ...

    @abstractmethod
    async def close(self):
        ...

    # -- chat messages ------------------------------------------------------

    @abstractmethod
    async def save_message(self, channel: str, sender: str, content: str,
                           timestamp: Optional[datetime] = None,
                           raw_data: Optional[str] = None) -> int:
        ...

    @abstractmethod
    async def query_messages(self, channel: Optional[str] = None,
                             since: Optional[datetime] = None,
                             limit: int = 100) -> List[Dict]:
        ...

    # -- pdf downloads ------------------------------------------------------

    @abstractmethod
    async def save_pdf_record(self, ticker: str, command: str,
                              filename: str, filepath: str) -> int:
        ...

    @abstractmethod
    async def query_pdfs(self, ticker: Optional[str] = None,
                         limit: int = 100) -> List[Dict]:
        ...


# ---------------------------------------------------------------------------
# SQLite implementation
# ---------------------------------------------------------------------------

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS chat_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    channel TEXT NOT NULL,
    sender TEXT,
    content TEXT,
    timestamp DATETIME,
    raw_data TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS pdf_downloads (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker TEXT NOT NULL,
    command TEXT,
    filename TEXT,
    filepath TEXT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_chat_channel ON chat_messages(channel);
CREATE INDEX IF NOT EXISTS idx_chat_ts ON chat_messages(timestamp);
CREATE INDEX IF NOT EXISTS idx_pdf_ticker ON pdf_downloads(ticker);
"""


class SQLiteBackend(DatabaseBackend):
    """Async SQLite storage via aiosqlite."""

    def __init__(self, db_path: str = None):
        self.db_path = db_path or str(DB_PATH)
        self._db: Optional[aiosqlite.Connection] = None

    async def init(self):
        self._db = await aiosqlite.connect(self.db_path)
        self._db.row_factory = aiosqlite.Row
        await self._db.executescript(SCHEMA_SQL)
        await self._db.commit()
        logger.info(f"SQLite database ready at {self.db_path}")

    async def close(self):
        if self._db:
            await self._db.close()
            self._db = None

    # -- chat ---------------------------------------------------------------

    async def save_message(self, channel: str, sender: str, content: str,
                           timestamp: Optional[datetime] = None,
                           raw_data: Optional[str] = None) -> int:
        ts = timestamp or datetime.now(timezone.utc)
        cursor = await self._db.execute(
            "INSERT INTO chat_messages (channel, sender, content, timestamp, raw_data) VALUES (?, ?, ?, ?, ?)",
            (channel, sender, content, ts.isoformat(), raw_data),
        )
        await self._db.commit()
        return cursor.lastrowid

    async def query_messages(self, channel: Optional[str] = None,
                             since: Optional[datetime] = None,
                             limit: int = 100) -> List[Dict]:
        conditions = []
        params = []
        if channel:
            conditions.append("channel = ?")
            params.append(channel)
        if since:
            conditions.append("timestamp >= ?")
            params.append(since.isoformat())
        where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
        sql = f"SELECT * FROM chat_messages {where} ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)
        cursor = await self._db.execute(sql, params)
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

    # -- pdfs ---------------------------------------------------------------

    async def save_pdf_record(self, ticker: str, command: str,
                              filename: str, filepath: str) -> int:
        cursor = await self._db.execute(
            "INSERT INTO pdf_downloads (ticker, command, filename, filepath) VALUES (?, ?, ?, ?)",
            (ticker, command, filename, filepath),
        )
        await self._db.commit()
        return cursor.lastrowid

    async def query_pdfs(self, ticker: Optional[str] = None,
                         limit: int = 100) -> List[Dict]:
        if ticker:
            cursor = await self._db.execute(
                "SELECT * FROM pdf_downloads WHERE ticker = ? ORDER BY timestamp DESC LIMIT ?",
                (ticker, limit),
            )
        else:
            cursor = await self._db.execute(
                "SELECT * FROM pdf_downloads ORDER BY timestamp DESC LIMIT ?",
                (limit,),
            )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


# ---------------------------------------------------------------------------
# Convenience: get a ready backend
# ---------------------------------------------------------------------------

_backend: Optional[SQLiteBackend] = None


async def get_db(db_path: str = None) -> SQLiteBackend:
    """Return (and lazily initialise) the default SQLite backend."""
    global _backend
    if _backend is None:
        _backend = SQLiteBackend(db_path)
        await _backend.init()
    return _backend


async def close_db():
    global _backend
    if _backend:
        await _backend.close()
        _backend = None
