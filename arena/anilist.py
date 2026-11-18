"""Fetch the most popular anime from AniList (public GraphQL, no key needed)."""
from __future__ import annotations

import html
import json
import re
import time
import urllib.error
import urllib.request

QUERY = """query($p:Int,$n:Int){Page(page:$p,perPage:$n){pageInfo{hasNextPage}
media(type:ANIME,sort:POPULARITY_DESC,isAdult:false,format_in:[TV,MOVIE,ONA]){
id title{romaji english} synonyms seasonYear season episodes format averageScore popularity genres
studios(isMain:true){nodes{name}} tags{name rank} coverImage{large} description(asHtml:false)}}}"""


def _clean(desc: str | None) -> str:
    d = html.unescape(re.sub(r"<[^>]+>", " ", desc or ""))
    d = re.sub(r"\(Source:.*?\)|\[Written by.*?\]", "", d, flags=re.S)
    d = re.sub(r"\s+", " ", d).strip()
    return d[:320].rsplit(" ", 1)[0] + "…" if len(d) > 320 else d


def to_doc(m: dict) -> dict | None:
    studios = ((m.get("studios") or {}).get("nodes")) or []
    if not (m.get("seasonYear") and m.get("averageScore") and m.get("episodes") and studios and m.get("season")):
        return None
    t = m["title"]
    title = t.get("english") or t.get("romaji")
    aliases = [x for x in {t.get("romaji"), t.get("english"), *(m.get("synonyms") or [])} if x and x != title]
    return {
        "_id": m["id"], "title": title, "aliases": aliases[:8], "year": m["seasonYear"], "season": m["season"],
        "episodes": m["episodes"], "format": m["format"], "score": m["averageScore"],
        "popularity": m.get("popularity") or 0, "studio": studios[0]["name"], "genres": m.get("genres") or [],
        "tags": [x["name"] for x in sorted(m.get("tags") or [], key=lambda x: -(x.get("rank") or 0))[:6]],
        "desc": _clean(m.get("description")), "cover": (m.get("coverImage") or {}).get("large"), "src": "anilist",
    }


def _post(url: str, variables: dict, timeout: int = 25) -> dict:
    req = urllib.request.Request(url, data=json.dumps({"query": QUERY, "variables": variables}).encode(),
                                 headers={"Content-Type": "application/json", "Accept": "application/json",
                                          "User-Agent": "AniArena/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        if e.code == 429:
            time.sleep(min(int(e.headers.get("Retry-After", "10")), 40))
            return _post(url, variables, timeout)
        raise


def fetch_popular(url: str, size: int = 600) -> list[dict]:
    """Blocking; call through asyncio.to_thread. Returns catalog docs, most popular first."""
    out, page = [], 1
    while len(out) < size and page <= 20:
        data = _post(url, {"p": page, "n": 50})["data"]["Page"]
        out += [d for d in map(to_doc, data["media"]) if d]
        if not data["pageInfo"]["hasNextPage"]:
            break
        page += 1
        time.sleep(0.8)   # stay far below AniList's rate limit
    return out[:size]
