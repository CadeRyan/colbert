"""
Tests for the ledger's guarantees (see the docstring of ledger/core.py).

    python3 -m unittest discover -s ledger/tests -t .

Runs against SqliteStore, which also enforces Firestore's reads-before-writes rule, and
against the Firestore emulator when FIRESTORE_EMULATOR_HOST is set (see test_firestore.py).
"""
import hashlib
import os
import random
import tempfile
import threading
import time
import unittest

from ledger.core import CHUNK, Ledger, LedgerError
from ledger.store import Contention, SqliteStore
from ledger import core

ENGINE = "v1.0"
CPU, GPU = "cpu (8 threads)", "opencl: Test GPU"


def truth(k, n):
    """Stand-in for the right answer: a deterministic residue per number."""
    return hashlib.sha256(b"%d:%d" % (k, n)).hexdigest()[:16]


def retrying(fn):
    """What real clients do on 503 Contention: back off with jitter and try again."""
    def wrapped(*a, **kw):
        for attempt in range(60):
            try:
                return fn(*a, **kw)
            except Contention:
                import time
                time.sleep(random.uniform(0, 0.05 * (attempt + 1)))
        return fn(*a, **kw)
    return wrapped


class Clock:
    def __init__(self):
        self.t = 1_800_000_000.0

    def __call__(self):
        return self.t

    def advance(self, s):
        self.t += s


def make_store(tmp):
    return SqliteStore(os.path.join(tmp, "ledger.sqlite"), core.INDEXES)


class Base(unittest.TestCase):
    store_factory = staticmethod(make_store)

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.clock = Clock()
        self.store = self.store_factory(self.tmp)
        self.L = Ledger(self.store, clock=self.clock, rng=random.Random(1))
        self.L.set_config({"dc_fraction": 0.0, "worker_trust_after": 0, "engine_trust_after": 0,
                          "dc_other_impl_wait_seconds": 0.0})

    def tearDown(self):
        self.store.close()

    def worker(self, owner="alice", backend=CPU, engine=ENGINE):
        r = self.L.register(owner, owner + "-pc", {"engine": engine})
        r["backend"] = backend
        r["engine"] = engine
        return r

    @retrying
    def work(self, w, **extra):
        info = {"engine": w["engine"], "backend": w["backend"]}
        info.update(extra)
        return self.L.request_work(w["worker_id"], w["token"], info)

    @retrying
    def result(self, w, a, res64=None, verdict="composite", engine=None, backend=None):
        k, n = a["k"], a["n"]
        res64 = res64 or ("0" * 16 if verdict == "PRIME" else truth(k, n))
        return self.L.submit_result(w["worker_id"], w["token"], a["id"], {
            "k": k, "n": n, "result": verdict, "res64": res64, "iterations": n - 1,
            "engine": engine or w["engine"], "backend": backend or w["backend"], "seconds": 1})

    @retrying
    def beat(self, w, a, it=100):
        return self.L.progress(w["worker_id"], w["token"], a["id"], {"iteration": it, "ms_per_iter": 1.0})

    def seed(self, count=10, n0=1000, ks=(21181, 67607)):
        pairs = [(ks[i % len(ks)], n0 + i) for i in range(count)]
        self.L.seed(pairs)
        return pairs

    def assertClean(self):
        a = self.L.audit()
        self.assertEqual(a["problems"], [], a)


class Issuing(Base):
    def test_in_order_and_idempotent(self):
        pairs = self.seed(6)
        w1, w2 = self.worker("a"), self.worker("b")
        a1 = self.work(w1)["assignment"]
        self.assertEqual((a1["k"], a1["n"]), pairs[0])
        again = self.work(w1)["assignment"]
        self.assertEqual(again["id"], a1["id"], "asking again returns the same assignment")
        a2 = self.work(w2)["assignment"]
        self.assertEqual((a2["k"], a2["n"]), pairs[1])
        self.assertClean()

    def test_seed_is_idempotent_and_appends(self):
        self.seed(10)
        self.assertEqual(self.L.seed([(21181, 1000 + i) for i in range(10)])["added"], 0)
        self.assertEqual(self.L.seed([(21181, 5000), (21181, 5001)])["added"], 2)
        self.assertEqual(self.L.status()["candidates"], 12)

    def test_seed_spans_chunks(self):
        pairs = [(3, 400 + i) for i in range(CHUNK + 7)]
        self.assertEqual(self.L.seed(pairs)["added"], CHUNK + 7)
        w = self.worker()
        seen = []
        for _ in range(CHUNK + 7):
            a = self.work(w)["assignment"]
            seen.append((a["k"], a["n"]))
            self.result(w, a)
        self.assertEqual(seen, sorted(pairs, key=lambda p: (p[1], p[0])))
        self.assertEqual(self.work(w)["reason"], "exhausted")
        self.assertClean()

    def test_not_started(self):
        w = self.worker()
        self.assertEqual(self.work(w)["reason"], "not_started")

    def test_exhausted(self):
        self.seed(1)
        w = self.worker()
        self.result(w, self.work(w)["assignment"])
        r = self.work(w)
        self.assertIsNone(r["assignment"])
        self.assertEqual(r["reason"], "exhausted")

    def test_paused_and_blocked_engines(self):
        self.seed(3)
        w = self.worker()
        self.L.set_config({"paused": True})
        self.assertEqual(self.work(w)["reason"], "paused")
        self.L.set_config({"paused": False, "blocked_engines": [ENGINE]})
        with self.assertRaises(LedgerError) as e:
            self.work(w)
        self.assertEqual(e.exception.status, 426)
        self.L.set_config({"blocked_engines": [], "accept_dirty_engines": False})
        with self.assertRaises(LedgerError):
            self.work(w, engine="abc123-dirty")

    def test_too_slow(self):
        self.seed(1, n0=48_000_000)
        self.L.set_config({"max_projected_days": 30.0})
        w = self.worker()
        with self.assertRaises(LedgerError) as e:
            self.work(w, ms_per_iter=200.0)       # about 111 days
        self.assertEqual(e.exception.code, "too_slow")
        self.assertIsNotNone(self.work(w, ms_per_iter=5.0)["assignment"])

    def test_auth_and_registration(self):
        with self.assertRaises(LedgerError):
            self.L.request_work("wnope", "x", {"engine": ENGINE})
        w = self.worker()
        with self.assertRaises(LedgerError):
            self.L.request_work(w["worker_id"], "wrong", {"engine": ENGINE})
        self.L.set_config({"registration": "invite", "invite_code": "s3cret"})
        with self.assertRaises(LedgerError):
            self.L.register("eve", "pc", {})
        self.assertTrue(self.L.register("bob", "pc", {}, invite="s3cret")["token"])
        self.L.set_config({"registration": "closed"})
        with self.assertRaises(LedgerError):
            self.L.register("bob", "pc", {}, invite="s3cret")

    def test_result_validation(self):
        self.seed(2)
        w = self.worker()
        a = self.work(w)["assignment"]
        base = {"k": a["k"], "n": a["n"], "result": "composite", "res64": truth(a["k"], a["n"]),
                "iterations": a["n"] - 1, "engine": ENGINE, "backend": CPU}
        for bad in ({"iterations": 5}, {"res64": "xyz"}, {"result": "maybe"}, {"result": "PRIME"},
                    {"n": a["n"] + 1}, {"engine": ""}):
            r = dict(base)
            r.update(bad)
            with self.assertRaises(LedgerError, msg=str(bad)):
                self.L.submit_result(w["worker_id"], w["token"], a["id"], r)
        first = self.L.submit_result(w["worker_id"], w["token"], a["id"], base)
        again = self.L.submit_result(w["worker_id"], w["token"], a["id"], base)
        self.assertTrue(first["accepted"] and again.get("duplicate"))
        self.assertEqual(self.L.status()["results"], 1)


class Leases(Base):
    def test_heartbeat_keeps_lease(self):
        self.seed(3)
        self.L.set_config({"lease_seconds": 100})
        w1, w2 = self.worker("a"), self.worker("b")
        a = self.work(w1)["assignment"]
        for _ in range(5):
            self.clock.advance(60)
            self.assertEqual(self.beat(w1, a)["action"], "continue")
        b = self.work(w2)["assignment"]
        self.assertNotEqual((a["k"], a["n"]), (b["k"], b["n"]))

    def test_expired_lease_is_reissued_and_late_result_accepted(self):
        pairs = self.seed(3)
        self.L.set_config({"lease_seconds": 100})
        w1, w2 = self.worker("a"), self.worker("b")
        a = self.work(w1)["assignment"]
        self.clock.advance(101)
        b = self.work(w2)["assignment"]
        self.assertEqual((b["k"], b["n"]), pairs[0], "the expired candidate is reissued first")
        self.assertClean()
        # the first worker comes back and finishes anyway: its result counts
        self.assertEqual(self.result(w1, a)["status"], "done")
        self.assertEqual(self.beat(w2, b)["action"], "abandon", "no longer needed")
        self.assertClean()

    def test_late_result_becomes_double_check(self):
        self.seed(2)
        self.L.set_config({"lease_seconds": 100, "worker_trust_after": 5})
        w1, w2 = self.worker("a"), self.worker("b")
        a = self.work(w1)["assignment"]
        self.clock.advance(101)
        b = self.work(w2)["assignment"]
        self.assertEqual(self.result(w1, a)["status"], "awaiting_dc")
        self.assertEqual(self.beat(w2, b)["action"], "continue", "the reissue now serves as the check")
        self.assertEqual(self.result(w2, b)["status"], "verified")
        self.assertClean()

    def test_returning_worker_reclaims_queued_work(self):
        pairs = self.seed(4)
        self.L.set_config({"lease_seconds": 100})
        w1, w2, w3 = self.worker("a"), self.worker("b"), self.worker("c")
        a1, a2 = self.work(w1)["assignment"], self.work(w2)["assignment"]
        self.clock.advance(101)
        got = self.work(w3)["assignment"]             # expires both; takes the lower one
        self.assertEqual((got["k"], got["n"]), pairs[0])
        # w2 returns before anyone takes its queued candidate: it gets it back
        self.assertEqual(self.beat(w2, a2)["action"], "continue")
        self.assertClean()
        w4 = self.worker("d")
        nxt = self.work(w4)["assignment"]
        self.assertEqual((nxt["k"], nxt["n"]), pairs[2], "pairs[1] is w2's again, not reissued")
        self.assertEqual(self.beat(w1, a1)["action"], "continue", "w1 may still finish pairs[0]")
        self.assertClean()

    def test_release_requeues(self):
        pairs = self.seed(3)
        w1, w2 = self.worker("a"), self.worker("b")
        a = self.work(w1)["assignment"]
        self.assertTrue(self.L.release(w1["worker_id"], w1["token"], a["id"])["released"])
        b = self.work(w2)["assignment"]
        self.assertEqual((b["k"], b["n"]), pairs[0])
        self.assertEqual(self.beat(w1, a)["action"], "abandon")
        self.assertClean()


class Checking(Base):
    def test_untrusted_worker_is_double_checked_by_someone_else(self):
        self.seed(3)
        self.L.set_config({"worker_trust_after": 1})
        w1, w2 = self.worker("a"), self.worker("b")
        a = self.work(w1)["assignment"]
        self.assertEqual(self.result(w1, a)["status"], "awaiting_dc")
        other = self.work(w1)["assignment"]
        self.assertNotEqual((other["k"], other["n"]), (a["k"], a["n"]), "never your own double check")
        dc = self.work(w2)["assignment"]
        self.assertEqual(((dc["k"], dc["n"]), dc["kind"]), ((a["k"], a["n"]), "dc"))
        self.assertEqual(self.result(w2, dc)["status"], "verified")
        self.assertEqual(self.L.worker_info(w1["worker_id"], w1["token"])["verified"], 1)
        self.assertClean()

    def test_trusted_worker_not_rechecked(self):
        self.seed(10)
        self.L.set_config({"worker_trust_after": 1})
        w1, w2 = self.worker("a"), self.worker("b")
        a = self.work(w1)["assignment"]
        self.result(w1, a)
        self.result(w2, self.work(w2)["assignment"])          # w2 checks w1
        self.result(w1, self.work(w1)["assignment"])          # w1's next result is not checked... (w1 is now trusted)
        st = self.L.status()["counts"]
        self.assertEqual(st.get("verified"), 1)
        self.assertEqual(st.get("done"), 1)

    def test_prime_is_always_double_checked(self):
        self.seed(2)
        w1, w2 = self.worker("a"), self.worker("b")
        a = self.work(w1)["assignment"]
        r = self.result(w1, a, verdict="PRIME")
        self.assertEqual(r["status"], "awaiting_dc")
        self.assertEqual(self.L.status()["primes"][0]["status"], "awaiting_dc")
        dc = self.work(w2)["assignment"]
        self.assertEqual(self.result(w2, dc, verdict="PRIME")["status"], "verified")
        self.assertEqual(self.L.status()["primes"][0]["status"], "verified")

    def test_mismatch_goes_to_tiebreak(self):
        self.seed(2)
        self.L.set_config({"worker_trust_after": 1})
        good1, bad, good2 = self.worker("a"), self.worker("b"), self.worker("c")
        a = self.work(bad)["assignment"]
        self.result(bad, a, res64="deadbeefdeadbeef")
        dc = self.work(good1)["assignment"]
        self.assertEqual(self.result(good1, dc)["status"], "conflict")
        tb = self.work(bad)["assignment"]
        self.assertNotEqual((tb["k"], tb["n"]), (a["k"], a["n"]), "a party to the conflict can't break the tie")
        tie = self.work(good2)["assignment"]
        self.assertEqual(((tie["k"], tie["n"]), tie["kind"]), ((a["k"], a["n"]), "tiebreak"))
        self.assertEqual(self.result(good2, tie)["status"], "verified")
        self.assertEqual(self.L.worker_info(bad["worker_id"], bad["token"])["verified"], 0)
        self.assertClean()

    def test_engine_trust_needs_a_different_implementation(self):
        self.seed(2)
        self.L.set_config({"engine_trust_after": 1, "dc_other_impl_wait_seconds": 0.0})
        g1, g2, c1 = self.worker("a", GPU), self.worker("b", GPU), self.worker("c", CPU)
        engine = lambda: self.store.transaction(lambda t: t.get("engines", ENGINE))
        # two GPU workers on the same build agree: the candidate settles, the build earns nothing
        a = self.work(g1)["assignment"]
        self.assertEqual(self.result(g1, a)["status"], "awaiting_dc")
        dc = self.work(g2)["assignment"]
        self.assertEqual(dc["kind"], "dc")
        self.assertEqual(self.result(g2, dc)["status"], "verified")
        self.assertEqual(engine()["verified"], 0)
        # a CPU result agreeing with a GPU one is evidence about the build itself
        b = self.work(g1)["assignment"]
        self.result(g1, b)
        dc = self.work(c1)["assignment"]
        self.assertEqual(self.result(c1, dc)["status"], "verified")
        self.assertEqual(engine()["verified"], 1)

    def test_double_check_prefers_another_implementation(self):
        self.seed(4)
        self.L.set_config({"engine_trust_after": 1, "dc_other_impl_wait_seconds": 3600.0})
        g1, g2, g3, c1 = self.worker("a", GPU), self.worker("b", GPU), self.worker("d", GPU), self.worker("c", CPU)
        a = self.work(g1)["assignment"]
        self.result(g1, a)
        nxt = self.work(g2)["assignment"]
        self.assertEqual(nxt["kind"], "first", "same implementation: fresh work instead")
        dc = self.work(c1)["assignment"]
        self.assertEqual((dc["kind"], dc["n"]), ("dc", a["n"]), "a different backend takes the check")
        # with nobody else around, a check that has waited long enough goes to anyone
        b = self.work(g3)["assignment"]
        self.result(g3, b)
        self.clock.advance(3601)
        self.result(g2, nxt)
        late = self.work(g2)["assignment"]
        self.assertEqual((late["kind"], late["n"]), ("dc", b["n"]))

    def test_invalidate_engine(self):
        self.seed(4)
        w1, w2 = self.worker("a", engine="bad1"), self.worker("b", engine="good1")
        a = self.work(w1)["assignment"]
        self.assertEqual(self.result(w1, a)["status"], "done")
        out = self.L.invalidate_engine("bad1")
        self.assertEqual(out["candidates_requeued"], 1)
        with self.assertRaises(LedgerError):
            self.work(w1)
        again = self.work(w2)["assignment"]
        self.assertEqual((again["k"], again["n"]), (a["k"], a["n"]), "retested first")
        self.assertEqual(self.result(w2, again)["status"], "done")
        self.assertClean()

    def test_remove(self):
        pairs = self.seed(6)
        w = self.worker()
        a = self.work(w)["assignment"]
        self.assertEqual(self.L.remove([pairs[0], pairs[2]])["removed"], 2)
        self.assertEqual(self.beat(w, a)["action"], "abandon")
        got = []
        while True:
            r = self.work(w)
            if r.get("reason") == "exhausted":
                break
            if r["assignment"]:
                got.append((r["assignment"]["k"], r["assignment"]["n"]))
                self.result(w, r["assignment"])
        self.assertEqual(got, [pairs[1], pairs[3], pairs[4], pairs[5]])
        self.assertClean()

    def test_remove_ahead_of_the_cursor_counts(self):
        pairs = self.seed(8)
        w = self.worker()
        a = self.work(w)["assignment"]                      # pairs[0] issued
        self.assertEqual(self.L.remove([pairs[3], pairs[5], pairs[6]])["removed"], 3)
        self.assertEqual(self.L.remove([pairs[3]])["removed"], 0, "removing twice is harmless")
        s = self.L.status()
        self.assertEqual((s["candidates"], s["removed"], s["issued"], s["unissued"], s["remaining"]), (5, 3, 1, 4, 5))
        self.assertClean()
        self.result(w, a)
        while True:                                         # the cursor passes all three
            r = self.work(w)
            if r.get("reason") == "exhausted":
                break
            if r["assignment"]:
                self.result(w, r["assignment"])
        s = self.L.status()
        self.assertEqual((s["candidates"], s["removed"], s["issued"], s["unissued"], s["remaining"]), (5, 3, 5, 0, 0))
        self.assertEqual(s["counts"].get("done"), 5)
        self.assertClean()

    def test_audit_repairs_the_removed_count(self):
        pairs = self.seed(6)
        self.L.remove([pairs[2], pairs[4]])
        def forget(t):                                      # a ledger written before the count existed
            st = self.L._state(t)
            st.pop("removed_ahead")
            t.set("meta", "state", st)
        self.L.store.transaction(forget)
        self.assertEqual(self.L.status()["candidates"], 6)
        a = self.L.audit()
        self.assertEqual(a["problems"], [{"kind": "removed_count", "stored": 0, "actual": 2}])
        self.assertEqual(self.L.audit(repair=True)["repaired"], 1)
        self.assertEqual(self.L.status()["candidates"], 4)
        self.assertClean()


class Factoring(Base):
    """P-1 factors: checked by the ledger itself, final, and no double check needed."""

    @retrying
    def factor(self, w, a, f, **extra):
        r = {"k": a["k"], "n": a["n"], "factor": str(f), "b1": 500000, "b2": 25000000, "stage": 1,
             "engine": w["engine"], "backend": w["backend"], "seconds": 1}
        r.update(extra)
        return self.L.submit_result(w["worker_id"], w["token"], a["id"], r)

    def test_factor_settles_the_candidate(self):
        pairs = self.seed(4, n0=1001)                      # 21181*2^1001+1 is divisible by 3
        w = self.worker()
        a = self.work(w)["assignment"]
        self.assertEqual((a["k"], a["n"]), pairs[0])
        out = self.factor(w, a, 3)
        self.assertEqual(out["status"], "factored")
        self.assertFalse(out["double_check"])
        s = self.L.status()
        self.assertEqual((s["counts"].get("factored"), s["factors"], s["remaining"]), (1, 1, 3))
        nxt = self.work(w)["assignment"]
        self.assertNotEqual((nxt["k"], nxt["n"]), pairs[0], "a factored number is never issued again")
        self.assertClean()

    def test_a_non_factor_is_refused(self):
        self.seed(2, n0=1001)
        w = self.worker()
        a = self.work(w)["assignment"]
        with self.assertRaises(LedgerError) as cm:
            self.factor(w, a, 5)
        self.assertEqual(cm.exception.code, "not_a_factor")
        for bad in ("0", "1", "-3", "abc", "03"):
            with self.assertRaises(LedgerError):
                self.factor(w, a, bad)
        self.assertEqual(self.beat(w, a)["action"], "continue", "the assignment is still live")
        self.assertClean()

    def test_factor_ends_a_pending_double_check(self):
        self.L.set_config({"dc_fraction": 1.0})
        self.seed(2, n0=1001)
        w1, w2 = self.worker("alice"), self.worker("bob")
        a = self.work(w1)["assignment"]
        self.assertEqual(self.result(w1, a)["status"], "awaiting_dc")
        b = self.work(w2)["assignment"]
        self.assertEqual((b["kind"], b["k"], b["n"]), ("dc", a["k"], a["n"]))
        self.assertEqual(self.factor(w2, b, 3)["status"], "factored")
        self.assertEqual(self.L.status()["counts"].get("awaiting_dc", 0), 0)
        self.assertClean()

    def test_factor_check_never_builds_the_number(self):
        # 3 divides 2^n+1 for every odd n; at n = 2^31-1, building P to compare would take 256 MiB
        t0 = time.time()
        self.assertEqual(Ledger._validate_factor({"k": 1, "n": 2 ** 31 - 1, "factor": "3"})["factor"], "3")
        self.assertLess(time.time() - t0, 1.0)
        p = 3 * 2 ** 300 + 1                                # the number itself is not a proper factor
        with self.assertRaises(LedgerError) as cm:
            Ledger._validate_factor({"k": 3, "n": 300, "factor": str(p)})
        self.assertEqual(cm.exception.code, "not_a_factor")

    def test_factor_is_checked_only_for_a_known_worker(self):
        self.seed(2, n0=1001)
        huge = {"k": 1, "n": 2 ** 31 - 1, "factor": "3"}
        with self.assertRaises(LedgerError) as cm:
            self.L.submit_result("wnobody", "wrong", "a0", huge)
        self.assertEqual((cm.exception.status, cm.exception.code), (401, "unauthorized"))
        w = self.worker()
        a = self.work(w)["assignment"]
        with self.assertRaises(LedgerError) as cm:            # a valid factor of another number
            self.L.submit_result(w["worker_id"], w["token"], a["id"], huge)
        self.assertEqual(cm.exception.status, 400)
        self.assertClean()

    def test_factor_refutes_a_reported_prime(self):
        self.seed(2, n0=1001)
        w1, w2 = self.worker("alice"), self.worker("bob")
        a = self.work(w1)["assignment"]
        self.result(w1, a, verdict="PRIME")
        self.assertEqual(self.L.status()["primes"][0]["status"], "awaiting_dc")
        b = self.work(w2)["assignment"]
        self.factor(w2, b, 3)
        self.assertEqual(self.L.status()["primes"][0]["status"], "refuted")
        self.assertClean()

    def test_pm1_without_a_factor_is_remembered(self):
        pairs = self.seed(2, n0=1001)
        w1, w2 = self.worker("alice"), self.worker("bob")
        a = self.work(w1)["assignment"]
        self.assertNotIn("pm1_done", a)
        r = self.L.progress(w1["worker_id"], w1["token"], a["id"], {"iteration": 0, "phase": "pm1", "pm1": {"b1": 1000, "b2": 30000}})
        self.assertEqual(r["action"], "continue")
        self.L.progress(w1["worker_id"], w1["token"], a["id"], {"pm1": {"b1": 500, "b2": 600}})   # smaller: ignored
        self.L.release(w1["worker_id"], w1["token"], a["id"])
        b = self.work(w2)["assignment"]
        self.assertEqual((b["k"], b["n"]), pairs[0])
        self.assertEqual(b["pm1_done"], {"b1": 1000, "b2": 30000})
        with self.assertRaises(LedgerError):
            self.L.progress(w2["worker_id"], w2["token"], b["id"], {"pm1": {"b1": "x"}})
        self.assertClean()

    def test_config_tells_clients_about_pm1(self):
        self.seed(1)
        w = self.worker()
        cfg = self.work(w)["config"]
        self.assertEqual((cfg["pm1"], cfg["sieve_bits"]), (True, 32.0))

class ReviewFindings(Base):
    """Regression tests for problems found in review."""

    def test_refuted_prime_is_not_shown_as_verified(self):
        self.seed(2)
        a1, a2, a3 = self.worker("a"), self.worker("b"), self.worker("c")
        x = self.work(a1)["assignment"]
        self.result(a1, x, verdict="PRIME")
        y = self.work(a2)["assignment"]
        self.assertEqual(self.result(a2, y)["status"], "conflict")
        z = self.work(a3)["assignment"]
        self.assertEqual(self.result(a3, z)["status"], "verified")
        self.assertEqual(self.L.status()["primes"][0]["status"], "refuted")

    def test_withdrawn_build_in_flight(self):
        self.seed(3)
        bad, good = self.worker("a", engine="bad1"), self.worker("b", engine="good1")
        a = self.work(bad)["assignment"]
        self.L.invalidate_engine("bad1")
        r = self.beat(bad, a)
        self.assertEqual(r["action"], "abandon")
        again = self.work(good)["assignment"]
        self.assertEqual((again["k"], again["n"]), (a["k"], a["n"]), "back in the pool at once")
        # a result that arrives anyway is kept but counts for nothing
        out = self.result(bad, a)
        self.assertNotEqual(out["status"], "done")
        self.assertEqual(self.result(good, again)["status"], "done")
        self.assertClean()

    def test_one_owner_cannot_outvote_an_independent_result(self):
        self.seed(2)
        self.L.set_config({"lease_seconds": 100, "worker_trust_after": 1})
        a1, a2, b = self.worker("alice"), self.worker("alice"), self.worker("bob")
        x = self.work(a1)["assignment"]
        self.clock.advance(101)
        y = self.work(a2)["assignment"]                      # alice's second machine gets it
        self.assertEqual((y["k"], y["n"]), (x["k"], x["n"]))
        self.result(a2, y, res64="1111111111111111")
        dc = self.work(b)["assignment"]
        self.assertEqual(self.result(b, dc)["status"], "conflict")
        # alice's first machine comes back with the same wrong residue: still a conflict
        self.assertEqual(self.result(a1, x, res64="1111111111111111")["status"], "conflict")
        self.assertClean()

    def test_even_split_is_not_settled(self):
        """Late results can produce 2 against 2; that settles nothing."""
        cfg = self.L.get_config()
        r = lambda w, o, x: {"worker": w, "owner": o, "result": "composite", "res64": x}
        c = {"k": 3, "n": 1000, "results": [r("w1", "a", "1" * 16), r("w2", "b", "2" * 16),
                                             r("w3", "c", "1" * 16), r("w4", "d", "2" * 16)]}
        self.assertEqual(Ledger._evaluate(c, cfg)[0], "conflict")
        c["results"].append(r("w5", "e", "1" * 16))
        self.assertEqual(Ledger._evaluate(c, cfg)[0], "verified")

    def test_invalidation_rewrites_the_queue_entry(self):
        self.seed(3)
        self.L.set_config({"worker_trust_after": 1})
        bad, other = self.worker("a", engine="bad1"), self.worker("b", engine="good1")
        a = self.work(bad)["assignment"]
        self.result(bad, a)                                  # awaiting a check, queued as "dc"
        self.L.invalidate_engine("bad1")
        q = self.store.transaction(lambda t: t.get("queue", "%d_%d" % (a["k"], a["n"])))
        self.assertEqual(q["kind"], "first")
        self.assertEqual(self.L.status()["tested_through_n"], a["n"])
        self.assertClean()


class Frontier(Base):
    def test_status_frontiers(self):
        pairs = self.seed(5)
        self.L.set_config({"worker_trust_after": 1})
        w1, w2 = self.worker("a"), self.worker("b")
        a = self.work(w1)["assignment"]
        b = self.work(w2)["assignment"]
        self.result(w2, b)                                    # pairs[1] tested, needs a check
        s = self.L.status()
        self.assertEqual(s["tested_through_n"], pairs[0][1])
        self.result(w1, a)
        s = self.L.status()
        self.assertEqual(s["tested_through_n"], pairs[2][1])
        self.assertEqual(s["complete_through_n"], pairs[0][1])
        self.assertEqual(s["tests_last_24h"], 2)


class Concurrency(Base):
    THREADS, COUNT = 8, 120

    def test_many_workers_no_duplicates_no_gaps(self):
        """Many threads, short leases, some workers vanish mid-test, one is faulty."""
        count = self.COUNT
        pairs = self.seed(count, n0=2000)
        self.L.set_config({"lease_seconds": 30, "worker_trust_after": 1, "dc_fraction": 0.2,
                           "dc_other_impl_wait_seconds": 1e9})
        lock = threading.Lock()
        firsts = {}
        errors = []

        def run(idx):
            try:
                w = self.worker("owner%d" % idx, GPU if idx % 2 else CPU)
                rng = random.Random(idx)
                while True:
                    r = self.work(w)
                    a = r["assignment"]
                    if not a:
                        if r["reason"] in ("exhausted", "waiting"):
                            return
                        continue
                    if a["kind"] == "first":
                        with lock:
                            firsts.setdefault((a["k"], a["n"]), []).append(a["id"])
                    if rng.random() < 0.15:
                        # vanish: make a fresh identity; the old lease must expire and be reissued
                        with lock:
                            self.clock.advance(31)
                        w = self.worker("owner%d" % idx, w["backend"])
                        continue
                    faulty = idx == 3 and rng.random() < 0.5
                    self.result(w, a, res64="0123456789abcdef" if faulty else None)
            except Exception as e:          # pragma: no cover
                errors.append(repr(e))

        threads = [threading.Thread(target=run, args=(i,)) for i in range(self.THREADS)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(errors, [])
        # drain: tie-breaks and checks left behind by vanished workers
        finisher = [self.worker("fin%d" % i, b) for i, b in enumerate((CPU, GPU, CPU, GPU))]
        for _ in range(500):
            self.clock.advance(31)
            busy = False
            for w in finisher:
                r = self.work(w)
                if r["assignment"]:
                    busy = True
                    self.result(w, r["assignment"])
            if not busy and self.L.status()["remaining"] == 0:
                break
        s = self.L.status()
        self.assertEqual(s["remaining"], 0, s)
        self.assertEqual(sum(s["counts"].get(x, 0) for x in ("done", "verified")), count, s["counts"])
        self.assertClean()
        # every candidate was issued as a first test; reissues happened only after an expiry
        self.assertEqual(set(firsts), set(pairs))
        rows = self.L.export(limit=10_000)["candidates"]
        for c in rows:
            ok = [r for r in c["results"] if r["res64"] == truth(c["k"], c["n"])]
            if c["status"] == "verified":
                self.assertGreaterEqual(len({r["worker"] for r in ok}), 2, c)
        wrong_settled = [c for c in rows if c["status"] == "verified" and
                         not any(r["res64"] == truth(c["k"], c["n"]) for r in c["results"])]
        self.assertEqual(wrong_settled, [])


if __name__ == "__main__":
    unittest.main()
