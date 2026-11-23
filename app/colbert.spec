# PyInstaller recipe for the downloadable app (one folder, engine included):
#
#     pyinstaller app/colbert.spec          -> dist/Colbert/ (Windows, Linux) or dist/Colbert.app (macOS)
#
# The engine binaries must already be in app/engine/ (colbert, colbert-cpu and any libraries
# they need beside them); CI puts them there. COLBERT_TARGET_ARCH=universal2 builds a Mac app
# for both Apple Silicon and Intel (Python and the engine must then be universal too).
import os
import re
import sys

HERE = SPECPATH
ENGINE = os.path.join(HERE, "engine")
VERSION = re.search(r'VERSION = "([^"]+)"', open(os.path.join(HERE, "colbert_app", "__init__.py")).read()).group(1)
ICONS = os.path.join(HERE, "icons")

if not os.path.isdir(ENGINE) or not any(f.startswith("colbert") for f in os.listdir(ENGINE)):
    sys.exit("app/engine/ has no engine binaries: build them first (make STATIC=1 colbert colbert-cpu)")

a = Analysis(
    [os.path.join(HERE, "run.py")],
    pathex=[HERE],
    binaries=[(os.path.join(ENGINE, f), "engine") for f in sorted(os.listdir(ENGINE))],
    datas=[(os.path.join(HERE, "colbert_app", "ui"), os.path.join("colbert_app", "ui"))],
    excludes=["tkinter", "unittest", "pydoc", "test"],
)
pyz = PYZ(a.pure)

windowed = sys.platform in ("darwin", "win32")      # Linux keeps its terminal output
exe = EXE(
    pyz, a.scripts, [],
    exclude_binaries=True,
    name="Colbert",
    console=not windowed,
    icon=os.path.join(ICONS, "colbert.ico" if sys.platform == "win32" else "colbert.icns"),
    target_arch=os.environ.get("COLBERT_TARGET_ARCH") or None,
    codesign_identity=os.environ.get("COLBERT_CODESIGN_IDENTITY") or None,   # unset: ad-hoc signed
)
coll = COLLECT(exe, a.binaries, a.datas, name="Colbert")

if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name="Colbert.app",
        icon=os.path.join(ICONS, "colbert.icns"),
        bundle_identifier="ie.cade.colbert",
        version=VERSION,
        info_plist={
            "CFBundleDisplayName": "Colbert",
            "CFBundleShortVersionString": VERSION,
            "CFBundleVersion": VERSION,
            "LSMinimumSystemVersion": "12.0",
            "NSHighResolutionCapable": True,
            "LSApplicationCategoryType": "public.app-category.education",
            "NSHumanReadableCopyright": "Colbert: Proth tests for the Sierpinski problem",
        },
    )
