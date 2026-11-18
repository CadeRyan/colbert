"""All scenes, in film order."""
import importlib
from ..core import Scene

MODULES = ["story", "how", "idea", "finale"]
ORDER, BY_NAME, BY_ID = [], {}, {}
for _m in MODULES:
    try:
        mod = importlib.import_module(f"toon.scenes.{_m}")
    except ModuleNotFoundError as e:
        if e.name == f"toon.scenes.{_m}":
            continue
        raise
    for _n, _o in vars(mod).items():
        if isinstance(_o, type) and issubclass(_o, Scene) and _o is not Scene and getattr(_o, "ID", "") and getattr(_o, "__module__", "") == mod.__name__:
            BY_NAME[_n] = _o
            BY_ID[_o.ID] = _o
from film.script import SCENES as _S  # noqa: E402
BY_ID.pop("17_credits", None)
BY_ID.update({c.ID: c for n, c in BY_NAME.items() if n != "Thumbnail"})
ORDER = [BY_ID[s["id"]] for s in _S if s["id"] in BY_ID]
