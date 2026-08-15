from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MARKER = "KAYI always-transparent walls runtime hotfix 20260815"
VERSION = "20260815-1906-transparent"


def patch_runtime_js() -> None:
    path = ROOT / "static" / "js" / "room-planner.js"
    if not path.exists():
        raise RuntimeError("Room Planner runtime JS is missing")
    text = path.read_text(encoding="utf-8")
    if MARKER not in text:
        addition = f'''\n\n// {MARKER}\n(() => {{\n  const forceAlwaysTransparentWalls = () => {{\n    state.view ||= {{}};\n    state.view.transparent_near_walls = true;\n    wallMeshes.forEach((wall) => {{\n      const mat = wall?.material;\n      if (!mat) return;\n      mat.transparent = true;\n      mat.opacity = 0.08;\n      mat.depthWrite = false;\n      mat.side = THREE.DoubleSide;\n      if (mat.color?.setHex) mat.color.setHex(0xf5f6f7);\n      mat.needsUpdate = true;\n    }});\n  }};\n\n  // Override every older camera-dependent wall visibility rule.\n  updateWallTransparency = forceAlwaysTransparentWalls;\n  forceAlwaysTransparentWalls();\n  document.querySelector('[data-rp-toggle="transparent_near_walls"]')?.remove();\n  queueRender();\n}})();\n'''
        path.write_text(text.rstrip() + addition, encoding="utf-8")


def patch_template() -> None:
    path = ROOT / "templates" / "rebuild" / "room_planner.html"
    if not path.exists():
        raise RuntimeError("Room Planner template is missing")
    text = path.read_text(encoding="utf-8")

    # The wall transparency is no longer optional: remove the obsolete control.
    text = re.sub(
        r'<button[^>]*data-rp-toggle=["\']transparent_near_walls["\'][^>]*>.*?</button>',
        "",
        text,
        count=1,
        flags=re.DOTALL,
    )

    # Force browsers/PWA clients to request the new module instead of a cached copy.
    text, count = re.subn(
        r"(\{%\s*static\s+'js/room-planner\.js'\s*%\}\?v=)[^\"']+",
        rf"\g<1>{VERSION}",
        text,
        count=1,
    )
    if count != 1:
        raise RuntimeError("Could not cache-bust Room Planner JS in template")
    path.write_text(text, encoding="utf-8")


def guard() -> None:
    js = (ROOT / "static" / "js" / "room-planner.js").read_text(encoding="utf-8")
    template = (ROOT / "templates" / "rebuild" / "room_planner.html").read_text(encoding="utf-8")
    required = [MARKER, "mat.opacity = 0.08", "mat.depthWrite = false", "updateWallTransparency = forceAlwaysTransparentWalls"]
    for needle in required:
        if needle not in js:
            raise RuntimeError(f"Room wall transparency hotfix missing: {needle}")
    if 'data-rp-toggle="transparent_near_walls"' in template:
        raise RuntimeError("Legacy wall transparency toggle is still present")
    if f"room-planner.js' %}}?v={VERSION}" not in template:
        raise RuntimeError("Room Planner JS cache-bust was not applied")


patch_runtime_js()
patch_template()
guard()
print("Room Planner walls forced to 8% opacity in the assembled production runtime.")
