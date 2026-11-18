"""AniArena entrypoint."""
from __future__ import annotations

import asyncio
import logging
import random

from arena import anilist, bot, config, db as database
from arena.catalog import Catalog
from arena.daily import Daily
from arena.hol import HigherLower

log = logging.getLogger("arena")


async def amain() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    s = config.load()
    if not (s.bot_token and s.api_id and s.api_hash):
        raise SystemExit("Set BOT_TOKEN, API_ID and API_HASH (see .env.example).")
    db = database.connect(s)
    await database.ensure_indexes(db)
    catalog = Catalog(db)
    await catalog.ensure(lambda n: anilist.fetch_popular(s.anilist_url, n), s.catalog_size, s.refresh_days)
    log.info("catalog ready: %d titles", len(catalog.items))

    from pyrogram import Client, idle      # late import: tests run without Kurigram installed
    app = Client("aniarena", api_id=s.api_id, api_hash=s.api_hash, bot_token=s.bot_token, in_memory=True)
    bot.setup(app, {"db": db, "catalog": catalog, "daily": Daily(db, catalog, s.tz_offset_hours),
                    "hol": HigherLower(db, catalog, random.Random(), s.tz_offset_hours), "settings": s})
    await app.start()
    me = await app.get_me()
    bot.CTX["username"] = me.username
    log.info("Bot @%s is live.", me.username)
    tasks = [asyncio.create_task(bot.reminder_loop(app))]

    async def weekly_refresh():       # keep the catalog fresh without restarts
        while True:
            await asyncio.sleep(86400)
            await catalog.ensure(lambda n: anilist.fetch_popular(s.anilist_url, n), s.catalog_size, s.refresh_days)
    tasks.append(asyncio.create_task(weekly_refresh()))
    await idle()
    for t in tasks:
        t.cancel()
    await app.stop()


if __name__ == "__main__":
    asyncio.run(amain())
