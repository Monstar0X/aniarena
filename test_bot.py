"""Run the real handlers against a stubbed `pyrogram` (no Telegram, no network)."""
import asyncio
import random
import sys
import types
import unittest
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock


def _stub():
    if getattr(sys.modules.get("pyrogram"), "_stub", False):
        return
    pg = types.ModuleType("pyrogram"); pg._stub = True
    pg.enums = types.ModuleType("pyrogram.enums")
    pg.enums.ParseMode = NS(HTML="HTML"); pg.enums.ChatType = NS(PRIVATE="private", SUPERGROUP="supergroup")
    pg.enums.ChatMemberStatus = NS(OWNER="owner", ADMINISTRATOR="admin")
    class F:
        new_chat_members = private = group = text = "flt"
        def __invert__(self): return self
        @staticmethod
        def command(n): return ("command", n)
        @staticmethod
        def regex(r): return ("regex", r)
    class Flt:
        def __invert__(self): return self
        def __and__(self, o): return self
    f = F(); f.new_chat_members = Flt(); f.private = Flt(); f.group = Flt(); f.text = Flt(); f.command = F.command; f.regex = F.regex
    class Cmd(Flt): pass
    pg.filters = types.SimpleNamespace(new_chat_members=Flt(), private=Flt(), group=Flt(), text=Flt(),
                                       command=lambda n: _C(("command", n)), regex=lambda r: _C(("regex", r)))
    h = types.ModuleType("pyrogram.handlers")
    class H:
        def __init__(self, fn, flt=None, *a): self.fn, self.flt = fn, flt
    h.MessageHandler = h.CallbackQueryHandler = h.InlineQueryHandler = H
    t = types.ModuleType("pyrogram.types")
    class Btn:
        def __init__(self, text, callback_data=None, url=None): self.text, self.callback_data, self.url = text, callback_data, url
    class Kb:
        def __init__(self, rows): self.rows = rows
    class Art:
        def __init__(self, **k): self.__dict__.update(k)
    t.InlineKeyboardButton, t.InlineKeyboardMarkup = Btn, Kb
    t.InlineQueryResultArticle, t.InputTextMessageContent = Art, lambda text: text
    errs = types.ModuleType("pyrogram.errors"); errs.FloodWait = type("FloodWait", (Exception,), {})
    pg.handlers, pg.types, pg.errors = h, t, errs
    sys.modules.update({"pyrogram": pg, "pyrogram.enums": pg.enums, "pyrogram.handlers": h, "pyrogram.types": t, "pyrogram.errors": errs})


class _C:
    def __init__(self, v): self.v = v
    def __and__(self, o): return self
    def __invert__(self): return self


_stub()
from arena import bot, progress  # noqa: E402
from arena.catalog import Catalog  # noqa: E402
from arena.config import Settings  # noqa: E402
from arena.daily import Daily  # noqa: E402
from arena.hol import HigherLower  # noqa: E402
from arena.memdb import MemoryDB  # noqa: E402


def run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def user(uid=1, name="Asha"):
    return NS(id=uid, first_name=name, username=None, is_bot=False)


def msg(text, uid=1, name="Asha", chat=None, private=True):
    m = NS(text=text, command=text.lstrip("/").split() if text.startswith("/") else None, from_user=user(uid, name),
           chat=NS(id=chat or uid, type="private" if private else "supergroup", title=None if private else "Grp"),
           new_chat_members=None, reply_to_message=None)
    m.reply_text = AsyncMock(return_value=NS(edit_text=AsyncMock())); m.reply_photo = AsyncMock(); m.delete = AsyncMock()
    return m


def cbq(data, uid=1, name="Asha", private=True):
    m = msg("", uid, name, private=private)
    q = NS(data=data, from_user=user(uid, name), message=m)
    q.answer = AsyncMock(); m.edit_text = AsyncMock(); m.delete = AsyncMock()
    return q


class BotTests(unittest.TestCase):
    def setUp(self):
        self.db = MemoryDB()
        self.cat = Catalog(self.db)
        run(self.cat.ensure())
        s = Settings("t", 0, "", "", "aniarena", frozenset({99}), 0, 600, 7, "", 0)
        bot.SESS.clear(); bot._LAST.clear()
        app = NS(handlers=[], add_handler=lambda h, group=0: app.handlers.append(h))
        self.app = app
        bot.setup(app, {"db": self.db, "catalog": self.cat, "daily": Daily(self.db, self.cat), "hol": HigherLower(self.db, self.cat, random.Random(5)),
                        "settings": s, "username": "AniArenaBot"})
        self.client = NS(send_message=AsyncMock(return_value=NS(edit_text=AsyncMock())), send_photo=AsyncMock(),
                         get_me=AsyncMock(return_value=NS(id=777, username="AniArenaBot")),
                         get_chat_member=AsyncMock(return_value=NS(status="member")))

    def test_all_commands_wired(self):
        names = {h.flt.v[1] for h in self.app.handlers if getattr(h.flt, "v", None) and h.flt.v[0] == "command"}
        self.assertEqual(names, {"start", "help", "daily", "hol", "arena", "stop", "top", "me", "invite", "remind", "stats", "broadcast"})

    def test_start_with_referral_rewards_both(self):
        run(bot.cmd_start(self.client, msg("/start", 1, "Ref")))
        m = msg("/start ref_1", 2, "New"); run(bot.cmd_start(self.client, m))
        self.assertIn("Welcome bonus", m.reply_text.call_args[0][0])
        self.client.send_message.assert_called()                                   # referrer notified
        self.assertEqual(self.client.send_message.call_args[0][0], 1)
        self.assertEqual(run(progress.get_user(self.db, 1))["refs"], 1)

    def test_daily_full_game_via_chat(self):
        run(bot.cmd_daily(self.client, msg("/daily")))
        target = run(Daily(self.db, self.cat).game(1))["target"]
        title = self.cat.get(target)["title"]
        wrong = next(d for d in self.cat.items.values() if d["_id"] != target)
        m = msg(wrong["title"]); run(bot.on_private_text(self.client, m)); bot._LAST.clear()
        self.assertIn("1. " + wrong["title"].replace("&", "&amp;"), m.reply_text.call_args[0][0])
        m = msg("zzzzqq"); run(bot.on_private_text(self.client, m)); bot._LAST.clear()
        self.assertIn("No anime found", m.reply_text.call_args[0][0])
        m = msg(title); run(bot.on_private_text(self.client, m))
        texts = [c[0][0] for c in m.reply_text.call_args_list]
        self.assertTrue(any("Solved in 2/8" in t for t in texts), texts)
        kb = m.reply_text.call_args[1]["reply_markup"]
        self.assertIn("t.me/share/url", kb.rows[0][0].url)
        self.assertIn("start%3Dref_1", kb.rows[0][0].url.replace("%3F", "").replace("?", ""))  # share link carries the referral
        again = msg(title); bot._LAST.clear(); run(bot.on_private_text(self.client, again))
        self.assertIn("done today's Daily", again.reply_text.call_args[0][0])

    def test_ambiguous_guess_offers_buttons(self):
        m = msg("death"); run(bot.on_private_text(self.client, m))
        kb = m.reply_text.call_args[1]["reply_markup"]
        self.assertTrue(all(r[0].callback_data.startswith("dg:") for r in kb.rows))
        mid = kb.rows[0][0].callback_data.split(":")[1]
        q = cbq(f"dg:{mid}"); run(bot.cb_daily_pick(self.client, q))
        self.assertIn("1.", q.message.reply_text.call_args[0][0])

    def test_group_gets_dm_button_for_daily(self):
        m = msg("/daily", chat=-5, private=False); run(bot.cmd_daily(self.client, m))
        self.assertIn("start=daily", m.reply_text.call_args[1]["reply_markup"].rows[0][0].url)

    def test_hol_buttons(self):
        m = msg("/hol"); run(bot.cmd_hol(self.client, m))
        self.assertIn("Higher or Lower", m.reply_text.call_args[0][0])
        st = run(HigherLower(self.db, self.cat).state(1))
        right = "h" if st["b"]["score"] > st["a"]["score"] else "l"
        q = cbq("hl:" + right); run(bot.cb_hol(self.client, q))
        self.assertIn("Correct", q.answer.call_args[0][0])
        st = run(HigherLower(self.db, self.cat).state(1))
        wrong = "l" if st["b"]["score"] > st["a"]["score"] else "h"
        q = cbq("hl:" + wrong); run(bot.cb_hol(self.client, q))
        self.assertIn("Final streak", q.message.edit_text.call_args[0][0])

    def test_arena_battle_end_to_end(self):
        async def t():
            m = msg("/arena 3", 1, "Asha", chat=-100, private=False)
            await bot.cmd_arena(self.client, m)
            sess = bot.SESS[-100]; b = sess["b"]
            await asyncio.sleep(3.6)                                              # round 1 starts after the 3 s countdown
            self.assertEqual(b.round_no, 1)
            wrong = msg("nonsense words", 2, "Ben", chat=-100, private=False)
            await bot.on_group_text(self.client, wrong); wrong.reply_text.assert_not_called()
            ok = msg(b.current.anime["title"], 2, "Ben", chat=-100, private=False)
            await bot.on_group_text(self.client, ok)
            self.assertIn("got it", ok.reply_text.call_args[0][0])
            u = await progress.get_user(self.db, 2)
            self.assertGreater(u["xp"], 0); self.assertEqual(u["st"]["arena_wins"], 1)
            top = await progress.top_chat(self.db, -100)
            self.assertEqual(top[0]["user"], 2)
            stop = msg("/stop", 1, "Asha", chat=-100, private=False)           # starter can stop
            await bot.cmd_stop(self.client, stop)
            await asyncio.sleep(0.1)
            self.assertNotIn(-100, bot.SESS)
            self.assertIn("Battle results", self.client.send_message.call_args[0][1])
            dup = msg("/arena", 1, chat=-100, private=False)
            await bot.cmd_arena(self.client, dup)                                 # new one can start after stop
            bot.SESS[-100]["task"].cancel()
        run(t())

    def test_only_starter_or_admin_can_stop(self):
        async def t():
            await bot.cmd_arena(self.client, msg("/arena", 1, chat=-7, private=False))
            m = msg("/stop", 2, "Ben", chat=-7, private=False)
            await bot.cmd_stop(self.client, m)
            self.assertIn("Only the person", m.reply_text.call_args[0][0])
            bot.SESS[-7]["task"].cancel()
        run(t())

    def test_arena_in_private_redirects(self):
        m = msg("/arena"); run(bot.cmd_arena(self.client, m))
        self.assertIn("groups", m.reply_text.call_args[0][0])

    def test_top_me_invite_remind(self):
        run(bot.cmd_start(self.client, msg("/start", 1)))
        run(progress.award_xp(self.db, 1, "Asha", 130))
        m = msg("/top"); run(bot.cmd_top(self.client, m)); self.assertIn("Asha", m.reply_text.call_args[0][0])
        m = msg("/top", chat=-5, private=False); run(bot.cmd_top(self.client, m)); self.assertIn("this chat", m.reply_text.call_args[0][0])
        m = msg("/me"); run(bot.cmd_me(self.client, m)); m.reply_photo.assert_called_once()
        m = msg("/invite"); run(bot.cmd_invite(self.client, m)); self.assertIn("start=ref_1", m.reply_text.call_args[0][0])
        run(bot.cmd_remind(self.client, msg("/remind off")))
        self.assertFalse(run(progress.get_user(self.db, 1))["remind"])

    def test_inline_results(self):
        q = NS(from_user=user(1), answer=AsyncMock())
        run(bot.on_inline(self.client, q))
        self.assertEqual(len(q.answer.call_args[0][0]), 3)

    def test_owner_only_stats(self):
        m = msg("/stats", 5); run(bot.cmd_stats(self.client, m)); m.reply_text.assert_not_called()
        m = msg("/stats", 99); run(bot.cmd_stats(self.client, m)); self.assertIn("Users", m.reply_text.call_args[0][0])

    def test_bot_added_to_group_is_recorded(self):
        m = msg("", 1, chat=-50, private=False); m.new_chat_members = [NS(id=777)]
        run(bot.on_new_members(self.client, m))
        self.assertTrue(run(self.db.chats.find_one({"_id": -50}))["active"])
        self.assertIn("AniArena is here", m.reply_text.call_args[0][0])

    def test_reminder_targets_only_lapsed_streaks(self):
        async def t():
            day = progress.today(0).isoformat()
            for uid, streak, last in ((1, 5, "2000-01-01"), (2, 5, day), (3, 1, "2000-01-01")):
                await progress.register_user(self.db, uid, f"u{uid}")
                await self.db.users.update_one({"_id": uid}, {"$set": {"streak": streak, "last_daily": last}})
            due = await self.db.users.find({"streak": {"$gte": 2}, "last_daily": {"$ne": day}, "remind": {"$ne": False}, "reminded": {"$ne": day}}).to_list(10)
            self.assertEqual([u["_id"] for u in due], [1])
        run(t())


if __name__ == "__main__":
    unittest.main()
