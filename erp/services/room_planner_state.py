from __future__ import annotations

from copy import deepcopy
from decimal import Decimal, InvalidOperation
from typing import Any

from django.core.exceptions import ValidationError

from erp.models import NativeRoomScan, RoomMeasurement
from erp.services.room_models import initial_room_model_state

SCHEMA_VERSION = 3
ROOM_LIMIT = Decimal("50")

OBJECT_SPECS: dict[str, dict[str, Any]] = {
    "shower": {"label": "Dusche", "category": "sanitary", "anchor": "floor", "size": (1.2, 0.9, 2.1), "color": "#9ed9ea"},
    "vanity": {"label": "Waschtisch", "category": "sanitary", "anchor": "floor", "size": (0.9, 0.5, 0.85), "color": "#d8d0c7"},
    "sink": {"label": "Waschbecken", "category": "sanitary", "anchor": "wall", "size": (0.65, 0.5, 0.25), "color": "#f4f7f8", "elevation": 0.75},
    "toilet": {"label": "WC", "category": "sanitary", "anchor": "floor", "size": (0.42, 0.72, 0.82), "color": "#f6f8f9"},
    "bathtub": {"label": "Badewanne", "category": "sanitary", "anchor": "floor", "size": (1.75, 0.78, 0.62), "color": "#eef3f5"},
    "radiator": {"label": "Heizkörper", "category": "heating", "anchor": "wall", "size": (0.9, 0.12, 0.75), "color": "#e8ecef", "elevation": 0.15},
    "boiler": {"label": "Boiler", "category": "heating", "anchor": "wall", "size": (0.55, 0.35, 0.95), "color": "#edf0f3", "elevation": 1.15},
    "water_heater": {"label": "Warmwasserspeicher", "category": "heating", "anchor": "floor", "size": (0.65, 0.65, 1.55), "color": "#e8edf1"},
    "heat_pump": {"label": "Wärmepumpe", "category": "heating", "anchor": "floor", "size": (0.85, 0.45, 1.35), "color": "#dfe6eb"},
    "cabinet": {"label": "Schrank", "category": "furniture", "anchor": "floor", "size": (0.8, 0.45, 1.8), "color": "#8a6a4d"},
    "wardrobe": {"label": "Kleiderschrank", "category": "furniture", "anchor": "floor", "size": (1.2, 0.6, 2.1), "color": "#9c7d61"},
    "shelf": {"label": "Regal", "category": "furniture", "anchor": "wall", "size": (0.9, 0.25, 0.35), "color": "#9d826b", "elevation": 1.25},
    "table": {"label": "Tisch", "category": "furniture", "anchor": "floor", "size": (1.2, 0.75, 0.76), "color": "#9a7657"},
    "chair": {"label": "Stuhl", "category": "furniture", "anchor": "floor", "size": (0.48, 0.48, 0.9), "color": "#8d755f"},
    "sofa": {"label": "Sofa", "category": "furniture", "anchor": "floor", "size": (2.0, 0.9, 0.82), "color": "#8796a3"},
    "bed": {"label": "Bett", "category": "furniture", "anchor": "floor", "size": (2.0, 1.6, 0.55), "color": "#c6b8a7"},
    "kitchen_base": {"label": "Unterschrank", "category": "kitchen", "anchor": "floor", "size": (0.6, 0.6, 0.9), "color": "#d7d1c8"},
    "kitchen_wall": {"label": "Hängeschrank", "category": "kitchen", "anchor": "wall", "size": (0.6, 0.35, 0.7), "color": "#d7d1c8", "elevation": 1.35},
    "fridge": {"label": "Kühlschrank", "category": "kitchen", "anchor": "floor", "size": (0.6, 0.65, 1.85), "color": "#dbe1e5"},
    "oven": {"label": "Backofen", "category": "kitchen", "anchor": "floor", "size": (0.6, 0.6, 0.9), "color": "#40464d"},
    "stove": {"label": "Kochfeld", "category": "kitchen", "anchor": "floor", "size": (0.6, 0.6, 0.92), "color": "#343a40"},
    "dishwasher": {"label": "Spülmaschine", "category": "kitchen", "anchor": "floor", "size": (0.6, 0.6, 0.86), "color": "#d8dde1"},
    "washing_machine": {"label": "Waschmaschine", "category": "appliance", "anchor": "floor", "size": (0.6, 0.62, 0.86), "color": "#f1f4f6"},
    "dryer": {"label": "Trockner", "category": "appliance", "anchor": "floor", "size": (0.6, 0.62, 0.86), "color": "#eef2f4"},
    "socket": {"label": "Steckdose", "category": "electrical", "anchor": "wall", "size": (0.09, 0.025, 0.09), "color": "#f7f7f4", "elevation": 0.3},
    "switch": {"label": "Schalter", "category": "electrical", "anchor": "wall", "size": (0.09, 0.025, 0.09), "color": "#f7f7f4", "elevation": 1.05},
    "pipe": {"label": "Rohr / Leitung", "category": "technical", "anchor": "wall", "size": (0.08, 0.08, 1.0), "color": "#b7c2ca", "elevation": 0.2},
    "drain": {"label": "Ablauf", "category": "technical", "anchor": "floor", "size": (0.16, 0.16, 0.03), "color": "#7f8b93"},
    "column": {"label": "Stütze / Schacht", "category": "structural", "anchor": "floor", "size": (0.45, 0.45, 2.5), "color": "#c5c9cc"},
    "fixture": {"label": "Objekt", "category": "general", "anchor": "floor", "size": (0.6, 0.6, 0.8), "color": "#aeb9c2"},
}

ALLOWED_KINDS = set(OBJECT_SPECS)
ALLOWED_WALLS = {"back", "left", "right", "front"}
ALLOWED_ANCHORS = {"floor", "wall"}
ALLOWED_OPENINGS = {"door", "window", "opening"}


def _decimal(value: Any, field: str, *, minimum: Decimal = Decimal("0"), maximum: Decimal = ROOM_LIMIT) -> Decimal:
    try:
        number = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValidationError({field: "Ungültiger Zahlenwert."}) from exc
    if not number.is_finite() or number < minimum or number > maximum:
        raise ValidationError({field: f"Wert muss zwischen {minimum} und {maximum} liegen."})
    return number.quantize(Decimal("0.001"))


def _color(value: Any, fallback: str) -> str:
    text = str(value or "").strip()
    if len(text) == 7 and text.startswith("#") and all(c in "0123456789abcdefABCDEF" for c in text[1:]):
        return text.lower()
    return fallback


def _confidence(value: Any) -> str:
    try:
        return str(_decimal(value if value is not None else 1, "confidence", maximum=Decimal("1")))
    except ValidationError:
        return "0.500"


# A+Bau renovation semantics state 20260815
def _normalize_renovation(raw: Any) -> dict[str, Any]:
    source = raw if isinstance(raw, dict) else {}
    intent = source.get("intent") if isinstance(source.get("intent"), dict) else {}
    surfaces = source.get("surface_plan") if isinstance(source.get("surface_plan"), dict) else {}
    scope = source.get("work_scope") if isinstance(source.get("work_scope"), dict) else {}

    def section(name: str) -> dict[str, Any]:
        value = surfaces.get(name)
        return value if isinstance(value, dict) else {}

    def number(value: Any, minimum: float = 0.0, maximum: float = 500.0) -> float | None:
        if value is None or value == "":
            return None
        try:
            parsed = float(value)
        except (TypeError, ValueError):
            return None
        if parsed < minimum or parsed > maximum:
            return None
        return round(parsed, 3)

    def text_value(value: Any, limit: int = 300) -> str | None:
        if value is None:
            return None
        cleaned = str(value).strip()
        return cleaned[:limit] if cleaned else None

    floor = section("floor")
    wet_zone = section("wet_zone")
    other_walls = section("other_walls")
    ceiling = section("ceiling")
    applies_to = [
        str(item) for item in (wet_zone.get("applies_to") or [])
        if str(item) in ALLOWED_WALLS
    ][:4]

    return {
        "intent": {
            "preserve_positions": bool(intent.get("preserve_positions", True)),
            "allow_relayout": bool(intent.get("allow_relayout", False)),
            "replace_sanitary_in_place": bool(intent.get("replace_sanitary_in_place", False)),
        },
        "surface_plan": {
            "floor": {
                "remove_existing": bool(floor.get("remove_existing", False)),
                "finish": text_value(floor.get("finish")),
                "tile_color": text_value(floor.get("tile_color"), 80),
                "tile_width_cm": number(floor.get("tile_width_cm"), 1, 300),
                "tile_height_cm": number(floor.get("tile_height_cm"), 1, 300),
            },
            "wet_zone": {
                "present": bool(wet_zone.get("present", False)),
                "height_m": number(wet_zone.get("height_m"), 0, 12),
                "wall_tile_color": text_value(wet_zone.get("wall_tile_color"), 80),
                "tile_width_cm": number(wet_zone.get("tile_width_cm"), 1, 300),
                "tile_height_cm": number(wet_zone.get("tile_height_cm"), 1, 300),
                "applies_to": applies_to,
                "basis": text_value(wet_zone.get("basis"), 500),
            },
            "other_walls": {
                "height_m": number(other_walls.get("height_m"), 0, 12),
                "wall_tile_color": text_value(other_walls.get("wall_tile_color"), 80),
                "tile_width_cm": number(other_walls.get("tile_width_cm"), 1, 300),
                "tile_height_cm": number(other_walls.get("tile_height_cm"), 1, 300),
                "upper_finish": text_value(other_walls.get("upper_finish"), 300),
            },
            "ceiling": {
                "finish": text_value(ceiling.get("finish"), 300),
            },
        },
        "work_scope": {
            "remove_old_wall_coverings": bool(scope.get("remove_old_wall_coverings", False)),
            "remove_old_floor_coverings": bool(scope.get("remove_old_floor_coverings", False)),
            "door_finish": text_value(scope.get("door_finish"), 300),
            "replace_bathtub": bool(scope.get("replace_bathtub", False)),
            "replace_toilet": bool(scope.get("replace_toilet", False)),
            "replace_sink": bool(scope.get("replace_sink", False)),
            "replace_shower": bool(scope.get("replace_shower", False)),
            "notes": [str(item)[:300] for item in (scope.get("notes") or [])[:20]],
        },
        "source_command": str(source.get("source_command") or "")[:4000],
    }


def object_defaults(kind: str) -> dict[str, Any]:
    spec = OBJECT_SPECS.get(kind, OBJECT_SPECS["fixture"])
    width, depth, height = spec["size"]
    return {
        "kind": kind if kind in ALLOWED_KINDS else "fixture",
        "label": spec["label"],
        "category": spec["category"],
        "anchor": spec["anchor"],
        "wall": "back" if spec["anchor"] == "wall" else "",
        "x_m": "0.500",
        "z_m": "0.500",
        "elevation_m": str(Decimal(str(spec.get("elevation", 0))).quantize(Decimal("0.001"))),
        "width_m": str(Decimal(str(width)).quantize(Decimal("0.001"))),
        "depth_m": str(Decimal(str(depth)).quantize(Decimal("0.001"))),
        "height_m": str(Decimal(str(height)).quantize(Decimal("0.001"))),
        "rotation_deg": "0.000",
        "color": spec["color"],
        "enabled": True,
        "locked": False,
        "source": "manual",
        "confidence": "1.000",
        "evidence": "",
    }


def blank_room_state() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "room": {"length_m": "4.000", "width_m": "3.000", "height_m": "2.500", "wall_thickness_m": "0.120"},
        "openings": [],
        "objects": [],
        "renovation": _normalize_renovation({}),
        "materials": {
            "floor": "#d8d4ce", "wall": "#f2f3f2", "ceiling": "#ffffff", "accent": "#31526b",
            "grout_color": "#c8c8c5", "pattern": "straight", "tile_width_cm": "60.000", "tile_height_cm": "60.000",
        },
        "lighting": {"brightness": "1.100", "warmth": "42.000"},
        "view": {"mode": "perspective", "rotation_deg": "0.000", "show_ceiling": False, "transparent_near_walls": True, "grid": True, "snap": True},
        "calibration": {"scale_verified": False, "method": "manual", "confidence": "1.000", "warnings": []},
    }


def _upgrade_legacy_state(state: dict[str, Any], measurement: RoomMeasurement | None = None, scan: NativeRoomScan | None = None) -> dict[str, Any]:
    if not state:
        if measurement is None:
            return blank_room_state()
        state = initial_room_model_state(measurement, scan)
    result = blank_room_state()
    result["room"].update(deepcopy(state.get("room") or {}))
    result["materials"].update(deepcopy(state.get("materials") or {}))
    result["lighting"].update(deepcopy(state.get("lighting") or {}))
    result["view"].update(deepcopy(state.get("view") or {}))
    result["calibration"].update(deepcopy(state.get("calibration") or {}))
    result["openings"] = deepcopy(state.get("openings") or [])
    result["objects"] = deepcopy(state.get("objects") or [])
    result["renovation"] = _normalize_renovation(deepcopy(state.get("renovation") or {}))
    result["schema_version"] = SCHEMA_VERSION
    return result


def normalize_room_state(state: Any, measurement: RoomMeasurement | None = None, scan: NativeRoomScan | None = None) -> dict[str, Any]:
    if not isinstance(state, dict):
        raise ValidationError({"state": "Modellzustand muss ein JSON-Objekt sein."})
    state = _upgrade_legacy_state(state, measurement, scan)
    room = state.get("room") if isinstance(state.get("room"), dict) else {}
    length = _decimal(room.get("length_m", 4), "room.length_m", minimum=Decimal("0.1"))
    width = _decimal(room.get("width_m", 3), "room.width_m", minimum=Decimal("0.1"))
    height = _decimal(room.get("height_m", 2.5), "room.height_m", minimum=Decimal("0.1"), maximum=Decimal("12"))
    wall_thickness = _decimal(room.get("wall_thickness_m", 0.12), "room.wall_thickness_m", minimum=Decimal("0.04"), maximum=Decimal("0.6"))

    openings: list[dict[str, Any]] = []
    for index, raw in enumerate((state.get("openings") or [])[:120]):
        if not isinstance(raw, dict):
            continue
        kind = str(raw.get("kind") or raw.get("type") or "opening")
        kind = kind if kind in ALLOWED_OPENINGS else "opening"
        wall = str(raw.get("wall") or "back")
        wall = wall if wall in ALLOWED_WALLS else "back"
        wall_length = length if wall in {"left", "right"} else width
        opening_width = _decimal(raw.get("width_m", 0.9), f"openings[{index}].width_m", minimum=Decimal("0.05"), maximum=Decimal("10"))
        opening_width = min(opening_width, wall_length)
        opening_height = _decimal(raw.get("height_m", 2 if kind == "door" else 1), f"openings[{index}].height_m", minimum=Decimal("0.05"), maximum=Decimal("10"))
        sill = _decimal(raw.get("sill_height_m", raw.get("sill_m", 0 if kind == "door" else 0.9)), f"openings[{index}].sill_height_m", maximum=height)
        if sill + opening_height > height:
            opening_height = max(Decimal("0.05"), height - sill)
        maximum_offset = max(Decimal("0.000"), wall_length - opening_width).quantize(Decimal("0.001"))
        offset = min(_decimal(raw.get("offset_m", 0.5), f"openings[{index}].offset_m"), maximum_offset).quantize(Decimal("0.001"))
        openings.append({
            "id": str(raw.get("id") or f"opening-{index + 1}")[:80], "kind": kind, "wall": wall,
            "width_m": str(opening_width), "height_m": str(opening_height), "offset_m": str(offset), "sill_height_m": str(sill),
            "source": str(raw.get("source") or "manual")[:24], "confidence": _confidence(raw.get("confidence")),
            "evidence": str(raw.get("evidence") or "")[:500],
        })

    objects: list[dict[str, Any]] = []
    for index, raw in enumerate((state.get("objects") or [])[:180]):
        if not isinstance(raw, dict):
            continue
        requested_kind = str(raw.get("kind") or raw.get("category") or raw.get("type") or "fixture")
        kind = requested_kind if requested_kind in ALLOWED_KINDS else "fixture"
        defaults = object_defaults(kind)
        anchor = str(raw.get("anchor") or defaults["anchor"])
        anchor = anchor if anchor in ALLOWED_ANCHORS else defaults["anchor"]
        wall = str(raw.get("wall") or defaults["wall"])
        wall = wall if wall in ALLOWED_WALLS else ("back" if anchor == "wall" else "")
        obj_width = _decimal(raw.get("width_m", defaults["width_m"]), f"objects[{index}].width_m", minimum=Decimal("0.02"), maximum=Decimal("10"))
        obj_depth = _decimal(raw.get("depth_m", defaults["depth_m"]), f"objects[{index}].depth_m", minimum=Decimal("0.01"), maximum=Decimal("10"))
        obj_height = _decimal(raw.get("height_m", defaults["height_m"]), f"objects[{index}].height_m", minimum=Decimal("0.02"), maximum=Decimal("10"))
        x = _decimal(raw.get("x_m", defaults["x_m"]), f"objects[{index}].x_m")
        z = _decimal(raw.get("z_m", defaults["z_m"]), f"objects[{index}].z_m")
        elevation = _decimal(raw.get("elevation_m", defaults["elevation_m"]), f"objects[{index}].elevation_m", maximum=height)
        rotation = _decimal(raw.get("rotation_deg", 0), f"objects[{index}].rotation_deg", maximum=Decimal("360"))
        objects.append({
            "id": str(raw.get("id") or f"object-{index + 1}")[:80], "kind": kind,
            "label": str(raw.get("label") or defaults["label"])[:100], "category": str(raw.get("category") or defaults["category"])[:40],
            "anchor": anchor, "wall": wall, "x_m": str(min(x, width)), "z_m": str(min(z, length)), "elevation_m": str(elevation),
            "width_m": str(obj_width), "depth_m": str(obj_depth), "height_m": str(obj_height), "rotation_deg": str(rotation),
            "color": _color(raw.get("color"), defaults["color"]), "enabled": bool(raw.get("enabled", True)), "locked": bool(raw.get("locked", False)),
            "source": str(raw.get("source") or "manual")[:24], "confidence": _confidence(raw.get("confidence")),
            "evidence": str(raw.get("evidence") or "")[:500],
        })

    materials = state.get("materials") if isinstance(state.get("materials"), dict) else {}
    lighting = state.get("lighting") if isinstance(state.get("lighting"), dict) else {}
    view = state.get("view") if isinstance(state.get("view"), dict) else {}
    calibration = state.get("calibration") if isinstance(state.get("calibration"), dict) else {}
    pattern = str(materials.get("pattern") or "straight")
    if pattern not in {"straight", "diagonal", "herringbone"}:
        pattern = "straight"
    mode = str(view.get("mode") or "perspective")
    if mode not in {"perspective", "top", "front", "left", "right"}:
        mode = "perspective"

    return {
        "schema_version": SCHEMA_VERSION,
        "room": {"length_m": str(length), "width_m": str(width), "height_m": str(height), "wall_thickness_m": str(wall_thickness)},
        "openings": openings,
        "objects": objects,
        "renovation": _normalize_renovation(state.get("renovation")),
        "materials": {
            "floor": _color(materials.get("floor"), "#d8d4ce"), "wall": _color(materials.get("wall"), "#f2f3f2"),
            "ceiling": _color(materials.get("ceiling"), "#ffffff"), "accent": _color(materials.get("accent"), "#31526b"),
            "grout_color": _color(materials.get("grout_color"), "#c8c8c5"), "pattern": pattern,
            "tile_width_cm": str(_decimal(materials.get("tile_width_cm", 60), "materials.tile_width_cm", minimum=Decimal("1"), maximum=Decimal("300"))),
            "tile_height_cm": str(_decimal(materials.get("tile_height_cm", 60), "materials.tile_height_cm", minimum=Decimal("1"), maximum=Decimal("300"))),
        },
        "lighting": {
            "brightness": str(_decimal(lighting.get("brightness", 1.1), "lighting.brightness", minimum=Decimal("0.3"), maximum=Decimal("2.2"))),
            "warmth": str(_decimal(lighting.get("warmth", 42), "lighting.warmth", minimum=Decimal("0"), maximum=Decimal("100"))),
        },
        "view": {
            "mode": mode, "rotation_deg": str(_decimal(view.get("rotation_deg", 0), "view.rotation_deg", maximum=Decimal("360"))),
            "show_ceiling": bool(view.get("show_ceiling", False)), "transparent_near_walls": bool(view.get("transparent_near_walls", True)),
            "grid": bool(view.get("grid", True)), "snap": bool(view.get("snap", True)),
        },
        "calibration": {
            "scale_verified": bool(calibration.get("scale_verified", False)), "method": str(calibration.get("method") or "manual")[:40],
            "confidence": _confidence(calibration.get("confidence")), "warnings": [str(item)[:300] for item in (calibration.get("warnings") or [])[:20]],
        },
    }


def opening_area(state: dict[str, Any]) -> Decimal:
    total = Decimal("0")
    for item in state.get("openings", []):
        try:
            total += Decimal(str(item["width_m"])) * Decimal(str(item["height_m"]))
        except (InvalidOperation, KeyError, TypeError, ValueError):
            continue
    return total.quantize(Decimal("0.001"))


def merge_vision_result(current_state: dict[str, Any], vision: dict[str, Any]) -> dict[str, Any]:
    state = deepcopy(current_state or blank_room_state())
    room = state.setdefault("room", {})
    detected_room = vision.get("room") if isinstance(vision.get("room"), dict) else {}
    scale_verified = bool(vision.get("scale_verified"))
    if scale_verified:
        for key in ("length_m", "width_m", "height_m"):
            value = detected_room.get(key)
            if value is not None:
                room[key] = value
    length = float(room.get("length_m") or 4)
    width = float(room.get("width_m") or 3)

    new_openings = []
    for index, raw in enumerate(vision.get("openings") or []):
        wall = raw.get("wall") if raw.get("wall") in ALLOWED_WALLS else "back"
        wall_length = length if wall in {"left", "right"} else width
        opening_width = raw.get("width_m") if scale_verified and raw.get("width_m") else max(0.5, wall_length * float(raw.get("width_ratio") or 0.25))
        offset = raw.get("offset_m") if scale_verified and raw.get("offset_m") is not None else wall_length * float(raw.get("offset_ratio") or 0.2)
        kind = raw.get("kind") if raw.get("kind") in ALLOWED_OPENINGS else "opening"
        new_openings.append({
            "id": str(raw.get("id") or f"ai-opening-{index + 1}"), "kind": kind, "wall": wall,
            "width_m": opening_width, "height_m": raw.get("height_m") or (2.0 if kind == "door" else 1.0),
            "offset_m": offset, "sill_height_m": raw.get("sill_m") if raw.get("sill_m") is not None else (0 if kind == "door" else 0.9),
            "source": "ai_photo", "confidence": raw.get("confidence", 0.5), "evidence": raw.get("evidence", ""),
        })

    new_objects = []
    for index, raw in enumerate(vision.get("objects") or []):
        kind = raw.get("kind") if raw.get("kind") in ALLOWED_KINDS else "fixture"
        obj = object_defaults(kind)
        obj.update({
            "id": str(raw.get("id") or f"ai-object-{index + 1}"), "label": raw.get("label") or obj["label"],
            "anchor": raw.get("anchor") if raw.get("anchor") in ALLOWED_ANCHORS else obj["anchor"],
            "wall": raw.get("wall") if raw.get("wall") in ALLOWED_WALLS else obj["wall"],
            "x_m": float(raw.get("x_m")) if scale_verified and raw.get("x_m") is not None else width * float(raw.get("x_ratio") or 0.5),
            "z_m": float(raw.get("z_m")) if scale_verified and raw.get("z_m") is not None else length * float(raw.get("z_ratio") or 0.5),
            "elevation_m": raw.get("elevation_m") if raw.get("elevation_m") is not None else obj["elevation_m"],
            "width_m": raw.get("width_m") or obj["width_m"], "depth_m": raw.get("depth_m") or obj["depth_m"], "height_m": raw.get("height_m") or obj["height_m"],
            "rotation_deg": raw.get("rotation_deg") or 0, "source": "ai_photo", "confidence": raw.get("confidence", 0.5), "evidence": raw.get("evidence", ""),
        })
        new_objects.append(obj)

    if new_openings:
        preserved_openings = [item for item in (state.get("openings") or []) if item.get("source") != "ai_photo"]
        state["openings"] = preserved_openings + new_openings
    if new_objects:
        preserved_objects = [item for item in (state.get("objects") or []) if item.get("source") != "ai_photo"]
        state["objects"] = preserved_objects + new_objects
    state["calibration"] = {
        "scale_verified": scale_verified, "method": str(vision.get("method") or "visual_only"),
        "confidence": vision.get("confidence", 0.5), "warnings": vision.get("warnings") or [],
    }
    return state

# A+Bau renovation state persistence 20260815
# Keep the structured KI renovation plan through every normalization/save/revision
# round-trip. Geometry normalization remains authoritative; this wrapper only
# preserves a bounded, explicitly supported renovation payload.
_kayi_geometry_normalize_room_state = normalize_room_state
_kayi_geometry_blank_room_state = blank_room_state


def _kayi_renovation_number(value, *, minimum=0.0, maximum=50.0):
    if value in (None, ""):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number != number or number in (float("inf"), float("-inf")):
        return None
    return max(minimum, min(maximum, number))


def _kayi_renovation_text(value, limit=500):
    if value in (None, ""):
        return None
    return str(value).strip()[:limit] or None


def _kayi_sanitize_renovation(value):
    raw = value if isinstance(value, dict) else {}
    raw_intent = raw.get("intent") if isinstance(raw.get("intent"), dict) else {}
    raw_surface = raw.get("surface_plan") if isinstance(raw.get("surface_plan"), dict) else {}
    raw_work = raw.get("work_scope") if isinstance(raw.get("work_scope"), dict) else {}

    floor = raw_surface.get("floor") if isinstance(raw_surface.get("floor"), dict) else {}
    wet = raw_surface.get("wet_zone") if isinstance(raw_surface.get("wet_zone"), dict) else {}
    other = raw_surface.get("other_walls") if isinstance(raw_surface.get("other_walls"), dict) else {}
    ceiling = raw_surface.get("ceiling") if isinstance(raw_surface.get("ceiling"), dict) else {}
    walls = [item for item in (wet.get("applies_to") or []) if item in {"back", "front", "left", "right"}][:4]

    return {
        "intent": {
            "preserve_positions": bool(raw_intent.get("preserve_positions", False)),
            "allow_relayout": bool(raw_intent.get("allow_relayout", False)),
            "replace_sanitary_in_place": bool(raw_intent.get("replace_sanitary_in_place", False)),
        },
        "surface_plan": {
            "floor": {
                "remove_existing": bool(floor.get("remove_existing", False)),
                "finish": _kayi_renovation_text(floor.get("finish"), 120),
                "tile_color": _kayi_renovation_text(floor.get("tile_color"), 80),
                "tile_width_cm": _kayi_renovation_number(floor.get("tile_width_cm"), minimum=1, maximum=300),
                "tile_height_cm": _kayi_renovation_number(floor.get("tile_height_cm"), minimum=1, maximum=300),
            },
            "wet_zone": {
                "present": bool(wet.get("present", False)),
                "height_m": _kayi_renovation_number(wet.get("height_m"), minimum=0, maximum=12),
                "wall_tile_color": _kayi_renovation_text(wet.get("wall_tile_color"), 80),
                "tile_width_cm": _kayi_renovation_number(wet.get("tile_width_cm"), minimum=1, maximum=300),
                "tile_height_cm": _kayi_renovation_number(wet.get("tile_height_cm"), minimum=1, maximum=300),
                "applies_to": walls,
                "basis": _kayi_renovation_text(wet.get("basis"), 500),
            },
            "other_walls": {
                "height_m": _kayi_renovation_number(other.get("height_m"), minimum=0, maximum=12),
                "wall_tile_color": _kayi_renovation_text(other.get("wall_tile_color"), 80),
                "tile_width_cm": _kayi_renovation_number(other.get("tile_width_cm"), minimum=1, maximum=300),
                "tile_height_cm": _kayi_renovation_number(other.get("tile_height_cm"), minimum=1, maximum=300),
                "upper_finish": _kayi_renovation_text(other.get("upper_finish"), 300),
            },
            "ceiling": {
                "finish": _kayi_renovation_text(ceiling.get("finish"), 300),
            },
        },
        "work_scope": {
            "remove_old_wall_coverings": bool(raw_work.get("remove_old_wall_coverings", False)),
            "remove_old_floor_coverings": bool(raw_work.get("remove_old_floor_coverings", False)),
            "door_finish": _kayi_renovation_text(raw_work.get("door_finish"), 300),
            "replace_bathtub": bool(raw_work.get("replace_bathtub", False)),
            "replace_toilet": bool(raw_work.get("replace_toilet", False)),
            "replace_sink": bool(raw_work.get("replace_sink", False)),
            "replace_shower": bool(raw_work.get("replace_shower", False)),
            "notes": [str(item)[:500] for item in (raw_work.get("notes") or [])[:20]],
        },
        "source_command": str(raw.get("source_command") or "")[:4000],
    }


def blank_room_state():
    state = _kayi_geometry_blank_room_state()
    state["renovation"] = _kayi_sanitize_renovation({})
    return state


def normalize_room_state(state, measurement=None, scan=None):
    renovation = _kayi_sanitize_renovation(state.get("renovation") if isinstance(state, dict) else {})
    normalized = _kayi_geometry_normalize_room_state(state, measurement, scan)
    normalized["renovation"] = renovation
    return normalized

