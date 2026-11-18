"""Daily puzzle ("guess the anime" with Wordle-style attribute feedback)."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from . import progress
from .catalog import Catalog, daily_number

MAX_GUESSES = 8
HIT, NEAR, MISS = "🟩", "🟨", "🟥"
SEASON_EMOJI = {"WINTER": "❄️", "SPRING": "🌸", "SUMMER": "☀️", "FALL": "🍂"}


@dataclass
class Cell:
    key: str
    value: str
    state: str          # HIT / NEAR / MISS
    arrow: str = ""     # direction the answer lies in: ⬆️ higher, ⬇️ lower


def _num(key: str, g: int, t: int, near_abs: float, hit_abs: float = 0, rel: float | None = None) -> Cell:
    diff = abs(g - t)
    tol_near = max(near_abs, rel * t) if rel else near_abs
    state = HIT if diff <= hit_abs else NEAR if diff <= tol_near else MISS
    arrow = "" if state == HIT else ("⬆️" if t > g else "⬇️")
    return Cell(key, str(g), state, arrow)


def compare(g: dict, t: dict) -> list[Cell]:
    gs, ts = set(g["genres"]), set(t["genres"])
    shared = len(gs & ts)
    gstate = HIT if gs == ts else NEAR if shared else MISS
    return [
        _num("year", g["year"], t["year"], near_abs=2),
        _num("episodes", g["episodes"], t["episodes"], near_abs=2, hit_abs=0, rel=0.25),
        _num("score", g["score"], t["score"], near_abs=7, hit_abs=2),
        Cell("format", g["format"], HIT if g["format"] == t["format"] else MISS),
        Cell("season", g["season"], HIT if g["season"] == t["season"] else MISS),
        Cell("studio", g["studio"], HIT if g["studio"] == t["studio"] else MISS),
        Cell("genres", ", ".join(g["genres"][:3]) + ("" if gstate != NEAR else f" ({shared} shared)"), gstate),
    ]


def render_guess(n: int, g: dict, cells: list[Cell]) -> str:
    c = {x.key: x for x in cells}
    f = lambda x: f"{x.state}{x.arrow}"
    return (f"<b>{n}. {_esc(g['title'])}</b>\n"
            f"📅 {c['year'].value} {f(c['year'])}  🎞 {c['episodes'].value} {f(c['episodes'])}  ⭐ {c['score'].value} {f(c['score'])}\n"
            f"📺 {c['format'].value} {f(c['format'])}  {SEASON_EMOJI.get(c['season'].value, '')} {c['season'].value.title()} {f(c['season'])}\n"
            f"🏢 {_esc(c['studio'].value)} {f(c['studio'])}\n🎭 {_esc(c['genres'].value)} {f(c['genres'])}")


def _esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def squares(cells: list[Cell]) -> str:
    return "".join(c.state for c in cells)


def share_text(num: int, game_rows: list[str], won: bool, tries: int, streak: int, link: str) -> str:
    score = f"{tries}/{MAX_GUESSES}" if won else f"X/{MAX_GUESSES}"
    head = f"🧩 AniArena Daily #{num}  {score}" + (f"  🔥{streak}" if streak > 1 else "")
    return head + "\n\n" + "\n".join(game_rows) + f"\n\nCan you beat me? {link}"


def xp_for_result(won: bool, tries: int, streak: int) -> int:
    return 40 + 15 * (MAX_GUESSES - tries) + min(streak, 10) * 4 if won else 8


class Daily:
    def __init__(self, db, catalog: Catalog, tz: int = 0):
        self.db, self.cat, self.tz = db, catalog, tz

    def today(self) -> date:
        return progress.today(self.tz)

    def hint(self, tries: int, target: dict) -> str | None:
        """Free help that unlocks late in the game so it stays winnable for newcomers."""
        if tries >= 6:
            return f"💡 Hint: it starts with “{target['title'][0]}” and has {len(target['title'])} characters."
        if tries >= 4:
            return f"💡 Hint: one of its tags is “{target['tags'][0]}”." if target.get("tags") else None
        return None

    async def game(self, uid: int, day: date | None = None) -> dict:
        day = day or self.today()
        gid = f"{uid}:{day.isoformat()}"
        g = await self.db.daily_games.find_one({"_id": gid})
        if not g:
            target = self.cat.daily(day)
            await self.db.daily_games.update_one(
                {"_id": gid}, {"$setOnInsert": {"user": uid, "date": day.isoformat(), "target": target["_id"],
                                                "guesses": [], "done": False, "won": False}}, upsert=True)
            g = await self.db.daily_games.find_one({"_id": gid})
        return g

    async def guess(self, uid: int, name: str, mid: int) -> dict:
        day = self.today()
        game = await self.game(uid, day)
        if game["done"]:
            return {"status": "done", "game": game}
        g = self.cat.get(mid)
        if not g:
            return {"status": "invalid", "game": game}
        if mid in game["guesses"]:
            return {"status": "dup", "game": game}
        target = self.cat.get(game["target"])
        cells = compare(g, target)
        won = mid == target["_id"]
        tries = len(game["guesses"]) + 1
        finished = won or tries >= MAX_GUESSES
        gid = game["_id"]
        await self.db.daily_games.update_one({"_id": gid, "done": False}, {"$push": {"guesses": mid}})
        out = {"status": "ok", "cells": cells, "guess": g, "won": won, "finished": finished, "tries": tries,
               "target": target, "number": daily_number(day)}
        if finished:
            await self.db.daily_games.update_one({"_id": gid}, {"$set": {"done": True, "won": won}})
            st = await progress.update_streak(self.db, uid, day)
            xp = xp_for_result(won, tries, st["streak"])
            lvl = await progress.award_xp(self.db, uid, name, xp, day=day)
            await progress.bump_stat(self.db, uid, "daily_played")
            if won:
                await progress.bump_stat(self.db, uid, "daily_wins")
                if tries <= 2:
                    await progress.bump_stat(self.db, uid, "fast_wins")
            out.update(xp=xp, streak=st, level=lvl, badges=await progress.check_badges(self.db, uid))
        return out

    async def rows(self, game: dict) -> list[str]:
        """Spoiler-free emoji rows for sharing and for re-rendering the board."""
        target = self.cat.get(game["target"])
        return [squares(compare(self.cat.get(m), target)) for m in game["guesses"] if self.cat.get(m)]

    async def board(self, game: dict) -> str:
        target = self.cat.get(game["target"])
        parts = [render_guess(i, self.cat.get(m), compare(self.cat.get(m), target))
                 for i, m in enumerate(game["guesses"], 1) if self.cat.get(m)]
        return "\n\n".join(parts)
