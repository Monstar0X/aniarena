"""Higher or Lower: is the next anime rated higher or lower than the one shown? Stateless between taps (state in MongoDB)."""
from __future__ import annotations

import random

from . import progress
from .catalog import Catalog

DAILY_XP_CAP = 150
RECENT = 25


class HigherLower:
    def __init__(self, db, catalog: Catalog, rng: random.Random | None = None, tz: int = 0):
        self.db, self.cat, self.rng, self.tz = db, catalog, rng or random.Random(), tz

    def _pick(self, avoid_score: int, recent: list[int]) -> dict:
        pool = [i for i in self.cat.pool(250) if i not in recent and self.cat.get(i)["score"] != avoid_score]
        pool = pool or [i for i in self.cat.pool(250) if self.cat.get(i)["score"] != avoid_score]
        return self.cat.get(self.rng.choice(pool))

    async def start(self, uid: int) -> dict:
        a = self._pick(-1, [])
        b = self._pick(a["score"], [a["_id"]])
        st = {"_id": uid, "a": a["_id"], "b": b["_id"], "streak": 0, "recent": [a["_id"], b["_id"]]}
        await self.db.hol.replace_one({"_id": uid}, st, upsert=True)
        return {"a": a, "b": b, "streak": 0}

    async def state(self, uid: int) -> dict | None:
        st = await self.db.hol.find_one({"_id": uid})
        if not st or st.get("over"):
            return None
        return {"a": self.cat.get(st["a"]), "b": self.cat.get(st["b"]), "streak": st["streak"]}

    async def answer(self, uid: int, name: str, choice: str) -> dict:
        st = await self.db.hol.find_one({"_id": uid})
        if not st or st.get("over"):
            return {"status": "nogame"}
        a, b = self.cat.get(st["a"]), self.cat.get(st["b"])
        correct = (b["score"] > a["score"]) if choice == "h" else (b["score"] < a["score"])
        if correct:
            streak = st["streak"] + 1
            nxt = self._pick(b["score"], st["recent"][-RECENT:])
            await self.db.hol.update_one({"_id": uid}, {"$set": {"a": b["_id"], "b": nxt["_id"], "streak": streak},
                                                        "$push": {"recent": nxt["_id"]}})
            return {"status": "correct", "a": b, "b": nxt, "revealed": b, "prev": a, "streak": streak}
        streak = st["streak"]
        await self.db.hol.update_one({"_id": uid}, {"$set": {"over": True}})
        u = await progress.get_user(self.db, uid) or {}
        day = progress.today(self.tz).isoformat()
        used = u.get("hol_xp", {}).get("x", 0) if u.get("hol_xp", {}).get("d") == day else 0
        xp = max(0, min(streak * 3, DAILY_XP_CAP - used))
        lvl = None
        if xp:
            lvl = await progress.award_xp(self.db, uid, name, xp)
            await self.db.users.update_one({"_id": uid}, {"$set": {"hol_xp": {"d": day, "x": used + xp}}})
        await progress.bump_stat(self.db, uid, "hol_played")
        await progress.set_stat_max(self.db, uid, "hol_best", streak)
        badges = await progress.check_badges(self.db, uid)
        best = (await progress.get_user(self.db, uid))["st"].get("hol_best", 0)
        return {"status": "over", "a": a, "b": b, "streak": streak, "xp": xp, "best": best, "level": lvl, "badges": badges}
