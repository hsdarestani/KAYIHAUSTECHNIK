from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any

from django.core.exceptions import ValidationError

from erp.models import NativeRoomScan, RoomMeasurement


ROOM_LIMIT = Decimal("50")


def _number(value: Any, field: str, *, minimum: Decimal = Decimal("0"), maximum: Decimal = ROOM_LIMIT) -> Decimal:
    try:
        number = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValidationError({field: "Ungültiger Zahlenwert."}) from exc
    if not number.is_finite() or number < minimum or number > maximum:
        raise ValidationError({field: f"Wert muss zwischen {minimum} und {maximum} liegen."})
    return number.quantize(Decimal("0.001"))


def _safe_color(value: Any, fallback: str) -> str:
    value = str(value or "").strip()
    if len(value) == 7 and value.startswith("#") and all(char in "0123456789abcdefABCDEF" for char in value[1:]):
        return value.lower()
    return fallback


def _opening(item: Any, index: int) -> dict[str, Any] | None:
    if not isinstance(item, dict):
        return None
    dimensions = item.get("dimensions") if isinstance(item.get("dimensions"), dict) else item
    position = item.get("position") if isinstance(item.get("position"), dict) else item
    kind = str(item.get("kind") or item.get("type") or "opening")[:32]
    if kind not in {"door", "window", "opening"}:
        kind = "opening"
    wall = str(item.get("wall") or position.get("wall") or "back")
    if wall not in {"back", "left", "right", "front"}:
        wall = "back"
    width = _number(dimensions.get("width_m", dimensions.get("width", 0.9)), f"openings[{index}].width_m", minimum=Decimal("0.05"), maximum=Decimal("10"))
    height = _number(dimensions.get("height_m", dimensions.get("height", 2.0)), f"openings[{index}].height_m", minimum=Decimal("0.05"), maximum=Decimal("10"))
    offset = _number(position.get("offset_m", position.get("offset", 0.5)), f"openings[{index}].offset_m", maximum=ROOM_LIMIT)
    sill = _number(position.get("sill_m", position.get("sill", 0)), f"openings[{index}].sill_m", maximum=Decimal("10"))
    return {
        "id": str(item.get("id") or f"opening-{index + 1}")[:80],
        "kind": kind,
        "wall": wall,
        "width_m": str(width),
        "height_m": str(height),
        "offset_m": str(offset),
        "sill_m": str(sill),
    }


def _fixture(item: Any, index: int) -> dict[str, Any] | None:
    if not isinstance(item, dict):
        return None
    kind = str(item.get("kind") or item.get("category") or item.get("type") or "fixture")[:40]
    if kind not in {"shower", "vanity", "toilet", "bathtub", "radiator", "cabinet", "fixture"}:
        kind = "fixture"
    defaults = {
        "shower": (Decimal("1.2"), Decimal("0.9"), Decimal("2.1"), "#9fd8ee"),
        "vanity": (Decimal("0.9"), Decimal("0.5"), Decimal("0.85"), "#d9d0c5"),
        "toilet": (Decimal("0.4"), Decimal("0.7"), Decimal("0.8"), "#f6f7f8"),
        "bathtub": (Decimal("1.7"), Decimal("0.75"), Decimal("0.6"), "#f2f4f6"),
        "radiator": (Decimal("0.8"), Decimal("0.15"), Decimal("0.7"), "#e9ecef"),
        "cabinet": (Decimal("0.8"), Decimal("0.45"), Decimal("1.8"), "#8a6a4d"),
        "fixture": (Decimal("0.6"), Decimal("0.6"), Decimal("0.8"), "#cbd5df"),
    }
    default_width, default_depth, default_height, default_color = defaults[kind]
    return {
        "id": str(item.get("id") or f"fixture-{index + 1}")[:80],
        "kind": kind,
        "x_m": str(_number(item.get("x_m", item.get("x", 0.5)), f"objects[{index}].x_m")),
        "z_m": str(_number(item.get("z_m", item.get("z", 0.5)), f"objects[{index}].z_m")),
        "width_m": str(_number(item.get("width_m", item.get("width", default_width)), f"objects[{index}].width_m", minimum=Decimal("0.05"), maximum=Decimal("10"))),
        "depth_m": str(_number(item.get("depth_m", item.get("depth", default_depth)), f"objects[{index}].depth_m", minimum=Decimal("0.05"), maximum=Decimal("10"))),
        "height_m": str(_number(item.get("height_m", item.get("height", default_height)), f"objects[{index}].height_m", minimum=Decimal("0.05"), maximum=Decimal("10"))),
        "rotation_deg": str(_number(item.get("rotation_deg", item.get("rotation", 0)), f"objects[{index}].rotation_deg", maximum=Decimal("360"))),
        "color": _safe_color(item.get("color"), default_color),
        "enabled": bool(item.get("enabled", True)),
    }


def initial_room_model_state(measurement: RoomMeasurement, scan: NativeRoomScan | None = None) -> dict[str, Any]:
    payload = (scan.normalized_payload if scan else None) or measurement.ai_payload or {}
    room = payload.get("room") if isinstance(payload, dict) else {}
    room = room if isinstance(room, dict) else {}
    dimensions = room.get("dimensions") if isinstance(room.get("dimensions"), dict) else {}

    length = measurement.length_m or dimensions.get("length_m") or Decimal("4")
    width = measurement.width_m or dimensions.get("width_m") or Decimal("3")
    height = measurement.height_m or dimensions.get("height_m") or Decimal("2.5")

    raw_openings: list[Any] = []
    if isinstance(payload, dict):
        for key, kind in (("doors", "door"), ("windows", "window"), ("openings", "opening")):
            for item in payload.get(key, []) if isinstance(payload.get(key), list) else []:
                if isinstance(item, dict):
                    raw_openings.append({**item, "kind": kind})
    openings = []
    for index, item in enumerate(raw_openings[:50]):
        try:
            normalized = _opening(item, index)
        except ValidationError:
            continue
        if normalized:
            openings.append(normalized)

    raw_objects = payload.get("objects", []) if isinstance(payload, dict) and isinstance(payload.get("objects"), list) else []
    objects = []
    for index, item in enumerate(raw_objects[:50]):
        try:
            normalized = _fixture(item, index)
        except ValidationError:
            continue
        if normalized:
            objects.append(normalized)

    return {
        "schema_version": 2,
        "room": {"length_m": str(length), "width_m": str(width), "height_m": str(height)},
        "openings": openings,
        "objects": objects,
        "materials": {
            "floor": "#3d434b",
            "wall": "#eef2f6",
            "ceiling": "#f8fafc",
            "accent": "#6e8fa8",
            "grout_color": "#c7cdd3",
            "pattern": "straight",
            "tile_width_cm": "60.000",
            "tile_height_cm": "60.000",
        },
        "lighting": {"brightness": "1.000", "warmth": "35.000"},
        "view": {"mode": "perspective", "rotation_deg": "0.000"},
    }


def normalize_room_model_state(state: Any, measurement: RoomMeasurement, scan: NativeRoomScan | None = None) -> dict[str, Any]:
    if not isinstance(state, dict):
        raise ValidationError({"state": "Modellzustand muss ein JSON-Objekt sein."})
    fallback = initial_room_model_state(measurement, scan)
    room = state.get("room") if isinstance(state.get("room"), dict) else {}
    length = _number(room.get("length_m", fallback["room"]["length_m"]), "room.length_m", minimum=Decimal("0.1"))
    width = _number(room.get("width_m", fallback["room"]["width_m"]), "room.width_m", minimum=Decimal("0.1"))
    height = _number(room.get("height_m", fallback["room"]["height_m"]), "room.height_m", minimum=Decimal("0.1"), maximum=Decimal("12"))

    openings = []
    for index, item in enumerate((state.get("openings") or [])[:100]):
        normalized = _opening(item, index)
        if normalized:
            openings.append(normalized)

    objects = []
    for index, item in enumerate((state.get("objects") or [])[:100]):
        normalized = _fixture(item, index)
        if normalized:
            objects.append(normalized)

    materials = state.get("materials") if isinstance(state.get("materials"), dict) else {}
    pattern = str(materials.get("pattern") or "straight")
    if pattern not in {"straight", "diagonal", "herringbone"}:
        pattern = "straight"
    view = state.get("view") if isinstance(state.get("view"), dict) else {}
    mode = str(view.get("mode") or "perspective")
    if mode not in {"perspective", "front", "top"}:
        mode = "perspective"

    lighting = state.get("lighting") if isinstance(state.get("lighting"), dict) else {}
    return {
        "schema_version": 2,
        "room": {"length_m": str(length), "width_m": str(width), "height_m": str(height)},
        "openings": openings,
        "objects": objects,
        "materials": {
            "floor": _safe_color(materials.get("floor"), "#3d434b"),
            "wall": _safe_color(materials.get("wall"), "#eef2f6"),
            "ceiling": _safe_color(materials.get("ceiling"), "#f8fafc"),
            "accent": _safe_color(materials.get("accent"), "#6e8fa8"),
            "grout_color": _safe_color(materials.get("grout_color"), "#c7cdd3"),
            "pattern": pattern,
            "tile_width_cm": str(_number(materials.get("tile_width_cm", 60), "materials.tile_width_cm", minimum=Decimal("1"), maximum=Decimal("300"))),
            "tile_height_cm": str(_number(materials.get("tile_height_cm", 60), "materials.tile_height_cm", minimum=Decimal("1"), maximum=Decimal("300"))),
        },
        "lighting": {
            "brightness": str(_number(lighting.get("brightness", 1), "lighting.brightness", minimum=Decimal("0.4"), maximum=Decimal("1.8"))),
            "warmth": str(_number(lighting.get("warmth", 35), "lighting.warmth", minimum=Decimal("0"), maximum=Decimal("100"))),
        },
        "view": {
            "mode": mode,
            "rotation_deg": str(_number(view.get("rotation_deg", 0), "view.rotation_deg", maximum=Decimal("360"))),
        },
    }


def opening_area(state: dict[str, Any]) -> Decimal:
    total = Decimal("0")
    for item in state.get("openings", []):
        try:
            total += Decimal(item["width_m"]) * Decimal(item["height_m"])
        except (InvalidOperation, KeyError, TypeError):
            continue
    return total.quantize(Decimal("0.001"))
