"""Telegram front-end (Kurigram/Pyrogram). Handlers are thin; game logic lives in the other modules."""
from __future__ import annotations

import asyncio
import html
import io
import logging
import random
import time
from urllib.parse import quote

from pyrogram import enums, filters
from pyrogram.handlers import CallbackQueryHandler, InlineQueryHandler, MessageHandler
from pyrogram.types import (InlineKeyboardButton as Btn, InlineKeyboardMarkup as Kb, InlineQueryResultArticle,
                            InputTextMessageContent)

from . import cards, progress
from .battle import ROUND_SECONDS, Battle
from .catalog import daily_number
from .daily import MAX_GUESSES, share_text

log = logging.getLogger("arena.bot")
HTML = enums.ParseMode.HTML
esc = html.escape
CTX: dict = {}
SESS: dict[int, dict] = {}       # chat_id -> {"b": Battle, "task": Task, "starter": uid}
_LAST: dict[int, float] = {}


def name_of(u) -> str:
    return (u.first_name or u.username or str(u.id))[:24]


def throttle(uid: int, gap: float = 0.7) -> bool:
    now = time.monotonic()
    if now - _LAST.get(uid, 0) < gap:
        return False
    _LAST[uid] = now
    if len(_LAST) > 20000:
        _LAST.clear()
    return True


async def bot_link(client, payload: str = "") -> str:
    if "username" not in CTX:
        CTX["username"] = (await client.get_me()).username
    return f"https://t.me/{CTX['username']}" + (f"?start={payload}" if payload else "")


def menu_kb(username: str) -> Kb:
    return Kb([[Btn("🧩 Daily Puzzle", callback_data="m:daily"), Btn("📈 Higher/Lower", callback_data="m:hol")],
               [Btn("🏆 Leaderboard", callback_data="m:top"), Btn("👤 My Card", callback_data="m:me")],
               [Btn("➕ Add to a group (Arena battles)", url=f"https://t.me/{username}?startgroup=arena")]])


def extras(res: dict) -> str:
    out = []
    lvl = res.get("level") or {}
    if lvl.get("leveled"):
        out.append(f"⬆️ <b>Level {lvl['new_level']}</b> - {progress.title_for(lvl['new_level'])}!")
    for _, emoji, name in res.get("badges") or []:
        out.append(f"{emoji} New badge: <b>{esc(name)}</b>")
    return "\n".join(out)


# ===================================================================== start / menu
HELP = ("<b>AniArena</b> - anime games for you and your group.\n\n"
        "🧩 /daily - one mystery anime a day, Wordle-style clues, keep your 🔥 streak\n"
        "📈 /hol - Higher or Lower on anime ratings\n"
        "⚔️ /arena <code>[rounds]</code> - group trivia battle (add me to a group!)\n"
        "🏆 /top - leaderboards   👤 /me - your player card\n"
        "🤝 /invite - get a link: friends who join earn you XP + a streak freeze\n"
        "🔔 /remind <code>on|off</code> - daily streak reminder")


async def cmd_start(client, message):
    u = message.from_user
    payload = message.command[1] if len(message.command) > 1 else ""
    ref = int(payload[4:]) if payload.startswith("ref_") and payload[4:].isdigit() else None
    info = await progress.register_user(CTX["db"], u.id, name_of(u), ref)
    me = (await client.get_me()).username
    CTX["username"] = me
    if info["referrer"]:
        try:
            await client.send_message(info["referrer"], f"🎉 <b>{esc(name_of(u))}</b> joined through your link! "
                                      f"+{progress.REF_REFERRER_XP} XP and +1 ❄️ streak freeze.", parse_mode=HTML)
        except Exception:
            pass
    if message.chat.type != enums.ChatType.PRIVATE:
        return await message.reply_text("Tap to play 👇", reply_markup=Kb([[Btn("🎮 Open AniArena", url=f"https://t.me/{me}?start=menu")]]))
    if payload == "daily":
        return await cmd_daily(client, message)
    bonus = f"\n\n🎁 Welcome bonus: +{progress.REF_INVITEE_XP} XP for joining via a friend!" if info["referrer"] else ""
    await message.reply_text(HELP + bonus, parse_mode=HTML, reply_markup=menu_kb(me))


async def cmd_help(client, message):
    await message.reply_text(HELP, parse_mode=HTML)


async def cb_menu(client, query):
    act = query.data.split(":")[1]
    await query.answer()
    await progress.register_user(CTX["db"], query.from_user.id, name_of(query.from_user))
    fake = query.message
    fake.from_user = query.from_user   # the button was pressed by this user
    if act == "daily":
        await cmd_daily(client, fake)
    elif act == "hol":
        await cmd_hol(client, fake)
    elif act == "top":
        await cmd_top(client, fake)
    elif act == "me":
        await cmd_me(client, fake)


# ===================================================================== daily puzzle
def share_kb(url: str, txt: str) -> Kb:
    return Kb([[Btn("📤 Share my result", url=f"https://t.me/share/url?url={quote(url)}&text={quote(txt)}")]])


async def daily_prompt(game: dict, daily) -> str:
    board = await daily.board(game)
    n = len(game["guesses"])
    head = f"🧩 <b>AniArena Daily #{daily_number(daily.today())}</b>  ·  guess {n + 1}/{MAX_GUESSES}\n"
    legend = "🟩 match  🟨 close  🟥 no  ⬆️⬇️ the answer is higher/lower"
    hint = daily.hint(n, daily.cat.get(game["target"]))
    return (head + (board + "\n\n" if board else "\nI picked a secret anime. Type a title to guess it!\n\n")
            + f"<i>{legend}</i>" + (f"\n\n{hint}" if hint else ""))


async def cmd_daily(client, message):
    d = CTX["daily"]
    u = message.from_user
    if message.chat.type != enums.ChatType.PRIVATE:
        me = await bot_link(client, "daily")
        return await message.reply_text("🧩 The Daily is played in private so nobody spoils it:", reply_markup=Kb([[Btn("Play today's puzzle", url=me)]]))
    await progress.register_user(CTX["db"], u.id, name_of(u))
    game = await d.game(u.id)
    if game["done"]:
        return await show_finished(client, message, u.id, game)
    await message.reply_text(await daily_prompt(game, d), parse_mode=HTML)


async def show_finished(client, message, uid: int, game: dict, res: dict | None = None):
    d = CTX["daily"]
    target = d.cat.get(game["target"])
    user = await progress.get_user(CTX["db"], uid)
    rows = await d.rows(game)
    n = daily_number(d.today())
    tries = len(game["guesses"])
    link = await bot_link(client, f"ref_{uid}")
    txt = share_text(n, rows, game["won"], tries, user.get("streak", 0), link)
    if game["won"]:
        head = f"🎉 <b>Solved in {tries}/{MAX_GUESSES}!</b> It was <b>{esc(target['title'])}</b>."
    else:
        head = f"😵 Out of guesses! It was <b>{esc(target['title'])}</b> ({target['year']}, {esc(target['studio'])})."
    lines = [head]
    if res:
        lines.append(f"✨ +{res['xp']} XP   🔥 Streak: {res['streak']['streak']} day(s)   ❄️ Freezes: {user.get('freezes', 0)}")
        if res["streak"]["used_freezes"]:
            lines.append(f"❄️ A streak freeze saved your streak ({res['streak']['used_freezes']} used).")
        if res["streak"]["broke"]:
            lines.append("💔 Your streak reset - start a new one today!")
        if res["streak"]["milestone"]:
            lines.append("🎁 7-day milestone: +1 ❄️ streak freeze!")
        ex = extras(res)
        if ex:
            lines.append(ex)
    else:
        lines.append(f"🔥 Streak: {user.get('streak', 0)}   Come back tomorrow for a new one!")
    lines.append("\n<code>" + "\n".join(rows) + "</code>")
    await message.reply_text("\n".join(lines), parse_mode=HTML, reply_markup=share_kb(link, txt))


async def do_guess(client, message, uid: int, name: str, mid: int):
    d = CTX["daily"]
    res = await d.guess(uid, name, mid)
    if res["status"] == "done":
        return await message.reply_text("You've already finished today's puzzle. Come back tomorrow! 🌅")
    if res["status"] == "dup":
        return await message.reply_text("You already guessed that one. Try something else.")
    if res["status"] != "ok":
        return await message.reply_text("I don't know that anime. Try another title.")
    game = await d.game(uid)
    if res["finished"]:
        await message.reply_text(await d.board(game), parse_mode=HTML)
        return await show_finished(client, message, uid, game, res)
    await message.reply_text(await daily_prompt(game, d), parse_mode=HTML)


async def on_private_text(client, message):
    u = message.from_user
    if not u or u.is_bot or not message.text or len(message.text) > 80 or not throttle(u.id):
        return
    d = CTX["daily"]
    await progress.register_user(CTX["db"], u.id, name_of(u))
    game = await d.game(u.id)
    if game["done"]:
        return await message.reply_text("You've done today's Daily 🎉 Try /hol or add me to a group for /arena battles!",
                                        reply_markup=menu_kb(CTX.get("username", "")))
    hit = d.cat.exact(message.text)
    if hit:
        return await do_guess(client, message, u.id, name_of(u), hit["_id"])
    found = [x for x, s in d.cat.search(message.text, 6) if x["_id"] not in game["guesses"]][:5]
    if not found:
        return await message.reply_text("🤔 No anime found with that name. Try the English or romaji title.")
    await message.reply_text("Did you mean…", reply_markup=Kb([[Btn(f"{x['title'][:40]} ({x['year']})", callback_data=f"dg:{x['_id']}")] for x in found]))


async def cb_daily_pick(client, query):
    mid = int(query.data.split(":")[1])
    u = query.from_user
    await query.answer()
    try:
        await query.message.delete()
    except Exception:
        pass
    msg = query.message
    msg.from_user = u
    await do_guess(client, msg, u.id, name_of(u), mid)


# ===================================================================== higher / lower
def hol_text(a: dict, b: dict, streak: int, note: str = "") -> str:
    return (f"📈 <b>Higher or Lower</b>   🔥 {streak}\n\n{note}"
            f"<b>{esc(a['title'])}</b> is rated <b>{a['score']}</b>/100\n"
            f"vs\n<b>{esc(b['title'])}</b> is rated <b>???</b>\n\nIs the second one rated higher or lower?")


HOL_KB = Kb([[Btn("⬆️ Higher", callback_data="hl:h"), Btn("⬇️ Lower", callback_data="hl:l")]])


async def cmd_hol(client, message):
    u = message.from_user
    await progress.register_user(CTX["db"], u.id, name_of(u))
    s = await CTX["hol"].start(u.id)
    await message.reply_text(hol_text(s["a"], s["b"], 0), parse_mode=HTML, reply_markup=HOL_KB)


async def cb_hol(client, query):
    u = query.from_user
    act = query.data.split(":")[1]
    if act == "new":
        s = await CTX["hol"].start(u.id)
        await query.answer()
        return await query.message.edit_text(hol_text(s["a"], s["b"], 0), parse_mode=HTML, reply_markup=HOL_KB)
    r = await CTX["hol"].answer(u.id, name_of(u), act)
    if r["status"] == "nogame":
        return await query.answer("Game over - start a new one with /hol", show_alert=True)
    if r["status"] == "correct":
        await query.answer("✅ Correct!")
        note = f"✅ <b>{esc(r['prev']['title'])}</b> → {r['revealed']['score']}. Keep going!\n\n"
        return await query.message.edit_text(hol_text(r["a"], r["b"], r["streak"], note), parse_mode=HTML, reply_markup=HOL_KB)
    await query.answer("❌ Wrong!")
    txt = (f"❌ <b>{esc(r['b']['title'])}</b> is rated <b>{r['b']['score']}</b> (vs {r['a']['score']}).\n\n"
           f"Final streak: <b>{r['streak']}</b>   Best: <b>{r['best']}</b>\n✨ +{r['xp']} XP")
    ex = extras(r)
    await query.message.edit_text(txt + (f"\n{ex}" if ex else ""), parse_mode=HTML,
                                  reply_markup=Kb([[Btn("🔁 Play again", callback_data="hl:new")]]))


# ===================================================================== arena (groups)
def medal(i: int) -> str:
    return ["🥇", "🥈", "🥉"][i] if i < 3 else f"{i + 1}."


async def cmd_arena(client, message):
    if message.chat.type == enums.ChatType.PRIVATE:
        me = (await client.get_me()).username
        return await message.reply_text("⚔️ Arena battles are for groups. Add me to yours:",
                                        reply_markup=Kb([[Btn("➕ Add to group", url=f"https://t.me/{me}?startgroup=arena")]]))
    chat = message.chat.id
    if chat in SESS:
        return await message.reply_text("A battle is already running here! Send /stop to end it.")
    arg = message.command[1] if len(message.command) > 1 else "5"
    n = max(3, min(15, int(arg))) if arg.isdigit() else 5
    b = Battle(CTX["catalog"], chat, n, starter=message.from_user.id, rng=random.Random())
    SESS[chat] = {"b": b, "starter": message.from_user.id}
    await CTX["db"].chats.update_one({"_id": chat}, {"$set": {"title": message.chat.title, "active": True}, "$inc": {"battles": 1}}, upsert=True)
    await message.reply_text(f"⚔️ <b>AniArena battle!</b> {n} rounds.\nJust type the anime's name in chat - first correct answer wins the round.\n"
                             "Starting in 3 seconds…", parse_mode=HTML)
    SESS[chat]["task"] = asyncio.create_task(run_battle(client, chat))


async def post_round(client, chat: int, b: Battle):
    r = b.current
    if r.kind == "pixel":
        data = await asyncio.to_thread(cards.fetch, r.anime.get("cover"))
        if data:
            r.image = data
            try:
                bio = io.BytesIO(await asyncio.to_thread(cards.pixelate, data, 0)); bio.name = "round.jpg"
                return await client.send_photo(chat, bio, caption=b.prompt(), parse_mode=HTML)
            except Exception:
                log.exception("pixel round failed")
        b.downgrade()
    return await client.send_message(chat, b.prompt(), parse_mode=HTML)


async def wait_or_solved(r, seconds: float) -> bool:
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        if r.solved_by is not None:
            return True
        await asyncio.sleep(0.4)
    return r.solved_by is not None


async def run_battle(client, chat: int):
    s = SESS.get(chat)
    b: Battle = s["b"]
    try:
        await asyncio.sleep(3)
        while True:
            r = b.start_round()
            if r is None:
                break
            sent = await post_round(client, chat, b)
            for wait, kind in ((20, "hint"), (15, "hint"), (ROUND_SECONDS - 35, "end")):
                if await wait_or_solved(r, wait):
                    break
                if kind == "hint":
                    new = b.hint()
                    if r.kind == "pixel" and getattr(r, "image", None):
                        bio = io.BytesIO(await asyncio.to_thread(cards.pixelate, r.image, b.pixel_level())); bio.name = "round.jpg"
                        await client.send_photo(chat, bio, caption="💡 Sharper…\n\n" + (new or ""), parse_mode=HTML)
                    elif new:
                        try:
                            await sent.edit_text(new, parse_mode=HTML)
                        except Exception:
                            await client.send_message(chat, "💡 " + new, parse_mode=HTML)
                else:
                    miss = b.timeout()
                    if miss:
                        await client.send_message(chat, f"⏰ Time's up! It was <b>{esc(miss['anime']['title'])}</b>.", parse_mode=HTML)
            await asyncio.sleep(3.5)
        await finish_battle(client, chat)
    except asyncio.CancelledError:
        raise
    except Exception:
        log.exception("battle crashed")
        await client.send_message(chat, "💥 The battle crashed. Start a new one with /arena.")
    finally:
        SESS.pop(chat, None)


async def finish_battle(client, chat: int, stopped: bool = False):
    b: Battle = SESS[chat]["b"]
    rows = b.standings()
    if not rows:
        return await client.send_message(chat, "🏁 Battle over - nobody scored. Try again with /arena!")
    lines = ["🏁 <b>Battle results</b>\n"]
    for i, (uid, name, pts, wins) in enumerate(rows[:10]):
        lines.append(f"{medal(i)} {esc(name)} - <b>{pts}</b> pts ({wins} won)")
    if len(rows) >= 2 and not stopped:
        winner = rows[0]
        res = await progress.award_xp(CTX["db"], winner[0], winner[1], 15, chat=chat)
        lines.append(f"\n👑 <b>{esc(winner[1])}</b> takes the crown (+15 XP bonus)")
    lines.append("\n/arena to go again · /top for the weekly chat ranking")
    me = (await client.get_me()).username
    await client.send_message(chat, "\n".join(lines), parse_mode=HTML,
                              reply_markup=Kb([[Btn("➕ Add me to another group", url=f"https://t.me/{me}?startgroup=arena")]]))


async def on_group_text(client, message):
    chat = message.chat.id
    s = SESS.get(chat)
    u = message.from_user
    if not s or not u or u.is_bot or not message.text:
        return
    b: Battle = s["b"]
    res = b.answer(u.id, name_of(u), message.text)
    if not res:
        return
    db = CTX["db"]
    await progress.register_user(db, u.id, name_of(u))
    lvl = await progress.award_xp(db, u.id, name_of(u), res["points"], chat=chat)
    await progress.bump_stat(db, u.id, "arena_wins")
    badges = await progress.check_badges(db, u.id)
    txt = (f"✅ <b>{esc(res['name'])}</b> got it in {res['seconds']}s! <b>{esc(res['anime']['title'])}</b>  +{res['points']} pts")
    ex = extras({"level": lvl, "badges": badges})
    await message.reply_text(txt + (f"\n{ex}" if ex else ""), parse_mode=HTML)


async def cmd_stop(client, message):
    chat = message.chat.id
    s = SESS.get(chat)
    if not s:
        return await message.reply_text("No battle is running.")
    u = message.from_user
    ok = u.id == s["starter"] or u.id in CTX["settings"].owner_ids
    if not ok:
        try:
            m = await client.get_chat_member(chat, u.id)
            ok = m.status in (enums.ChatMemberStatus.OWNER, enums.ChatMemberStatus.ADMINISTRATOR)
        except Exception:
            ok = False
    if not ok:
        return await message.reply_text("Only the person who started it or an admin can stop the battle.")
    task = s.get("task")
    if task:
        task.cancel()
    try:
        await finish_battle(client, chat, stopped=True)
    finally:
        SESS.pop(chat, None)


# ===================================================================== leaderboards / profile / growth
def board_text(title: str, rows: list[dict], me: int | None = None) -> str:
    if not rows:
        return f"{title}\n\nNobody here yet - be the first! 🏁"
    out = [title, ""]
    for i, r in enumerate(rows):
        nm = esc(r.get("name") or str(r.get("user") or r.get("_id")))
        out.append(f"{medal(i)} {'<b>' if (r.get('user') or r['_id']) == me else ''}{nm}{'</b>' if (r.get('user') or r['_id']) == me else ''} - {r['xp']:,} XP")
    return "\n".join(out)


async def cmd_top(client, message):
    db, u = CTX["db"], message.from_user
    arg = message.command[1].lower() if getattr(message, "command", None) and len(message.command) > 1 else ""
    if message.chat.type != enums.ChatType.PRIVATE and arg != "all":
        rows = await progress.top_chat(db, message.chat.id)
        return await message.reply_text(board_text("🏆 <b>This week in this chat</b>", rows, u.id), parse_mode=HTML)
    if arg == "week":
        rows = await progress.top_week(db)
        return await message.reply_text(board_text("🔥 <b>Global - this week</b>", rows, u.id), parse_mode=HTML)
    rows = await progress.top_global(db)
    rank = await progress.rank_of(db, u.id)
    await message.reply_text(board_text("🌍 <b>Global - all time</b>", rows, u.id) + (f"\n\nYour rank: <b>#{rank}</b>" if rank else "") +
                             "\n\n<i>/top week for the weekly board</i>", parse_mode=HTML)


async def cmd_me(client, message):
    db, u = CTX["db"], message.from_user
    await progress.register_user(db, u.id, name_of(u))
    user = await progress.get_user(db, u.id)
    rank = await progress.rank_of(db, u.id)
    png = await asyncio.to_thread(cards.profile_card, user, rank)
    bio = io.BytesIO(png); bio.name = "card.png"
    link = await bot_link(client, f"ref_{u.id}")
    await message.reply_photo(bio, caption=f"👤 <b>{esc(name_of(u))}</b> · Level {progress.level_for(user['xp'])}\nInvite friends: {link}", parse_mode=HTML,
                              reply_markup=share_kb(link, "Come play AniArena with me - daily anime puzzle, trivia battles and leagues! 🎮"))


async def cmd_invite(client, message):
    u = message.from_user
    await progress.register_user(CTX["db"], u.id, name_of(u))
    user = await progress.get_user(CTX["db"], u.id)
    link = await bot_link(client, f"ref_{u.id}")
    await message.reply_text(
        f"🤝 <b>Invite friends</b>\nYour link: {link}\n\nEvery friend who joins gives you <b>+{progress.REF_REFERRER_XP} XP</b> and a "
        f"❄️ streak freeze (they get +{progress.REF_INVITEE_XP} XP).\nFriends invited so far: <b>{user.get('refs', 0)}</b>",
        parse_mode=HTML, reply_markup=share_kb(link, "I'm playing AniArena - guess the daily anime & battle in groups! 🎮"))


async def cmd_remind(client, message):
    u = message.from_user
    arg = message.command[1].lower() if len(message.command) > 1 else ""
    if arg not in ("on", "off"):
        return await message.reply_text("Usage: /remind on | off")
    await progress.register_user(CTX["db"], u.id, name_of(u))
    await CTX["db"].users.update_one({"_id": u.id}, {"$set": {"remind": arg == "on"}})
    await message.reply_text("🔔 Streak reminders are " + ("on." if arg == "on" else "off."))


async def on_new_members(client, message):
    me = await client.get_me()
    CTX["username"] = me.username
    if not any(m.id == me.id for m in (message.new_chat_members or [])):
        return
    chat = message.chat
    await CTX["db"].chats.update_one({"_id": chat.id}, {"$set": {"title": chat.title, "active": True},
                                                       "$setOnInsert": {"added": time.time(), "battles": 0}}, upsert=True)
    await message.reply_text("👋 <b>AniArena is here!</b>\n\n⚔️ /arena - trivia battle (first to type the anime wins)\n🏆 /top - this week's chat ranking\n"
                             "🧩 /daily - the daily puzzle (in DM)\n\n<i>Tip: for the battle to read answers, make me an admin or turn off my privacy mode in BotFather.</i>",
                             parse_mode=HTML, reply_markup=Kb([[Btn("⚔️ Start a battle", callback_data="m:arena")]]))
    log_ch = CTX["settings"].log_channel
    if log_ch:
        try:
            await client.send_message(log_ch, f"➕ Added to <b>{esc(chat.title or str(chat.id))}</b> (<code>{chat.id}</code>)", parse_mode=HTML)
        except Exception:
            pass


async def cb_arena_button(client, query):
    await query.answer()
    msg = query.message
    msg.from_user = query.from_user
    msg.command = ["arena"]
    await cmd_arena(client, msg)


# ===================================================================== inline mode (viral sharing)
async def on_inline(client, query):
    u = query.from_user
    link = await bot_link(client, f"ref_{u.id}")
    d = CTX["daily"]
    user = await progress.get_user(CTX["db"], u.id) or {}
    play = Kb([[Btn("🎮 Play AniArena", url=link)]])
    results = [
        InlineQueryResultArticle(id="daily", title="🧩 Challenge friends: today's Daily", description="Send a Wordle-style anime puzzle invite",
                                 input_message_content=InputTextMessageContent(
                                     f"🧩 AniArena Daily #{daily_number(d.today())} - can you guess today's anime in {MAX_GUESSES} tries?"),
                                 reply_markup=play),
        InlineQueryResultArticle(id="me", title="👤 Share my player card", description=f"Level {progress.level_for(user.get('xp', 0))} · 🔥 {user.get('streak', 0)}",
                                 input_message_content=InputTextMessageContent(
                                     f"👤 {name_of(u)} - Level {progress.level_for(user.get('xp', 0))} {progress.title_for(progress.level_for(user.get('xp', 0)))}, "
                                     f"🔥 {user.get('streak', 0)}-day streak on AniArena. Beat me!"), reply_markup=play),
        InlineQueryResultArticle(id="arena", title="⚔️ Invite to an anime trivia battle", description="Add the bot to your group and send /arena",
                                 input_message_content=InputTextMessageContent("⚔️ Anime trivia battle! Add AniArena to this group and send /arena - first to type the anime wins."),
                                 reply_markup=play),
    ]
    await query.answer(results, cache_time=5, is_personal=True)


# ===================================================================== owner tools & background jobs
def is_owner(message) -> bool:
    return message.from_user and message.from_user.id in CTX["settings"].owner_ids


async def cmd_stats(client, message):
    if not is_owner(message):
        return
    db = CTX["db"]
    day = CTX["daily"].today().isoformat()
    users, chats = await db.users.count_documents({}), await db.chats.count_documents({"active": True})
    today_games = await db.daily_games.count_documents({"date": day})
    solved = await db.daily_games.count_documents({"date": day, "won": True})
    await message.reply_text(f"📊 Users: <b>{users}</b>\nGroups: <b>{chats}</b>\nDailies today: <b>{today_games}</b> ({solved} solved)\n"
                             f"Live battles: <b>{len(SESS)}</b>\nCatalog: <b>{len(CTX['catalog'].items)}</b> titles", parse_mode=HTML)


async def cmd_broadcast(client, message):
    if not is_owner(message) or not message.reply_to_message:
        return
    from pyrogram.errors import FloodWait
    ids = [u["_id"] for u in await CTX["db"].users.find({}).to_list(None)]
    ok = bad = 0
    status = await message.reply_text(f"📣 Sending to {len(ids)} users…")
    for uid in ids:
        try:
            await message.reply_to_message.copy(uid)
            ok += 1
        except FloodWait as e:
            await asyncio.sleep(e.value + 1)
        except Exception:
            bad += 1
        await asyncio.sleep(0.05)
    await status.edit_text(f"📣 Done. Delivered: {ok}, failed: {bad}.")


async def reminder_loop(client, hour: int = 17):
    """Once a day (at `hour`, in the configured timezone) nudge players with a streak who haven't played yet."""
    sent_day = None
    while True:
        try:
            tz = CTX["settings"].tz_offset_hours
            now = progress.today(tz)
            local_hour = int(((time.time() // 3600) + tz) % 24)
            if local_hour == hour and sent_day != now:
                sent_day = now
                day = now.isoformat()
                due = await CTX["db"].users.find({"streak": {"$gte": 2}, "last_daily": {"$ne": day}, "remind": {"$ne": False},
                                                  "reminded": {"$ne": day}}).to_list(5000)
                for u in due:
                    try:
                        await client.send_message(u["_id"], f"🔥 Your <b>{u['streak']}-day streak</b> is on the line! Today's Daily is waiting - /daily\n"
                                                  "<i>/remind off to stop these.</i>", parse_mode=HTML)
                    except Exception:
                        await CTX["db"].users.update_one({"_id": u["_id"]}, {"$set": {"remind": False}})
                    await CTX["db"].users.update_one({"_id": u["_id"]}, {"$set": {"reminded": day}})
                    await asyncio.sleep(0.06)
        except Exception:
            log.exception("reminder loop")
        await asyncio.sleep(600)


# ===================================================================== wiring
def setup(app, ctx: dict) -> None:
    CTX.update(ctx)
    for name, fn in {"start": cmd_start, "help": cmd_help, "daily": cmd_daily, "hol": cmd_hol, "arena": cmd_arena,
                     "stop": cmd_stop, "top": cmd_top, "me": cmd_me, "invite": cmd_invite, "remind": cmd_remind,
                     "stats": cmd_stats, "broadcast": cmd_broadcast}.items():
        app.add_handler(MessageHandler(fn, filters.command(name)))
    app.add_handler(MessageHandler(on_new_members, filters.new_chat_members))
    app.add_handler(MessageHandler(on_private_text, filters.private & filters.text & ~filters.regex(r"^/")))
    app.add_handler(MessageHandler(on_group_text, filters.group & filters.text & ~filters.regex(r"^/")), group=1)
    app.add_handler(CallbackQueryHandler(cb_menu, filters.regex(r"^m:(daily|hol|top|me)$")))
    app.add_handler(CallbackQueryHandler(cb_arena_button, filters.regex(r"^m:arena$")))
    app.add_handler(CallbackQueryHandler(cb_daily_pick, filters.regex(r"^dg:\d+$")))
    app.add_handler(CallbackQueryHandler(cb_hol, filters.regex(r"^hl:(h|l|new)$")))
    app.add_handler(InlineQueryHandler(on_inline))
