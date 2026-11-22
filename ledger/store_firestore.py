"""
Firestore implementation of the store interface in store.py, for Cloud Run.

Needs `pip install google-cloud-firestore`. Credentials come from the environment: on Cloud
Run, the service account; locally, `gcloud auth application-default login`; against the
emulator, FIRESTORE_EMULATOR_HOST=localhost:8686.

All queries the ledger makes are covered by Firestore's automatic single-field indexes, so
the database needs no index configuration.
"""
from __future__ import annotations

from typing import Any, List, Optional

from google.api_core import exceptions as gexc
from google.cloud import firestore

try:                                    # google-cloud-firestore >= 2.11
    from google.cloud.firestore_v1.base_query import FieldFilter
except ImportError:                     # pragma: no cover
    FieldFilter = None

from .store import Contention, ReadAfterWrite, Store, Txn

_OPS = {"==": "==", "<": "<", "<=": "<=", ">": ">", ">=": ">=", "array_contains": "array_contains"}


class _FsTxn(Txn):
    def __init__(self, store: "FirestoreStore", txn):
        self.s, self.txn = store, txn
        self.wrote = False

    def _check(self):
        if self.wrote:
            raise ReadAfterWrite("read after write inside a transaction")

    def _ref(self, col, doc_id):
        return self.s.client.collection(self.s.prefix + col).document(doc_id)

    def get(self, col, doc_id):
        self._check()
        snap = self._ref(col, doc_id).get(transaction=self.txn)
        if not snap.exists:
            return None
        d = snap.to_dict()
        d["_id"] = snap.id
        return d

    def query(self, col, where=(), order_by=None, descending=False, limit=None) -> List[Any]:
        self._check()
        q = self.s.client.collection(self.s.prefix + col)
        for field, op, value in where:
            q = q.where(filter=FieldFilter(field, _OPS[op], value)) if FieldFilter else q.where(field, _OPS[op], value)
        if order_by:
            q = q.order_by(order_by, direction=firestore.Query.DESCENDING if descending else firestore.Query.ASCENDING)
        if limit:
            q = q.limit(int(limit))
        out = []
        for snap in q.get(transaction=self.txn):
            d = snap.to_dict()
            d["_id"] = snap.id
            out.append(d)
        return out

    def set(self, col, doc_id, doc):
        self.wrote = True
        self.txn.set(self._ref(col, doc_id), {k: v for k, v in doc.items() if k != "_id"})

    def delete(self, col, doc_id):
        self.wrote = True
        self.txn.delete(self._ref(col, doc_id))


class FirestoreStore(Store):
    def __init__(self, project: Optional[str] = None, database: str = "(default)", prefix: str = ""):
        """`prefix` is prepended to every collection name (used to isolate test runs)."""
        self.client = firestore.Client(project=project, database=database)
        self.prefix = prefix

    def transaction(self, fn):
        @firestore.transactional
        def run(txn):
            return fn(_FsTxn(self, txn))
        try:
            return run(self.client.transaction(max_attempts=10))
        except (gexc.Aborted, gexc.DeadlineExceeded, gexc.ServiceUnavailable) as e:
            raise Contention(str(e)) from e
        except ValueError as e:
            if "Failed to commit transaction" in str(e):
                raise Contention(str(e)) from e
            raise

    def close(self):
        self.client.close()
