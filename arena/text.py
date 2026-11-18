"""Text helpers: normalisation, fuzzy matching, spoiler-masking and letter hints."""
from __future__ import annotations

import difflib
import random
import re
import unicodedata

_STOP_SUFFIX = re.compile(r"\b(season|part|cour|the animation|tv)\b.*$")


def norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(c for c in s if not unicodedata.combining(c)).lower().replace("&", " and ")
    s = re.sub(r"[^a-z0-9\u3040-\u30ff\u4e00-\u9fff]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def ratio(a: str, b: str) -> float:
    return difflib.SequenceMatcher(None, a, b).ratio()


def strict_match(guess: str, aliases: list[str]) -> bool:
    """Used for typed answers in group rounds: exact alias, or a near-exact typo on long names."""
    g = norm(guess)
    if not g:
        return False
    for a in aliases:
        if g == a:
            return True
        if len(a) >= 7 and len(g) >= 6 and ratio(g, a) >= 0.9:
            return True
    return False


def mask(text: str, names: list[str], token: str = "▒▒▒") -> str:
    """Hide the title (and its long words) inside a synopsis so it can't be pasted as the answer."""
    words = set()
    for n in names:
        words.add(n)
        words.update(w for w in re.split(r"\W+", n) if len(w) >= 4)
    for w in sorted(words, key=len, reverse=True):
        if len(w) >= 3:
            text = re.sub(re.escape(w), token, text, flags=re.I)
    return text


def hint_pattern(title: str, level: int, rng: random.Random | None = None) -> str:
    """level 1: word lengths only. level 2: first letters + a few random ones."""
    rng = rng or random.Random()
    out = []
    for word in title.split(" "):
        chars = []
        for i, c in enumerate(word):
            if not c.isalnum():
                chars.append(c)
            elif level >= 2 and (i == 0 or rng.random() < 0.2):
                chars.append(c)
            else:
                chars.append("_")
        out.append(" ".join(chars))
    return "   ".join(out)
