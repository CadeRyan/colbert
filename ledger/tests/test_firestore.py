"""
The same tests as test_core.py, against Firestore (the emulator, never a real database).

    gcloud emulators firestore start --host-port=localhost:8686 &
    FIRESTORE_EMULATOR_HOST=localhost:8686 python3 -m unittest ledger.tests.test_firestore

Skipped when FIRESTORE_EMULATOR_HOST is not set or google-cloud-firestore is missing.
"""
import os
import secrets
import unittest

from ledger.tests import test_core as T

EMULATOR = os.environ.get("FIRESTORE_EMULATOR_HOST")
try:
    from ledger.store_firestore import FirestoreStore
except ImportError:                     # pragma: no cover
    FirestoreStore = None


def make_fs_store(_tmp):
    return FirestoreStore(project="colbert-test", prefix="t%s_" % secrets.token_hex(4))


@unittest.skipUnless(EMULATOR and FirestoreStore, "needs FIRESTORE_EMULATOR_HOST and google-cloud-firestore")
class FsIssuing(T.Issuing):
    store_factory = staticmethod(make_fs_store)
    test_seed_spans_chunks = None       # 5000+ sequential round trips: slow on the emulator


@unittest.skipUnless(EMULATOR and FirestoreStore, "needs FIRESTORE_EMULATOR_HOST and google-cloud-firestore")
class FsLeases(T.Leases):
    store_factory = staticmethod(make_fs_store)


@unittest.skipUnless(EMULATOR and FirestoreStore, "needs FIRESTORE_EMULATOR_HOST and google-cloud-firestore")
class FsChecking(T.Checking):
    store_factory = staticmethod(make_fs_store)


@unittest.skipUnless(EMULATOR and FirestoreStore, "needs FIRESTORE_EMULATOR_HOST and google-cloud-firestore")
class FsReviewFindings(T.ReviewFindings):
    store_factory = staticmethod(make_fs_store)


@unittest.skipUnless(EMULATOR and FirestoreStore, "needs FIRESTORE_EMULATOR_HOST and google-cloud-firestore")
class FsFrontier(T.Frontier):
    store_factory = staticmethod(make_fs_store)


@unittest.skipUnless(EMULATOR and FirestoreStore, "needs FIRESTORE_EMULATOR_HOST and google-cloud-firestore")
class FsConcurrency(T.Concurrency):
    """Real transaction conflicts and retries. Fewer threads than the SQLite run: the emulator
    serialises transactions far more coarsely than production Firestore, and even three
    threads with no pause between requests is far beyond the ledger's real load (a few
    requests per minute per thousand GPUs)."""
    store_factory = staticmethod(make_fs_store)
    THREADS, COUNT = 3, 40


if __name__ == "__main__":
    unittest.main()


@unittest.skipUnless(EMULATOR and FirestoreStore, "needs FIRESTORE_EMULATOR_HOST and google-cloud-firestore")
class FsFactoring(T.Factoring):
    store_factory = staticmethod(make_fs_store)
