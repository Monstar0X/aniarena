"""PNG cards (Pillow): profile card and pixel-reveal images."""
from __future__ import annotations

import io
import urllib.request

from PIL import Image, ImageDraw, ImageFont

from . import progress

W, H = 1000, 560
BG1, BG2 = (16, 14, 36), (52, 22, 74)
PINK, CYAN, INK, MUT = (255, 107, 157), (110, 231, 255), (244, 244, 252), (150, 154, 190)
_DIRS = ["/usr/share/fonts/truetype/dejavu/", "/usr/share/fonts/dejavu/", "/Library/Fonts/", "C:/Windows/Fonts/",
         "/usr/share/fonts/truetype/liberation/"]


def font(size: int, bold: bool = False):
    names = ["DejaVuSans-Bold.ttf", "arialbd.ttf", "LiberationSans-Bold.ttf"] if bold else ["DejaVuSans.ttf", "arial.ttf", "LiberationSans-Regular.ttf"]
    for d in _DIRS:
        for n in names:
            try:
                return ImageFont.truetype(d + n, size)
            except OSError:
                pass
    return ImageFont.load_default(size)


def _bg() -> Image.Image:
    img = Image.new("RGB", (W, H))
    px = img.load()
    for y in range(H):
        for x in range(W):
            t = x / W * 0.6 + y / H * 0.4
            px[x, y] = tuple(int(BG1[i] + (BG2[i] - BG1[i]) * t) for i in range(3))
    return img


def profile_card(user: dict, rank: int | None) -> bytes:
    from .progress import BADGES
    img = _bg().convert("RGBA")
    ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)
    xp, lvl = user.get("xp", 0), progress.level_for(user.get("xp", 0))
    d.text((50, 36), "ANIARENA  •  PLAYER CARD", font=font(20, True), fill=CYAN)
    d.text((50, 76), (user.get("name") or "Player")[:22], font=font(54, True), fill=INK)
    d.text((50, 148), f"{progress.title_for(lvl)}  •  Level {lvl}" + (f"  •  Rank #{rank}" if rank else ""), font=font(26), fill=PINK)
    lo, hi = progress.xp_for_level(lvl), progress.xp_for_level(lvl + 1)
    frac = (xp - lo) / max(1, hi - lo)
    d.rounded_rectangle([50, 200, 950, 226], 13, fill=(255, 255, 255, 30))
    d.rounded_rectangle([50, 200, 50 + max(26, int(900 * frac)), 226], 13, fill=PINK)
    d.text((50, 234), f"{xp:,} XP  /  {hi:,} for level {lvl + 1}", font=font(18), fill=MUT)
    st = user.get("st", {})
    tiles = [("STREAK", f"{user.get('streak', 0)} days"), ("BEST STREAK", str(user.get("best_streak", 0))),
             ("DAILY WINS", str(st.get("daily_wins", 0))), ("ARENA WINS", str(st.get("arena_wins", 0))),
             ("HIGHER/LOWER", str(st.get("hol_best", 0))), ("FRIENDS", str(user.get("refs", 0)))]
    for i, (k, v) in enumerate(tiles):
        x, y = 50 + (i % 3) * 305, 290 + (i // 3) * 95
        d.rounded_rectangle([x, y, x + 285, y + 80], 14, fill=(255, 255, 255, 24))
        d.text((x + 16, y + 10), k, font=font(15, True), fill=MUT)
        d.text((x + 16, y + 34), v, font=font(30, True), fill=INK)
    x = 50
    for key in user.get("badges", [])[:8]:
        if key in BADGES:
            label = BADGES[key][1]
            w = int(d.textlength(label, font=font(17, True))) + 28
            if x + w > 950:
                break
            d.rounded_rectangle([x, 492, x + w, 524], 16, fill=(255, 107, 157, 70), outline=PINK)
            d.text((x + 14, 498), label, font=font(17, True), fill=INK)
            x += w + 10
    img.alpha_composite(ov)
    out = io.BytesIO()
    img.convert("RGB").save(out, "PNG")
    return out.getvalue()


def fetch(url: str | None, timeout: int = 8) -> bytes | None:
    if not url:
        return None
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "AniArena/1.0"}), timeout=timeout) as r:
            return r.read(8_000_000)
    except Exception:
        return None


_BLOCKS = {0: 14, 1: 8, 2: 4}   # reveal level -> pixel block size (3+ = sharp)


def pixelate(data: bytes, level: int) -> bytes:
    img = Image.open(io.BytesIO(data)).convert("RGB")
    img.thumbnail((480, 640))
    bs = _BLOCKS.get(level)
    if bs:
        small = img.resize((max(1, img.width // bs), max(1, img.height // bs)), Image.BILINEAR)
        img = small.resize(img.size, Image.NEAREST)
    out = io.BytesIO()
    img.save(out, "JPEG", quality=85)
    return out.getvalue()
