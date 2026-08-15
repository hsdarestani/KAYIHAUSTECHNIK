from __future__ import annotations

import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MARKER = "KAYI always-transparent walls runtime hotfix 20260815"
VERSION = "20260815-1906-transparent"
RENOVATION_MARKER = "KAYI renovation semantics state 20260815"


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

    text = re.sub(
        r'<button[^>]*data-rp-toggle=["\']transparent_near_walls["\'][^>]*>.*?</button>',
        "",
        text,
        count=1,
        flags=re.DOTALL,
    )

    text, count = re.subn(
        r"(\{%\s*static\s+'js/room-planner\.js'\s*%\}\?v=)[^\"']+",
        rf"\g<1>{VERSION}",
        text,
        count=1,
    )
    if count != 1:
        raise RuntimeError("Could not cache-bust Room Planner JS in template")
    path.write_text(text, encoding="utf-8")


def patch_room_ai_runtime() -> None:
    source = ROOT / "overlays" / "customer_3d_polish" / "erp" / "services" / "room_ai.py"
    target = ROOT / "erp" / "services" / "room_ai.py"
    if not source.exists():
        raise RuntimeError("Renovation-aware Room AI source is missing")
    if not target.parent.exists():
        raise RuntimeError("Assembled Room AI service directory is missing")
    shutil.copy2(source, target)


def patch_room_state_renovation() -> None:
    path = ROOT / "erp" / "services" / "room_planner_state.py"
    if not path.exists():
        raise RuntimeError("Assembled Room Planner state service is missing")
    text = path.read_text(encoding="utf-8")
    if RENOVATION_MARKER in text:
        return

    confidence_anchor = '''def _confidence(value: Any) -> str:\n    try:\n        return str(_decimal(value if value is not None else 1, "confidence", maximum=Decimal("1")))\n    except ValidationError:\n        return "0.500"\n\n\n'''
    if confidence_anchor not in text:
        raise RuntimeError("Could not locate Room Planner confidence helper for renovation state patch")

    helper = f'''# {RENOVATION_MARKER}\ndef _normalize_renovation(raw: Any) -> dict[str, Any]:\n    source = raw if isinstance(raw, dict) else {{}}\n    intent = source.get("intent") if isinstance(source.get("intent"), dict) else {{}}\n    surfaces = source.get("surface_plan") if isinstance(source.get("surface_plan"), dict) else {{}}\n    scope = source.get("work_scope") if isinstance(source.get("work_scope"), dict) else {{}}\n\n    def section(name: str) -> dict[str, Any]:\n        value = surfaces.get(name)\n        return value if isinstance(value, dict) else {{}}\n\n    def number(value: Any, minimum: float = 0.0, maximum: float = 500.0) -> float | None:\n        if value is None or value == "":\n            return None\n        try:\n            parsed = float(value)\n        except (TypeError, ValueError):\n            return None\n        if parsed < minimum or parsed > maximum:\n            return None\n        return round(parsed, 3)\n\n    def text_value(value: Any, limit: int = 300) -> str | None:\n        if value is None:\n            return None\n        cleaned = str(value).strip()\n        return cleaned[:limit] if cleaned else None\n\n    floor = section("floor")\n    wet_zone = section("wet_zone")\n    other_walls = section("other_walls")\n    ceiling = section("ceiling")\n    applies_to = [\n        str(item) for item in (wet_zone.get("applies_to") or [])\n        if str(item) in ALLOWED_WALLS\n    ][:4]\n\n    return {{\n        "intent": {{\n            "preserve_positions": bool(intent.get("preserve_positions", True)),\n            "allow_relayout": bool(intent.get("allow_relayout", False)),\n            "replace_sanitary_in_place": bool(intent.get("replace_sanitary_in_place", False)),\n        }},\n        "surface_plan": {{\n            "floor": {{\n                "remove_existing": bool(floor.get("remove_existing", False)),\n                "finish": text_value(floor.get("finish")),\n                "tile_color": text_value(floor.get("tile_color"), 80),\n                "tile_width_cm": number(floor.get("tile_width_cm"), 1, 300),\n                "tile_height_cm": number(floor.get("tile_height_cm"), 1, 300),\n            }},\n            "wet_zone": {{\n                "present": bool(wet_zone.get("present", False)),\n                "height_m": number(wet_zone.get("height_m"), 0, 12),\n                "wall_tile_color": text_value(wet_zone.get("wall_tile_color"), 80),\n                "tile_width_cm": number(wet_zone.get("tile_width_cm"), 1, 300),\n                "tile_height_cm": number(wet_zone.get("tile_height_cm"), 1, 300),\n                "applies_to": applies_to,\n                "basis": text_value(wet_zone.get("basis"), 500),\n            }},\n            "other_walls": {{\n                "height_m": number(other_walls.get("height_m"), 0, 12),\n                "wall_tile_color": text_value(other_walls.get("wall_tile_color"), 80),\n                "tile_width_cm": number(other_walls.get("tile_width_cm"), 1, 300),\n                "tile_height_cm": number(other_walls.get("tile_height_cm"), 1, 300),\n                "upper_finish": text_value(other_walls.get("upper_finish"), 300),\n            }},\n            "ceiling": {{\n                "finish": text_value(ceiling.get("finish"), 300),\n            }},\n        }},\n        "work_scope": {{\n            "remove_old_wall_coverings": bool(scope.get("remove_old_wall_coverings", False)),\n            "remove_old_floor_coverings": bool(scope.get("remove_old_floor_coverings", False)),\n            "door_finish": text_value(scope.get("door_finish"), 300),\n            "replace_bathtub": bool(scope.get("replace_bathtub", False)),\n            "replace_toilet": bool(scope.get("replace_toilet", False)),\n            "replace_sink": bool(scope.get("replace_sink", False)),\n            "replace_shower": bool(scope.get("replace_shower", False)),\n            "notes": [str(item)[:300] for item in (scope.get("notes") or [])[:20]],\n        }},\n        "source_command": str(source.get("source_command") or "")[:4000],\n    }}\n\n\n'''
    text = text.replace(confidence_anchor, confidence_anchor + helper, 1)

    blank_anchor = '        "objects": [],\n        "materials": {\n'
    if blank_anchor not in text:
        raise RuntimeError("Could not add renovation defaults to blank room state")
    text = text.replace(
        blank_anchor,
        '        "objects": [],\n        "renovation": _normalize_renovation({}),\n        "materials": {\n',
        1,
    )

    upgrade_anchor = '    result["objects"] = deepcopy(state.get("objects") or [])\n    result["schema_version"] = SCHEMA_VERSION\n'
    if upgrade_anchor not in text:
        raise RuntimeError("Could not preserve renovation data during state upgrade")
    text = text.replace(
        upgrade_anchor,
        '    result["objects"] = deepcopy(state.get("objects") or [])\n'
        '    result["renovation"] = _normalize_renovation(deepcopy(state.get("renovation") or {}))\n'
        '    result["schema_version"] = SCHEMA_VERSION\n',
        1,
    )

    return_anchor = '        "objects": objects,\n        "materials": {\n'
    if return_anchor not in text:
        raise RuntimeError("Could not preserve renovation data during state normalization")
    text = text.replace(
        return_anchor,
        '        "objects": objects,\n        "renovation": _normalize_renovation(state.get("renovation")),\n        "materials": {\n',
        1,
    )

    path.write_text(text, encoding="utf-8")


def patch_room_ai_response() -> None:
    path = ROOT / "erp" / "room_planner_views.py"
    if not path.exists():
        raise RuntimeError("Assembled Room Planner view is missing")
    text = path.read_text(encoding="utf-8")
    old = '''        "state": result["state"],\n        "summary": result.get("summary") or "KI-Vorschlag erstellt.",\n        "warnings": result.get("warnings") or [],\n    })\n'''
    new = '''        "state": result["state"],\n        "summary": result.get("summary") or "KI-Vorschlag erstellt.",\n        "warnings": result.get("warnings") or [],\n        "renovation": result.get("renovation") or result["state"].get("renovation", {}),\n    })\n'''
    if new in text:
        return
    if old not in text:
        raise RuntimeError("Could not expose structured renovation result from Room AI endpoint")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def guard() -> None:
    js = (ROOT / "static" / "js" / "room-planner.js").read_text(encoding="utf-8")
    template = (ROOT / "templates" / "rebuild" / "room_planner.html").read_text(encoding="utf-8")
    room_ai = (ROOT / "erp" / "services" / "room_ai.py").read_text(encoding="utf-8")
    room_state = (ROOT / "erp" / "services" / "room_planner_state.py").read_text(encoding="utf-8")
    views = (ROOT / "erp" / "room_planner_views.py").read_text(encoding="utf-8")

    required = [MARKER, "mat.opacity = 0.08", "mat.depthWrite = false", "updateWallTransparency = forceAlwaysTransparentWalls"]
    for needle in required:
        if needle not in js:
            raise RuntimeError(f"Room wall transparency hotfix missing: {needle}")
    if 'data-rp-toggle="transparent_near_walls"' in template:
        raise RuntimeError("Legacy wall transparency toggle is still present")
    if f"room-planner.js' %}}?v={VERSION}" not in template:
        raise RuntimeError("Room Planner JS cache-bust was not applied")

    ai_required = [
        "KAYI-Renovierungsplaner",
        "_replacement_only_guard",
        "surface_plan",
        "work_scope",
        "replace_sanitary_in_place",
        "AM BESTEHENDEN ORT",
    ]
    for needle in ai_required:
        if needle not in room_ai:
            raise RuntimeError(f"Renovation-aware Room AI runtime is missing: {needle}")
    if RENOVATION_MARKER not in room_state or '"renovation": _normalize_renovation' not in room_state:
        raise RuntimeError("Structured renovation state is not persisted by Room Planner")
    if '"renovation": result.get("renovation")' not in views:
        raise RuntimeError("Room AI endpoint does not expose structured renovation result")

    compile(room_ai, str(ROOT / "erp" / "services" / "room_ai.py"), "exec")
    compile(room_state, str(ROOT / "erp" / "services" / "room_planner_state.py"), "exec")
    compile(views, str(ROOT / "erp" / "room_planner_views.py"), "exec")


patch_runtime_js()
patch_template()
patch_room_ai_runtime()
patch_room_state_renovation()
patch_room_ai_response()
guard()
print("Room Planner walls are transparent and Room AI now preserves in-place replacements plus structured renovation scope.")
