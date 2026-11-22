"""
A small transactional document store, and its SQLite implementation.

The ledger logic (core.py) is written once against this interface and runs on either:

  SqliteStore      local development, tests, and self-hosting on one machine (this file)
  FirestoreStore   Google Cloud: Cloud Run + Firestore (store_firestore.py)

Rules the ledger code follows so that both behave identically:

  * Everything happens inside store.transaction(fn). fn may be retried, so it must not have
    side effects outside the transaction object.
  * Inside a transaction every read happens before the first write. Firestore requires
    this; SqliteStore enforces it, so a violation fails in local tests, not in production.
  * Documents are JSON objects of strings, numbers, booleans, lists of scalars and dicts.
    No lists of lists (Firestore forbids them) and no None in fields that queries use.
  * query(order_by=F) returns only documents that have field F. The ledger relies on this:
    for example only active assignments carry `expires_at`.
  * Filters: == < <= > >= and array_contains. An inequality filter must be on the order_by
    field (true of Firestore's automatic single-field indexes, so no composite index is ever
    needed).
"""
from __future__ import annotations

import json
import re
import sqlite3
import threading
import time
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple

Doc = Dict[str, Any]
Filter = Tuple[str, str, Any]

OPS = {"==": "=", "<": "<", "<=": "<=", ">": ">", ">=": ">="}
_FIELD = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z_][A-Za-z0-9_]*)*$")


def _jx(field: str) -> str:
    """json_extract(data, '$.field') as a literal, so expression indexes apply."""
    if not _FIELD.match(field):
        raise ValueError("bad field name %r" % field)
    return "json_extract(data, '$.%s')" % field


class ReadAfterWrite(RuntimeError):
    """A transaction read after writing; Firestore would reject it."""


class Contention(RuntimeError):
    """The transaction kept conflicting with others and gave up. Safe to retry later; the
    HTTP layer turns it into 503 with Retry-After."""


class Txn:
    def get(self, col: str, doc_id: str) -> Optional[Doc]: ...
    def query(self, col: str, where: Iterable[Filter] = (), order_by: Optional[str] = None,
              descending: bool = False, limit: Optional[int] = None) -> List[Doc]: ...
    def set(self, col: str, doc_id: str, doc: Doc) -> None: ...
    def delete(self, col: str, doc_id: str) -> None: ...


class Store:
    def transaction(self, fn: Callable[[Txn], Any]) -> Any: ...
    def close(self) -> None: ...


# --------------------------------------------------------------------------------- SQLite

class _SqliteTxn(Txn):
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn
        self.writes: List[Tuple[str, str, Optional[str]]] = []

    def _check(self):
        if self.writes:
            raise ReadAfterWrite("read after write inside a transaction (not allowed on Firestore)")

    def get(self, col, doc_id):
        self._check()
        row = self.conn.execute("SELECT data FROM docs WHERE col=? AND id=?", (col, doc_id)).fetchone()
        if not row:
            return None
        d = json.loads(row[0])
        d["_id"] = doc_id
        return d

    def query(self, col, where=(), order_by=None, descending=False, limit=None):
        self._check()
        sql = ["SELECT id, data FROM docs WHERE col=?"]
        args: List[Any] = [col]
        for field, op, value in where:
            if op == "array_contains":
                _jx(field)
                sql.append("AND EXISTS (SELECT 1 FROM json_each(docs.data, '$.%s') WHERE json_each.value = ?)" % field)
            else:
                sql.append("AND %s %s ?" % (_jx(field), OPS[op]))
            args.append(value)
        if order_by:
            sql.append("AND %s IS NOT NULL ORDER BY %s %s" % (_jx(order_by), _jx(order_by), "DESC" if descending else "ASC"))
        if limit:
            sql.append("LIMIT %d" % int(limit))
        out = []
        for doc_id, data in self.conn.execute(" ".join(sql), args):
            d = json.loads(data)
            d["_id"] = doc_id
            out.append(d)
        return out

    def set(self, col, doc_id, doc):
        clean = {k: v for k, v in doc.items() if k != "_id"}
        self.writes.append((col, doc_id, json.dumps(clean, separators=(",", ":"))))

    def delete(self, col, doc_id):
        self.writes.append((col, doc_id, None))


class SqliteStore(Store):
    """One file, any number of threads. Writers are serialised by SQLite's lock
    (BEGIN IMMEDIATE), which makes every transaction trivially serialisable."""

    def __init__(self, path: str, indexes: Iterable[Tuple[str, str]] = ()):
        self.path = path
        self.local = threading.local()
        self.all_conns: List[sqlite3.Connection] = []
        self.lock = threading.Lock()
        conn = self._conn()
        conn.execute("CREATE TABLE IF NOT EXISTS docs (col TEXT NOT NULL, id TEXT NOT NULL, data TEXT NOT NULL, PRIMARY KEY (col, id))")
        try:
            conn.execute("SELECT json_extract('{\"a\":1}', '$.a')").fetchone()
        except sqlite3.OperationalError as e:      # pragma: no cover
            raise RuntimeError("this Python's SQLite lacks JSON support (need SQLite >= 3.38 or JSON1)") from e
        for col, field in indexes:
            name = "ix_%s_%s" % (col, field.replace(".", "_"))
            # query() inlines the same literal expression, so SQLite can use this index
            conn.execute("CREATE INDEX IF NOT EXISTS %s ON docs(col, json_extract(data, '$.%s'))" % (name, field))

    def _conn(self) -> sqlite3.Connection:
        c = getattr(self.local, "conn", None)
        if c is None:
            c = sqlite3.connect(self.path, timeout=60, isolation_level=None, check_same_thread=False)
            c.execute("PRAGMA journal_mode=WAL")
            c.execute("PRAGMA synchronous=NORMAL")
            c.execute("PRAGMA busy_timeout=60000")
            self.local.conn = c
            with self.lock:
                self.all_conns.append(c)
        return c

    def transaction(self, fn):
        conn = self._conn()
        for attempt in range(50):
            try:
                conn.execute("BEGIN IMMEDIATE")
            except sqlite3.OperationalError:       # database is locked beyond busy_timeout
                time.sleep(0.05 * (attempt + 1))
                continue
            try:
                t = _SqliteTxn(conn)
                out = fn(t)
                for col, doc_id, data in t.writes:
                    if data is None:
                        conn.execute("DELETE FROM docs WHERE col=? AND id=?", (col, doc_id))
                    else:
                        conn.execute("INSERT OR REPLACE INTO docs (col, id, data) VALUES (?, ?, ?)", (col, doc_id, data))
                conn.execute("COMMIT")
                return out
            except BaseException:
                conn.execute("ROLLBACK")
                raise
        raise Contention("could not obtain the database lock")

    def close(self):
        with self.lock:
            for c in self.all_conns:
                c.close()
            self.all_conns = []
        self.local = threading.local()
