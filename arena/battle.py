"""Group trivia battle engine ("Arena"). Pure state machine - no Telegram, no timers - so it is fully testable.

The bot drives it: start_round() -> post prompt -> after 20s hint() -> after 35s hint() -> after 45s timeout().
Anyone's chat message goes to answer(); the first correct one wins the round."""
from __future__ import annotations

import random
import time
from dataclasses import dataclass, field

from . import text
from .catalog import Catalog

ROUND_SECONDS = 45
KINDS = ("synopsis", "pixel", "clues")


def _esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


@dataclass
class Round:
    anime: dict
    kind: str
    started: float
    hints: int = 0
    solved_by: int | None = None


@dataclass
class Battle:
    catalog: Catalog
    chat_id: int
    total: int = 5
    starter: int = 0
    rng: random.Random = field(default_factory=random.Random)
    clock: callable = time.monotonic
    can_pixel: bool = True
    round_no: int = 0
    used: set = field(default_factory=set)
    scores: dict = field(default_factory=dict)      # uid -> points
    names: dict = field(default_factory=dict)
    solves: dict = field(default_factory=dict)      # uid -> rounds won
    current: Round | None = None
    finished: bool = False

    # ------------------------------------------------------------ rounds
    def start_round(self) -> Round | None:
        if self.round_no >= self.total:
            self.finished = True
            self.current = None
            return None
        self.round_no += 1
        anime = self.catalog.random(self.rng, self.used)
        self.used.add(anime["_id"])
        kinds = [k for k in KINDS if k != "pixel" or (self.can_pixel and anime.get("cover"))]
        if anime.get("desc") is None or len(anime.get("desc", "")) < 40:
            kinds = [k for k in kinds if k != "synopsis"] or ["clues"]
        self.current = Round(anime, self.rng.choice(kinds), self.clock())
        return self.current

    def downgrade(self) -> None:
        """Image could not be fetched -> play this round as a clue round."""
        if self.current and self.current.kind == "pixel":
            self.current.kind = "clues"

    # ------------------------------------------------------------ prompts
    def prompt(self) -> str:
        r = self.current
        a = r.anime
        head = f"⚔️ <b>Round {self.round_no}/{self.total}</b> · first correct answer wins!\n\n"
        if r.kind == "synopsis":
            body = "📖 <b>Guess the anime from its story:</b>\n\n<i>" + _esc(text.mask(a["desc"], [a["title"], *a.get("aliases", [])])) + "</i>"
        elif r.kind == "pixel":
            body = "🖼 <b>Guess the anime from its blurry cover!</b> It sharpens as time runs out."
        else:
            body = "🕵️ <b>Guess the anime from the clues:</b>\n\n" + self._clues()
        if r.hints >= 2 or (r.kind != "clues" and r.hints >= 1):
            body += "\n\n🔤 " + self._pattern()
        return head + body

    def _clues(self) -> str:
        a, lvl = self.current.anime, self.current.hints
        lines = [f"🎭 Genres: {', '.join(a['genres'][:4])}", f"📺 {a['format']} · {a['episodes']} episode(s)"]
        if lvl >= 1:
            lines.append(f"📅 Aired: {a['season'].title()} {a['year']}")
            lines.append(f"🏷 Tags: {', '.join(a['tags'][:3])}" if a.get("tags") else "")
        if lvl >= 2:
            lines.append(f"🏢 Studio: {_esc(a['studio'])}")
        return "\n".join(x for x in lines if x)

    def _pattern(self) -> str:
        lvl = 1 if self.current.hints < 3 else 2
        return "<code>" + _esc(text.hint_pattern(self.current.anime["title"], lvl, random.Random(self.current.anime["_id"]))) + "</code>"

    def pixel_level(self) -> int:
        return min(self.current.hints, 3)

    def hint(self) -> str | None:
        """Advance one hint level. Returns the new prompt, or None when there is nothing left to give."""
        r = self.current
        if not r or r.solved_by is not None or r.hints >= 3:
            return None
        r.hints += 1
        return self.prompt()

    # ------------------------------------------------------------ answering
    def answer(self, uid: int, name: str, guess: str) -> dict | None:
        r = self.current
        if not r or r.solved_by is not None or not self.catalog.is_answer(guess, r.anime["_id"]):
            return None
        r.solved_by = uid
        left = max(0.0, ROUND_SECONDS - (self.clock() - r.started))
        pts = 10 + int(10 * left / ROUND_SECONDS) + (5 if r.hints == 0 else 0) + (3 if r.kind == "pixel" else 0)
        self.scores[uid] = self.scores.get(uid, 0) + pts
        self.solves[uid] = self.solves.get(uid, 0) + 1
        self.names[uid] = name
        return {"uid": uid, "name": name, "points": pts, "anime": r.anime, "seconds": round(ROUND_SECONDS - left, 1)}

    def timeout(self) -> dict | None:
        r = self.current
        if not r or r.solved_by is not None:
            return None
        r.solved_by = -1
        return {"anime": r.anime}

    # ------------------------------------------------------------ results
    def standings(self) -> list[tuple[int, str, int, int]]:
        rows = [(u, self.names.get(u, str(u)), p, self.solves.get(u, 0)) for u, p in self.scores.items()]
        return sorted(rows, key=lambda x: (-x[2], x[1]))
