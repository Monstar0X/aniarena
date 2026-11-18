"""In-memory stand-in for a Motor database.

Implements exactly the subset of the Motor API this project uses, with Mongo semantics
(upsert from equality filter, $set/$inc/$setOnInsert/$addToSet/$push/$unset, dotted paths,
$gt/$gte/$lt/$lte/$in/$ne/$exists, sort/skip/limit). The same repo code therefore runs against
real MongoDB in production and against this class in tests / quick local runs.
"""
from __future__ import annotations

import copy
import itertools


def _get(doc, path, default=None):
    cur = doc
    for p in path.split("."):
        if not isinstance(cur, dict) or p not in cur:
            return default
        cur = cur[p]
    return cur


def _set(doc, path, value):
    parts = path.split(".")
    for p in parts[:-1]:
        doc = doc.setdefault(p, {})
    doc[parts[-1]] = value


def _unset(doc, path):
    parts = path.split(".")
    for p in parts[:-1]:
        doc = doc.get(p, {})
    doc.pop(parts[-1], None)


_MISSING = object()


def _match(doc, flt) -> bool:
    for key, cond in flt.items():
        val = _get(doc, key, _MISSING)
        if isinstance(cond, dict) and cond and all(k.startswith("$") for k in cond):
            for op, arg in cond.items():
                if op == "$exists":
                    if (val is not _MISSING) != bool(arg):
                        return False
                    continue
                if val is _MISSING:
                    if op == "$ne":
                        continue
                    return False
                if op == "$gt" and not val > arg: return False
                if op == "$gte" and not val >= arg: return False
                if op == "$lt" and not val < arg: return False
                if op == "$lte" and not val <= arg: return False
                if op == "$ne" and val == arg: return False
                if op == "$in" and val not in arg: return False
                if op == "$nin" and val in arg: return False
        else:
            if isinstance(val, list) and not isinstance(cond, list):
                if cond not in val:
                    return False
            elif val != cond:
                return False
    return True


class _Cursor:
    def __init__(self, docs):
        self._docs, self._sort, self._skip, self._limit = docs, [], 0, 0

    def sort(self, key, direction=None):
        self._sort = key if isinstance(key, list) else [(key, direction or 1)]
        return self

    def skip(self, n):
        self._skip = n
        return self

    def limit(self, n):
        self._limit = n
        return self

    async def to_list(self, length=None):
        docs = list(self._docs)
        for k, d in reversed(self._sort):
            docs.sort(key=lambda x, k=k: (_get(x, k) is None, _get(x, k)), reverse=(d == -1))
        docs = docs[self._skip:]
        n = self._limit or length
        if n:
            docs = docs[:n]
        return [copy.deepcopy(d) for d in docs]

    def __aiter__(self):
        async def gen():
            for d in await self.to_list():
                yield d
        return gen()


class _Result:
    def __init__(self, matched=0, modified=0, upserted_id=None, deleted=0, inserted_id=None):
        self.matched_count, self.modified_count, self.upserted_id = matched, modified, upserted_id
        self.deleted_count, self.inserted_id = deleted, inserted_id


class MemCollection:
    _ids = itertools.count(1)

    def __init__(self):
        self.docs: list[dict] = []

    async def create_index(self, *a, **k):
        return "idx"

    def _find(self, flt):
        return [d for d in self.docs if _match(d, flt or {})]

    async def find_one(self, flt=None, *a, **k):
        r = self._find(flt)
        return copy.deepcopy(r[0]) if r else None

    def find(self, flt=None, *a, **k):
        return _Cursor(self._find(flt))

    async def count_documents(self, flt=None):
        return len(self._find(flt))

    async def insert_one(self, doc):
        doc = copy.deepcopy(doc)
        doc.setdefault("_id", f"auto{next(self._ids)}")
        if any(d["_id"] == doc["_id"] for d in self.docs):
            raise ValueError(f"duplicate key {doc['_id']}")
        self.docs.append(doc)
        return _Result(inserted_id=doc["_id"])

    async def insert_many(self, docs):
        for d in docs:
            await self.insert_one(d)

    @staticmethod
    def _apply(doc, update, inserting):
        for op, fields in update.items():
            for path, v in fields.items():
                if op == "$set": _set(doc, path, copy.deepcopy(v))
                elif op == "$setOnInsert":
                    if inserting: _set(doc, path, copy.deepcopy(v))
                elif op == "$inc": _set(doc, path, (_get(doc, path, 0) or 0) + v)
                elif op == "$unset": _unset(doc, path)
                elif op == "$addToSet":
                    cur = _get(doc, path, None)
                    if cur is None:
                        cur = []; _set(doc, path, cur)
                    if v not in cur: cur.append(copy.deepcopy(v))
                elif op == "$push":
                    cur = _get(doc, path, None)
                    if cur is None:
                        cur = []; _set(doc, path, cur)
                    cur.append(copy.deepcopy(v))
                else:
                    raise NotImplementedError(op)

    async def update_one(self, flt, update, upsert=False):
        r = self._find(flt)
        if r:
            self._apply(r[0], update, False)
            return _Result(1, 1)
        if not upsert:
            return _Result(0, 0)
        doc = {k: copy.deepcopy(v) for k, v in flt.items() if not (isinstance(v, dict) and any(str(x).startswith("$") for x in v))}
        self._apply(doc, update, True)
        doc.setdefault("_id", f"auto{next(self._ids)}")
        self.docs.append(doc)
        return _Result(0, 0, upserted_id=doc["_id"])

    async def update_many(self, flt, update):
        r = self._find(flt)
        for d in r:
            self._apply(d, update, False)
        return _Result(len(r), len(r))

    async def replace_one(self, flt, doc, upsert=False):
        r = self._find(flt)
        doc = copy.deepcopy(doc)
        if r:
            doc["_id"] = r[0]["_id"]
            r[0].clear(); r[0].update(doc)
            return _Result(1, 1)
        if upsert:
            for k, v in flt.items():
                doc.setdefault(k, v)
            doc.setdefault("_id", f"auto{next(self._ids)}")
            self.docs.append(doc)
            return _Result(0, 0, upserted_id=doc["_id"])
        return _Result()

    async def delete_one(self, flt):
        r = self._find(flt)
        if r:
            self.docs.remove(r[0])
        return _Result(deleted=1 if r else 0)

    async def delete_many(self, flt):
        r = self._find(flt)
        for d in r:
            self.docs.remove(d)
        return _Result(deleted=len(r))


class MemoryDB:
    """`db.users`, `db.anime`, ... created on first access, like Motor."""

    def __init__(self):
        self._c: dict[str, MemCollection] = {}

    def __getattr__(self, name: str) -> MemCollection:
        if name.startswith("_"):
            raise AttributeError(name)
        return self._c.setdefault(name, MemCollection())

    def __getitem__(self, name: str) -> MemCollection:
        return getattr(self, name)
