"""Where the app keeps its files, and where it looks for the engine."""
from __future__ import annotations

import hashlib
import os
import shutil
import sys
from typing import List

EXE = ".exe" if os.name == "nt" else ""
FROZEN = bool(getattr(sys, "frozen", False))            # a downloaded app (PyInstaller), not a checkout
MAC_APP = FROZEN and sys.platform == "darwin"


def data_dir(override: str = "") -> str:
    """Per-user data directory: settings, checkpoints, results, logs. COLBERT_DATA overrides."""
    d = override or os.environ.get("COLBERT_DATA", "")
    if not d:
        if sys.platform == "darwin":
            d = os.path.expanduser("~/Library/Application Support/Colbert")
        elif os.name == "nt":
            d = os.path.join(os.environ.get("APPDATA") or os.path.expanduser("~"), "Colbert")
        else:
            d = os.path.join(os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share"), "colbert")
    d = os.path.abspath(os.path.expanduser(d))
    os.makedirs(d, exist_ok=True)
    return d


def app_root() -> str:
    """Directory holding the bundled engine: next to the frozen executable, or app/ in a checkout."""
    if FROZEN:
        return getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def repo_root() -> str:
    return os.path.dirname(app_root())


def _digest(path: str) -> str:
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def private_engine_dir(data: str) -> str:
    """macOS app: run the engine from a copy in the data folder, not from inside the app.

    Everything unpacked from a download carries macOS's quarantine flag, and Gatekeeper can
    stop a flagged helper program on its own even after the person allowed the app. A copy
    the app writes itself has no flag. The copy is refreshed whenever the bundled engine
    differs, so an updated app brings its engine with it. Returns "" if there is nothing to copy."""
    src = os.path.join(app_root(), "engine")
    if not MAC_APP or not os.path.isdir(src):
        return ""
    dst = os.path.join(data, "engine")
    os.makedirs(dst, exist_ok=True)
    for name in sorted(os.listdir(src)):
        s, t = os.path.join(src, name), os.path.join(dst, name)
        if not os.path.isfile(s):
            continue
        try:
            if os.path.isfile(t) and os.path.getsize(t) == os.path.getsize(s) and _digest(t) == _digest(s):
                continue
            tmp = t + ".new"
            shutil.copyfile(s, tmp)              # contents only: no quarantine flag
            os.chmod(tmp, 0o755)
            os.replace(tmp, t)
        except OSError:
            return ""                            # fall back to the bundled copy
    return dst


def engine_candidates(configured: str = "", data: str = "") -> List[str]:
    """Engine binaries to try, best first. Each directory may also hold a CPU-only build
    (colbert-cpu), used when the OpenCL loader library is missing and `colbert` can't start."""
    out: List[str] = []
    for p in (configured, os.environ.get("COLBERT_ENGINE", "")):
        if p:
            out.append(os.path.abspath(os.path.expanduser(p)))
    dirs = [os.path.join(app_root(), "engine"), repo_root()]
    private = private_engine_dir(data) if data else ""
    if private:
        dirs.insert(0, private)
    for d in dirs:
        out += [os.path.join(d, "colbert" + EXE), os.path.join(d, "colbert-cpu" + EXE)]
    found = shutil.which("colbert")
    if found:
        out.append(found)
    seen, uniq = set(), []
    for p in out:
        if p not in seen:
            seen.add(p)
            uniq.append(p)
    return uniq


def can_build_from_source() -> bool:
    return not FROZEN and os.path.exists(os.path.join(repo_root(), "Makefile")) and os.path.isdir(os.path.join(repo_root(), "src"))
