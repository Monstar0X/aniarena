import asyncio
import random
import unittest
from datetime import date, timedelta

from arena import cards, progress, text
from arena.battle import Battle
from arena.catalog import Catalog, daily_number
from arena.daily import Daily, compare, squares, HIT, MISS, NEAR, xp_for_result
from arena.hol import HigherLower
from arena.memdb import MemoryDB


def run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


async def make():
    db = MemoryDB()
    cat = Catalog(db)
    await cat.ensure()
    return db, cat


class MemDbTests(unittest.TestCase):
    def test_mongo_semantics(self):
        async def t():
            db = MemoryDB()
            r = await db.u.update_one({"_id": 1}, {"$set": {"a.b": 1}, "$inc": {"n": 2}, "$setOnInsert": {"j": 1}}, upsert=True)
            self.assertEqual(r.upserted_id, 1)
            r = await db.u.update_one({"_id": 1}, {"$inc": {"n": 3}, "$setOnInsert": {"j": 2}, "$addToSet": {"t": "x"}}, upsert=True)
            self.assertIsNone(r.upserted_id)
            self.assertEqual(await db.u.find_one({"_id": 1}), {"_id": 1, "a": {"b": 1}, "n": 5, "j": 1, "t": ["x"]})
            await db.u.update_one({"_id": 2}, {"$set": {"n": 9}}, upsert=True)
            rows = await db.u.find({"n": {"$gte": 5}}).sort("n", -1).limit(1).to_list(1)
            self.assertEqual(rows[0]["_id"], 2)
            self.assertEqual(await db.u.count_documents({"missing": {"$ne": 1}}), 2)   # $ne matches absent fields
            self.assertEqual((await db.u.update_one({"_id": 3}, {"$set": {"n": 1}})).matched_count, 0)
        run(t())

    def test_returns_copies(self):
        async def t():
            db = MemoryDB()
            await db.c.insert_one({"_id": 1, "l": [1]})
            d = await db.c.find_one({"_id": 1}); d["l"].append(2)
            self.assertEqual((await db.c.find_one({"_id": 1}))["l"], [1])
        run(t())


class TextTests(unittest.TestCase):
    def test_norm_and_strict(self):
        self.assertEqual(text.norm("Steins;Gate"), "steins gate")
        self.assertTrue(text.strict_match("attack on titans", ["attack on titan"]))
        self.assertFalse(text.strict_match("one", ["one piece"]))
        self.assertFalse(text.strict_match("", ["x"]))

    def test_mask_hides_title(self):
        m = text.mask("Death Note is a notebook, and the Note kills", ["Death Note"])
        self.assertNotIn("Death", m); self.assertNotIn("Note", m)

    def test_hint_pattern(self):
        self.assertEqual(text.hint_pattern("Ab Cd", 1), "_ _   _ _")
        self.assertTrue(text.hint_pattern("Naruto", 2, random.Random(1)).startswith("N"))


class CatalogTests(unittest.TestCase):
    def test_search_and_daily(self):
        async def t():
            _, cat = await make()
            self.assertEqual(cat.search("aot")[0][0]["title"], "Attack on Titan")
            self.assertEqual(cat.search("steins gate")[0][1], 1.0)
            self.assertEqual(cat.search("x"), [])
            d1, d2 = cat.daily(date(2026, 5, 1)), cat.daily(date(2026, 5, 1))
            self.assertEqual(d1["_id"], d2["_id"])
            self.assertEqual(len({cat.daily(date(2026, 1, 1) + timedelta(days=i))["_id"] for i in range(30)}) > 10, True)
            self.assertEqual(daily_number(date(2026, 1, 1)), 1)
        run(t())

    def test_refresh_replaces_seed_and_survives_errors(self):
        async def t():
            db = MemoryDB(); cat = Catalog(db)
            def boom(n): raise RuntimeError("anilist down")
            await cat.ensure(boom)
            self.assertGreater(len(cat.items), 50)                      # kept the seed
            fake = [{"_id": 900000 + i, "title": f"Show {i}", "aliases": [], "year": 2020, "season": "FALL", "episodes": 12, "format": "TV",
                     "score": 70, "popularity": 1000 - i, "studio": "S", "genres": ["Action"], "tags": ["x"], "desc": "d" * 50,
                     "cover": None, "src": "anilist"} for i in range(120)]
            await cat.ensure(lambda n: fake, refresh_days=0)
            self.assertEqual(len(cat.items), 120)
            self.assertTrue(all(d["src"] == "anilist" for d in cat.items.values()))
        run(t())


class DailyTests(unittest.TestCase):
    def test_compare_states(self):
        g = {"year": 2000, "episodes": 24, "score": 80, "format": "TV", "season": "FALL", "studio": "X", "genres": ["A", "B"]}
        t = dict(g, year=2003, episodes=26, score=90, format="MOVIE", studio="Y", genres=["B", "C"])
        c = {x.key: x for x in compare(g, t)}
        self.assertEqual((c["year"].state, c["year"].arrow), (MISS, "⬆️"))
        self.assertEqual(c["episodes"].state, NEAR)
        self.assertEqual((c["score"].state, c["score"].arrow), (MISS, "⬆️"))
        self.assertEqual(c["format"].state, MISS); self.assertEqual(c["season"].state, HIT)
        self.assertEqual(c["genres"].state, NEAR)
        self.assertEqual(squares(compare(g, g)), HIT * 7)

    def test_win_flow_streak_and_badges(self):
        async def t():
            db, cat = await make(); d = Daily(db, cat)
            await progress.register_user(db, 1, "A")
            game = await d.game(1)
            wrong = next(i for i in cat.pool() if i != game["target"])
            r = await d.guess(1, "A", wrong); self.assertFalse(r["finished"])
            self.assertEqual((await d.guess(1, "A", wrong))["status"], "dup")
            r = await d.guess(1, "A", game["target"])
            self.assertTrue(r["won"] and r["finished"])
            self.assertEqual(r["xp"], xp_for_result(True, 2, 1))
            self.assertEqual(r["streak"]["streak"], 1)
            self.assertIn("first_win", [b[0] for b in r["badges"]])
            self.assertIn("sniper", [b[0] for b in r["badges"]])
            self.assertEqual((await d.guess(1, "A", wrong))["status"], "done")
            u = await progress.get_user(db, 1)
            self.assertEqual(u["xp"], r["xp"]); self.assertEqual(u["st"]["daily_wins"], 1)
        run(t())

    def test_lose_after_max_guesses(self):
        async def t():
            db, cat = await make(); d = Daily(db, cat)
            game = await d.game(2)
            wrong = [i for i in cat.pool() if i != game["target"]][:8]
            for m in wrong: r = await d.guess(2, "B", m)
            self.assertTrue(r["finished"] and not r["won"])
            self.assertEqual(r["xp"], 8)
        run(t())

    def test_everyone_gets_same_target(self):
        async def t():
            db, cat = await make(); d = Daily(db, cat)
            self.assertEqual((await d.game(10))["target"], (await d.game(11))["target"])
        run(t())


class ProgressTests(unittest.TestCase):
    def test_levels(self):
        self.assertEqual(progress.level_for(0), 1); self.assertEqual(progress.level_for(60), 2)
        self.assertEqual(progress.level_for(239), 2); self.assertEqual(progress.level_for(240), 3)

    def test_streak_freeze_and_break(self):
        async def t():
            db, _ = await make()
            await progress.register_user(db, 1, "A")
            d0 = date(2026, 3, 1)
            self.assertEqual((await progress.update_streak(db, 1, d0))["streak"], 1)
            self.assertEqual((await progress.update_streak(db, 1, d0 + timedelta(days=1)))["streak"], 2)
            r = await progress.update_streak(db, 1, d0 + timedelta(days=3))     # missed 1 day, has 1 freeze
            self.assertEqual((r["streak"], r["used_freezes"]), (3, 1))
            r = await progress.update_streak(db, 1, d0 + timedelta(days=8))     # missed 4, no freezes left
            self.assertEqual((r["streak"], r["broke"]), (1, True))
            self.assertEqual((await progress.update_streak(db, 1, d0 + timedelta(days=8)))["streak"], 1)   # idempotent same day
        run(t())

    def test_referral_rules(self):
        async def t():
            db, _ = await make()
            await progress.register_user(db, 1, "Ref")
            r = await progress.register_user(db, 2, "New", ref=1)
            self.assertEqual(r["referrer"], 1)
            self.assertEqual((await progress.get_user(db, 1))["refs"], 1)
            self.assertEqual((await progress.get_user(db, 1))["xp"], progress.REF_REFERRER_XP)
            self.assertEqual((await progress.get_user(db, 2))["xp"], progress.REF_INVITEE_XP)
            self.assertEqual((await progress.get_user(db, 1))["freezes"], 2)
            r = await progress.register_user(db, 2, "New", ref=1)                # existing user can't be re-referred
            self.assertEqual(r["referrer"], None); self.assertEqual((await progress.get_user(db, 1))["refs"], 1)
            self.assertIsNone((await progress.register_user(db, 3, "Self", ref=3))["referrer"])
            self.assertIsNone((await progress.register_user(db, 4, "Ghost", ref=999))["referrer"])
        run(t())

    def test_leaderboards_and_rank(self):
        async def t():
            db, _ = await make(); day = date(2026, 4, 6)
            for uid, xp in ((1, 50), (2, 200), (3, 120)):
                await progress.register_user(db, uid, f"u{uid}")
                await progress.award_xp(db, uid, f"u{uid}", xp, chat=-5, day=day)
            self.assertEqual([r["_id"] for r in await progress.top_global(db)], [2, 3, 1])
            self.assertEqual([r["user"] for r in await progress.top_chat(db, -5, day=day)], [2, 3, 1])
            self.assertEqual(await progress.top_chat(db, -5, day=day + timedelta(days=7)), [])   # new week -> reset
            self.assertEqual(await progress.rank_of(db, 3), 2)
            res = await progress.award_xp(db, 1, "u1", 200)
            self.assertTrue(res["leveled"])
        run(t())


class BattleTests(unittest.TestCase):
    def setUp(self):
        self.db, self.cat = run(make())
        self.t = [0.0]
        self.b = Battle(self.cat, -1, 3, rng=random.Random(7), clock=lambda: self.t[0])

    def test_round_flow_and_scoring(self):
        r = self.b.start_round()
        self.assertIn("Round 1/3", self.b.prompt())
        self.assertIsNone(self.b.answer(1, "A", "definitely wrong"))
        self.t[0] = 5
        res = self.b.answer(1, "A", r.anime["title"])
        self.assertGreater(res["points"], 17)                                  # fast + no hints bonus
        self.assertIsNone(self.b.answer(2, "B", r.anime["title"]))              # round already solved
        self.assertEqual(self.b.standings()[0][:2], (1, "A"))

    def test_hints_lower_points_and_reveal_more(self):
        r = self.b.start_round()
        p0 = self.b.prompt()
        self.assertIsNotNone(self.b.hint()); self.assertIsNotNone(self.b.hint())
        self.assertNotEqual(p0, self.b.prompt())
        self.t[0] = 44
        res = self.b.answer(3, "C", r.anime["title"])
        self.assertLessEqual(res["points"], 11)

    def test_synopsis_never_leaks_title(self):
        for seed in range(40):
            b = Battle(self.cat, -1, 10, rng=random.Random(seed))
            r = b.start_round()
            if r.kind == "synopsis":
                low = b.prompt().lower()
                self.assertNotIn(r.anime["title"].lower(), low)

    def test_timeout_and_finish(self):
        for _ in range(3):
            r = self.b.start_round()
            self.assertEqual(self.b.timeout()["anime"]["_id"], r.anime["_id"])
        self.assertIsNone(self.b.start_round())
        self.assertTrue(self.b.finished)
        self.assertEqual(len({x for x in self.b.used}), 3)                     # no repeats within a battle

    def test_pixel_downgrade(self):
        b = Battle(self.cat, -1, 3, can_pixel=True)
        for d in self.cat.items.values(): d["cover"] = "http://x"
        for seed in range(30):
            b.rng = random.Random(seed); b.round_no = 0
            r = b.start_round()
            if r.kind == "pixel":
                b.downgrade(); self.assertEqual(b.current.kind, "clues"); return
        self.fail("no pixel round produced")


class HolTests(unittest.TestCase):
    def test_game_flow_and_xp_cap(self):
        async def t():
            db, cat = await make(); h = HigherLower(db, cat, random.Random(3))
            await progress.register_user(db, 1, "A")
            await h.start(1)
            for _ in range(60):
                s = await h.state(1)
                r = await h.answer(1, "A", "h" if s["b"]["score"] > s["a"]["score"] else "l")
                self.assertEqual(r["status"], "correct")
                self.assertNotEqual(r["a"]["score"], r["b"]["score"])
            s = await h.state(1)
            r = await h.answer(1, "A", "l" if s["b"]["score"] > s["a"]["score"] else "h")
            self.assertEqual((r["status"], r["streak"], r["xp"]), ("over", 60, 150))   # 60*3 capped at 150
            self.assertEqual((await h.answer(1, "A", "h"))["status"], "nogame")
            await h.start(1)                                                        # second game same day: cap exhausted
            s = await h.state(1)
            for _ in range(5):
                s = await h.state(1)
                r = await h.answer(1, "A", "h" if s["b"]["score"] > s["a"]["score"] else "l")
            s = await h.state(1)
            r = await h.answer(1, "A", "l" if s["b"]["score"] > s["a"]["score"] else "h")
            self.assertEqual(r["xp"], 0)
            self.assertEqual((await progress.get_user(db, 1))["st"]["hol_best"], 60)
        run(t())


class CardTests(unittest.TestCase):
    def test_profile_card_png(self):
        u = {"name": "Asha", "xp": 400, "streak": 5, "best_streak": 9, "refs": 2, "badges": ["first_win", "streak7"], "st": {"daily_wins": 3}}
        self.assertEqual(cards.profile_card(u, 4)[:4], b"\x89PNG")


if __name__ == "__main__":
    unittest.main()
