"""Database bootstrap: MongoDB through Motor in production, MemoryDB when MONGO_URI is empty."""
from __future__ import annotations

import logging

from .config import Settings
from .memdb import MemoryDB

log = logging.getLogger("arena.db")


def connect(s: Settings):
    if not s.mongo_uri:
        log.warning("MONGO_URI not set - using in-memory database (data is lost on restart!)")
        return MemoryDB()
    from motor.motor_asyncio import AsyncIOMotorClient   # imported late: tests/dev don't need Motor
    return AsyncIOMotorClient(s.mongo_uri, serverSelectionTimeoutMS=8000)[s.db_name]


async def ensure_indexes(db) -> None:
    await db.users.create_index([("xp", -1)])
    await db.users.create_index("ref_by")
    await db.week_scores.create_index([("week", 1), ("xp", -1)])
    await db.chat_scores.create_index([("chat", 1), ("week", 1), ("xp", -1)])
    await db.daily_games.create_index([("user", 1), ("date", 1)])
    await db.chats.create_index("active")
