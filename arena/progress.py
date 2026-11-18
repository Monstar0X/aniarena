"""XP, levels, streaks, badges, referrals and leaderboards. Everything lives in MongoDB."""
from __future__ import annotations

import time
from datetime import date, datetime, timedelta, timezone

TITLES = ["Newbie", "Casual Watcher", "Otaku", "Binge Master", "Senpai", "Sensei", "Legend", "Mythic", "Ascended"]
REF_REFERRER_XP, REF_INVITEE_XP, MAX_FREEZES = 100, 50, 5


def level_for(xp: int) -> int:
    return int((max(0, xp) / 60) ** 0.5) + 1


def xp_for_level(level: int) -> int:
    return 60 * (level - 1) ** 2


def title_for(level: int) -> str:
    return TITLES[min((level - 1) // 2, len(TITLES) - 1)]


def week_key(d: date) -> str:
    y, w, _ = d.isocalendar()
    return f"{y}-W{w:02d}"


def today(tz_hours: int = 0, now: float | None = None) -> date:
    t = datetime.fromtimestamp(now if now is not None else time.time(), timezone.utc) + timedelta(hours=tz_hours)
    return t.date()


BADGES = {
    "first_win":  ("🥇", "First Blood", "Win your first daily puzzle", lambda u: u["st"].get("daily_wins", 0) >= 1),
    "sniper":     ("🎯", "Sniper", "Solve the daily in 2 guesses or fewer", lambda u: u["st"].get("fast_wins", 0) >= 1),
    "streak7":    ("🔥", "Week Warrior", "7-day streak", lambda u: u.get("best_streak", 0) >= 7),
    "streak30":   ("🌋", "Unstoppable", "30-day streak", lambda u: u.get("best_streak", 0) >= 30),
    "daily50":    ("🧩", "Puzzle Addict", "Solve 50 dailies", lambda u: u["st"].get("daily_wins", 0) >= 50),
    "arena10":    ("⚔️", "Arena Champion", "Win 10 arena rounds", lambda u: u["st"].get("arena_wins", 0) >= 10),
    "arena100":   ("👑", "Arena Legend", "Win 100 arena rounds", lambda u: u["st"].get("arena_wins", 0) >= 100),
    "hol10":      ("📈", "Oracle", "Reach a streak of 10 in Higher/Lower", lambda u: u["st"].get("hol_best", 0) >= 10),
    "recruiter":  ("🤝", "Recruiter", "Invite 3 friends", lambda u: u.get("refs", 0) >= 3),
    "influencer": ("📣", "Influencer", "Invite 25 friends", lambda u: u.get("refs", 0) >= 25),
    "xp1000":     ("💎", "Thousandaire", "Earn 1,000 XP", lambda u: u.get("xp", 0) >= 1000),
}


def _blank_user(uid: int, name: str, now: float) -> dict:
    return {"name": name, "xp": 0, "streak": 0, "best_streak": 0, "freezes": 1, "last_daily": None,
            "badges": [], "refs": 0, "joined": now, "st": {}}


async def register_user(db, uid: int, name: str, ref: int | None = None, now: float | None = None) -> dict:
    """Create the user on first contact (applying a referral if valid). Always refreshes the name."""
    now = now or time.time()
    res = await db.users.update_one({"_id": uid}, {"$setOnInsert": {k: v for k, v in _blank_user(uid, name, now).items() if k != "name"}},
                                    upsert=True)
    await db.users.update_one({"_id": uid}, {"$set": {"name": name}})
    new = res.upserted_id is not None
    referrer = None
    if new and ref and ref != uid and await db.users.find_one({"_id": ref}):
        referrer = ref
        await db.users.update_one({"_id": uid}, {"$set": {"ref_by": ref}})
        await db.users.update_one({"_id": ref}, {"$inc": {"refs": 1}})
        await bump_freeze(db, ref)
        await award_xp(db, ref, None, REF_REFERRER_XP)
        await award_xp(db, uid, name, REF_INVITEE_XP)
    return {"new": new, "referrer": referrer}


async def bump_freeze(db, uid: int) -> None:
    await db.users.update_one({"_id": uid, "freezes": {"$lt": MAX_FREEZES}}, {"$inc": {"freezes": 1}})


async def get_user(db, uid: int) -> dict | None:
    return await db.users.find_one({"_id": uid})


async def award_xp(db, uid: int, name: str | None, amount: int, chat: int | None = None,
                   day: date | None = None) -> dict:
    """Add XP to the all-time, weekly and (optionally) per-chat boards. Returns level change info."""
    if amount <= 0:
        return {"xp": 0, "old_level": 0, "new_level": 0, "leveled": False}
    before = await _ensure(db, uid)
    await db.users.update_one({"_id": uid}, {"$inc": {"xp": amount}})
    name = name or before.get("name") or str(uid)
    wk = week_key(day or today())
    await db.week_scores.update_one({"_id": f"{wk}:{uid}"}, {"$inc": {"xp": amount}, "$set": {"week": wk, "user": uid, "name": name}}, upsert=True)
    if chat is not None:
        await db.chat_scores.update_one({"_id": f"{wk}:{chat}:{uid}"},
                                        {"$inc": {"xp": amount}, "$set": {"week": wk, "chat": chat, "user": uid, "name": name}}, upsert=True)
    old, new = level_for(before.get("xp", 0)), level_for(before.get("xp", 0) + amount)
    return {"xp": before.get("xp", 0) + amount, "old_level": old, "new_level": new, "leveled": new > old}


async def _ensure(db, uid: int) -> dict:
    """Fetch the user, creating a blank profile if they somehow have none (never crash a game on it)."""
    u = await db.users.find_one({"_id": uid})
    if u is None:
        await db.users.update_one({"_id": uid}, {"$setOnInsert": _blank_user(uid, str(uid), time.time())}, upsert=True)
        u = await db.users.find_one({"_id": uid})
    return u


async def update_streak(db, uid: int, day: date) -> dict:
    u = await _ensure(db, uid)
    last = date.fromisoformat(u["last_daily"]) if u.get("last_daily") else None
    streak, freezes, used, broke = u.get("streak", 0), u.get("freezes", 0), 0, False
    if last == day:
        return {"streak": streak, "used_freezes": 0, "broke": False, "milestone": False}
    if last is None:
        streak = 1
    else:
        gap = (day - last).days
        if gap == 1:
            streak += 1
        else:
            missed = gap - 1
            if missed <= freezes:
                freezes, used, streak = freezes - missed, missed, streak + 1
            else:
                streak, broke = 1, True
    milestone = streak % 7 == 0
    if milestone:
        freezes = min(MAX_FREEZES, freezes + 1)
    await db.users.update_one({"_id": uid}, {"$set": {"streak": streak, "freezes": freezes, "last_daily": day.isoformat(),
                                                     "best_streak": max(u.get("best_streak", 0), streak)}})
    return {"streak": streak, "used_freezes": used, "broke": broke, "milestone": milestone}


async def bump_stat(db, uid: int, key: str, n: int = 1) -> None:
    await db.users.update_one({"_id": uid}, {"$inc": {f"st.{key}": n}})


async def set_stat_max(db, uid: int, key: str, value: int) -> None:
    u = await _ensure(db, uid)
    if value > u.get("st", {}).get(key, 0):
        await db.users.update_one({"_id": uid}, {"$set": {f"st.{key}": value}})


async def check_badges(db, uid: int) -> list[tuple[str, str, str]]:
    u = await db.users.find_one({"_id": uid})
    if not u:
        return []
    u.setdefault("st", {})
    new = [(k, v[0], v[1]) for k, v in BADGES.items() if k not in u.get("badges", []) and v[3](u)]
    for k, _, _ in new:
        await db.users.update_one({"_id": uid}, {"$addToSet": {"badges": k}})
    return new


# -------------------------------------------------------------------- leaderboards
async def top_global(db, n: int = 10) -> list[dict]:
    return await db.users.find({"xp": {"$gt": 0}}).sort("xp", -1).limit(n).to_list(n)


async def top_week(db, n: int = 10, day: date | None = None) -> list[dict]:
    return await db.week_scores.find({"week": week_key(day or today())}).sort("xp", -1).limit(n).to_list(n)


async def top_chat(db, chat: int, n: int = 10, day: date | None = None) -> list[dict]:
    return await db.chat_scores.find({"chat": chat, "week": week_key(day or today())}).sort("xp", -1).limit(n).to_list(n)


async def rank_of(db, uid: int) -> int | None:
    u = await db.users.find_one({"_id": uid})
    if not u:
        return None
    return await db.users.count_documents({"xp": {"$gt": u.get("xp", 0)}}) + 1
