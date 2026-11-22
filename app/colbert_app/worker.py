"""
The app's engine room: picks a device, gets work, runs the engine, reports progress and
results, and survives restarts.

Robustness rules this file follows:
  * The current task (number, Gerbicz block length, assignment) is saved before the engine
    starts, so a crash, power cut or reboot resumes from the engine's last verified checkpoint.
  * Results go into a persistent outbox and are uploaded until the ledger accepts them.
  * Every engine build is re-validated (selftest + benchmark) on each device before it is
    trusted with work. Rebuilding the engine after tuning therefore re-runs validation
    automatically; a device that fails the selftest is never used with that build.
  * Only one instance runs per data directory, and a leftover engine process from a crashed
    session is stopped before a new one starts.
"""
from __future__ import annotations

import collections
import hashlib
import json
import os
import platform
import re
import socket
import subprocess
import threading
import time
from typing import Any, Dict, List, Optional

from . import PROJECT_LEDGER_URL, VERSION
from .engine import Engine, EngineError, choose_gerbicz, kill_pid, process_alive, split_args
from .ledger_client import LedgerClient, LedgerRefused, LedgerUnavailable
from .paths import can_build_from_source, engine_candidates, repo_root

DEFAULT_LEDGER_URL = os.environ.get("COLBERT_LEDGER_URL", "") or PROJECT_LEDGER_URL
BENCH_K, BENCH_N = 21181, 47856020        # the leading edge; what ledger work looks like
KNOWN_PRIME = (46157, 698207)             # Seventeen or Bust, 2002: a quick end-to-end check
SIERPINSKI_K = (21181, 22699, 24737, 55459, 67607)   # the five k still open

DEFAULTS: Dict[str, Any] = {
    "mode": "ledger" if DEFAULT_LEDGER_URL else "local",
    "ledger_url": DEFAULT_LEDGER_URL,
    "owner": "",
    "worker_name": socket.gethostname()[:60],
    "invite": "",
    "credentials": {},           # ledger url -> {"worker_id", "token"}
    "device": "auto",
    "cpu_threads": 0,            # 0: all cores
    "checkpoint_minutes": 10.0,
    "autostart": False,
    "engine_path": "",
    "extra_args": "",            # advanced: passed to every Proth test
    "pm1": True,                 # P-1 factoring before a first test, when it pays (docs/PM1.md)
    "sieve_bits": 32.0,          # your own lists: no factor below 2^sieve_bits (the ledger says for its own)
    "validated": {},             # "<engine version>|<device key>" -> selftest and benchmark
}
EDITABLE = ("mode", "ledger_url", "owner", "worker_name", "invite", "device", "cpu_threads",
            "checkpoint_minutes", "autostart", "engine_path", "extra_args", "pm1", "sieve_bits")


class AlreadyRunning(Exception):
    pass


class SingleInstance:
    """An OS-level lock on a file in the data directory, released automatically on exit or crash."""

    def __init__(self, path: str):
        self.f = open(path, "a+")
        try:
            if os.name == "nt":
                import msvcrt
                self.f.seek(0)
                msvcrt.locking(self.f.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            self.f.close()
            raise AlreadyRunning(path)


def _atomic_write(path: str, obj: Any):
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(obj, f, indent=1)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


def _load(path: str, default):
    try:
        with open(path) as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def parse_numbers(text: str) -> List[List[int]]:
    """'21181 47856020', '21181*2^47856020+1', '21181,47856020' -> [[k, n], ...]"""
    out = []
    for line in text.splitlines():
        line = line.split("#")[0].strip()
        if not line:
            continue
        m = re.match(r"^\s*(\d+)\s*(?:\*\s*2\s*\^\s*|[\s,;]+)(\d+)\s*(?:\+\s*1)?\s*$", line)
        if not m:
            raise ValueError("can't read %r: write 'k n' or 'k*2^n+1'" % line)
        k, n = int(m.group(1)), int(m.group(2))
        if not (1 <= k < 2 ** 32 and k % 2 == 1):
            raise ValueError("k must be odd and below 2^32: %r" % line)
        if not (300 <= n < 2 ** 31):
            raise ValueError("n must be between 300 and 2^31: %r" % line)
        out.append([k, n])
    return out


class Worker:
    def __init__(self, data_dir: str, headless: bool = False):
        self.dir = data_dir
        self.headless = headless
        os.makedirs(os.path.join(data_dir, "checkpoints"), exist_ok=True)
        os.makedirs(os.path.join(data_dir, "logs"), exist_ok=True)
        self.instance = SingleInstance(os.path.join(data_dir, "app.lock"))
        self.lock = threading.RLock()
        self.settings: Dict[str, Any] = dict(DEFAULTS)
        self.settings.update(_load(self.path("settings.json"), {}))
        if not self.settings.get("ledger_url") and DEFAULT_LEDGER_URL:
            self.settings["ledger_url"] = DEFAULT_LEDGER_URL
        self.state: Dict[str, Any] = {"current": None, "pending": [], "queue": [], "history": [], "engine_pid": 0}
        self.state.update(_load(self.path("state.json"), {}))
        self.engine: Optional[Engine] = None
        self.engine_error = ""
        self.devices: List[Dict[str, Any]] = []
        self.device: Optional[Dict[str, Any]] = None
        self.run = None
        self.status, self.status_text = "starting", "Starting"
        self.wanted = bool(self.settings["autostart"])
        self.restart_requested = False
        self.validate_request = False
        self.engine_stamp = None
        self.engine_hash = ""
        self.source_changed = False
        self.abandon_reason = ""
        self.live: Dict[str, Any] = {}
        self.rate = collections.deque(maxlen=1500)         # (time, ms per iteration, percent)
        self.ewma = 0.0
        self.logbuf = collections.deque(maxlen=600)
        self.validation: Dict[str, Any] = {"running": False}
        self.project: Dict[str, Any] = {}
        self.ledger_note = ""
        self.ledger_cfg: Dict[str, Any] = {}         # the ledger's public config (pm1, sieve_bits, ...)
        self.prime_alert = self.state.get("prime_alert")
        self.next_upload = 0.0
        self.quit_event = threading.Event()
        self.wake = threading.Event()
        self.thread = threading.Thread(target=self._loop, name="worker", daemon=True)
        self.poller = threading.Thread(target=self._poll_project, name="project", daemon=True)

    # ------------------------------------------------------------------ persistence & logging

    def path(self, *p) -> str:
        return os.path.join(self.dir, *p)

    def save(self):
        with self.lock:
            _atomic_write(self.path("settings.json"), self.settings)
            _atomic_write(self.path("state.json"), self.state)

    def log(self, msg: str, level: str = "info"):
        line = "%s %s %s" % (time.strftime("%Y-%m-%d %H:%M:%S"), level.upper()[:4], msg)
        self.logbuf.append(line)
        try:
            p = self.path("logs", "app.log")
            if os.path.exists(p) and os.path.getsize(p) > 5 << 20:
                os.replace(p, p + ".1")
            with open(p, "a") as f:
                f.write(line + "\n")
        except OSError:
            pass
        if self.headless:
            print(line, flush=True)

    def set_status(self, status: str, text: str):
        if (status, text) != (self.status, self.status_text):
            self.status, self.status_text = status, text
            if status in ("error", "waiting", "validating"):
                self.log(text, "warn" if status != "validating" else "info")

    def sleep(self, seconds: float) -> bool:
        """Interruptible sleep; returns True if woken early."""
        woke = self.wake.wait(seconds)
        self.wake.clear()
        return woke

    # ------------------------------------------------------------------ lifecycle

    def start(self):
        self.thread.start()
        self.poller.start()

    def shutdown(self, timeout: float = 150):
        self.log("shutting down")
        self.wanted = False
        self.quit_event.set()
        self.wake.set()
        self.thread.join(timeout)
        if self.run and self.run.poll() is None:
            self.run.kill()
        self.save()

    def _loop(self):
        self._recover_orphan()
        self.load_engine()
        while not self.quit_event.is_set():
            try:
                self._upload_pending()
                if self.source_changed:
                    self._apply_source_change()
                if self._engine_changed():
                    self.load_engine()
                if not self.wanted and self.validate_request and self.engine:
                    self._validate_pending()
                    continue
                if not self.wanted:
                    cur = self.state.get("current")
                    self.set_status("paused" if cur else "idle",
                                    "Paused: progress is saved" if cur else "Ready. Press Start to begin.")
                    self.sleep(5)
                    continue
                if not self.engine:
                    self.set_status("error", "No working engine: " + (self.engine_error or "not found"))
                    self.sleep(15)
                    self.load_engine()
                    continue
                dev = self._pick_device()
                if dev is None:
                    if not self.quit_event.is_set() and self.wanted and not self.restart_requested:
                        self.wanted = False
                        self.set_status("error", "No device passed the self-test with engine %s. See Devices." % self.engine.version)
                    self.restart_requested = False
                    continue
                self.device = dev
                task = self.state.get("current") or self._next_task(dev)
                if not task:
                    continue
                self._run_task(task, dev)
            except Exception as e:                       # keep going whatever happens
                self.log("unexpected error: %r" % e, "error")
                self.set_status("error", "Unexpected error: %s (retrying)" % e)
                self.sleep(30)
        self.set_status("stopped", "Stopped")

    def _recover_orphan(self):
        pid = int(self.state.get("engine_pid") or 0)
        if pid and process_alive(pid):
            self.log("an engine from a previous session is still running (pid %d); stopping it" % pid, "warn")
            open(self.path("stop"), "w").close()
            for _ in range(120):
                if not process_alive(pid):
                    break
                time.sleep(1)
            else:
                kill_pid(pid)
        self.state["engine_pid"] = 0
        self.save()

    # ------------------------------------------------------------------ engine & devices

    @staticmethod
    def _stamp(path):
        try:
            st = os.stat(path)
            return (path, st.st_size, st.st_mtime)
        except OSError:
            return None

    def _engine_changed(self) -> bool:
        """True when the engine binary was rebuilt or replaced since it was loaded."""
        return bool(self.engine) and self._stamp(self.engine.path) != self.engine_stamp

    def load_engine(self):
        errors = []
        for p in engine_candidates(self.settings.get("engine_path", "")):
            try:
                stamp = self._stamp(p)
                e = Engine(p).probe()
            except EngineError as ex:
                if os.path.exists(p):
                    errors.append(str(ex))
                continue
            try:
                with open(p, "rb") as f:
                    digest = hashlib.sha256(f.read()).hexdigest()[:12]
            except OSError:
                digest = "?"
            with self.lock:
                changed = not self.engine or self.engine.path != e.path or self.engine_hash != digest
                self.engine, self.engine_error, self.engine_stamp, self.engine_hash = e, "", stamp, digest
                self.devices = e.devices()
            if changed:
                self.log("engine %s (%s), protocol %d, backends %s; %d device(s)" %
                         (e.version, e.path, e.protocol, "+".join(e.backends), len(self.devices)))
                if any(self.validation_of(d) is None for d in self.devices):
                    self.log("this engine build has not been checked on every device yet; that happens before it gets work")
            return
        with self.lock:
            self.engine, self.devices = None, []
            self.engine_error = "; ".join(errors) if errors else (
                "no engine binary found. Build it with `make` in the colbert folder" if can_build_from_source()
                else "no engine binary found next to the app")

    def _threads_env(self, dev) -> Dict[str, str]:
        t = int(self.settings.get("cpu_threads") or 0)
        return {"OMP_NUM_THREADS": str(t)} if t > 0 and dev["backend"] == "cpu" else {}

    def vkey(self, dev) -> str:
        key = dev["key"]
        if dev["backend"] == "cpu":
            key += "|threads=%d" % int(self.settings.get("cpu_threads") or 0)
        # the binary's hash as well as its version: an uncommitted rebuild may keep the version
        return "%s|%s|%s" % (self.engine.version if self.engine else "?", self.engine_hash, key)

    def validation_of(self, dev) -> Optional[Dict[str, Any]]:
        return self.settings["validated"].get(self.vkey(dev))

    def _pick_device(self) -> Optional[Dict[str, Any]]:
        want = self.settings.get("device", "auto")
        pool = [d for d in self.devices if want == "auto" or d["id"] == want]
        if not pool:
            self.set_status("error", "The chosen device (%s) is not available; using automatic choice" % want)
            self.settings["device"] = "auto"
            pool = list(self.devices)
        for d in pool:
            if self._cancelled():
                return None
            if self.validation_of(d) is None:
                self.validate(d)
        good = [(self.validation_of(d) or {}, d) for d in pool]
        good = [(v, d) for v, d in good if v.get("ok") and v.get("ms_per_iter")]
        if not good:
            return None
        return min(good, key=lambda x: x[0]["ms_per_iter"])[1]

    def _cancelled(self) -> bool:
        return self.quit_event.is_set() or self.restart_requested or not (self.wanted or self.validate_request)

    def _validate_pending(self):
        """Check every device that this engine build has not been checked on (no work starts)."""
        for d in list(self.devices):
            if self._cancelled():
                break
            if self.validation_of(d) is None:
                self.validate(d)
        self.validate_request = False
        self.restart_requested = False

    def validate(self, dev) -> Dict[str, Any]:
        """Selftest, then a benchmark at the leading edge. Cached per engine build and device."""
        e = self.engine
        extra = split_args(self.settings.get("extra_args", ""))
        self.validation = {"running": True, "device": dev["label"], "step": "self-test", "started": time.time()}
        self.set_status("validating", "Checking %s with engine %s: self-test" % (dev["label"], e.version))
        rec: Dict[str, Any] = {"device": dev["label"], "at": time.time(), "engine": e.version}
        run = e.process(["selftest", "--json"] + Engine.device_args(dev) + extra, self._threads_env(dev), self.dir)
        code = self._wait_cancellable(run)
        summary = run.last("selftest") or {}
        fails = [ev.get("text", "") for ev in run.events if ev.get("event") == "check" and not ev.get("ok")]
        rec.update(passed=summary.get("passed", 0), total=summary.get("total", 0), selftest=code == 0 and bool(summary.get("ok")))
        if code is None:
            self.validation = {"running": False}
            return rec                                   # cancelled; not recorded
        if not rec["selftest"]:
            err = run.last("error")
            rec["error"] = (err or {}).get("message") or ("%d check(s) failed: %s" % (len(fails), "; ".join(fails[:3])) if fails else
                                                         (run.log[-1] if run.log else "self-test failed"))
            rec["ok"] = False
            self.log("self-test FAILED on %s: %s" % (dev["label"], rec["error"]), "error")
        else:
            self.validation["step"] = "benchmark"
            self.set_status("validating", "Checking %s: timing at full size" % dev["label"])
            k, n = BENCH_K, self._bench_n()
            run = e.process(["bench", str(k), str(n), "1000000", "--seconds", "10", "--json"] + Engine.device_args(dev) + extra,
                            self._threads_env(dev), self.dir)
            code = self._wait_cancellable(run)
            if code is None:
                self.validation = {"running": False}
                return rec
            b = run.last("bench")
            if code == 0 and b:
                rec.update(ok=True, ms_per_iter=b["ms_per_iter"], bench_n=n, bench_N=b.get("N"), hours_per_test=b.get("hours_per_test"))
                self.log("%s: self-test %d/%d, %.3f ms per iteration at n=%d (%.1f h per test)" %
                         (dev["label"], rec["passed"], rec["total"], b["ms_per_iter"], n, b.get("hours_per_test", 0)))
            else:
                err = run.last("error")
                rec.update(ok=False, error=(err or {}).get("message") or "benchmark failed")
                self.log("benchmark failed on %s: %s" % (dev["label"], rec["error"]), "error")
        with self.lock:
            self.settings["validated"][self.vkey(dev)] = rec
            self.validation = {"running": False}
            self.save()
        return rec

    @staticmethod
    def _bench_n() -> int:
        # always the leading edge, so devices compare on the work that matters (a small n can
        # favour the CPU) and "time per test" means the same thing everywhere
        return BENCH_N

    def _wait_cancellable(self, run) -> Optional[int]:
        while True:
            code = run.poll()
            if code is not None:
                run.wait(10)
                return code
            if self._cancelled():
                run.kill()
                run.wait(10)
                return None
            time.sleep(0.5)

    # ------------------------------------------------------------------ getting work

    def client(self) -> LedgerClient:
        url = self.settings["ledger_url"]
        cred = self.settings["credentials"].get(url, {})
        return LedgerClient(url, cred.get("worker_id", ""), cred.get("token", ""))

    def _work_info(self, dev) -> Dict[str, Any]:
        v = self.validation_of(dev) or {}
        return {"engine": self.engine.version, "engine_protocol": self.engine.protocol, "app_version": VERSION,
                "backend": "cpu" if dev["backend"] == "cpu" else "opencl", "device": dev["label"],
                "ms_per_iter": v.get("ms_per_iter", 0), "platform": "%s %s" % (platform.system(), platform.machine())}

    def _next_task(self, dev) -> Optional[Dict[str, Any]]:
        if self.settings["mode"] == "local":
            done = {(h["k"], h["n"]) for h in self.state["history"] if h.get("result")}
            while self.state["queue"]:
                k, n = self.state["queue"][0]
                if (k, n) in done:
                    self.state["queue"].pop(0)
                    continue
                task = self.state.setdefault("parked", {}).pop("%d_%d" % (k, n), None) or \
                    {"source": "local", "k": k, "n": n, "kind": "local", "added": time.time(),
                     "gerbicz": choose_gerbicz(self._ms_for(dev, n), self.settings["checkpoint_minutes"], n)}
                self.state["current"] = task
                self.save()
                return task
            self.wanted = False
            self.settings["autostart"] = False
            self.save()
            self.set_status("idle", "Nothing to do. Add numbers on the Work tab, or join the project.")
            return None
        # ---- ledger
        url = self.settings.get("ledger_url", "")
        if not url:
            self.wanted = False
            self.set_status("error", "No ledger address set. See the Work tab.")
            return None
        c = self.client()
        try:
            if not c.worker_id:
                if not self.settings.get("owner"):
                    self.wanted = False
                    self.set_status("error", "Enter your name on the Work tab to join the project.")
                    return None
                r = c.register(self.settings["owner"], self.settings["worker_name"], self._work_info(dev), self.settings.get("invite", ""))
                self.settings["credentials"][url] = {"worker_id": r["worker_id"], "token": r["token"]}
                self.save()
                self.log("joined the project at %s as %s (worker %s)" % (url, r["owner"], r["worker_id"]))
            r = c.work(self._work_info(dev))
        except LedgerUnavailable as e:
            self.set_status("waiting", "%s. Retrying in %d s." % (e, e.retry_after))
            self.sleep(e.retry_after)
            return None
        except LedgerRefused as e:
            return self._refused(e, url)
        self._note_config(r.get("config"))
        a = r.get("assignment")
        if not a:
            reason = {"paused": "The project is paused", "exhausted": "The project has no work left",
                      "not_started": "The project hasn't started handing out numbers yet",
                      "waiting": "No work right now: the remaining numbers are running elsewhere or awaiting a check by another computer",
                      "retry": "Skipping removed candidates"}.get(r.get("reason"), "No work available")
            wait = float(r.get("retry_after", 600))
            self.set_status("waiting", "%s. Asking again in %s." % (reason, _dur(wait)))
            self.sleep(wait)
            return None
        task = {"source": "ledger", "url": url, "assignment": a["id"], "k": a["k"], "n": a["n"], "kind": a["kind"],
                "added": time.time(), "heartbeat": float((r.get("config") or {}).get("heartbeat_seconds", 900)),
                "gerbicz": choose_gerbicz(self._ms_for(dev, a["n"]), self.settings["checkpoint_minutes"], a["n"])}
        if a.get("pm1_done"):
            task["pm1_done"] = a["pm1_done"]      # P-1 already run elsewhere without a factor
        self.state["current"] = task
        self.save()
        self.log("assignment %s: %d*2^%d+1 (%s)" % (a["id"], a["k"], a["n"], a["kind"]))
        return task

    def _ms_for(self, dev, n: int) -> float:
        """Benchmark speed scaled to n (time per squaring grows a little faster than n)."""
        v = self.validation_of(dev) or {}
        ms, bn = v.get("ms_per_iter", 0), v.get("bench_n", 0)
        return ms * (n / bn) ** 1.05 if ms and bn else 0

    def _refused(self, e: LedgerRefused, url: str):
        if e.status == 401:
            self.log("the ledger no longer knows this computer (%s); joining again" % e, "warn")
            self.settings["credentials"].pop(url, None)
            self.save()
            self.sleep(5)
            return None
        self.wanted = False
        self.settings["autostart"] = False
        self.save()
        self.set_status("error", "The project ledger refused: %s" % e)
        return None

    def _note_config(self, cfg):
        if cfg:
            self.ledger_note = cfg.get("message", "") or ""
            self.ledger_cfg = dict(cfg)

    # ------------------------------------------------------------------ running a test

    def _on_event(self, ev):
        kind = ev.get("event")
        t = ev["_t"]
        with self.lock:
            L = self.live
            for key in ("iteration", "total", "percent", "checks_passed", "rollbacks", "verified_iteration", "ms_per_iter",
                        "ms_per_iter_recent", "eta_seconds", "N", "backend", "gerbicz_block", "checkpoint", "resumed_from",
                        "stage", "b1", "b2", "D", "probability"):
                if key in ev:
                    L[key] = ev[key]
            if ev.get("phase") == "pm1":
                if kind == "start":
                    L["started_at"] = t
                    cur = self.state.get("current")
                    if cur and (cur["k"], cur["n"]) == (ev.get("k"), ev.get("n")) and ev.get("N") and not cur.get("N"):
                        cur["N"], cur["primes"] = ev["N"], ev.get("primes", 2)    # the test continues on the same size
                        self.save()
                    if str(ev.get("checkpoint", "")).startswith("rejected"):
                        self.log("saved P-1 progress could not be used: %s" % ev["checkpoint"], "warn")
                    elif ev.get("checkpoint") == "resumed":
                        self.log("resumed P-1 (stage %s)" % ev.get("stage"))
                elif kind == "stage2":
                    self.log("P-1 stage 1 found no factor; stage 2 (D=%s)" % ev.get("D"))
                r = ev.get("ms_per_iter_recent") or 0
                if kind == "progress" and r > 0:
                    self.ewma = r if not self.ewma else 0.85 * self.ewma + 0.15 * r
                return
            if kind == "start":
                L["started_at"] = t
                cur = self.state.get("current")
                if cur and (cur["k"], cur["n"]) == (ev.get("k"), ev.get("n")) and ev.get("N") and not cur.get("N"):
                    cur["N"], cur["primes"] = ev["N"], ev.get("primes", 2)
                    self.save()
                L["last_verified_at"] = t if ev.get("resumed_from") else None
                if str(ev.get("checkpoint", "")).startswith("rejected"):
                    self.log("saved progress could not be used: %s" % ev["checkpoint"], "warn")
                elif ev.get("resumed_from"):
                    self.log("resumed from verified iteration %d" % ev["resumed_from"])
            elif kind == "verified":
                L["last_verified_at"] = t
                cur = self.state.get("current")
                if cur:
                    cur["test_iteration"] = ev.get("verified_iteration", 0)   # saved progress (P-1 planning uses it)
                if cur and cur.get("errors"):
                    cur["errors"] = 0                    # failures only count if nothing is achieved between them
            elif kind == "rollback":
                self.log("an arithmetic error was detected and corrected (rolled back to iteration %d)" % ev.get("verified_iteration", 0), "warn")
            elif kind == "error":
                L["error"] = ev.get("message")
            r = ev.get("ms_per_iter_recent") or 0
            if kind in ("progress", "verified") and r > 0:
                self.ewma = r if not self.ewma else 0.85 * self.ewma + 0.15 * r
                self.rate.append((t, r, ev.get("percent", 0)))

    def _run_task(self, task, dev):
        if self._wants_pm1(task) and not self._run_pm1(task, dev):
            return                                   # paused, factored, or P-1 failed (retried later)
        self._run_test(task, dev)

    # ---------------------------------------------------------------- P-1

    def _sieve_bits(self, task) -> float:
        if task["source"] == "ledger":
            return float(self.ledger_cfg.get("sieve_bits", 32))
        return float(self.settings.get("sieve_bits", 32))

    def _wants_pm1(self, task) -> bool:
        """P-1 runs once per number, before its first test, and only where it saves work."""
        if not self.settings.get("pm1", True) or "pm1" not in (self.engine.features or []):
            return False
        if task.get("kind") not in ("first", "local") or task.get("pm1"):
            return False
        if task["source"] == "ledger" and not self.ledger_cfg.get("pm1", True):
            return False
        try:
            extra = ["--sieve-bits", str(self._sieve_bits(task))]
            if task.get("N"):
                extra += ["--size", str(task["N"]), "--primes", str(task.get("primes", 2))]
            plan = self.engine.info(task["k"], task["n"], extra).get("pm1") or {}
        except Exception as e:
            self.log("could not plan P-1 (%s); testing directly" % e, "warn")
            return False
        if not plan.get("b1"):
            task["pm1"] = {"skipped": "does not pay at this sieve depth"}
            return False
        done = task.get("pm1_done") or {}
        if done and done.get("b1", 0) >= plan["b1"] and done.get("b2", 0) >= plan["b2"]:
            task["pm1"] = dict(done, by="another computer")
            return False
        left = max(0, task["n"] - 1 - int(task.get("test_iteration") or 0))
        if plan["probability"] * left * 1.05 <= plan["cost_iterations"]:
            task["pm1"] = {"skipped": "the test is too far along for P-1 to pay"}
            return False
        task["pm1_plan"] = plan
        return True

    def _run_pm1(self, task, dev) -> bool:
        """True: go on to the test. False: stop here (paused, factor found, or P-1 failed)."""
        k, n, plan = task["k"], task["n"], task["pm1_plan"]
        args = ["pm1", str(k), str(n), "--json", "--event-seconds", "3", "--ckpt", "checkpoints", "--results",
                "engine-results.jsonl", "--stop-file", "stop", "--b1", str(plan["b1"]), "--b2", str(plan["b2"]),
                "--sieve-bits", str(self._sieve_bits(task))] + Engine.device_args(dev)
        if task.get("N"):
            args += ["--size", str(task["N"]), "--primes", str(task.get("primes", 2))]
        self._begin_live(task, "pm1")
        self.set_status("running", "Looking for a factor of %d·2^%d+1 (P−1) on %s" % (k, n, dev["label"]))
        self.log("P-1 on %d*2^%d+1 with B1=%d, B2=%d: a %.0f%% chance of a factor, for %.1f%% of a test's work"
                 % (k, n, plan["b1"], plan["b2"], 100 * plan["probability"], 100 * plan["cost_iterations"] / n))
        code, run, stopped = self._supervise(task, dev, args)
        res = run.last("pm1")
        if code == 0 and res:
            if res.get("factor"):
                self._finish_factor(task, dev, res)
                return False
            bounds = res.get("pm1") or {}
            task["pm1"] = {"b1": bounds.get("b1", plan["b1"]), "b2": bounds.get("b2", plan["b2"])}
            task["pm1_report"] = task["source"] == "ledger"
            task.pop("pm1_plan", None)
            self.log("P-1 found no factor of %d*2^%d+1 (%s); now the Proth test" % (k, n, _dur(res.get("seconds", 0))))
            self.save()
            if task["source"] == "ledger":
                self._heartbeat(task)                # so a reissue of this number skips P-1
            return True
        if code == 3 or stopped:
            self._stopped(task, run)
            return False
        err = (run.last("error") or {}).get("message") or (run.log[-1] if run.log else "engine exited with status %s" % code)
        task["pm1_errors"] = task.get("pm1_errors", 0) + 1
        self.log("P-1 failed on %d*2^%d+1 (%d time(s)): %s" % (k, n, task["pm1_errors"], err), "error")
        if task["pm1_errors"] >= 2:
            task["pm1"] = {"skipped": "P-1 failed: %s" % err[:200]}
            task.pop("pm1_plan", None)
            self.log("skipping P-1 for %d*2^%d+1; testing it directly" % (k, n), "warn")
            self.save()
            return True
        self.set_status("error", "P-1 failed: %s. Retrying shortly." % err)
        self.save()
        self.sleep(30)
        return False

    def _finish_factor(self, task, dev, res):
        k, n, f = task["k"], task["n"], str(res["factor"])
        self.log("P-1 found a factor of %d*2^%d+1: %s (stage %s, %s). No test is needed."
                 % (k, n, f, res.get("stage"), _dur(res.get("seconds", 0))))
        entry = self._remember(task, dev, {"result": "factor", "factor": f, "seconds": res.get("seconds", 0), "engine": res.get("engine", "")})
        if task["source"] == "ledger":
            bounds = res.get("pm1") or {}
            clean = {"k": k, "n": n, "factor": f, "b1": bounds.get("b1", 0), "b2": bounds.get("b2", 0), "stage": res.get("stage", 0),
                     "seconds": res.get("seconds", 0), "engine": res.get("engine", ""), "backend": res.get("backend", "")}
            self.state["pending"].append({"url": task["url"], "assignment": task["assignment"], "result": clean, "history_at": entry["at"]})
            self.next_upload = 0
        if task["source"] == "local" and self.state["queue"] and self.state["queue"][0] == [k, n]:
            self.state["queue"].pop(0)
        self._drop(task)
        self._upload_pending()

    # ---------------------------------------------------------------- the engine process

    def _begin_live(self, task, phase: str):
        k, n = task["k"], task["n"]
        with self.lock:
            if self.live.get("key") != (k, n, phase):
                self.rate.clear()
                self.ewma = 0.0
            self.live = {"key": (k, n, phase), "phase": phase, "iteration": 0, "total": n - 1 if phase == "test" else 0, "percent": 0.0}
            if phase == "pm1":
                plan = task.get("pm1_plan") or {}
                self.live.update({"b1": plan.get("b1"), "b2": plan.get("b2"), "probability": plan.get("probability")})
            self.abandon_reason = ""

    def _supervise(self, task, dev, args):
        """Run one engine command to completion, stop or abandonment. Returns (code, run, stopped)."""
        stop = self.path("stop")
        if os.path.exists(stop):
            os.remove(stop)
        if self.run is not None and self.run.poll() is None:
            raise RuntimeError("an engine is already running")      # never two on one checkpoint
        run = self.engine.process(args, self._threads_env(dev), self.dir)
        run.on_event = self._on_event
        run.on_log = lambda line: self.logbuf.append("engine: " + line)
        self.run = run
        stop_at = None
        try:
            self.state["engine_pid"] = run.pid
            self.save()
            next_beat = time.time() + min(60, task.get("heartbeat", 900))
            while True:
                code = run.poll()
                if code is not None:
                    break
                if stop_at is None and (self.quit_event.is_set() or not self.wanted or self.restart_requested or self.abandon_reason):
                    open(stop, "w").close()
                    stop_at = time.time()
                    self.set_status("stopping", "Saving progress and stopping")
                if stop_at and time.time() - stop_at > 300:
                    self.log("engine did not stop within 5 minutes; killing it (progress since the last checkpoint is lost)", "warn")
                    run.kill()
                if task["source"] == "ledger" and time.time() >= next_beat and not stop_at:
                    next_beat = time.time() + task.get("heartbeat", 900)
                    self._heartbeat(task)
                time.sleep(1)
        finally:
            # whatever happened above, never leave an engine running unsupervised
            if run.poll() is None:
                open(stop, "w").close()
                try:
                    run.wait(300)
                except Exception:
                    run.kill()
        code = run.wait(30)
        self.run = None
        self.state["engine_pid"] = 0
        try:
            os.remove(stop)
        except OSError:
            pass
        return code, run, stop_at is not None

    def _stopped(self, task, run):
        # we asked it to stop (on Windows a forced kill also exits with 1): a pause, not a failure
        k, n = task["k"], task["n"]
        if self.abandon_reason:
            self.log("abandoned %d*2^%d+1: %s" % (k, n, self.abandon_reason))
            self._drop(task)
        elif (run.last("stopped") or {}).get("phase") == "pm1":
            self.log("paused P-1 on %d*2^%d+1" % (k, n))
        else:
            self.log("paused %d*2^%d+1 at verified iteration %s" % (k, n, (run.last("stopped") or {}).get("iteration", "?")))
        self.restart_requested = False

    # ---------------------------------------------------------------- the Proth test

    def _run_test(self, task, dev):
        k, n = task["k"], task["n"]
        extra = split_args(self.settings.get("extra_args", ""))
        args = ["test", str(k), str(n), "--json", "--event-seconds", "3", "--ckpt", "checkpoints", "--results",
                "engine-results.jsonl", "--stop-file", "stop", "--gerbicz", str(task["gerbicz"])] + Engine.device_args(dev)
        if task.get("N"):
            # pin the transform this number started with, so a rebuilt engine whose automatic
            # choice differs can still continue from the checkpoint
            args += ["--size", str(task["N"]), "--primes", str(task.get("primes", 2))]
        args += extra
        self._begin_live(task, "test")
        self.set_status("running", "Testing %d·2^%d+1 on %s" % (k, n, dev["label"]))
        self.log("starting %d*2^%d+1 on %s (Gerbicz block %d)" % (k, n, dev["label"], task["gerbicz"]))
        code, run, stopped = self._supervise(task, dev, args)
        res = run.last("result")
        if code == 0 and res:
            self._finish(task, dev, res)
        elif code == 3 or stopped:
            self._stopped(task, run)
        elif task.get("N") and run.last("start") is None and not self._size_usable(task):
            # this engine build can't use the transform size the number started with
            self.log("this engine can't continue %d*2^%d+1 with its saved transform size; restarting it with the "
                     "engine's own choice" % (k, n), "warn")
            task.pop("N", None)
            task.pop("primes", None)
            self.save()
        else:
            err = (run.last("error") or {}).get("message") or (run.log[-1] if run.log else "engine exited with status %s" % code)
            task["errors"] = task.get("errors", 0) + 1
            self.log("engine failed on %d*2^%d+1 (%d time(s) in a row): %s" % (k, n, task["errors"], err), "error")
            if task["errors"] >= 3:
                self.log("giving up on %d*2^%d+1 for now" % (k, n), "error")
                self._remember(task, dev, {"result": "", "error": err})
                if task["source"] == "ledger":
                    try:
                        self.client().release(task["assignment"])
                    except (LedgerUnavailable, LedgerRefused):
                        pass
                    self._drop(task)
                else:
                    # keep its checkpoint and move it to the end of the list so the rest can run
                    q = self.state["queue"]
                    if [k, n] in q:
                        q.remove([k, n])
                        q.append([k, n])
                    task["errors"] = 0
                    self.state.setdefault("parked", {})["%d_%d" % (k, n)] = task
                    self._drop(task, keep_checkpoint=True)
            self.set_status("error", "The engine failed: %s. Retrying shortly." % err)
            self.save()
            self.sleep(30)
        self.save()

    def _size_usable(self, task) -> bool:
        try:
            self.engine.info(task["k"], task["n"], ["--size", str(task["N"]), "--primes", str(task.get("primes", 2))])
            return True
        except EngineError:
            return False
        except Exception:
            return True

    def _heartbeat(self, task):
        with self.lock:
            L = dict(self.live)
        if L.get("phase") == "pm1":
            report = {"iteration": int(task.get("test_iteration") or 0), "phase": "pm1"}
        else:
            report = {k: L[k] for k in ("iteration", "ms_per_iter", "checks_passed", "rollbacks") if k in L}
            report["phase"] = "test"
        sent_pm1 = bool(task.get("pm1_report") and isinstance(task.get("pm1"), dict) and task["pm1"].get("b1"))
        if sent_pm1:
            report["pm1"] = {"b1": task["pm1"]["b1"], "b2": task["pm1"]["b2"], "engine": self.engine.version}
        try:
            r = self.client().progress(task["assignment"], report)
            if sent_pm1:
                task["pm1_report"] = False
            self._note_config(r.get("config"))
            if r.get("action") == "abandon":
                self.abandon_reason = r.get("reason", "the project no longer needs it")
            else:
                hb = (r.get("config") or {}).get("heartbeat_seconds")
                if hb:
                    task["heartbeat"] = float(hb)
        except LedgerUnavailable as e:
            self.log("progress report failed (%s); will retry" % e, "warn")
        except LedgerRefused as e:
            if e.status == 404:
                self.abandon_reason = "the ledger has no record of this assignment"
            else:
                self.log("progress report refused: %s" % e, "warn")

    def _finish(self, task, dev, res):
        k, n = task["k"], task["n"]
        self.log("finished %d*2^%d+1: %s, res64 %s, %s" % (k, n, res.get("result"), res.get("res64"), _dur(res.get("seconds", 0))))
        entry = self._remember(task, dev, res)
        if res.get("result") == "PRIME":
            self.prime_alert = {"k": k, "n": n, "at": time.time(), "source": task["source"],
                                "known": [k, n] == list(KNOWN_PRIME), "sierpinski": k in SIERPINSKI_K}
            self.state["prime_alert"] = self.prime_alert
            if [k, n] == list(KNOWN_PRIME):
                self.log("end-to-end check passed: the known prime %d*2^%d+1 was proven prime on %s" % (k, n, dev["label"]))
            else:
                self.log("*** %d*2^%d+1 IS PRIME according to this test. Do not announce it yet: see the app. ***" % (k, n), "warn")
        if task["source"] == "ledger":
            clean = {key: v for key, v in res.items() if not key.startswith("_") and key != "event"}
            self.state["pending"].append({"url": task["url"], "assignment": task["assignment"], "result": clean, "history_at": entry["at"]})
            self.next_upload = 0
        if task["source"] == "local" and self.state["queue"] and self.state["queue"][0] == [k, n]:
            self.state["queue"].pop(0)
        self._drop(task)
        self._upload_pending()

    def _remember(self, task, dev, res) -> Dict[str, Any]:
        entry = {"k": task["k"], "n": task["n"], "result": res.get("result", ""), "res64": res.get("res64", ""), "factor": res.get("factor", ""),
                 "seconds": res.get("seconds", 0), "rollbacks": res.get("rollbacks", 0), "engine": res.get("engine", ""),
                 "device": dev["label"], "source": task["source"], "kind": task.get("kind", ""), "at": time.time(),
                 "ledger": "uploading" if task["source"] == "ledger" and res.get("result") else "", "error": res.get("error", "")}
        self.state["history"] = (self.state["history"] + [entry])[-500:]
        return entry

    def _drop(self, task, keep_checkpoint: bool = False):
        # save first: a crash in between must not leave a task whose checkpoint is gone
        self.state["current"] = None
        self.abandon_reason = ""
        self.save()
        if keep_checkpoint:
            return
        for suffix in (".ckpt", ".ckpt.tmp", ".ckpt.rejected", ".pm1", ".pm1.tmp", ".pm1.rejected"):
            p = self.path("checkpoints", "%d_%d%s" % (task["k"], task["n"], suffix))
            try:
                os.remove(p)
            except OSError:
                pass

    def _upload_pending(self):
        if not self.state["pending"] or time.time() < self.next_upload:
            return
        keep = []
        for p in self.state["pending"]:
            cred = self.settings["credentials"].get(p["url"], {})
            c = LedgerClient(p["url"], cred.get("worker_id", ""), cred.get("token", ""))
            outcome = None
            try:
                r = c.result(p["assignment"], p["result"])
                outcome = r.get("status", "accepted")
                what = {"done": "accepted", "verified": "confirmed by another computer",
                        "factored": "factor accepted: the number is settled without a test",
                        "awaiting_dc": "accepted; another computer will double-check it",
                        "conflict": "it disagrees with another computer's result; a third will break the tie"}.get(outcome, outcome)
                self.log("%s for %d*2^%d+1: %s" % ("factor" if "factor" in p["result"] else "result", p["result"]["k"], p["result"]["n"], what))
            except LedgerUnavailable as e:
                keep.append(p)
                self.next_upload = time.time() + e.retry_after
                self.log("result upload will be retried: %s" % e, "warn")
            except LedgerRefused as e:
                outcome = "refused: %s" % e
                self.log("the ledger refused a result: %s" % e, "error")
            if outcome:
                for h in self.state["history"]:
                    if h.get("at") == p.get("history_at") and (h["k"], h["n"]) == (p["result"]["k"], p["result"]["n"]):
                        h["ledger"] = outcome
        self.state["pending"] = keep
        self.save()

    def _poll_project(self):
        while not self.quit_event.is_set():
            if self.settings["mode"] == "ledger" and self.settings.get("ledger_url"):
                try:
                    self.project = self.client().status()
                    self.project["_at"] = time.time()
                except (LedgerUnavailable, LedgerRefused) as e:
                    self.project = dict(self.project, _error=str(e))
            self.quit_event.wait(600)

    # ------------------------------------------------------------------ user actions (web/CLI threads)

    def do_start(self):
        self.wanted = True
        self.settings["autostart"] = True
        self.save()
        self.wake.set()

    def do_pause(self):
        self.wanted = False
        self.settings["autostart"] = False
        self.save()
        self.wake.set()

    def do_settings(self, changes: Dict[str, Any]) -> Dict[str, Any]:
        bad = [k for k in changes if k not in EDITABLE]
        if bad:
            raise ValueError("unknown setting(s): %s" % ", ".join(bad))
        with self.lock:
            before = dict(self.settings)
            for k, v in changes.items():
                if k in ("cpu_threads",):
                    v = max(0, min(1024, int(v)))
                elif k == "checkpoint_minutes":
                    v = max(1.0, min(240.0, float(v)))
                elif k in ("autostart", "pm1"):
                    v = bool(v)
                elif k == "sieve_bits":
                    v = max(0.0, min(80.0, float(v)))
                elif k == "mode":
                    if v not in ("ledger", "local"):
                        raise ValueError("mode must be ledger or local")
                else:
                    v = str(v).strip()
                if k == "extra_args":
                    split_args(v)                    # raises on unbalanced quotes
                self.settings[k] = v
            if self.settings["mode"] != before["mode"] or self.settings["ledger_url"] != before["ledger_url"]:
                # the loop thread parks or hands back the current number once the engine has stopped
                self.source_changed = True
                self.restart_requested = bool(self.run)
            if any(self.settings[k] != before[k] for k in ("device", "cpu_threads", "extra_args", "engine_path")):
                self.restart_requested = True
            self.save()
        if self.settings["engine_path"] != before["engine_path"]:
            self.load_engine()
        self.wake.set()
        return self.public_settings()

    def _apply_source_change(self):
        """Runs on the loop thread, with no engine running: the user switched between their own
        list and the project (or to another ledger)."""
        self.source_changed = False
        cur = self.state.get("current")
        if not cur:
            return
        mode, url = self.settings["mode"], self.settings.get("ledger_url", "")
        if cur["source"] == "local" and mode == "local":
            return
        if cur["source"] == "ledger" and mode == "ledger" and cur["url"] == url:
            return
        if cur["source"] == "local":
            # park it with everything needed to resume its checkpoint later
            key = "%d_%d" % (cur["k"], cur["n"])
            self.state.setdefault("parked", {})[key] = cur
            if [cur["k"], cur["n"]] not in self.state["queue"]:
                self.state["queue"].insert(0, [cur["k"], cur["n"]])
            self.state["current"] = None
            self.save()
            self.log("set %d*2^%d+1 aside; it resumes when you switch back to your list" % (cur["k"], cur["n"]))
            return
        try:
            cred = self.settings["credentials"].get(cur["url"], {})
            LedgerClient(cur["url"], cred.get("worker_id", ""), cred.get("token", "")).release(cur["assignment"])
            self.log("handed %d*2^%d+1 back to the project" % (cur["k"], cur["n"]))
        except (LedgerUnavailable, LedgerRefused) as e:
            self.log("could not hand the assignment back (%s); it will expire on its own" % e, "warn")
        self._drop(cur)

    def do_join(self, url: str, owner: str, invite: str = "") -> Dict[str, Any]:
        url = url.strip().rstrip("/")
        if not re.match(r"^https?://", url):
            raise ValueError("the ledger address must start with https://")
        status = LedgerClient(url).status()              # raises if unreachable
        self.do_settings({"ledger_url": url, "owner": owner.strip()[:40], "invite": invite.strip(), "mode": "ledger"})
        self.project = dict(status, _at=time.time())
        return status

    def do_add(self, text: str) -> int:
        pairs = parse_numbers(text)
        with self.lock:
            have = {tuple(p) for p in self.state["queue"]}
            added = [p for p in pairs if tuple(p) not in have]
            self.state["queue"] += added
            self.save()
        self.wake.set()
        return len(added)

    def do_clear_queue(self):
        with self.lock:
            cur = self.state.get("current")
            self.state["queue"] = [q for q in self.state["queue"] if cur and q == [cur["k"], cur["n"]]]
            self.save()

    def do_validate(self, device_id: str = "all"):
        """Forget and redo the checks. If a test is running it pauses, and resumes afterwards."""
        self.load_engine()
        with self.lock:
            for d in self.devices:
                if device_id in ("all", d["id"]):
                    self.settings["validated"].pop(self.vkey(d), None)
            self.save()
        self.restart_requested = bool(self.run)
        self.validate_request = True
        self.wake.set()

    def do_dismiss_prime(self):
        self.prime_alert = None
        self.state.pop("prime_alert", None)
        self.save()

    def do_build(self) -> str:
        if not can_build_from_source():
            raise ValueError("building needs a source checkout with a Makefile")
        self.log("building the engine from source (make colbert colbert-cpu)")
        p = subprocess.run(["make", "colbert", "colbert-cpu"], cwd=repo_root(), capture_output=True, text=True, timeout=1800)
        for line in (p.stdout + p.stderr).splitlines()[-40:]:
            self.logbuf.append("make: " + line)
        if p.returncode != 0:
            raise ValueError("build failed; see the Log tab")
        self.load_engine()
        self.wake.set()
        return self.engine.version if self.engine else ""

    # ------------------------------------------------------------------ views

    def public_settings(self) -> Dict[str, Any]:
        s = {k: self.settings[k] for k in EDITABLE}
        cred = self.settings["credentials"].get(self.settings.get("ledger_url", ""), {})
        s["worker_id"] = cred.get("worker_id", "")
        return s

    def snapshot(self) -> Dict[str, Any]:
        with self.lock:
            L = dict(self.live)
            cur = self.state.get("current")
            now = time.time()
            eta = None
            if cur and L.get("total"):
                ms = self.ewma or L.get("ms_per_iter_recent") or L.get("ms_per_iter") or 0
                if ms:
                    eta = ms * max(0, L["total"] - L.get("iteration", 0)) / 1000
            devs = []
            for d in self.devices:
                v = self.validation_of(d) if self.engine else None
                devs.append({"id": d["id"], "label": d["label"], "type": d["type"], "backend": d["backend"], "validation": v,
                             "in_use": bool(self.device and self.device["id"] == d["id"] and self.run)})
            rate = list(self.rate)
            step = max(1, len(rate) // 300)
            return {
                "app_version": VERSION, "status": self.status, "status_text": self.status_text, "wanted": self.wanted,
                "engine": {"path": self.engine.path, "version": self.engine.version, "protocol": self.engine.protocol,
                           "backends": self.engine.backends} if self.engine else None,
                "engine_error": self.engine_error, "can_build": can_build_from_source(),
                "task": cur, "digits": int(cur["n"] * 0.30103 + len(str(cur["k"]))) if cur else None,
                "live": {k: v for k, v in L.items() if k != "key"}, "eta_seconds": eta, "now": now,
                "rate": [[round(t, 1), round(r, 5)] for t, r, _ in rate[::step]],
                "device": {"id": self.device["id"], "label": self.device["label"]} if self.device else None,
                "devices": devs, "validation": dict(self.validation),
                "settings": self.public_settings(), "queue": self.state["queue"][:200], "queue_len": len(self.state["queue"]),
                "history": list(reversed(self.state["history"][-100:])), "pending_uploads": len(self.state["pending"]),
                "project": {k: v for k, v in self.project.items()}, "ledger_note": self.ledger_note,
                "log": list(self.logbuf)[-300:], "prime_alert": self.prime_alert, "known_prime": list(KNOWN_PRIME),
            }


def _dur(s: float) -> str:
    s = float(s or 0)
    if s < 90:
        return "%d s" % s
    if s < 5400:
        return "%d min" % (s / 60)
    if s < 172800:
        return "%.1f h" % (s / 3600)
    return "%.1f days" % (s / 86400)
