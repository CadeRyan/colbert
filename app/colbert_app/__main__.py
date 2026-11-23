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
import subprocess
import sys
import threading
import time
import webbrowser

from . import VERSION
from .paths import FROZEN, MAC_APP, data_dir
from .worker import AlreadyRunning, SingleInstance, Worker, _dur


def main(argv=None):
    # A downloaded app started by double-click may have no console at all (Windows: stdout and
    # stderr are None). Give everything, argparse included, somewhere harmless to write until
    # the data folder is known; from then on output goes to a log file there.
    no_console = sys.stdout is None or sys.stderr is None
    if no_console:
        null = open(os.devnull, "w")
        sys.stdout, sys.stderr = sys.stdout or null, sys.stderr or null
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
    ap.add_argument("--serve", action="store_true", help=argparse.SUPPRESS)   # the macOS app's background process
    a = ap.parse_args(argv)

    d = data_dir(a.data)
    _keep_output(d, no_console)
    if FROZEN and sys.platform.startswith("linux"):
        # PyInstaller points LD_LIBRARY_PATH at the app's own libraries. The engine, a child
        # process, must load the system's (and the libgomp beside it, through its rpath).
        orig = os.environ.pop("LD_LIBRARY_PATH_ORIG", None)
        if orig is not None:
            os.environ["LD_LIBRARY_PATH"] = orig
        else:
            os.environ.pop("LD_LIBRARY_PATH", None)
    if MAC_APP and not (a.headless or a.serve):
        return mac_launch(d)
    if a.serve:
        a.no_browser = True                     # the launcher opens the page
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


def _keep_output(d: str, no_console: bool):
    """No console: send output to a log file in the data folder instead of losing it."""
    os.makedirs(os.path.join(d, "logs"), exist_ok=True)
    if no_console:
        f = open(os.path.join(d, "logs", "app-output.log"), "a", buffering=1, encoding="utf-8", errors="replace")
        sys.stdout = sys.stderr = f


# ---------------------------------------------------------------------------- macOS app

def mac_launch(d: str):
    """Colbert.app was opened from Finder, the Dock or Launchpad.

    macOS doesn't start an app that is already running, it only brings it to the front, and
    this app has no window to bring forward. So the app itself is just a launcher: the first
    time, it starts the worker as a separate background process; every time, it opens the
    page in the browser and exits. Opening Colbert again therefore always lands here."""
    exe = os.path.realpath(sys.executable)
    if "/AppTranslocation/" in exe or exe.startswith("/Volumes/"):
        # running from the disk image, or straight from Downloads: macOS runs such apps from
        # a temporary read-only copy that can vanish under a long-running worker
        _mac_alert("Please move Colbert to your Applications folder first.",
                   "Drag Colbert into Applications, then open it from there. It keeps working in the "
                   "background for days at a time, so it needs a permanent place.")
        return
    url_file = os.path.join(d, "app.url")
    try:
        probe = SingleInstance(os.path.join(d, "app.lock"))
    except AlreadyRunning:
        return _mac_open(_wait_for(url_file, None, 30), d)
    probe.f.close()                              # free the lock for the worker
    try:
        os.remove(url_file)
    except OSError:
        pass
    log = open(os.path.join(d, "logs", "app-output.log"), "ab")
    proc = subprocess.Popen([exe, "--serve", "--data", d], stdin=subprocess.DEVNULL, stdout=log,
                            stderr=subprocess.STDOUT, start_new_session=True, close_fds=True)
    _mac_open(_wait_for(url_file, proc, 90), d)


def _wait_for(url_file: str, proc, seconds: float) -> str:
    deadline = time.time() + seconds
    while time.time() < deadline:
        url = _read(url_file)
        if url:
            return url
        if proc is not None and proc.poll() is not None:
            break                                # the worker exited: it says why in the log
        time.sleep(0.25)
    return ""


def _mac_open(url: str, d: str):
    if url and os.environ.get("COLBERT_NO_BROWSER"):
        print("Colbert is running at %s" % url, flush=True)       # tests and remote sessions
    elif url:
        subprocess.run(["open", url], check=False)
    else:
        _mac_alert("Colbert couldn't start.", "What went wrong is at the end of this file:\n" +
                   os.path.join(d, "logs", "app-output.log"))


def _mac_alert(title: str, text: str):
    msg = (title + "\n\n" + text).replace("\\", "\\\\").replace('"', '\\"')
    subprocess.run(["osascript", "-e", 'display dialog "%s" with title "Colbert" buttons {"OK"} '
                                       'default button "OK" with icon caution giving up after 600' % msg], check=False,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


if __name__ == "__main__":
    main()
