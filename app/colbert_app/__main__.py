"""
Colbert app.

    python3 app/run.py                      open the app in your browser
    python3 app/run.py --headless --ledger URL --owner NAME
                                            no window: for servers and cloud GPUs
    python3 app/run.py --headless --local numbers.txt

Options:
    --data DIR          keep settings, checkpoints and results here (default: per-user app data)
    --port P            port for the local UI (default: any free port)
    --no-browser        don't open a browser (the address is printed)
    --device ID         auto (default), cpu, or ocl:N   (headless)
    --threads T         CPU threads for the CPU engine  (headless)
"""
from __future__ import annotations

import argparse
import os
import signal
import sys
import threading
import time
import webbrowser

from . import VERSION
from .paths import data_dir
from .worker import AlreadyRunning, Worker, _dur


def main(argv=None):
    ap = argparse.ArgumentParser(prog="colbert-app", description="Colbert: Proth tests for the Sierpinski problem")
    ap.add_argument("--data", default="")
    ap.add_argument("--port", type=int, default=0)
    ap.add_argument("--no-browser", action="store_true")
    ap.add_argument("--headless", action="store_true")
    ap.add_argument("--ledger", default="")
    ap.add_argument("--owner", default="")
    ap.add_argument("--invite", default="")
    ap.add_argument("--local", default="", help="file of 'k n' lines to test (headless)")
    ap.add_argument("--device", default="")
    ap.add_argument("--threads", type=int, default=-1)
    ap.add_argument("--version", action="version", version="colbert-app " + VERSION)
    a = ap.parse_args(argv)

    d = data_dir(a.data)
    try:
        w = Worker(d, headless=a.headless)
    except AlreadyRunning:
        url = _read(os.path.join(d, "app.url"))
        if a.headless or not url:
            sys.exit("Colbert is already running with data directory %s" % d)
        print("Colbert is already running: %s" % url)
        webbrowser.open(url)
        return

    if a.headless:
        return headless(w, a)

    from .web import UIServer
    ui = UIServer(w, a.port)
    ui.serve()
    w.start()
    with open(os.path.join(d, "app.url"), "w") as f:
        f.write(ui.url)
    print("Colbert %s is running at %s\n(data in %s; close with the Quit button or Ctrl-C)" % (VERSION, ui.url, d), flush=True)
    if not a.no_browser:
        threading.Timer(0.5, lambda: webbrowser.open(ui.url)).start()
    stop = _stop_on_signals()
    try:
        while not (ui.quit_requested.is_set() or stop.is_set()):
            time.sleep(0.5)
    except KeyboardInterrupt:
        pass
    print("saving progress and stopping (this can take a minute)...", flush=True)
    w.shutdown()
    ui.close()


def headless(w: Worker, a):
    changes = {}
    if a.ledger:
        changes.update(mode="ledger", ledger_url=a.ledger.rstrip("/"))
    if a.owner:
        changes["owner"] = a.owner
    if a.invite:
        changes["invite"] = a.invite
    if a.device:
        changes["device"] = a.device
    if a.threads >= 0:
        changes["cpu_threads"] = a.threads
    if a.local:
        changes["mode"] = "local"
    if changes:
        w.do_settings(changes)
    if a.local:
        with open(a.local) as f:
            print("%d number(s) added to the local list" % w.do_add(f.read()), flush=True)
    stop = _stop_on_signals()
    w.start()
    w.do_start()
    last = 0.0
    try:
        while not stop.is_set() and w.thread.is_alive():
            time.sleep(1)
            if time.time() - last >= 60:
                last = time.time()
                s = w.snapshot()
                L, t = s["live"], s["task"]
                if t and s["status"] == "running" and L.get("total"):
                    print("%s  %d*2^%d+1  %.2f%%  %.3f ms/it  %s left  checks %d  corrected %d" % (
                        time.strftime("%H:%M:%S"), t["k"], t["n"], L.get("percent", 0), L.get("ms_per_iter_recent") or L.get("ms_per_iter") or 0,
                        _dur(s["eta_seconds"] or 0), L.get("checks_passed", 0), L.get("rollbacks", 0)), flush=True)
                else:
                    print("%s  %s: %s" % (time.strftime("%H:%M:%S"), s["status"], s["status_text"]), flush=True)
                if s["status"] in ("idle",) and a.local and not s["queue_len"] and not t:
                    break
    except KeyboardInterrupt:
        pass
    print("saving progress and stopping...", flush=True)
    w.shutdown()


def _stop_on_signals() -> threading.Event:
    ev = threading.Event()

    def handler(*_):
        ev.set()
    for sig in ("SIGTERM", "SIGHUP"):
        if hasattr(signal, sig):
            try:
                signal.signal(getattr(signal, sig), handler)
            except (ValueError, OSError):
                pass
    return ev


def _read(p):
    try:
        with open(p) as f:
            return f.read().strip()
    except OSError:
        return ""


if __name__ == "__main__":
    main()
