from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _dotenv(path: Path) -> None:
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


@dataclass(frozen=True)
class Settings:
    bot_token: str
    api_id: int
    api_hash: str
    mongo_uri: str            # empty -> in-memory DB (dev only, data vanishes on restart)
    db_name: str
    owner_ids: frozenset[int]
    tz_offset_hours: int      # "day" boundary for the daily puzzle
    catalog_size: int         # how many popular anime to pull from AniList
    refresh_days: int
    anilist_url: str
    log_channel: int          # optional: new-group notifications (0 = off)


def load() -> Settings:
    _dotenv(Path(__file__).resolve().parent.parent / ".env")
    owners = {int(x) for x in os.getenv("OWNER_IDS", "").replace(" ", "").split(",") if x.lstrip("-").isdigit()}
    return Settings(
        bot_token=os.getenv("BOT_TOKEN", ""), api_id=int(os.getenv("API_ID", "0") or 0),
        api_hash=os.getenv("API_HASH", ""), mongo_uri=os.getenv("MONGO_URI", ""),
        db_name=os.getenv("DATABASE_NAME", "aniarena"), owner_ids=frozenset(owners),
        tz_offset_hours=int(os.getenv("TZ_OFFSET_HOURS", "0")),
        catalog_size=int(os.getenv("CATALOG_SIZE", "600")), refresh_days=int(os.getenv("REFRESH_DAYS", "7")),
        anilist_url=os.getenv("ANILIST_URL", "https://graphql.anilist.co"),
        log_channel=int(os.getenv("LOG_CHANNEL", "0") or 0),
    )
