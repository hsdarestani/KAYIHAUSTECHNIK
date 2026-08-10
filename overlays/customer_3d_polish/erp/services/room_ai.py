from __future__ import annotations

import json
from copy import deepcopy
from typing import Any

from erp.services.ai import SYSTEM_PROMPT, _create_response
from erp.services.room_planner_state import ALLOWED_KINDS, normalize_room_state


WALLS = ["back", "front", "left", "right"]


def adjust_room_scene(organization, command: str, current_state: dict[str, Any], *, measurement=None) -> dict[str, Any]:
    """Return a complete edited room scene from a natural-language German command.

    The model is deliberately not allowed to change the room envelope here. It
    may rearrange/add/remove openings and objects, while dimensions/materials
    remain under explicit user control in the planner. The returned scene stays
    a draft until the user presses ``Version speichern``.
    """
    command = str(command or "").strip()
    if not command:
        raise ValueError("Bitte eine Anweisung für den KI-Raumassistenten eingeben.")
    if len(command) > 4000:
        raise ValueError("Die KI-Anweisung ist zu lang. Bitte kürzer formulieren.")

    current = normalize_room_state(current_state, measurement, getattr(measurement, "native_scan", None) if measurement else None)

    nullable_number = {"type": ["number", "null"]}
    opening_schema = {
        "type": "object",
        "properties": {
            "id": {"type": "string"},
            "kind": {"type": "string", "enum": ["door", "window", "opening"]},
            "wall": {"type": "string", "enum": WALLS},
            "width_m": {"type": "number", "minimum": 0.05, "maximum": 10},
            "height_m": {"type": "number", "minimum": 0.05, "maximum": 10},
            "offset_m": {"type": "number", "minimum": 0, "maximum": 50},
            "sill_height_m": {"type": "number", "minimum": 0, "maximum": 12},
            "confidence": {"type": "number", "minimum": 0, "maximum": 1},
            "evidence": {"type": "string"},
        },
        "required": ["id", "kind", "wall", "width_m", "height_m", "offset_m", "sill_height_m", "confidence", "evidence"],
        "additionalProperties": False,
    }
    object_schema = {
        "type": "object",
        "properties": {
            "id": {"type": "string"},
            "kind": {"type": "string", "enum": sorted(ALLOWED_KINDS)},
            "label": {"type": "string"},
            "category": {"type": "string"},
            "anchor": {"type": "string", "enum": ["floor", "wall"]},
            "wall": {"type": ["string", "null"], "enum": WALLS + [None]},
            "x_m": {"type": "number", "minimum": 0, "maximum": 50},
            "z_m": {"type": "number", "minimum": 0, "maximum": 50},
            "elevation_m": {"type": "number", "minimum": 0, "maximum": 12},
            "width_m": {"type": "number", "minimum": 0.02, "maximum": 10},
            "depth_m": {"type": "number", "minimum": 0.01, "maximum": 10},
            "height_m": {"type": "number", "minimum": 0.02, "maximum": 10},
            "rotation_deg": {"type": "number", "minimum": 0, "maximum": 360},
            "color": {"type": "string"},
            "enabled": {"type": "boolean"},
            "locked": {"type": "boolean"},
            "confidence": {"type": "number", "minimum": 0, "maximum": 1},
            "evidence": {"type": "string"},
        },
        "required": [
            "id", "kind", "label", "category", "anchor", "wall", "x_m", "z_m", "elevation_m",
            "width_m", "depth_m", "height_m", "rotation_deg", "color", "enabled", "locked",
            "confidence", "evidence",
        ],
        "additionalProperties": False,
    }
    schema = {
        "type": "object",
        "properties": {
            "summary": {"type": "string"},
            "warnings": {"type": "array", "items": {"type": "string"}, "maxItems": 12},
            "objects": {"type": "array", "items": object_schema, "maxItems": 180},
            "openings": {"type": "array", "items": opening_schema, "maxItems": 120},
        },
        "required": ["summary", "warnings", "objects", "openings"],
        "additionalProperties": False,
    }

    user_text = (
        "Du bearbeitest den aktuellen KAYI-3D-Raum anhand einer deutschen Arbeitsanweisung. "
        "Gib IMMER die vollständige neue Liste aller Objekte und Öffnungen zurück, nicht nur Änderungen. "
        "Nicht erwähnte Elemente bleiben unverändert. Bestehende IDs müssen erhalten bleiben; neue Elemente erhalten "
        "stabile kurze IDs. Lösche ein Element nur, wenn die Anweisung das ausdrücklich verlangt. "
        "Die Raumhülle (Länge/Breite/Höhe) darfst du in diesem Schritt nicht verändern. "
        "Koordinaten: x = links nach rechts entlang der Rückwand, z = Rückwand zur Vorderwand. "
        "Bei 'rechte Wand/linke Wand/Rückwand/Vorderwand' passende wall-Verankerung verwenden. "
        "Objekte dürfen sich möglichst nicht überschneiden und müssen innerhalb des Raums liegen. "
        "Wenn eine Anweisung räumlich unklar ist, triff eine konservative sinnvolle Annahme und nenne sie unter warnings. "
        "Alle sichtbaren Texte ausschließlich auf Deutsch.\n\n"
        f"Anweisung:\n{command}\n\n"
        f"Raumhülle:\n{json.dumps(current.get('room', {}), ensure_ascii=False)}\n\n"
        f"Aktuelle Öffnungen:\n{json.dumps(current.get('openings', []), ensure_ascii=False)}\n\n"
        f"Aktuelle Objekte:\n{json.dumps(current.get('objects', []), ensure_ascii=False)}"
    )

    response = _create_response(
        organization,
        input=[
            {"role": "developer", "content": SYSTEM_PROMPT},
            {"role": "user", "content": [{"type": "input_text", "text": user_text}]},
        ],
        text={"format": {"type": "json_schema", "name": "room_3d_command", "schema": schema, "strict": True}},
        store=False,
    )
    result = json.loads(response.output_text)

    next_state = deepcopy(current)
    existing_sources = {str(item.get("id")): item.get("source") for item in current.get("objects", [])}
    existing_opening_sources = {str(item.get("id")): item.get("source") for item in current.get("openings", [])}
    next_state["objects"] = result.get("objects") or []
    next_state["openings"] = result.get("openings") or []
    for item in next_state["objects"]:
        item["source"] = existing_sources.get(str(item.get("id"))) or "ki_command"
        item["confidence"] = item.get("confidence", 0.75)
    for item in next_state["openings"]:
        item["source"] = existing_opening_sources.get(str(item.get("id"))) or "ki_command"
        item["confidence"] = item.get("confidence", 0.75)

    normalized = normalize_room_state(next_state, measurement, getattr(measurement, "native_scan", None) if measurement else None)
    return {
        "state": normalized,
        "summary": str(result.get("summary") or "KI-Vorschlag erstellt."),
        "warnings": [str(item) for item in (result.get("warnings") or [])[:12]],
    }
