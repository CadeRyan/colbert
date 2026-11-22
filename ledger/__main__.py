"""
    python3 -m ledger serve [--db FILE | --store SPEC] [--port 8080] [--host 127.0.0.1]
    python3 -m ledger admin COMMAND ...      (talks to a running ledger over HTTP)

Admin commands use LEDGER_URL and LEDGER_ADMIN_TOKEN from the environment:

    status                          public status
    config [key=value ...]          show, or change, policy (values are JSON: 0.1, true, "text")
    seed FILE [--min-n N] [--max-n N]
                                    append candidates from a sieve output (.txt or .gz, "k n" lines)
    remove FILE [--reason TEXT]     take candidates out (e.g. a deeper sieve found factors)
    invalidate ENGINE               discard one engine build's results, re-queue, and block it
    audit [--repair]                check the no-gaps invariant
    export [--out FILE]             every issued candidate with its results, as JSON Lines
"""
from __future__ import annotations

import argparse
import gzip
import json
import os
import sys
import urllib.error
import urllib.request


def serve(args):
    from wsgiref.simple_server import WSGIRequestHandler, WSGIServer, make_server
    from socketserver import ThreadingMixIn

    from .api import App, open_store
    from .core import Ledger

    class Server(ThreadingMixIn, WSGIServer):
        daemon_threads = True

    class Quiet(WSGIRequestHandler):
        def log_message(self, *a):
            pass

    store = open_store(args.store or ("sqlite:" + args.db))
    token = os.environ.get("LEDGER_ADMIN_TOKEN", "")
    app = App(Ledger(store), admin_token=token)
    httpd = make_server(args.host, args.port, app, server_class=Server, handler_class=Quiet)
    print("ledger on http://%s:%d  (store %s, admin %s)" % (args.host, args.port, args.store or args.db,
                                                            "enabled" if token else "disabled: set LEDGER_ADMIN_TOKEN"), flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass


def _call(method, path, body=None):
    url = os.environ.get("LEDGER_URL", "http://127.0.0.1:8080").rstrip("/") + path
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers={
        "Content-Type": "application/json", "Authorization": "Bearer admin:" + os.environ.get("LEDGER_ADMIN_TOKEN", "")})
    try:
        with urllib.request.urlopen(req, timeout=600) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        sys.exit("%s %s: %s" % (e.code, path, e.read().decode(errors="replace")))


def _read_pairs(path, min_n=0, max_n=1 << 62):
    opener = gzip.open if path.endswith(".gz") else open
    out = []
    with opener(path, "rt") as f:
        for line in f:
            parts = line.split("#")[0].split()
            if len(parts) >= 2:
                k, n = int(parts[0]), int(parts[1])
                if min_n <= n <= max_n:
                    out.append((k, n))
    out.sort(key=lambda p: (p[1], p[0]))
    return out


def admin(args):
    cmd = args.cmd
    if cmd == "status":
        print(json.dumps(_call("GET", "/v1/status"), indent=2))
    elif cmd == "config":
        if not args.rest:
            print(json.dumps(_call("GET", "/v1/admin/config"), indent=2))
            return
        changes = {}
        for kv in args.rest:
            k, _, v = kv.partition("=")
            try:
                changes[k] = json.loads(v)
            except ValueError:
                changes[k] = v
        print(json.dumps(_call("POST", "/v1/admin/config", changes), indent=2))
    elif cmd in ("seed", "remove"):
        if not args.rest:
            sys.exit("usage: admin %s FILE" % cmd)
        pairs = _read_pairs(args.rest[0], args.min_n, args.max_n)
        print("%d candidates read from %s" % (len(pairs), args.rest[0]))
        done = 0
        # a removal reads two documents per candidate, so smaller requests stay well inside
        # Cloud Run's request timeout; both commands are safe to re-run after an interruption
        step = 20000 if cmd == "seed" else 1000
        for i in range(0, len(pairs), step):
            part = [[k, n] for k, n in pairs[i:i + step]]
            body = {"pairs": part}
            if cmd == "remove":
                body["reason"] = args.reason
            r = _call("POST", "/v1/admin/" + cmd, body)
            done += r.get("added", r.get("removed", 0))
            print("  %d/%d sent, %d %s" % (min(i + step, len(pairs)), len(pairs), done, "added" if cmd == "seed" else "removed"), flush=True)
    elif cmd == "invalidate":
        print(json.dumps(_call("POST", "/v1/admin/invalidate", {"engine": args.rest[0]}), indent=2))
    elif cmd == "audit":
        print(json.dumps(_call("POST", "/v1/admin/audit", {"repair": args.repair}), indent=2))
    elif cmd == "export":
        out = open(args.out, "w") if args.out else sys.stdout
        after = -1
        while True:
            r = _call("GET", "/v1/admin/export?after=%d&limit=2000" % after)
            for c in r["candidates"]:
                out.write(json.dumps(c) + "\n")
            if r["next"] is None:
                break
            after = r["next"]
    else:
        sys.exit(__doc__)


def main(argv=None):
    ap = argparse.ArgumentParser(prog="python3 -m ledger", description="Colbert work ledger")
    sub = ap.add_subparsers(dest="what")
    s = sub.add_parser("serve")
    s.add_argument("--db", default="ledger.sqlite")
    s.add_argument("--store", help="sqlite:PATH or firestore[:PROJECT] (overrides --db)")
    s.add_argument("--host", default="127.0.0.1")
    s.add_argument("--port", type=int, default=int(os.environ.get("PORT", 8080)))
    a = sub.add_parser("admin")
    a.add_argument("cmd")
    a.add_argument("rest", nargs="*")
    a.add_argument("--min-n", type=int, default=0)
    a.add_argument("--max-n", type=int, default=1 << 62)
    a.add_argument("--reason", default="factor found")
    a.add_argument("--repair", action="store_true")
    a.add_argument("--out")
    args = ap.parse_args(argv)
    if args.what == "serve":
        serve(args)
    elif args.what == "admin":
        admin(args)
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
