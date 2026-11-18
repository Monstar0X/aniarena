"""Anime catalog: lives in MongoDB, mirrored in memory for fast fuzzy search and daily picks."""
from __future__ import annotations

import asyncio
import hashlib
import logging
import random
import time
from datetime import date

from . import text
from .seed import seed_docs

log = logging.getLogger("arena.catalog")
EPOCH = date(2026, 1, 1)
GUESSABLE = 300     # the daily answer always comes from the N most popular titles, so it is fair


def daily_number(day: date) -> int:
    return (day - EPOCH).days + 1


class Catalog:
    def __init__(self, db):
        self.db = db
        self.items: dict[int, dict] = {}
        self._names: dict[int, list[str]] = {}
        self._index: list[tuple[str, int]] = []
        self._by_pop: list[int] = []

    # ---------------------------------------------------------------- loading
    async def load(self) -> int:
        docs = await self.db.anime.find({}).to_list(None)
        self.items = {d["_id"]: d for d in docs}
        self._names, self._index = {}, []
        for d in docs:
            names = [text.norm(x) for x in [d["title"], *d.get("aliases", [])] if x]
            self._names[d["_id"]] = list(dict.fromkeys(n for n in names if n))
            self._index += [(n, d["_id"]) for n in self._names[d["_id"]]]
        self._by_pop = [d["_id"] for d in sorted(docs, key=lambda d: (-d.get("popularity", 0), d["_id"]))]
        return len(docs)

    async def ensure(self, fetcher=None, size: int = 600, refresh_days: int = 7) -> None:
        """Seed on first run; refresh from AniList when the catalog is older than `refresh_days`."""
        if not await self.db.anime.count_documents({}):
            await self.db.anime.insert_many(seed_docs())
            log.info("seeded catalog with %d bundled titles", len(seed_docs()))
        meta = await self.db.meta.find_one({"_id": "catalog"}) or {}
        stale = time.time() - meta.get("updated", 0) > refresh_days * 86400
        if fetcher and stale:
            try:
                docs = await asyncio.to_thread(fetcher, size)
                if len(docs) >= 100:
                    await self.db.anime.delete_many({"src": "seed"})
                    for d in docs:
                        await self.db.anime.replace_one({"_id": d["_id"]}, d, upsert=True)
                    await self.db.meta.update_one({"_id": "catalog"}, {"$set": {"updated": time.time(), "count": len(docs)}}, upsert=True)
                    log.info("catalog refreshed from AniList: %d titles", len(docs))
            except Exception as e:  # never let a flaky API stop the bot from starting
                log.warning("AniList refresh failed (%s) - keeping current catalog", e)
        await self.load()

    # ---------------------------------------------------------------- access
    def get(self, mid: int) -> dict | None:
        return self.items.get(mid)

    def names(self, mid: int) -> list[str]:
        return self._names.get(mid, [])

    def pool(self, top: int = GUESSABLE) -> list[int]:
        return self._by_pop[:top]

    def daily(self, day: date) -> dict:
        pool = sorted(self.pool())          # stable order regardless of popularity drift within the pool
        h = int(hashlib.sha256(f"aniarena:{day.isoformat()}".encode()).hexdigest(), 16)
        return self.items[pool[h % len(pool)]]

    def random(self, rng: random.Random, exclude=(), top: int = GUESSABLE) -> dict:
        pool = [i for i in self.pool(top) if i not in set(exclude)] or self.pool(top)
        return self.items[rng.choice(pool)]

    # ---------------------------------------------------------------- search
    def search(self, query: str, n: int = 5) -> list[tuple[dict, float]]:
        q = text.norm(query)
        if len(q) < 2:
            return []
        qt = q.split()
        best: dict[int, float] = {}
        for alias, mid in self._index:
            if alias == q:
                s = 1.0
            elif alias.startswith(q):
                s = 0.93
            elif all(t in alias.split() or any(w.startswith(t) for w in alias.split()) for t in qt):
                s = 0.88
            elif len(q) >= 4 and (alias[0] == q[0] or q[:3] in alias):
                s = text.ratio(q, alias) * 0.85
            else:
                continue
            if s > best.get(mid, 0):
                best[mid] = s
        ranked = sorted(best.items(), key=lambda kv: (-kv[1], self._by_pop.index(kv[0])))[:n]
        return [(self.items[m], s) for m, s in ranked if s >= 0.5]

    def exact(self, query: str) -> dict | None:
        q = text.norm(query)
        hits = [mid for a, mid in self._index if a == q]
        return self.items[hits[0]] if hits else None

    def is_answer(self, guess: str, mid: int) -> bool:
        return text.strict_match(guess, self._names.get(mid, []))
