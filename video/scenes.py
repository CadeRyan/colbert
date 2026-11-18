"""Entry point for manim: `manim render video/scenes.py S01ColdOpen`."""
import os, sys, importlib
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from manim import Scene

for _mod in ("film.scenes_a", "film.scenes_b", "film.scenes_c"):
    try:
        _m = importlib.import_module(_mod)
    except ModuleNotFoundError as e:
        if e.name == _mod:
            continue
        raise
    for _name, _obj in vars(_m).items():
        if isinstance(_obj, type) and issubclass(_obj, Scene) and getattr(_obj, "SCENE_ID", ""):
            # manim only lists scenes defined in this module
            globals()[_name] = type(_name, (_obj,), {"__module__": __name__})

# master renders: higher-quality H.264 than manim's default (crf 23)
if os.environ.get("COLBERT_MASTER") == "1":
    from manim import config as _config
    _config.video_encoder_options = {"crf": "16", "preset": "medium"}
