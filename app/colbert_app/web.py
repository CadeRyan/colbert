"""
The app's user interface: a small web server on 127.0.0.1 that serves one page (ui/index.html)
and a JSON API the page polls. Standard library only.

Only this computer can reach it, and only the page it served can use it: every API call must
carry a random per-launch token embedded in that page, and requests whose Host header isn't
127.0.0.1/localhost are refused (which defeats DNS-rebinding attacks from other websites).
"""
from __future__ import annotations

import json
import os
import secrets
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Dict

from .worker import Worker

UI = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ui", "index.html")


class UIServer:
    def __init__(self, worker: Worker, port: int = 0):
        self.worker = worker
        self.token = secrets.token_urlsafe(24)
        self.quit_requested = threading.Event()
        server = self

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def log_message(self, *a):
                pass

            def _host_ok(self) -> bool:
                host = (self.headers.get("Host") or "").split(":")[0]
                return host in ("127.0.0.1", "localhost")

            def _send(self, code: int, body: bytes, ctype: str):
                self.send_response(code)
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store")
                self.send_header("X-Content-Type-Options", "nosniff")
                self.send_header("X-Frame-Options", "DENY")
                self.send_header("Referrer-Policy", "no-referrer")
                self.end_headers()
                self.wfile.write(body)

            def _json(self, code: int, obj: Any):
                self._send(code, json.dumps(obj).encode(), "application/json")

            def do_GET(self):
                if not self._host_ok():
                    return self._send(403, b"forbidden", "text/plain")
                path = self.path.split("?")[0]
                if path in ("/", "/index.html"):
                    with open(UI, "rb") as f:
                        page = f.read().replace(b"__COLBERT_TOKEN__", server.token.encode())
                    return self._send(200, page, "text/html; charset=utf-8")
                if path == "/api/state":
                    if self.headers.get("X-Colbert-Token") != server.token:
                        return self._json(403, {"error": "bad token"})
                    return self._json(200, server.worker.snapshot())
                self._send(404, b"not found", "text/plain")

            def do_POST(self):
                if not self._host_ok() or self.headers.get("X-Colbert-Token") != server.token:
                    return self._json(403, {"error": "forbidden"})
                n = int(self.headers.get("Content-Length") or 0)
                if n > 4 << 20:
                    return self._json(413, {"error": "too large"})
                try:
                    body = json.loads(self.rfile.read(n) or b"{}") if n else {}
                    out = server.action(self.path.split("?")[0], body)
                    self._json(200, {"ok": True, "result": out})
                except (ValueError, KeyError, TypeError) as e:
                    self._json(400, {"ok": False, "error": str(e)})
                except Exception as e:      # ledger unreachable while joining, and the like
                    self._json(502, {"ok": False, "error": str(e)})

        self.httpd = ThreadingHTTPServer(("127.0.0.1", port), Handler)
        self.httpd.daemon_threads = True
        self.port = self.httpd.server_address[1]
        self.url = "http://127.0.0.1:%d/" % self.port

    def action(self, path: str, b: Dict[str, Any]):
        w = self.worker
        if path == "/api/start":
            return w.do_start()
        if path == "/api/pause":
            return w.do_pause()
        if path == "/api/settings":
            return w.do_settings(b)
        if path == "/api/join":
            return w.do_join(b["url"], b.get("owner", ""), b.get("invite", ""))
        if path == "/api/add":
            return w.do_add(b["text"])
        if path == "/api/clear_queue":
            return w.do_clear_queue()
        if path == "/api/validate":
            return w.do_validate(b.get("device", "all"))
        if path == "/api/dismiss_prime":
            return w.do_dismiss_prime()
        if path == "/api/build":
            return w.do_build()
        if path == "/api/quit":
            self.quit_requested.set()
            return True
        raise ValueError("unknown action " + path)

    def serve(self):
        t = threading.Thread(target=self.httpd.serve_forever, name="ui", daemon=True)
        t.start()
        return t

    def close(self):
        self.httpd.shutdown()
