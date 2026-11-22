"""Client for the shared ledger (docs/LEDGER.md). Standard library only."""
from __future__ import annotations

import json
import random
import urllib.error
import urllib.request
from typing import Any, Dict, Optional

from . import VERSION


class LedgerUnavailable(Exception):
    """Network trouble, 429 or 503: try again after `retry_after` seconds."""

    def __init__(self, message: str, retry_after: float = 60):
        super().__init__(message)
        self.retry_after = retry_after


class LedgerRefused(Exception):
    """The ledger said no (bad credentials, outdated engine, policy). Retrying won't help."""

    def __init__(self, message: str, status: int, code: str = ""):
        super().__init__(message)
        self.status, self.code = status, code


class LedgerClient:
    def __init__(self, url: str, worker_id: str = "", token: str = "", timeout: float = 30):
        self.url = url.rstrip("/")
        self.worker_id, self.token = worker_id, token
        self.timeout = timeout

    def _call(self, method: str, path: str, body: Optional[Dict[str, Any]] = None, auth: bool = True) -> Dict[str, Any]:
        headers = {"Content-Type": "application/json", "User-Agent": "colbert-app/" + VERSION}
        if auth:
            headers["Authorization"] = "Bearer %s:%s" % (self.worker_id, self.token)
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(self.url + path, data=data, method=method, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as r:
                return json.loads(r.read() or b"{}")
        except urllib.error.HTTPError as e:
            try:
                info = json.loads(e.read() or b"{}")
            except ValueError:
                info = {}
            msg = info.get("error") or e.reason or "HTTP %d" % e.code
            if e.code in (429, 500, 502, 503, 504):
                ra = e.headers.get("Retry-After")
                raise LedgerUnavailable(msg, float(ra) if ra and ra.isdigit() else 30 + random.uniform(0, 30))
            raise LedgerRefused(msg, e.code, info.get("code", ""))
        except (urllib.error.URLError, OSError, ValueError) as e:
            raise LedgerUnavailable("cannot reach the ledger at %s (%s)" % (self.url, getattr(e, "reason", e)),
                                    60 + random.uniform(0, 60))

    def status(self) -> Dict[str, Any]:
        return self._call("GET", "/v1/status", auth=False)

    def register(self, owner: str, name: str, info: Dict[str, Any], invite: str = "") -> Dict[str, Any]:
        r = self._call("POST", "/v1/register", {"owner": owner, "name": name, "info": info, "invite": invite}, auth=False)
        self.worker_id, self.token = r["worker_id"], r["token"]
        return r

    def work(self, info: Dict[str, Any]) -> Dict[str, Any]:
        return self._call("POST", "/v1/work", {"info": info})

    def progress(self, assignment: str, report: Dict[str, Any]) -> Dict[str, Any]:
        return self._call("POST", "/v1/progress", {"assignment": assignment, "report": report})

    def result(self, assignment: str, result: Dict[str, Any]) -> Dict[str, Any]:
        return self._call("POST", "/v1/result", {"assignment": assignment, "result": result})

    def release(self, assignment: str) -> Dict[str, Any]:
        return self._call("POST", "/v1/release", {"assignment": assignment})

    def me(self) -> Dict[str, Any]:
        return self._call("GET", "/v1/me")
