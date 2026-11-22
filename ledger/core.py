"""
The ledger: which numbers have been handed out, to whom, and what came back.

Guarantees (each is exercised by ledger/tests/test_core.py):

  No gaps          Candidates are issued strictly in list order (ascending n) from a cursor.
                   A candidate that is issued but not yet settled always has at least one
                   live assignment or one queue entry, so nothing can fall through. `audit`
                   checks this invariant over the whole ledger and can repair violations.
  No needless      A candidate has at most one queue entry and is reissued only when its
  duplication      lease expires. A worker that asks again gets its current assignment back.
                   A worker holding work that is no longer needed is told to abandon it.
  Checked results  A result is double-checked when policy says so: always for a prime,
                   always while the worker or the engine build has not yet earned trust, and
                   for a random share (dc_fraction) of the rest. Two matching results from
                   different workers settle a candidate; a mismatch triggers a tie-break.
  Retractable      Every result records its engine build. A build can be blocked from new
  builds           work, and `invalidate_engine` discards its results and re-queues whatever
                   they had settled. A build earns trust only from matches with a *different*
                   build or backend, since a deterministic bug would agree with itself.

Every public method is a single store transaction that reads before it writes (store.py).
"""
from __future__ import annotations

import bisect
import hashlib
import hmac
import re
import secrets
import time
from typing import Any, Dict, Iterable, List, Optional, Tuple

from .store import Doc, Store

CHUNK = 5000                        # candidates per chunk document
PROTOCOL = 1                        # version of the HTTP protocol in docs/LEDGER.md

DEFAULT_CONFIG: Dict[str, Any] = {
    "lease_seconds": 3 * 86400,     # reissue an assignment after this long without a heartbeat
    "heartbeat_seconds": 900,       # how often clients report progress
    "dc_fraction": 0.05,            # random share of trusted results double-checked anyway
    "worker_trust_after": 2,        # verified results before a worker is only spot-checked
    "engine_trust_after": 5,        # cross-checked results before an engine build is trusted
    "dc_distinct_owner": False,     # strict: checks must come from a different owner, and
                                    # agreement counts owners rather than workers
    "dc_other_impl_wait_seconds": 86400.0,   # a check waits this long for a different owner,
                                    # build and backend before any other worker may take it
    "max_projected_days": 0.0,      # refuse work to devices slower than this (0: no limit)
    "blocked_engines": [],          # engine builds that get no new work
    "allowed_engines": [],          # if non-empty, only these builds get work
    "accept_dirty_engines": True,   # builds from a modified source tree ("...-dirty")
    "registration": "open",         # open | invite | closed
    "invite_code": "",
    "message": "",                  # shown by every client
    "paused": False,                # stop issuing work; results are still accepted
    "pm1": True,                    # clients run P-1 factoring before a first test (docs/PM1.md)
    "sieve_bits": 32.0,             # the candidate list has no factor below 2^sieve_bits; P-1
                                    # bounds are chosen from it
}
PUBLIC_CONFIG = ("heartbeat_seconds", "lease_seconds", "message", "paused", "registration", "pm1", "sieve_bits")

# Fields the ledger queries on. SqliteStore builds expression indexes for them; Firestore's
# automatic single-field indexes cover them, so no composite index is ever needed.
INDEXES = [("assignments", "expires_at"), ("assignments", "active_n"), ("assignments", "first_n"),
           ("queue", "priority"), ("queue", "first_n"), ("owners", "results"), ("candidates", "index"),
           ("candidates", "engines")]

FINAL = ("done", "verified", "removed", "factored")
HEX16 = re.compile(r"^[0-9a-f]{16}$")
DIGITS = re.compile(r"^[1-9][0-9]{0,3999}$")


class LedgerError(Exception):
    """A problem with the request (bad input, auth, policy). `status` is the HTTP status."""

    def __init__(self, message: str, status: int = 400, code: str = "bad_request"):
        super().__init__(message)
        self.status, self.code = status, code


def cid(k: int, n: int) -> str:
    return "%d_%d" % (k, n)


def backend_class(backend: str) -> str:
    """'cpu (14 threads)' -> 'cpu'; 'opencl: NVIDIA GeForce RTX 4090' -> 'opencl'."""
    b = (backend or "").strip().lower()
    return "cpu" if b.startswith("cpu") else "opencl" if b.startswith("opencl") else (b.split(":")[0] or "unknown")


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _engine_id(v: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]", "_", v)[:80] or "unknown"


def _owner_id(name: str) -> str:
    return hashlib.sha1(name.encode()).hexdigest()[:16]


class Ledger:
    def __init__(self, store: Store, clock=time.time, rng=None):
        self.store = store
        self.clock = clock
        self.rng = rng or secrets.SystemRandom()

    # ================================================================== helpers

    @staticmethod
    def _cfg(t) -> Dict[str, Any]:
        cfg = dict(DEFAULT_CONFIG)
        cfg.update({k: v for k, v in (t.get("meta", "config") or {}).items() if k in DEFAULT_CONFIG})
        return cfg

    @staticmethod
    def _state(t) -> Dict[str, Any]:
        st = t.get("meta", "state") or {}
        st.pop("_id", None)
        for key, v in (("total", 0), ("cursor", 0), ("issued", 0), ("results", 0), ("active", 0)):
            st.setdefault(key, v)
        for key in ("counts", "hourly"):
            st.setdefault(key, {})
        for key in ("primes", "chunk_n", "last"):
            st.setdefault(key, [])
        return st

    @staticmethod
    def _public(cfg) -> Dict[str, Any]:
        return {k: cfg[k] for k in PUBLIC_CONFIG}

    def _auth(self, t, worker_id: str, token: str) -> Doc:
        w = t.get("workers", worker_id) if worker_id else None
        if not w or not hmac.compare_digest(w.get("token_hash", ""), _hash(token or "")):
            raise LedgerError("unknown worker or wrong token", 401, "unauthorized")
        if w.get("disabled"):
            raise LedgerError("this worker has been disabled by the project", 403, "disabled")
        return w

    @staticmethod
    def _engine_refusal(cfg, engine: str) -> Optional[str]:
        if not engine:
            return "the client did not say which engine build it runs"
        if engine in cfg["blocked_engines"]:
            return "engine build %s has been withdrawn; please update" % engine
        if cfg["allowed_engines"] and engine not in cfg["allowed_engines"]:
            return "engine build %s is not accepted by this project; please update" % engine
        if "-dirty" in engine and not cfg["accept_dirty_engines"]:
            return "engine %s was built from modified source; this project accepts release builds only" % engine
        return None

    @staticmethod
    def _evaluate(c: Doc, cfg) -> Tuple[str, List[List[Doc]]]:
        """Status of a candidate from its results, and its result groups (largest first).
        Agreement counts distinct workers, or distinct owners in strict mode (dc_distinct_owner)."""
        if c.get("status") == "removed":
            return "removed", []
        if c.get("factor"):
            return "factored", []           # a factor is its own proof: the ledger checked it
        who = "owner" if cfg["dc_distinct_owner"] else "worker"
        valid = [r for r in c.get("results", []) if not r.get("invalid")]
        groups: Dict[Tuple[str, str], List[Doc]] = {}
        for r in valid:
            groups.setdefault((r["result"], r["res64"]), []).append(r)
        size = lambda g: len({r[who] for r in g})
        ordered = sorted(groups.values(), key=lambda g: -size(g))
        # Settled when the largest group has two independent members and strictly outnumbers the
        # runner-up. Once results have disagreed, the winners must also span two owners: one
        # person's machines may share the fault that caused the disagreement.
        if ordered and size(ordered[0]) >= 2 and (len(ordered) == 1 or size(ordered[0]) > size(ordered[1])) \
                and (len(ordered) == 1 or len({r["owner"] for r in ordered[0]}) >= 2):
            return "verified", ordered
        if not valid:
            return "untested", ordered
        if len(ordered) > 1:
            return "conflict", ordered
        return ("done" if c.get("needed", 1) <= 1 else "awaiting_dc"), ordered

    @staticmethod
    def _kind(status: str) -> str:
        return {"awaiting_dc": "dc", "conflict": "tiebreak"}.get(status, "first")

    @staticmethod
    def _assignment_doc(a: Doc) -> Doc:
        """Query fields exist only while an assignment is live (store.py: order_by)."""
        out = {k: v for k, v in a.items() if k not in ("_id", "expires_at", "active_n", "first_n")}
        if out["state"] == "active":
            out["expires_at"] = out["lease_until"]
            out["active_n"] = out["n"]
            if out["kind"] == "first":
                out["first_n"] = out["n"]
        return out

    def _queue_doc(self, c: Doc, cfg, now: float, also_exclude: Iterable[str] = ()) -> Doc:
        status = self._evaluate(c, cfg)[0]
        valid = [r for r in c.get("results", []) if not r.get("invalid")]
        q = {"k": c["k"], "n": c["n"], "index": c["index"], "priority": c["n"], "kind": self._kind(status),
             "exclude": sorted({r["worker"] for r in valid} | set(also_exclude)),
             "exclude_owners": sorted({r["owner"] for r in valid}),
             "impls": sorted({r["engine"] + "|" + backend_class(r["backend"]) for r in valid}),
             "created_at": now}
        if status == "untested":
            q["first_n"] = c["n"]
        return q

    @staticmethod
    def _bump(st, frm: Optional[str], to: Optional[str]):
        if frm == to:
            return
        if frm:
            st["counts"][frm] = st["counts"].get(frm, 0) - 1
        if to:
            st["counts"][to] = st["counts"].get(to, 0) + 1

    @staticmethod
    def _apply(t, writes: List[Tuple[str, str, Optional[Doc]]]):
        """Write each document once (the last version wins)."""
        final: Dict[Tuple[str, str], Optional[Doc]] = {}
        for col, i, d in writes:
            final.pop((col, i), None)
            final[(col, i)] = d
        for (col, i), d in final.items():
            if d is None:
                t.delete(col, i)
            else:
                t.set(col, i, d)

    # ================================================================== admin

    def seed(self, pairs: Iterable[Tuple[int, int]]) -> Dict[str, Any]:
        """Append candidates. They are issued in (n, k) order. Anything at or below the last
        candidate already in the list is skipped, so re-running a seed is harmless and a
        longer list extends the search."""
        todo = sorted({(int(n), int(k)) for k, n in pairs})
        for n, k in todo:
            if not (1 <= k < 2 ** 32 and 300 <= n < 2 ** 31):
                raise LedgerError("candidate out of range: k=%d n=%d" % (k, n))
        added = 0
        while todo:
            def txn(t, todo=todo):
                st = self._state(t)
                last = tuple(st["last"]) if st["last"] else (0, 0)
                fresh = [p for p in todo if p > last]
                total = st["total"]
                ci = total // CHUNK
                chunk = t.get("chunks", "%06d" % ci) or {"start": ci * CHUNK, "items": [], "removed": []}
                chunk.pop("_id", None)
                take = fresh[:CHUNK - total % CHUNK]
                if not take:
                    return 0, len(todo)
                if total % CHUNK == 0:
                    st["chunk_n"].append(take[0][0])
                for n, k in take:
                    chunk["items"] += [k, n]
                st["total"] = total + len(take)
                st["last"] = list(take[-1])
                t.set("chunks", "%06d" % ci, chunk)
                t.set("meta", "state", st)
                return len(take), (todo.index(take[-1]) + 1)
            n_added, consumed = self.store.transaction(txn)
            added += n_added
            todo = todo[consumed:]
        return {"added": added, "total": self.store.transaction(lambda t: self._state(t)["total"])}

    def set_config(self, changes: Dict[str, Any]) -> Dict[str, Any]:
        for key in changes:
            if key not in DEFAULT_CONFIG:
                raise LedgerError("unknown config key %r" % key)

        def txn(t):
            cfg = self._cfg(t)
            for key, v in changes.items():
                want = type(DEFAULT_CONFIG[key])
                if want is float and isinstance(v, int) and not isinstance(v, bool):
                    v = float(v)
                if not isinstance(v, want) or (want in (int, float) and isinstance(v, bool)):
                    raise LedgerError("config %s must be of type %s" % (key, want.__name__))
                cfg[key] = v
            t.set("meta", "config", cfg)
            return cfg
        return self.store.transaction(txn)

    def get_config(self) -> Dict[str, Any]:
        return self.store.transaction(self._cfg)

    def remove(self, pairs: Iterable[Tuple[int, int]], reason: str = "factor found") -> Dict[str, Any]:
        """Take candidates out of the search, e.g. after a deeper sieve found a factor."""
        st0 = self.store.transaction(self._state)
        by_chunk: Dict[int, List[Tuple[int, int]]] = {}
        for k, n in pairs:
            ci = bisect.bisect_right(st0["chunk_n"], int(n)) - 1
            # equal n can straddle a chunk boundary; check the previous chunk as well
            for c_i in {max(ci, 0), max(ci - 1, 0)}:
                by_chunk.setdefault(c_i, []).append((int(k), int(n)))
        removed = 0
        for ci, plist in sorted(by_chunk.items()):
            for s in range(0, len(plist), 200):
                part = plist[s:s + 200]

                def txn(t, ci=ci, part=part):
                    st = self._state(t)
                    ch = t.get("chunks", "%06d" % ci)
                    if not ch:
                        return 0
                    ch.pop("_id", None)
                    where = {(ch["items"][2 * j], ch["items"][2 * j + 1]): j for j in range(len(ch["items"]) // 2)}
                    hits = [(p, where[p]) for p in part if p in where]
                    cands = {p: t.get("candidates", cid(*p)) for p, _ in hits}
                    queued = {p: t.get("queue", cid(*p)) for p, _ in hits}
                    count = 0
                    for p, j in hits:
                        c = cands[p]
                        if c is not None:
                            old = c.get("status")
                            if old in FINAL:
                                continue
                            c["status"], c["removed_reason"] = "removed", reason
                            self._bump(st, old, "removed")
                            t.set("candidates", cid(*p), c)
                            if queued[p]:
                                t.delete("queue", cid(*p))
                        elif j not in ch.setdefault("removed", []):
                            ch["removed"].append(j)
                            st["removed_ahead"] = st.get("removed_ahead", 0) + 1   # not issued yet
                        else:
                            continue
                        count += 1
                    t.set("chunks", "%06d" % ci, ch)
                    t.set("meta", "state", st)
                    return count
                removed += self.store.transaction(txn)
        return {"removed": removed}

    # ================================================================== workers

    def register(self, owner: str, name: str, info: Dict[str, Any], invite: str = "") -> Dict[str, Any]:
        owner = re.sub(r"\s+", " ", (owner or "")).strip()[:40] or "anonymous"
        name = re.sub(r"\s+", " ", (name or "")).strip()[:60] or "worker"
        token = secrets.token_urlsafe(24)
        worker_id = "w" + secrets.token_hex(6)

        def txn(t):
            cfg = self._cfg(t)
            if cfg["registration"] == "closed":
                raise LedgerError("this project is not accepting new workers", 403, "registration_closed")
            if cfg["registration"] == "invite" and not hmac.compare_digest(str(invite or ""), cfg["invite_code"] or "\0"):
                raise LedgerError("joining this project needs an invite code", 403, "invite_required")
            now = self.clock()
            t.set("workers", worker_id, {
                "token_hash": _hash(token), "owner": owner, "name": name, "created_at": now, "last_seen": now,
                "platform": str(info.get("platform", ""))[:80], "device": str(info.get("device", ""))[:120],
                "app_version": str(info.get("app_version", ""))[:40], "engine": str(info.get("engine", ""))[:60],
                "results": 0, "verified": 0, "bad": 0, "history": []})
            return {"worker_id": worker_id, "token": token, "owner": owner, "config": self._public(cfg)}
        return self.store.transaction(txn)

    # ================================================================== work

    def request_work(self, worker_id: str, token: str, info: Dict[str, Any]) -> Dict[str, Any]:
        """Hand out one assignment, or the worker's current one if it still holds a live one."""
        engine = str(info.get("engine", ""))[:60]
        impl = engine + "|" + backend_class(str(info.get("backend", "")))
        ms = float(info.get("ms_per_iter") or 0)

        def txn(t):
            now = self.clock()
            w = self._auth(t, worker_id, token)
            cfg, st = self._cfg(t), self._state(t)
            why = self._engine_refusal(cfg, engine)
            if why:
                raise LedgerError(why, 426, "upgrade_required")
            cur = t.get("assignments", w["assignment"]) if w.get("assignment") else None
            if cur and cur["state"] == "active":
                return {"assignment": self._public_assignment(cur), "config": self._public(cfg)}
            if cfg["paused"]:
                return {"assignment": None, "reason": "paused", "retry_after": 900, "config": self._public(cfg)}

            expired = t.query("assignments", [("expires_at", "<", now)], order_by="expires_at", limit=5)
            queue = t.query("queue", order_by="priority", limit=25)
            queued = {q["_id"] for q in queue}
            ids = sorted({cid(a["k"], a["n"]) for a in expired} | queued)
            cands = {i: t.get("candidates", i) for i in ids}
            outside = {i: t.get("queue", i) for i in ids if i not in queued}      # queued beyond the head
            chunk = t.get("chunks", "%06d" % (st["cursor"] // CHUNK)) if st["cursor"] < st["total"] else None
            # ---------------- no reads below this line
            writes: List[Tuple[str, str, Optional[Doc]]] = []

            # 1. expire stale leases; their candidates return to the pool if nothing covers them
            pool = []                                   # (n, index, source, candidate, queue doc)
            for a in expired:
                i = cid(a["k"], a["n"])
                a["state"], a["expired_at"] = "expired", now
                writes.append(("assignments", a["_id"], self._assignment_doc(a)))
                st["active"] -= 1
                c = cands.get(i)
                if c is None:
                    continue
                c["active"] = [x for x in c.get("active", []) if x != a["_id"]]
                writes.append(("candidates", i, c))
                if self._evaluate(c, cfg)[0] in FINAL or c["active"] or i in queued or outside.get(i):
                    continue
                if any(p[3] is c for p in pool):
                    continue
                pool.append((c["n"], c["index"], "expired", c, self._queue_doc(c, cfg, now)))
            for q in queue:
                c = cands.get(q["_id"])
                if c is None or self._evaluate(c, cfg)[0] in FINAL:
                    writes.append(("queue", q["_id"], None))     # stale entry
                else:
                    pool.append((q["n"], q["index"], "queue", c, q))
            pool.sort(key=lambda p: (p[0], p[1]))

            # 2. pick: older work first. Never your own result's check. A check should also come
            #    from a different owner and implementation (build or backend): one person's
            #    machines may share a fault, and a deterministic bug agrees with itself. A worker
            #    that would not be independent takes fresh work instead, unless the check has
            #    already waited dc_other_impl_wait_seconds for someone who is.
            def eligible(p):
                q = p[4]
                # strict mode, and every tie-break: never an owner who already has a result
                hard_owner = cfg["dc_distinct_owner"] or q["kind"] == "tiebreak"
                return worker_id not in q["exclude"] and not (hard_owner and w["owner"] in q["exclude_owners"])

            def preferred(p):
                q = p[4]
                # for a tie-break the existing results already disagree, so any other owner
                # settles it; for a check, the implementation must differ as well
                independent = w["owner"] not in q["exclude_owners"] and (q["kind"] == "tiebreak" or impl not in q.get("impls", []))
                return eligible(p) and (q["kind"] == "first" or independent
                                        or now - q.get("created_at", now) >= cfg["dc_other_impl_wait_seconds"])
            pick = next((p for p in pool if preferred(p)), None)
            for p in pool:
                if p is not pick and p[2] == "expired":
                    writes.append(("queue", cid(p[3]["k"], p[3]["n"]), p[4]))

            if pick:
                c = pick[3]
                if pick[2] == "queue":
                    writes.append(("queue", pick[4]["_id"], None))
                kind = self._kind(self._evaluate(c, cfg)[0])
            else:
                # 3. the next candidate from the cursor
                c = None
                while chunk and st["cursor"] < st["total"] and st["cursor"] // CHUNK == chunk["start"] // CHUNK:
                    j = st["cursor"] - chunk["start"]
                    st["cursor"] += 1
                    if j in chunk.get("removed", []):
                        st["skipped"] = st.get("skipped", 0) + 1     # removed before it was issued
                        st["removed_ahead"] = max(0, st.get("removed_ahead", 0) - 1)
                        continue
                    k, n = chunk["items"][2 * j], chunk["items"][2 * j + 1]
                    c = {"k": k, "n": n, "index": st["cursor"] - 1, "status": "untested", "needed": 1,
                         "results": [], "engines": [], "active": [], "created_at": now}
                    self._bump(st, None, "untested")
                    break
                if c is None:
                    writes.append(("meta", "state", st))
                    self._apply(t, writes)
                    if st["cursor"] < st["total"]:          # crossed a chunk of removed candidates
                        return {"assignment": None, "reason": "retry", "retry_after": 1, "config": self._public(cfg)}
                    if pool:                                # checks remain, waiting for someone independent
                        # come back when the soonest of them opens up to any eligible worker
                        opens = [p[4].get("created_at", now) + cfg["dc_other_impl_wait_seconds"] - now for p in pool if eligible(p)]
                        wait = max(30, min(900, min(opens))) if opens else 900
                        return {"assignment": None, "reason": "waiting", "retry_after": int(wait), "config": self._public(cfg)}
                    if st["total"] == 0:                    # nothing has been loaded yet
                        return {"assignment": None, "reason": "not_started", "retry_after": 3600, "config": self._public(cfg)}
                    if st["active"] > 0:                    # tests still running may need checking
                        return {"assignment": None, "reason": "waiting", "retry_after": 600, "config": self._public(cfg)}
                    return {"assignment": None, "reason": "exhausted", "retry_after": 3600, "config": self._public(cfg)}
                kind = "first"

            if cfg["max_projected_days"] and ms > 0:
                days = ms * c["n"] / 1000 / 86400
                if days > cfg["max_projected_days"]:
                    raise LedgerError("this device would need about %.0f days per test; the project's limit is %g days"
                                      % (days, cfg["max_projected_days"]), 403, "too_slow")

            a_id = "a" + secrets.token_hex(8)
            a = {"_id": a_id, "k": c["k"], "n": c["n"], "kind": kind, "worker": worker_id, "owner": w["owner"],
                 "state": "active", "issued_at": now, "last_seen": now, "lease_until": now + cfg["lease_seconds"],
                 "iteration": 0, "total": c["n"] - 1, "engine": engine}
            if c.get("pm1"):
                a["pm1_done"] = {"b1": c["pm1"]["b1"], "b2": c["pm1"]["b2"]}
            c.setdefault("active", []).append(a_id)
            w["assignment"], w["last_seen"] = a_id, now
            st["active"] += 1
            st["issued"] += 1
            writes += [("candidates", cid(c["k"], c["n"]), c), ("assignments", a_id, self._assignment_doc(a)),
                       ("workers", worker_id, w), ("meta", "state", st)]
            self._apply(t, writes)
            return {"assignment": self._public_assignment(a), "config": self._public(cfg)}
        return self.store.transaction(txn)

    @staticmethod
    def _public_assignment(a: Doc) -> Dict[str, Any]:
        out = {"id": a["_id"], "k": a["k"], "n": a["n"], "kind": a["kind"], "issued_at": a["issued_at"],
               "lease_until": a.get("lease_until"), "iteration": a.get("iteration", 0)}
        if a.get("pm1_done"):
            out["pm1_done"] = a["pm1_done"]          # P-1 already run to these bounds, without a factor
        return out

    def progress(self, worker_id: str, token: str, assignment_id: str, report: Dict[str, Any]) -> Dict[str, Any]:
        """Heartbeat: extends the lease and says whether to continue or abandon."""
        def txn(t):
            now = self.clock()
            w = self._auth(t, worker_id, token)
            cfg = self._cfg(t)
            a = t.get("assignments", assignment_id)
            if not a or a["worker"] != worker_id:
                raise LedgerError("no such assignment for this worker", 404, "not_found")
            if a["state"] in ("completed", "abandoned", "released"):
                return {"action": "abandon", "reason": "assignment is " + a["state"], "config": self._public(cfg)}
            i = cid(a["k"], a["n"])
            c = t.get("candidates", i)
            status = self._evaluate(c, cfg)[0] if c else "removed"
            other = None
            if a["state"] == "expired" and w.get("assignment") and w["assignment"] != assignment_id:
                other = t.get("assignments", w["assignment"])
            refused = self._engine_refusal(cfg, a.get("engine", "")) if a.get("engine") else None
            touch_state = a["state"] == "expired" or status in FINAL or bool(refused)
            st = self._state(t) if touch_state else None
            q = t.get("queue", i) if (a["state"] == "expired" or refused) else None
            # ---------------- writes
            if refused:
                # this build has been withdrawn: stop, and put the number back if nobody else has it
                if a["state"] == "active":
                    st["active"] -= 1
                a["state"], a["ended_at"] = "abandoned", now
                t.set("assignments", assignment_id, self._assignment_doc(a))
                if c:
                    c["active"] = [x for x in c.get("active", []) if x != assignment_id]
                    if status not in FINAL and not c["active"] and not q:
                        t.set("queue", i, self._queue_doc(c, cfg, now))
                    t.set("candidates", i, c)
                if w.get("assignment") == assignment_id:
                    w.pop("assignment")
                    t.set("workers", worker_id, w)
                t.set("meta", "state", st)
                return {"action": "abandon", "reason": refused, "config": self._public(cfg)}
            if status in FINAL or (other and other["state"] == "active"):
                if a["state"] == "active":
                    st["active"] -= 1
                a["state"], a["ended_at"] = "abandoned", now
                t.set("assignments", assignment_id, self._assignment_doc(a))
                if c:
                    c["active"] = [x for x in c.get("active", []) if x != assignment_id]
                    t.set("candidates", i, c)
                if w.get("assignment") == assignment_id:
                    w.pop("assignment")
                    t.set("workers", worker_id, w)
                t.set("meta", "state", st)
                why = "no longer needed (%s)" % status if status in FINAL else "you have newer work"
                return {"action": "abandon", "reason": why, "config": self._public(cfg)}
            for key in ("iteration", "ms_per_iter", "checks_passed", "rollbacks"):
                if isinstance(report.get(key), (int, float)) and not isinstance(report.get(key), bool):
                    a[key] = report[key]
            if isinstance(report.get("phase"), str):
                a["phase"] = report["phase"][:16]
            pm = report.get("pm1")
            if isinstance(pm, dict) and c is not None:
                # P-1 finished without a factor: remember the bounds, so a reissue skips it
                try:
                    b1, b2 = int(pm["b1"]), int(pm["b2"])
                except (KeyError, TypeError, ValueError):
                    raise LedgerError("pm1 report needs integer b1 and b2")
                old_pm = c.get("pm1") or {}
                if 2 <= b1 <= 10 ** 12 and b1 <= b2 <= 10 ** 14 and (b1, b2) > (old_pm.get("b1", 0), old_pm.get("b2", 0)):
                    c["pm1"] = {"b1": b1, "b2": b2, "worker": worker_id, "owner": w["owner"], "at": now,
                                "engine": str(pm.get("engine", ""))[:60]}
                    t.set("candidates", i, c)
            a["last_seen"], a["lease_until"] = now, now + cfg["lease_seconds"]
            if a["state"] == "expired":
                # back after the lease ran out; take it back unless someone else is on it
                a["state"] = "active"
                a.pop("expired_at", None)
                c["active"] = c.get("active", []) + [assignment_id]
                t.set("candidates", i, c)
                if q:
                    t.delete("queue", i)
                st["active"] += 1
                t.set("meta", "state", st)
                w["assignment"], w["last_seen"] = assignment_id, now
                t.set("workers", worker_id, w)
            t.set("assignments", assignment_id, self._assignment_doc(a))
            return {"action": "continue", "lease_until": a["lease_until"], "config": self._public(cfg)}
        return self.store.transaction(txn)

    def release(self, worker_id: str, token: str, assignment_id: str) -> Dict[str, Any]:
        """The client hands work back (left the project, or switched to its own list)."""
        def txn(t):
            now = self.clock()
            w = self._auth(t, worker_id, token)
            cfg, st = self._cfg(t), self._state(t)
            a = t.get("assignments", assignment_id)
            if not a or a["worker"] != worker_id:
                raise LedgerError("no such assignment for this worker", 404, "not_found")
            i = cid(a["k"], a["n"])
            c = t.get("candidates", i)
            q = t.get("queue", i)
            if a["state"] not in ("active", "expired"):
                return {"released": False, "reason": a["state"]}
            if a["state"] == "active":
                st["active"] -= 1
            a["state"], a["ended_at"] = "released", now
            t.set("assignments", assignment_id, self._assignment_doc(a))
            if c:
                c["active"] = [x for x in c.get("active", []) if x != assignment_id]
                if self._evaluate(c, cfg)[0] not in FINAL and not c["active"] and not q:
                    t.set("queue", i, self._queue_doc(c, cfg, now, also_exclude=[worker_id]))
                t.set("candidates", i, c)
            if w.get("assignment") == assignment_id:
                w.pop("assignment")
            t.set("workers", worker_id, w)
            t.set("meta", "state", st)
            return {"released": True}
        return self.store.transaction(txn)

    # ================================================================== results

    def submit_result(self, worker_id: str, token: str, assignment_id: str, r: Dict[str, Any]) -> Dict[str, Any]:
        if isinstance(r, dict) and "factor" in r:
            return self._submit_factor(worker_id, token, assignment_id, r)     # checked after the token
        res = self._validate_result(r)

        def txn(t):
            now = self.clock()
            w = self._auth(t, worker_id, token)
            cfg, st = self._cfg(t), self._state(t)
            a = t.get("assignments", assignment_id)
            if not a or a["worker"] != worker_id:
                raise LedgerError("no such assignment for this worker", 404, "not_found")
            if (a["k"], a["n"]) != (res["k"], res["n"]):
                raise LedgerError("result is for %d*2^%d+1 but the assignment is %d*2^%d+1" % (res["k"], res["n"], a["k"], a["n"]))
            if a["state"] == "completed":
                return {"accepted": True, "duplicate": True, "status": a.get("outcome", "")}
            i = cid(a["k"], a["n"])
            c = t.get("candidates", i)
            q = t.get("queue", i)
            eng_id = _engine_id(res["engine"])
            eng = t.get("engines", eng_id) or {"version": res["engine"], "results": 0, "verified": 0, "bad": 0}
            others = sorted({x["worker"] for x in c.get("results", [])} - {worker_id})
            workers = {o: t.get("workers", o) for o in others}
            engines = {e: t.get("engines", _engine_id(e)) for e in sorted(set(c.get("engines", [])) - {res["engine"]})}
            owner = t.get("owners", _owner_id(w["owner"])) or {"name": w["owner"], "results": 0}
            # ---------------- writes
            old = c.get("status", "untested")
            res.update({"worker": worker_id, "owner": w["owner"], "assignment": assignment_id, "at": now, "kind": a["kind"]})
            refused = self._engine_refusal(cfg, res["engine"])
            if refused:
                res["invalid"] = refused          # kept for the record; counts for nothing
            c.setdefault("results", []).append(res)
            if res["engine"] not in c.setdefault("engines", []):
                c["engines"].append(res["engine"])
            c["active"] = [x for x in c.get("active", []) if x != assignment_id]
            if a["state"] == "active":
                st["active"] -= 1
            a["state"], a["ended_at"] = "completed", now

            status, groups = self._evaluate(c, cfg)
            if status == "done":
                # the only valid result so far: does policy want it double-checked?
                why = self._dc_reason(cfg, res, w, eng)
                if why:
                    c["needed"], c["dc_reason"] = 2, why
                    status, groups = self._evaluate(c, cfg)
            c["status"] = status
            self._bump(st, old, status)

            workers[worker_id] = w
            engines = {e: d for e, d in engines.items() if d}
            engines[res["engine"]] = eng
            if status == "verified" and not c.get("trust_counted"):
                c["trust_counted"] = True
                self._credit(groups, workers, engines)

            if status not in FINAL and not c["active"] and not q:
                t.set("queue", i, self._queue_doc(c, cfg, now))
            elif status in FINAL and q:
                t.delete("queue", i)
            # (not final but another assignment is live: that one becomes the check)

            if res["result"] == "PRIME" and not res.get("invalid") and \
                    not any((p["k"], p["n"]) == (res["k"], res["n"]) for p in st["primes"]):
                st["primes"].append({"k": res["k"], "n": res["n"], "owner": w["owner"], "at": now})
            self._prime_status(st, c, status, groups)
            st["results"] += 1
            hour = str(int(now // 3600))
            st["hourly"][hour] = st["hourly"].get(hour, 0) + 1
            for key in sorted(st["hourly"], key=int)[:-72]:
                del st["hourly"][key]
            a["outcome"] = status
            w["results"] = w.get("results", 0) + 1
            w["last_seen"] = now
            w["history"] = (w.get("history", []) + [{"k": res["k"], "n": res["n"], "result": res["result"],
                                                      "res64": res["res64"], "at": now}])[-20:]
            if w.get("assignment") == assignment_id:
                w.pop("assignment")
            eng["results"] = eng.get("results", 0) + 1
            owner["results"] = owner.get("results", 0) + 1
            owner["last_at"] = now
            c["updated_at"] = now
            t.set("candidates", i, c)
            t.set("assignments", assignment_id, self._assignment_doc(a))
            for wid, wd in workers.items():
                if wd is not None:
                    t.set("workers", wid, wd)
            for e, ed in engines.items():
                t.set("engines", _engine_id(e), ed)
            t.set("owners", _owner_id(w["owner"]), owner)
            t.set("meta", "state", st)
            return {"accepted": True, "status": status, "double_check": status in ("awaiting_dc", "conflict")}
        return self.store.transaction(txn)

    @staticmethod
    def _validate_factor(r: Dict[str, Any]) -> Dict[str, Any]:
        try:
            k, n, f = int(r["k"]), int(r["n"]), str(r["factor"]).strip()
            out = {"k": k, "n": n, "factor": f, "b1": int(r.get("b1", 0)), "b2": int(r.get("b2", 0)),
                   "stage": int(r.get("stage", 0)), "seconds": float(r.get("seconds", 0)),
                   "backend": str(r.get("backend", ""))[:120], "engine": str(r.get("engine", ""))[:60]}
        except (KeyError, TypeError, ValueError) as e:
            raise LedgerError("malformed factor: %s" % e)
        if not (1 <= k < 2 ** 32 and 300 <= n < 2 ** 31) or not DIGITS.match(f):
            raise LedgerError("malformed factor")
        q = int(f)
        # The whole proof: q is a proper divisor of P = k*2^n+1. P itself is never built (at
        # n ~ 2^31 that would take hundreds of MB): it has exactly n + k.bit_length() bits, so a
        # divisor with fewer bits is proper, and q (at most 4000 digits) can only have as many
        # when n is small.
        pbits = n + k.bit_length()
        if q < 2 or q.bit_length() > pbits or (k * pow(2, n, q) + 1) % q != 0 or \
                (q.bit_length() == pbits and q == k * 2 ** n + 1):
            raise LedgerError("%s does not divide %d*2^%d+1" % (f if len(f) < 40 else f[:37] + "...", k, n), 422, "not_a_factor")
        return out

    def _submit_factor(self, worker_id: str, token: str, assignment_id: str, r: Dict[str, Any]) -> Dict[str, Any]:
        def txn(t):
            now = self.clock()
            w = self._auth(t, worker_id, token)
            res = self._validate_factor(r)          # only for a known worker: the check costs CPU
            cfg, st = self._cfg(t), self._state(t)
            a = t.get("assignments", assignment_id)
            if not a or a["worker"] != worker_id:
                raise LedgerError("no such assignment for this worker", 404, "not_found")
            if (a["k"], a["n"]) != (res["k"], res["n"]):
                raise LedgerError("factor is for %d*2^%d+1 but the assignment is %d*2^%d+1" % (res["k"], res["n"], a["k"], a["n"]))
            if a["state"] == "completed":
                return {"accepted": True, "duplicate": True, "status": a.get("outcome", "")}
            i = cid(a["k"], a["n"])
            c = t.get("candidates", i)
            q = t.get("queue", i)
            owner = t.get("owners", _owner_id(w["owner"])) or {"name": w["owner"], "results": 0}
            # ---------------- writes
            old = self._evaluate(c, cfg)[0]
            if not c.get("factor"):
                c["factor"] = res["factor"]
                c["factor_info"] = dict(res, worker=worker_id, owner=w["owner"], assignment=assignment_id, at=now)
                st["factors"] = st.get("factors", 0) + 1
                hour = str(int(now // 3600))
                st["hourly"][hour] = st["hourly"].get(hour, 0) + 1
                for key in sorted(st["hourly"], key=int)[:-72]:
                    del st["hourly"][key]
            status = self._evaluate(c, cfg)[0]
            c["status"] = status
            self._bump(st, old, status)
            c["active"] = [x for x in c.get("active", []) if x != assignment_id]
            if a["state"] == "active":
                st["active"] -= 1
            a["state"], a["ended_at"], a["outcome"] = "completed", now, status
            if q:
                t.delete("queue", i)
            self._prime_status(st, c, status, [])
            w["results"] = w.get("results", 0) + 1
            w["factors"] = w.get("factors", 0) + 1
            w["last_seen"] = now
            w["history"] = (w.get("history", []) + [{"k": res["k"], "n": res["n"], "result": "factor", "factor": res["factor"][:60], "at": now}])[-20:]
            if w.get("assignment") == assignment_id:
                w.pop("assignment")
            owner["results"] = owner.get("results", 0) + 1
            owner["last_at"] = now
            c["updated_at"] = now
            t.set("candidates", i, c)
            t.set("assignments", assignment_id, self._assignment_doc(a))
            t.set("workers", worker_id, w)
            t.set("owners", _owner_id(w["owner"]), owner)
            t.set("meta", "state", st)
            return {"accepted": True, "status": status, "double_check": False}
        return self.store.transaction(txn)

    @staticmethod
    def _prime_status(st, c, status, groups):
        """Keep the public list of reported primes in step with what the evidence says."""
        for p in st["primes"]:
            if (p["k"], p["n"]) != (c["k"], c["n"]):
                continue
            if status == "verified":
                p["status"] = "verified" if groups[0][0]["result"] == "PRIME" else "refuted"
            elif status == "factored":
                p["status"] = "refuted"                 # a checked factor beats any residue
            elif status in ("done", "removed"):
                p["status"] = "refuted" if not groups or groups[0][0]["result"] != "PRIME" else "awaiting_dc"
            elif status == "untested":
                p["status"] = "withdrawn"
            else:
                p["status"] = status

    @staticmethod
    def _credit(groups, workers, engines):
        """A candidate just settled: credit the agreeing workers and builds, debit the others."""
        win = groups[0]
        for wid in {x["worker"] for x in win}:
            if workers.get(wid) is not None:
                workers[wid]["verified"] = workers[wid].get("verified", 0) + 1
        # a build earns trust only from agreement with a different build or backend
        impls = {(x["engine"], backend_class(x["backend"])) for x in win}
        if len(impls) >= 2:
            for e in {x["engine"] for x in win}:
                if engines.get(e) is not None:
                    engines[e]["verified"] = engines[e].get("verified", 0) + 1
        win_engines = {x["engine"] for x in win}
        losers = [x for g in groups[1:] for x in g]
        for wid in {x["worker"] for x in losers}:
            if workers.get(wid) is not None:
                workers[wid]["bad"] = workers[wid].get("bad", 0) + 1
        for e in {x["engine"] for x in losers} - win_engines:
            if engines.get(e) is not None:
                engines[e]["bad"] = engines[e].get("bad", 0) + 1

    def _dc_reason(self, cfg, res, w, eng) -> Optional[str]:
        if res["result"] == "PRIME":
            return "prime"
        if w.get("verified", 0) < cfg["worker_trust_after"] * (1 + w.get("bad", 0)):
            return "worker not yet trusted"
        if eng.get("verified", 0) < cfg["engine_trust_after"] * (1 + eng.get("bad", 0)):
            return "engine build not yet trusted"
        if res.get("rollbacks", 0) >= 3:
            return "several errors were corrected during the run"
        if self.rng.random() < cfg["dc_fraction"]:
            return "random spot check"
        return None

    @staticmethod
    def _validate_result(r: Dict[str, Any]) -> Dict[str, Any]:
        try:
            out = {"k": int(r["k"]), "n": int(r["n"]), "result": str(r["result"]), "res64": str(r["res64"]).lower(),
                   "base": int(r.get("base", 0)), "N": int(r.get("N", 0)), "iterations": int(r["iterations"]),
                   "gerbicz_ok": int(r.get("gerbicz_ok", 0)), "rollbacks": int(r.get("rollbacks", 0)),
                   "seconds": float(r.get("seconds", 0)), "backend": str(r.get("backend", ""))[:120],
                   "engine": str(r.get("engine", ""))[:60]}
        except (KeyError, TypeError, ValueError) as e:
            raise LedgerError("malformed result: %s" % e)
        if out["result"] not in ("PRIME", "composite"):
            raise LedgerError("result must be PRIME or composite")
        if not HEX16.match(out["res64"]):
            raise LedgerError("res64 must be 16 hex digits")
        if out["iterations"] != out["n"] - 1:
            raise LedgerError("a complete test has n-1 iterations")
        if (out["result"] == "PRIME") != (out["res64"] == "0" * 16):
            raise LedgerError("verdict and residue disagree")
        if not out["engine"]:
            raise LedgerError("result has no engine version")
        return out

    # ================================================================== operations

    def invalidate_engine(self, engine: str) -> Dict[str, Any]:
        """Discard every result from one engine build, re-queue what they settled, block it."""
        self.set_config({"blocked_engines": sorted(set(self.get_config()["blocked_engines"]) | {engine})})
        ids = self.store.transaction(lambda t: [d["_id"] for d in t.query("candidates", [("engines", "array_contains", engine)])])
        touched = 0
        for i in ids:
            def txn(t, i=i):
                now = self.clock()
                cfg, st = self._cfg(t), self._state(t)
                c = t.get("candidates", i)
                q = t.get("queue", i)
                if not c:
                    return 0
                hit = [r for r in c.get("results", []) if r["engine"] == engine and not r.get("invalid")]
                if not hit:
                    return 0
                for r in hit:
                    r["invalid"] = "engine build %s withdrawn" % engine
                old = c.get("status")
                # whatever remains must be confirmed afresh
                c["needed"] = 2 if any(not r.get("invalid") for r in c["results"]) else 1
                c.pop("trust_counted", None)
                status, groups = self._evaluate(c, cfg)
                c["status"] = status
                self._bump(st, old, status)
                self._prime_status(st, c, status, groups)
                # the old entry (if any) describes a check of results that no longer count
                if status not in FINAL and (q or not c.get("active")):
                    t.set("queue", i, self._queue_doc(c, cfg, now))
                elif status in FINAL and q:
                    t.delete("queue", i)
                t.set("candidates", i, c)
                t.set("meta", "state", st)
                return 1
            touched += self.store.transaction(txn)
        return {"candidates_requeued": touched, "blocked": engine}

    def audit(self, repair: bool = False) -> Dict[str, Any]:
        """Check every issued candidate against the no-gaps invariant; optionally repair."""
        st = self.store.transaction(self._state)
        cfg = self.get_config()
        live = {a["_id"] for a in self.store.transaction(lambda t: t.query("assignments", order_by="active_n"))}
        queue = {q["_id"] for q in self.store.transaction(lambda t: t.query("queue", order_by="priority"))}
        problems, checked, after = [], 0, -1
        indices = set()
        while True:
            page = self.store.transaction(lambda t, after=after: t.query("candidates", [("index", ">", after)], order_by="index", limit=1000))
            for c in page:
                checked += 1
                indices.add(c["index"])
                status = self._evaluate(c, cfg)[0]
                if c.get("status") != status:
                    problems.append({"kind": "status_mismatch", "id": c["_id"], "stored": c.get("status"), "actual": status})
                if status not in FINAL and not any(x in live for x in c.get("active", [])) and c["_id"] not in queue:
                    problems.append({"kind": "orphan", "id": c["_id"], "status": status})
            if len(page) < 1000:
                break
            after = page[-1]["index"]
        if indices and max(indices) >= st["cursor"]:
            problems.append({"kind": "beyond_cursor", "index": max(indices), "cursor": st["cursor"]})
        # every list position below the cursor has a candidate document or was skipped as removed
        if len(indices) != checked or len(indices) + st.get("skipped", 0) != st["cursor"]:
            problems.append({"kind": "gap", "documents": len(indices), "skipped": st.get("skipped", 0), "cursor": st["cursor"]})
        stored, actual = self.store.transaction(self._removed_ahead)
        if stored != actual:
            problems.append({"kind": "removed_count", "stored": stored, "actual": actual})
        repaired = 0
        if repair:
            for p in problems:
                if p["kind"] == "removed_count":
                    repaired += self.store.transaction(lambda t: self._removed_ahead(t, fix=True))
                if p["kind"] != "orphan":
                    continue

                def fix(t, i=p["id"]):
                    cfg = self._cfg(t)
                    c = t.get("candidates", i)
                    q = t.get("queue", i)
                    alive = [t.get("assignments", x) for x in c.get("active", [])]
                    if q or self._evaluate(c, cfg)[0] in FINAL or any(x and x["state"] == "active" for x in alive):
                        return 0
                    t.set("queue", i, self._queue_doc(c, cfg, self.clock()))
                    return 1
                repaired += self.store.transaction(fix)
        return {"candidates_checked": checked, "cursor": st["cursor"], "problems": problems, "repaired": repaired}

    def _removed_ahead(self, t, fix: bool = False):
        """(stored, actual) count of removed candidates the cursor hasn't reached. With fix, store
        the actual count; returns 1 if that changed it."""
        st = self._state(t)
        cur = st["cursor"]
        chunks = [t.get("chunks", "%06d" % ci) for ci in range(cur // CHUNK, (st["total"] + CHUNK - 1) // CHUNK)]
        actual = sum(1 for ch in chunks if ch for j in ch.get("removed", []) if ch["start"] + j >= cur)
        stored = st.get("removed_ahead", 0)
        if not fix:
            return stored, actual
        if stored == actual:
            return 0
        st["removed_ahead"] = actual
        t.set("meta", "state", st)
        return 1

    # ================================================================== reporting

    def status(self) -> Dict[str, Any]:
        def txn(t):
            st, cfg = self._state(t), self._cfg(t)
            got = {"a_all": t.query("assignments", order_by="active_n", limit=1),
                   "a_first": t.query("assignments", order_by="first_n", limit=1),
                   "q_all": t.query("queue", order_by="priority", limit=1),
                   "q_first": t.query("queue", order_by="first_n", limit=1),
                   "owners": t.query("owners", order_by="results", descending=True, limit=10)}
            got["chunk"] = t.get("chunks", "%06d" % (st["cursor"] // CHUNK)) if st["cursor"] < st["total"] else None
            return st, cfg, got
        st, cfg, g = self.store.transaction(txn)
        now = self.clock()
        cursor_n = None
        if g["chunk"]:
            cursor_n = g["chunk"]["items"][2 * (st["cursor"] - g["chunk"]["start"]) + 1]
        end_n = st["last"][0] if st["last"] else None
        start_n = st["chunk_n"][0] if st["chunk_n"] else None

        def lowest(*xs):
            xs = [x for x in xs if x is not None]
            return min(xs) if xs else None
        tested = lowest(*(x[0]["n"] for x in (g["a_first"], g["q_first"]) if x), cursor_n)
        complete = lowest(*(x[0]["n"] for x in (g["a_all"], g["q_all"]) if x), cursor_n)
        h = int(now // 3600)
        last24 = sum(v for key, v in st["hourly"].items() if h - int(key) < 24)
        counts = {k: v for k, v in st["counts"].items() if v}
        open_ = sum(v for k, v in counts.items() if k not in FINAL)
        skipped, ahead = st.get("skipped", 0), st.get("removed_ahead", 0)
        unissued = max(0, st["total"] - st["cursor"] - ahead)
        removed = skipped + ahead + counts.get("removed", 0)
        remaining = unissued + open_
        return {
            "protocol": PROTOCOL, "now": now, "message": cfg["message"], "paused": cfg["paused"],
            # candidates: loaded minus removed (a deeper sieve found a factor)
            "candidates": st["total"] - removed, "removed": removed, "factors": st.get("factors", 0),
            "issued": st["cursor"] - skipped, "unissued": unissued,
            "counts": counts, "active_assignments": st["active"], "results": st["results"],
            "tests_last_24h": last24, "remaining": remaining, "eta_days": (remaining / last24) if last24 else None,
            "range": [start_n, end_n],
            # every candidate below these n has at least one result / is fully settled
            "tested_through_n": tested if tested is not None else end_n,
            "complete_through_n": complete if complete is not None else end_n,
            "primes": st["primes"], "top_owners": [{"name": o["name"], "results": o["results"]} for o in g["owners"]],
        }

    def worker_info(self, worker_id: str, token: str) -> Dict[str, Any]:
        def txn(t):
            w = self._auth(t, worker_id, token)
            return w, (t.get("assignments", w["assignment"]) if w.get("assignment") else None)
        w, a = self.store.transaction(txn)
        return {"worker_id": worker_id, "owner": w["owner"], "name": w["name"], "results": w.get("results", 0),
                "verified": w.get("verified", 0), "history": w.get("history", []),
                "assignment": self._public_assignment(a) if a and a["state"] == "active" else None}

    def export(self, after: int = -1, limit: int = 1000) -> Dict[str, Any]:
        rows = self.store.transaction(lambda t: t.query("candidates", [("index", ">", int(after))], order_by="index", limit=limit))
        return {"candidates": rows, "next": rows[-1]["index"] if len(rows) == limit else None}
