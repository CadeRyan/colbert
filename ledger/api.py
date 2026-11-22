"""
HTTP interface of the ledger (protocol in docs/LEDGER.md). A plain WSGI application:

    python3 -m ledger serve --db ledger.sqlite          # local, standard library only
    gunicorn --threads 8 'ledger.api:create_app()'      # Cloud Run (see ledger/Dockerfile)

Configuration (environment):
    LEDGER_STORE        sqlite:PATH (default sqlite:ledger.sqlite) | firestore | firestore:PROJECT
    LEDGER_ADMIN_TOKEN  secret for /v1/admin/*; admin endpoints are disabled when unset
    LEDGER_PROXY_HOPS   proxies in front that append to X-Forwarded-For (default 1 on Cloud Run,
                        0 elsewhere: the connection's own address is used)
"""
from __future__ import annotations

import hmac
import html
import json
import os
import random
import sys
import threading
import time
import traceback
from typing import Any, Callable, Dict, Optional, Tuple

from . import core
from .core import Ledger, LedgerError
from .store import Contention, SqliteStore

MAX_BODY = 1 << 20
MAX_ADMIN_BODY = 32 << 20
STATUS_TTL = 30.0              # seconds; status costs several reads, so it is cached per instance


def open_store(spec: str):
    if spec.startswith("firestore"):
        from .store_firestore import FirestoreStore
        project = spec.split(":", 1)[1] if ":" in spec else None
        return FirestoreStore(project=project or None)
    path = spec.split(":", 1)[1] if spec.startswith("sqlite:") else spec
    return SqliteStore(path, core.INDEXES)


class RateLimit:
    """Per-key token bucket, per process. Enough to stop a runaway client."""

    def __init__(self, per_minute: float, burst: int):
        self.rate, self.burst = per_minute / 60.0, burst
        self.buckets: Dict[str, Tuple[float, float]] = {}
        self.lock = threading.Lock()

    def allow(self, key: str) -> bool:
        now = time.monotonic()
        with self.lock:
            tokens, last = self.buckets.get(key, (self.burst, now))
            tokens = min(self.burst, tokens + (now - last) * self.rate)
            if tokens < 1:
                self.buckets[key] = (tokens, now)
                return False
            self.buckets[key] = (tokens - 1, now)
            if len(self.buckets) > 100_000:
                self.buckets.clear()
            return True


def _proxy_hops() -> int:
    v = (os.environ.get("LEDGER_PROXY_HOPS") or "").strip()
    if v.isdigit():
        return int(v)
    return 1 if os.environ.get("K_SERVICE") else 0       # K_SERVICE is set on Cloud Run


class App:
    def __init__(self, ledger: Ledger, admin_token: Optional[str] = None, log=sys.stdout,
                 proxy_hops: Optional[int] = None):
        self.L = ledger
        self.admin_token = admin_token or ""
        self.log = log
        self.proxy_hops = _proxy_hops() if proxy_hops is None else proxy_hops
        self.status_cache: Tuple[float, Optional[Dict[str, Any]]] = (0.0, None)
        self.status_lock = threading.Lock()
        self.per_worker = RateLimit(per_minute=30, burst=20)
        self.per_ip_register = RateLimit(per_minute=0.5, burst=10)
        self.routes: Dict[Tuple[str, str], Callable] = {
            ("GET", "/"): self.page,
            ("GET", "/healthz"): lambda req: (200, {"ok": True}),
            ("GET", "/v1/status"): lambda req: (200, self.status()),
            ("POST", "/v1/register"): self.register,
            ("POST", "/v1/work"): self.work,
            ("POST", "/v1/progress"): self.progress,
            ("POST", "/v1/result"): self.result,
            ("POST", "/v1/release"): self.release,
            ("GET", "/v1/me"): self.me,
            ("GET", "/v1/admin/config"): self.admin(lambda req: self.L.get_config()),
            ("POST", "/v1/admin/config"): self.admin(lambda req: self.L.set_config(req["body"])),
            ("POST", "/v1/admin/seed"): self.admin(lambda req: self.L.seed(_pairs(req["body"]))),
            ("POST", "/v1/admin/remove"): self.admin(lambda req: self.L.remove(_pairs(req["body"]), req["body"].get("reason", "removed"))),
            ("POST", "/v1/admin/invalidate"): self.admin(lambda req: self.L.invalidate_engine(str(req["body"]["engine"]))),
            ("POST", "/v1/admin/audit"): self.admin(lambda req: self.L.audit(repair=bool(req["body"].get("repair")))),
            ("GET", "/v1/admin/export"): self.admin(lambda req: self.L.export(int(req["query"].get("after", -1)),
                                                                              min(5000, int(req["query"].get("limit", 1000))))),
        }

    # ---------------------------------------------------------------- plumbing

    def __call__(self, environ, start_response):
        t0 = time.time()
        method, path = environ["REQUEST_METHOD"], environ.get("PATH_INFO", "/") or "/"
        status, body, headers = 500, {"error": "internal error"}, []
        try:
            handler = self.routes.get((method, path))
            if handler is None:
                status, body = (405, {"error": "method not allowed"}) if any(p == path for _, p in self.routes) else (404, {"error": "not found"})
            else:
                req = self._request(environ, path)
                out = handler(req)
                status, body = out[0], out[1]
                if len(out) > 2:
                    headers = out[2]
        except LedgerError as e:
            status, body = e.status, {"error": str(e), "code": e.code}
        except Contention:
            status, body = 503, {"error": "busy, retry shortly", "code": "contention"}
            headers = [("Retry-After", str(random.randint(2, 10)))]
        except _BadRequest as e:
            status, body = 400, {"error": str(e), "code": "bad_request"}
        except Exception:
            traceback.print_exc(file=sys.stderr)
            status, body = 500, {"error": "internal error", "code": "internal"}
        if isinstance(body, (bytes, str)):
            data = body.encode() if isinstance(body, str) else body
            ctype = "text/html; charset=utf-8"
        else:
            data = json.dumps(body, separators=(",", ":")).encode()
            ctype = "application/json"
        headers = [("Content-Type", ctype), ("Content-Length", str(len(data))), ("Cache-Control", "no-store"),
                   ("X-Content-Type-Options", "nosniff")] + headers
        if path == "/v1/status":
            headers.append(("Access-Control-Allow-Origin", "*"))
        start_response("%d %s" % (status, _REASON.get(status, "")), headers)
        self._log(method, path, status, time.time() - t0, environ)
        return [data]

    def _log(self, method, path, status, dt, environ):
        if path == "/healthz":
            return
        print(json.dumps({"severity": "ERROR" if status >= 500 else "WARNING" if status >= 400 else "INFO",
                          "message": "%s %s %d %.0fms" % (method, path, status, dt * 1000)}), file=self.log, flush=True)

    def _request(self, environ, path) -> Dict[str, Any]:
        q = {}
        for part in (environ.get("QUERY_STRING") or "").split("&"):
            if "=" in part:
                k, v = part.split("=", 1)
                q[k] = v
        body: Any = {}
        if environ["REQUEST_METHOD"] == "POST":
            try:
                n = int(environ.get("CONTENT_LENGTH") or 0)
            except ValueError:
                n = 0
            limit = MAX_ADMIN_BODY if path.startswith("/v1/admin/") else MAX_BODY
            if n > limit:
                raise LedgerError("request too large", 413, "too_large")
            raw = environ["wsgi.input"].read(n) if n else b""
            try:
                body = json.loads(raw or b"{}")
            except ValueError:
                raise _BadRequest("body must be JSON")
            if not isinstance(body, dict):
                raise _BadRequest("body must be a JSON object")
        auth = environ.get("HTTP_AUTHORIZATION", "")
        return {"body": body, "query": q, "auth": auth[7:] if auth.startswith("Bearer ") else "", "ip": self._client_ip(environ)}

    def _client_ip(self, environ) -> str:
        """The address the registration limit counts. A client can put anything in
        X-Forwarded-For; each trusted proxy then appends the address it saw. So the client is
        the entry proxy_hops from the end (on Cloud Run, the last one), never the first."""
        if self.proxy_hops:
            xff = [p.strip() for p in environ.get("HTTP_X_FORWARDED_FOR", "").split(",") if p.strip()]
            if len(xff) >= self.proxy_hops:
                return xff[-self.proxy_hops]
        return environ.get("REMOTE_ADDR", "")

    def _worker(self, req) -> Tuple[str, str]:
        wid, _, token = req["auth"].partition(":")
        if not wid or not token:
            raise LedgerError("missing credentials (Authorization: Bearer WORKER_ID:TOKEN)", 401, "unauthorized")
        if not self.per_worker.allow(wid):
            raise LedgerError("too many requests", 429, "rate_limited")
        return wid, token

    def admin(self, fn):
        def handler(req):
            who, _, token = req["auth"].partition(":")
            if not self.admin_token:
                raise LedgerError("admin interface disabled (LEDGER_ADMIN_TOKEN not set)", 403, "forbidden")
            if who != "admin" or not hmac.compare_digest(token, self.admin_token):
                raise LedgerError("admin credentials required", 401, "unauthorized")
            if req["body"] is None:
                req["body"] = {}
            return 200, fn(req)
        return handler

    # ---------------------------------------------------------------- endpoints

    def status(self) -> Dict[str, Any]:
        now = time.time()
        with self.status_lock:
            at, cached = self.status_cache
            if cached is not None and now - at < STATUS_TTL:
                return cached
        s = self.L.status()
        with self.status_lock:
            self.status_cache = (now, s)
        return s

    def register(self, req):
        if not self.per_ip_register.allow(req["ip"]):
            raise LedgerError("too many registrations from this address", 429, "rate_limited")
        b = req["body"]
        return 200, self.L.register(str(b.get("owner", "")), str(b.get("name", "")), b.get("info") or {}, str(b.get("invite", "")))

    def work(self, req):
        wid, tok = self._worker(req)
        return 200, self.L.request_work(wid, tok, req["body"].get("info") or {})

    def progress(self, req):
        wid, tok = self._worker(req)
        b = req["body"]
        return 200, self.L.progress(wid, tok, str(b.get("assignment", "")), b.get("report") or {})

    def result(self, req):
        wid, tok = self._worker(req)
        b = req["body"]
        if not isinstance(b.get("result"), dict):
            raise _BadRequest("result must be an object")
        return 200, self.L.submit_result(wid, tok, str(b.get("assignment", "")), b["result"])

    def release(self, req):
        wid, tok = self._worker(req)
        return 200, self.L.release(wid, tok, str(req["body"].get("assignment", "")))

    def me(self, req):
        wid, tok = self._worker(req)
        return 200, self.L.worker_info(wid, tok)

    def page(self, req):
        return 200, render_page(self.status())


class _BadRequest(Exception):
    pass


def _pairs(body) -> list:
    pairs = body.get("pairs")
    if not isinstance(pairs, list):
        raise _BadRequest("pairs must be a list of [k, n]")
    try:
        return [(int(p[0]), int(p[1])) for p in pairs]
    except (TypeError, ValueError, IndexError):
        raise _BadRequest("pairs must be a list of [k, n]")


_REASON = {200: "OK", 400: "Bad Request", 401: "Unauthorized", 403: "Forbidden", 404: "Not Found",
           405: "Method Not Allowed", 409: "Conflict", 413: "Payload Too Large", 426: "Upgrade Required",
           429: "Too Many Requests", 500: "Internal Server Error", 503: "Service Unavailable"}


def _fmt(n) -> str:
    return "—" if n is None else "{:,}".format(n)


def render_page(s: Dict[str, Any]) -> str:
    e = html.escape
    counts = s.get("counts", {})
    done = counts.get("done", 0) + counts.get("verified", 0) + counts.get("factored", 0)
    total = max(1, s.get("candidates", 0))
    pct = 100.0 * done / total
    primes = "".join("<li><b>%s·2<sup>%s</sup>+1</b> reported by %s: <b>%s</b></li>"
                     % (e(str(p["k"])), e(str(p["n"])), e(p.get("owner", "")),
                        "verified prime" if p.get("status") == "verified" else "awaiting independent check")
                     for p in s.get("primes", []))
    owners = "".join("<tr><td>%s</td><td class=num>%s</td></tr>" % (e(o["name"]), _fmt(o["results"])) for o in s.get("top_owners", []))
    eta = s.get("eta_days")
    rows = [("Candidates in the search", _fmt(s.get("candidates"))),
            ("Removed (a deeper sieve found a factor)", _fmt(s.get("removed", 0))),
            ("Settled (tested and checked where required, or factored)", "%s (%.2f%%)" % (_fmt(done), pct)),
            ("Factors found by P\u22121 (no test needed)", _fmt(counts.get("factored", 0))),
            ("Every candidate below this n has a result", _fmt(s.get("tested_through_n"))),
            ("Every candidate below this n is settled", _fmt(s.get("complete_through_n"))),
            ("Tests running now", _fmt(s.get("active_assignments"))),
            ("Awaiting a double check", _fmt(counts.get("awaiting_dc", 0))),
            ("Conflicting results awaiting a tie-break", _fmt(counts.get("conflict", 0))),
            ("Results in the last 24 hours", _fmt(s.get("tests_last_24h"))),
            ("Time to finish at that rate", "%.0f days" % eta if eta else "—")]
    table = "".join("<tr><td>%s</td><td class=num>%s</td></tr>" % (e(a), e(b)) for a, b in rows)
    rng = s.get("range") or [None, None]
    msg = "<p class=msg>%s</p>" % e(s["message"]) if s.get("message") else ""
    paused = "<p class=msg>The project is paused: no new work is being handed out.</p>" if s.get("paused") else ""
    return _PAGE % {"table": table, "pct": "%.3f" % pct, "owners": owners or "<tr><td colspan=2>No results yet</td></tr>",
                    "primes": "<h2>Primes reported</h2><ul>%s</ul>" % primes if primes else "",
                    "lo": _fmt(rng[0]), "hi": _fmt(rng[1]), "msg": msg + paused}


_PAGE = """<!doctype html><html lang=en><head><meta charset=utf-8>
<meta name=viewport content="width=device-width,initial-scale=1"><meta http-equiv=refresh content=120>
<title>Colbert ledger</title><style>
:root{--bg:#fbfaf7;--fg:#1d1d1b;--mut:#6b6a66;--line:#e4e1da;--acc:#2f6f4f}
@media (prefers-color-scheme:dark){:root{--bg:#141413;--fg:#ecebe6;--mut:#9b9a94;--line:#2c2b28;--acc:#6fbf8f}}
body{background:var(--bg);color:var(--fg);font:16px/1.5 system-ui,-apple-system,Segoe UI,sans-serif;margin:0;padding:32px 16px}
main{max-width:720px;margin:0 auto}h1{font-size:26px;margin:0 0 4px}h2{font-size:18px;margin:28px 0 8px}
p{color:var(--mut);margin:0 0 16px}table{width:100%%;border-collapse:collapse}td{padding:8px 0;border-bottom:1px solid var(--line)}
.num{text-align:right;font-variant-numeric:tabular-nums}.bar{height:10px;background:var(--line);border-radius:5px;overflow:hidden;margin:16px 0 24px}
.bar>div{height:100%%;background:var(--acc);width:%(pct)s%%;min-width:2px}.msg{color:var(--fg);border-left:3px solid var(--acc);padding-left:12px}
</style></head><body><main>
<h1>Colbert: the last five Sierpiński candidates</h1>
<p>Shared ledger for Proth tests of k·2<sup>n</sup>+1, n from %(lo)s to %(hi)s. Join with the Colbert app.</p>
%(msg)s<div class=bar><div></div></div><table>%(table)s</table>%(primes)s
<h2>Most results</h2><table>%(owners)s</table></main></body></html>"""


def create_app() -> App:
    store = open_store(os.environ.get("LEDGER_STORE", "sqlite:ledger.sqlite"))
    return App(Ledger(store), admin_token=os.environ.get("LEDGER_ADMIN_TOKEN"))
