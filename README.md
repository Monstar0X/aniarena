# AniArena

**Anime games for Telegram that spread by themselves: a daily Wordle-style puzzle, group trivia battles, Higher/Lower,
XP + streaks + weekly leagues, and built-in invite loops.** Python 3.10+, Kurigram, **MongoDB (Motor)**, Pillow.

It is built around the things that make Telegram bots grow: a daily habit (streaks), a reason to add the bot to
groups (battles + weekly chat leaderboards), and sharing baked into every game (result cards + referral links).

---

## What users get

### 🧩 Daily Puzzle (`/daily`) - the habit
Everyone gets the same secret anime each day. Type a title (fuzzy search, aliases like `aot`, `hxh`, `jjk`; ambiguous
names show tap-to-pick buttons). Each guess is compared on **year, episodes, score, format, season, studio and genres**
with 🟩/🟨/🟥 and ⬆️/⬇️ arrows. 8 guesses; hints unlock late so newcomers can still win.
Finishing gives XP, extends your 🔥 streak, and produces a **spoiler-free emoji result to share**
(`🟩🟨🟥…` rows + your referral link).

### ⚔️ Arena (`/arena [3-15]`, groups) - the growth engine
Rapid-fire trivia where the **first correct message in the chat wins the round**. Round types:
* **Story** - the synopsis with the title (and its long words) masked out
* **Pixel** - the cover art, blocky at first and sharper as time runs out
* **Clues** - genres/format, then year/tags, then studio

Speed + "no hints" bonuses, live hints at 20 s and 35 s, a results board, and XP going to a **weekly per-chat leaderboard**
(`/top` in the group). Groups that play together keep the bot.

### 📈 Higher or Lower (`/hol`)
Two anime, one rating hidden. Pure streak game with inline buttons; daily XP cap prevents farming.

### 🏆 Progression everywhere
XP, levels and titles (Newbie -> Ascended), **streaks with freezes** (earn one every 7 days or per friend invited),
11 badges, global / weekly / per-chat leaderboards, and a **player card PNG** (`/me`).

### 🤝 Built-in virality
* **Referrals:** `/invite` -> friends who join via your link give you +100 XP and a streak freeze (they get +50 XP).
* **Share buttons** on every result and card carry your referral link.
* **Inline mode:** type `@YourBot` anywhere to drop a Daily challenge, your player card or an Arena invite into any chat.
* **Group-add hook:** when the bot is added to a group it posts a one-tap "Start a battle" welcome.
* **Streak reminders** at a configurable hour for players about to lose a streak (`/remind off` to opt out).

### 🛠 Owner tools
`/stats` (users, groups, dailies today) and `/broadcast` (reply to any message; throttled, FloodWait-safe).
Optional `LOG_CHANNEL` pings you whenever the bot joins a group.

---

## Setup

1. **BotFather:** create the bot, then
   * `/setinline` -> enable inline mode (placeholder e.g. "Challenge a friend")
   * `/setjoingroups` -> enabled
   * `/setprivacy` -> **Disable** (Arena needs to read typed answers in groups; alternatively make the bot admin)
   * `/setcommands`:
   ```
   daily - Today's anime puzzle
   arena - Trivia battle in this group
   hol - Higher or Lower
   top - Leaderboards
   me - My player card
   invite - Invite friends, earn rewards
   remind - Streak reminders on/off
   help - How to play
   ```
2. **Config:** copy `.env.example` to `.env` (`BOT_TOKEN`, `API_ID`, `API_HASH`, `MONGO_URI`, `OWNER_IDS`).
   MongoDB Atlas free tier is plenty. Leave `MONGO_URI` empty to try it with a throw-away in-memory DB.
3. **Run:** `pip install -r requirements.txt && python main.py` - or deploy the included `Dockerfile` / `Procfile`
   (it is a worker, no web port needed; set the same env vars).

On first start the bot seeds 59 bundled titles, then pulls the **top ~600 popular anime from AniList** (public API, no key)
and refreshes weekly. If AniList is unreachable it keeps whatever it has.

> Tip: set `TZ_OFFSET_HOURS` so the daily rolls over at a sensible hour for your audience.

---

## MongoDB layout

| Collection | Key | Purpose |
|---|---|---|
| `users` | tg id | name, xp, streak, freezes, badges, refs, `st.*` stats, reminder flags |
| `anime` | AniList id | catalog (title, aliases, year, season, episodes, studio, genres, tags, cover, teaser) |
| `daily_games` | `user:date` | one row per player per day (target, guesses, done/won) |
| `hol` | tg id | current Higher/Lower game state (restart-safe) |
| `week_scores` | `week:user` | weekly global leaderboard |
| `chat_scores` | `week:chat:user` | weekly per-group leaderboard |
| `chats` | chat id | groups the bot is in, battles played |
| `meta` | `catalog` | last catalog refresh |

Indexes are created at startup. Only simple operators are used (`$set $inc $setOnInsert $addToSet $push`, equality /
`$gt $gte $lt $ne` filters, sort/limit) - no aggregation pipelines - so it runs on any MongoDB tier.
Live Arena rounds are kept in memory (a restart just ends the current battle; all scores are already saved).

---

## Code map

```
main.py            entrypoint (Mongo, catalog sync, bot, reminder loop)
arena/bot.py       Telegram handlers (thin)
arena/daily.py     puzzle comparison, board rendering, XP
arena/battle.py    Arena state machine (rounds, hints, scoring) - no Telegram, fully testable
arena/hol.py       Higher/Lower
arena/progress.py  XP, levels, streaks+freezes, badges, referrals, leaderboards
arena/catalog.py   MongoDB-backed catalog + fuzzy search + deterministic daily pick
arena/anilist.py   AniList GraphQL fetch        arena/seed.py   bundled starter titles
arena/cards.py     player card + pixel-reveal images (Pillow)
arena/memdb.py     in-memory MongoDB look-alike used by tests / quick local runs
```

## Tests
```bash
python -m unittest discover -s tests -t .      # 36 tests, ~5 s, no network / Telegram / MongoDB needed
```
Covers the Mongo-semantics layer, fuzzy matching, daily comparison and XP, streak freezes and breaks, referral rules
(no self/ghost/repeat referrals), weekly boards, battle scoring and hint flow (including "synopsis never leaks the
title"), the Higher/Lower XP cap, and every Telegram handler end-to-end (including a full Arena battle) against a stubbed Kurigram.

## Honest notes
* **Verified here:** all game logic, the progression system, the handlers (stubbed Kurigram) and the data layer against
  `memdb.py`, which mirrors Motor's API for the operators used.
* **Not verified here:** this build environment had no internet, MongoDB, Motor or Kurigram, so the real Motor connection,
  the live AniList fetch and real Telegram delivery were not exercised. Do one smoke test after deploying:
  `/start`, `/daily`, add the bot to a group, `/arena 3`. If AniList changes a field, fix `arena/anilist.py::to_doc`.
* Arena reads every group message while a battle is active (that is how typed answers work). It stores nothing from them.
* English only for now; all user-facing strings live in `bot.py`.
* Anime data and cover art come from AniList and belong to their owners; the bundled teasers are original text.

MIT licence.
