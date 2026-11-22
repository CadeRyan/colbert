"""
The colbert engine, driven only through its machine interface (docs/ENGINE_PROTOCOL.md):
`--json` events on stdout, exit codes, and --stop-file. Nothing here parses human-readable
output, so tuning the engine cannot break the app unless it breaks that contract, which
`tools/check_protocol.py` (run by `make check`) guards.
"""
from __future__ import annotations

import json
import os
import shlex
import subprocess
import sys
import threading
import time
from typing import Any, Callable, Dict, List, Optional

from . import ENGINE_PROTOCOLS

IS_WIN = os.name == "nt"
# Windows: no console window, and below-normal priority so the computer stays responsive
_WIN_FLAGS = (0x08000000 | 0x00004000) if IS_WIN else 0


def _lower_priority():                      # POSIX preexec_fn
    try:
        os.nice(10)
    except OSError:
        pass


class EngineError(RuntimeError):
    pass


class Engine:
    """One engine binary. `probe()` checks it runs and speaks a protocol this app knows."""

    def __init__(self, path: str):
        self.path = path
        self.version = ""
        self.protocol = 0
        self.backends: List[str] = []
        self.features: List[str] = []

    def _run(self, args: List[str], timeout: float, env=None) -> subprocess.CompletedProcess:
        return subprocess.run([self.path] + args, capture_output=True, text=True, timeout=timeout,
                              creationflags=_WIN_FLAGS, env=env)

    @staticmethod
    def events(stdout: str) -> List[Dict[str, Any]]:
        out = []
        for line in stdout.splitlines():
            line = line.strip()
            if line.startswith("{"):
                try:
                    out.append(json.loads(line))
                except ValueError:
                    pass
        return out

    def probe(self) -> "Engine":
        if not os.path.isfile(self.path):
            raise EngineError("not found: %s" % self.path)
        try:
            p = self._run(["version", "--json"], timeout=30)
        except OSError as e:          # e.g. missing shared library on some systems, wrong architecture
            raise EngineError("cannot start %s: %s" % (self.path, e))
        except subprocess.TimeoutExpired:
            raise EngineError("%s did not answer `version`" % self.path)
        ev = next((e for e in self.events(p.stdout) if e.get("event") == "version"), None)
        if p.returncode != 0 or not ev:
            hint = (p.stderr or "").strip().splitlines()[-1:] or ["no output"]
            raise EngineError("%s does not support `version --json` (too old, or it failed to start: %s)" % (self.path, hint[0]))
        self.version = str(ev.get("version", "unknown"))
        self.protocol = int(ev.get("protocol", 0))
        self.backends = list(ev.get("backends", []))
        self.features = list(ev.get("features", []))
        if self.protocol not in ENGINE_PROTOCOLS:
            raise EngineError("engine speaks protocol %d; this app understands %s. Update the %s."
                              % (self.protocol, list(ENGINE_PROTOCOLS), "app" if self.protocol > max(ENGINE_PROTOCOLS) else "engine"))
        return self

    def devices(self) -> List[Dict[str, Any]]:
        """Devices this engine can use. Always includes the built-in CPU engine."""
        out = [{"id": "cpu", "backend": "cpu", "index": None, "type": "CPU", "name": "Built-in CPU engine",
                "label": "CPU (built-in engine, %d threads)" % (os.cpu_count() or 1), "key": "cpu", "detail": {}}]
        if "ocl" not in self.backends:
            return out
        try:
            p = self._run(["devices", "--json"], timeout=60)
            ev = next((e for e in self.events(p.stdout) if e.get("event") == "devices"), {})
        except (OSError, subprocess.TimeoutExpired):
            ev = {}
        for d in ev.get("devices", []):
            kind = d.get("type", "other")
            label = d.get("name", "OpenCL device")
            if kind == "GPU":
                label += " (integrated GPU)" if d.get("unified_memory") else " (GPU)"
            elif kind == "CPU":
                label += " (OpenCL on CPU)"
            out.append({"id": "ocl:%d" % d.get("index", 0), "backend": "ocl", "index": d.get("index", 0), "type": kind,
                        "name": d.get("name", ""), "label": label,
                        "key": "ocl:%s|%s|%s" % (d.get("name", ""), d.get("vendor", ""), d.get("driver", "")), "detail": d})
        return out

    @staticmethod
    def device_args(dev: Dict[str, Any]) -> List[str]:
        if dev["backend"] == "cpu":
            return ["--backend", "cpu"]
        return ["--backend", "ocl", "--device", str(dev["index"])]

    def info(self, k: int, n: int, extra: List[str] = ()) -> Dict[str, Any]:
        p = self._run(["info", str(k), str(n), "--json"] + list(extra), timeout=60)
        ev = self.events(p.stdout)
        if p.returncode != 0 or not ev or ev[-1].get("event") != "info":
            msg = ev[-1].get("message") if ev and ev[-1].get("event") == "error" else (p.stderr.strip() or "info failed")
            raise EngineError(msg)
        return ev[-1]

    def process(self, args: List[str], env: Dict[str, str], cwd: str) -> "Run":
        return Run(self.path, args, env, cwd)


class Run:
    """A running engine command. Events and stderr lines arrive on reader threads."""

    def __init__(self, path: str, args: List[str], env: Dict[str, str], cwd: str):
        full_env = dict(os.environ)
        full_env.update(env)
        self.args = args
        self.events: List[Dict[str, Any]] = []
        self.log: List[str] = []
        self.on_event: Optional[Callable[[Dict[str, Any]], None]] = None
        self.on_log: Optional[Callable[[str], None]] = None
        self.lock = threading.Lock()
        self.proc = subprocess.Popen([path] + args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.DEVNULL,
                                     text=True, bufsize=1, cwd=cwd, env=full_env, creationflags=_WIN_FLAGS,
                                     preexec_fn=None if IS_WIN else _lower_priority)
        self.t_out = threading.Thread(target=self._read_out, daemon=True)
        self.t_err = threading.Thread(target=self._read_err, daemon=True)
        self.t_out.start()
        self.t_err.start()

    @property
    def pid(self) -> int:
        return self.proc.pid

    def _read_out(self):
        for line in self.proc.stdout:
            line = line.strip()
            if not line.startswith("{"):
                continue
            try:
                ev = json.loads(line)
            except ValueError:
                continue
            ev["_t"] = time.time()
            with self.lock:
                self.events.append(ev)
                if len(self.events) > 2000:
                    del self.events[:1000]
            if self.on_event:
                try:
                    self.on_event(ev)
                except Exception as e:      # never let a UI problem kill the reader
                    print("event handler error: %r" % e, file=sys.stderr)

    def _read_err(self):
        for line in self.proc.stderr:
            line = line.rstrip()
            if not line:
                continue
            with self.lock:
                self.log.append(line)
                if len(self.log) > 2000:
                    del self.log[:1000]
            if self.on_log:
                self.on_log(line)

    def poll(self) -> Optional[int]:
        return self.proc.poll()

    def wait(self, timeout: Optional[float] = None) -> int:
        code = self.proc.wait(timeout)
        self.t_out.join(5)
        self.t_err.join(5)
        return code

    def kill(self):
        try:
            self.proc.kill()
        except OSError:
            pass

    def last(self, kind: str) -> Optional[Dict[str, Any]]:
        with self.lock:
            for ev in reversed(self.events):
                if ev.get("event") == kind:
                    return ev
        return None


def split_args(extra: str) -> List[str]:
    """User-supplied extra engine arguments (an advanced setting, for the tuning phase)."""
    if not extra.strip():
        return []
    return shlex.split(extra, posix=not IS_WIN)


def choose_gerbicz(ms_per_iter: float, target_minutes: float, n: int) -> int:
    """Gerbicz block length L. Verified checkpoints come every L*L iterations, and the check
    costs about 2/L of the run, so pick L to checkpoint about every `target_minutes`."""
    default = max(4, min(1000, int(((n - 1) / 2) ** 0.5)))
    if ms_per_iter <= 0:
        return default
    want = (target_minutes * 60 * 1000 / ms_per_iter) ** 0.5
    return int(max(16, min(default, round(want))))


def process_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    if IS_WIN:
        try:
            out = subprocess.run(["tasklist", "/FI", "PID eq %d" % pid, "/NH"], capture_output=True, text=True,
                                 creationflags=0x08000000, timeout=10).stdout
            return str(pid) in out and "colbert" in out.lower()
        except (OSError, subprocess.TimeoutExpired):
            return False
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    try:
        name = subprocess.run(["ps", "-p", str(pid), "-o", "comm="], capture_output=True, text=True, timeout=10).stdout
        return "colbert" in name
    except (OSError, subprocess.TimeoutExpired):
        return True


def kill_pid(pid: int):
    try:
        if IS_WIN:
            subprocess.run(["taskkill", "/PID", str(pid), "/F"], capture_output=True, creationflags=0x08000000, timeout=10)
        else:
            os.kill(pid, 9)
    except (OSError, subprocess.TimeoutExpired):
        pass
