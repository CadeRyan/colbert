"""Where the app keeps its files, and where it looks for the engine."""
from __future__ import annotations

import os
import shutil
import sys
from typing import List

EXE = ".exe" if os.name == "nt" else ""


def data_dir(override: str = "") -> str:
    """Per-user data directory: settings, checkpoints, results, logs."""
    if override:
        d = override
    elif sys.platform == "darwin":
        d = os.path.expanduser("~/Library/Application Support/Colbert")
    elif os.name == "nt":
        d = os.path.join(os.environ.get("APPDATA") or os.path.expanduser("~"), "Colbert")
    else:
        d = os.path.join(os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share"), "colbert")
    os.makedirs(d, exist_ok=True)
    return d


def app_root() -> str:
    """Directory holding the bundled engine: next to the frozen executable, or app/ in a checkout."""
    if getattr(sys, "frozen", False):
        return getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def repo_root() -> str:
    return os.path.dirname(app_root())


def engine_candidates(configured: str = "") -> List[str]:
    """Engine binaries to try, best first. Each directory may also hold a CPU-only build
    (colbert-cpu), used when the OpenCL loader library is missing and `colbert` can't start."""
    out: List[str] = []
    for p in (configured, os.environ.get("COLBERT_ENGINE", "")):
        if p:
            out.append(os.path.abspath(os.path.expanduser(p)))
    for d in (os.path.join(app_root(), "engine"), repo_root()):
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
    return os.path.exists(os.path.join(repo_root(), "Makefile")) and os.path.isdir(os.path.join(repo_root(), "src"))
