from __future__ import annotations

import json
import re
from copy import deepcopy
from typing import Any

from erp.services.ai import SYSTEM_PROMPT, _create_response
from erp.services.room_planner_state import ALLOWED_KINDS, normalize_room_state


WALLS = ["back", "front", "left", "right"]
SANITARY_KINDS = {"bathtub", "toilet", "sink", "vanity", "shower"}
SANITARY_ALIASES = {
    "bathtub": ("badewanne", "wanne"),
    "toilet": ("toilette", "wc"),
    "sink": ("waschbecken",),
    "vanity": ("waschtisch", "waschbecken"),
    "shower": ("dusche", "dusch"),
}
MOVE_STEMS = (
    "versetz", "verschieb", "umplatzier", "neu anord", "anders anord", "positionier",
    "an die rechte wand", "an die linke wand", "an die rückwand", "an die vorderwand",
    "rechts neben", "links neben",
)
REPLACEMENT_STEMS = (
    "austausch", "ersetz", "erneu", "neue badewanne", "neuer badewanne",
    "neue toilette", "neues wc", "neues waschbecken", "neuer waschtisch",
)


def _contains_any(text: str, needles: tuple[str, ...]) -> bool:
    normalized = (text or "").lower()
    return any(needle in normalized for needle in needles)


def _explicit_move_for_kind(command: str, kind: str) -> bool:
    text = (command or "").lower()
    if re.search(r"(sanitär|sanitaer|sanitärobjekt|sanitaerobjekt).{0,80}(neu anord|anord|versetz|verschieb|umplatzier)", text):
        return True
    if re.search(r"(neu anord|anord|versetz|verschieb|umplatzier).{0,80}(sanitär|sanitaer|sanitärobjekt|sanitaerobjekt)", text):
        return True
    aliases = SANITARY_ALIASES.get(kind, ())
    for alias in aliases:
        for match in re.finditer(re.escape(alias), text):
            start = max(0, match.start() - 110)
            end = min(len(text), match.end() + 110)
            window = text[start:end]
            if _contains_any(window, MOVE_STEMS):
                return True
    return False


def _replacement_only_guard(command: str, current: dict[str, Any], result: dict[str, Any]) -> bool:
    """Keep existing sanitary geometry when the instruction asks for replacement, not relocation."""
    text = (command or "").lower()
    replacement_requested = _contains_any(text, REPLACEMENT_STEMS)
    if not replacement_requested:
        return False

    output_objects = result.get("objects")
    if not isinstance(output_objects, list):
        output_objects = []
        result["objects"] = output_objects

    by_id = {str(item.get("id")): item for item in output_objects if isinstance(item, dict) and item.get("id")}
    used_ids: set[int] = set()
    geometry_fields = ("x_m", "z_m", "elevation_m", "rotation_deg", "wall", "anchor")

    for original in current.get("objects", []):
        if not isinstance(original, dict) or original.get("kind") not in SANITARY_KINDS:
            continue
        kind = str(original.get("kind"))
        if _explicit_move_for_kind(command, kind):
            continue

        candidate = by_id.get(str(original.get("id")))
        if candidate is None:
            compatible = {kind}
            if kind in {"sink", "vanity"}:
                compatible = {"sink", "vanity"}
            for item in output_objects:
                if not isinstance(item, dict) or id(item) in used_ids:
                    continue
                if item.get("kind") in compatible:
                    candidate = item
                    break

        if candidate is None:
            candidate = deepcopy(original)
            candidate["source"] = original.get("source") or "manual"
            output_objects.append(candidate)

        used_ids.add(id(candidate))
        candidate["id"] = original.get("id", candidate.get("id"))
        candidate["kind"] = original.get("kind", candidate.get("kind"))
        for field in geometry_fields:
            if field in original:
                candidate[field] = original[field]

    intent = result.setdefault("intent", {})
    movable_sanitary = any(_explicit_move_for_kind(command, kind) for kind in SANITARY_KINDS)
    if not movable_sanitary:
        intent["preserve_positions"] = True
        intent["allow_relayout"] = False
        intent["replace_sanitary_in_place"] = True
    return not movable_sanitary


def _apply_surface_plan_to_legacy_materials(next_state: dict[str, Any], surface_plan: dict[str, Any]) -> None:
    """Mirror compatible floor settings into legacy material fields while retaining the richer renovation plan."""
    floor = surface_plan.get("floor") if isinstance(surface_plan, dict) else None
    if not isinstance(floor, dict):
        return
    materials = next_state.setdefault("materials", {})
    width = floor.get("tile_width_cm")
    height = floor.get("tile_height_cm")
    if isinstance(width, (int, float)) and width > 0:
        materials["tile_width_cm"] = width
    if isinstance(height, (int, float)) and height > 0:
        materials["tile_height_cm"] = height
    color_name = str(floor.get("tile_color") or "").strip().lower()
    known_colors = {
        "hellgrau": "#d9d9d9",
        "hell grau": "#d9d9d9",
        "grau": "#b8b8b8",
        "weiß": "#f4f4f2",
        "weiss": "#f4f4f2",
        "schwarz": "#303236",
        "beige": "#d9cfbd",
    }
    if color_name in known_colors:
        materials["floor"] = known_colors[color_name]


def adjust_room_scene(organization, command: str, current_state: dict[str, Any], *, measurement=None) -> dict[str, Any]:
    """Interpret a German renovation instruction and return a safe, reviewable full room draft."""
    command = str(command or "").strip()
    if not command:
        raise ValueError("Bitte eine Anweisung für den KI-Raumassistenten eingeben.")
    if len(command) > 4000:
        raise ValueError("Die KI-Anweisung ist zu lang. Bitte kürzer formulieren.")

    current = normalize_room_state(
        current_state,
        measurement,
        getattr(measurement, "native_scan", None) if measurement else None,
    )

    nullable_number = {"type": ["number", "null"]}
    nullable_string = {"type": ["string", "null"]}

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
    surface_plan_schema = {
        "type": "object",
        "properties": {
            "floor": {
                "type": "object",
                "properties": {
                    "remove_existing": {"type": "boolean"},
                    "finish": nullable_string,
                    "tile_color": nullable_string,
                    "tile_width_cm": nullable_number,
                    "tile_height_cm": nullable_number,
                },
                "required": ["remove_existing", "finish", "tile_color", "tile_width_cm", "tile_height_cm"],
                "additionalProperties": False,
            },
            "wet_zone": {
                "type": "object",
                "properties": {
                    "present": {"type": "boolean"},
                    "height_m": nullable_number,
                    "wall_tile_color": nullable_string,
                    "tile_width_cm": nullable_number,
                    "tile_height_cm": nullable_number,
                    "applies_to": {"type": "array", "items": {"type": "string", "enum": WALLS}, "maxItems": 4},
                    "basis": nullable_string,
                },
                "required": ["present", "height_m", "wall_tile_color", "tile_width_cm", "tile_height_cm", "applies_to", "basis"],
                "additionalProperties": False,
            },
            "other_walls": {
                "type": "object",
                "properties": {
                    "height_m": nullable_number,
                    "wall_tile_color": nullable_string,
                    "tile_width_cm": nullable_number,
                    "tile_height_cm": nullable_number,
                    "upper_finish": nullable_string,
                },
                "required": ["height_m", "wall_tile_color", "tile_width_cm", "tile_height_cm", "upper_finish"],
                "additionalProperties": False,
            },
            "ceiling": {
                "type": "object",
                "properties": {"finish": nullable_string},
                "required": ["finish"],
                "additionalProperties": False,
            },
        },
        "required": ["floor", "wet_zone", "other_walls", "ceiling"],
        "additionalProperties": False,
    }
    work_scope_schema = {
        "type": "object",
        "properties": {
            "remove_old_wall_coverings": {"type": "boolean"},
            "remove_old_floor_coverings": {"type": "boolean"},
            "door_finish": nullable_string,
            "replace_bathtub": {"type": "boolean"},
            "replace_toilet": {"type": "boolean"},
            "replace_sink": {"type": "boolean"},
            "replace_shower": {"type": "boolean"},
            "notes": {"type": "array", "items": {"type": "string"}, "maxItems": 20},
        },
        "required": [
            "remove_old_wall_coverings", "remove_old_floor_coverings", "door_finish",
            "replace_bathtub", "replace_toilet", "replace_sink", "replace_shower", "notes",
        ],
        "additionalProperties": False,
    }
    intent_schema = {
        "type": "object",
        "properties": {
            "preserve_positions": {"type": "boolean"},
            "allow_relayout": {"type": "boolean"},
            "replace_sanitary_in_place": {"type": "boolean"},
        },
        "required": ["preserve_positions", "allow_relayout", "replace_sanitary_in_place"],
        "additionalProperties": False,
    }
    schema = {
        "type": "object",
        "properties": {
            "summary": {"type": "string"},
            "warnings": {"type": "array", "items": {"type": "string"}, "maxItems": 12},
            "objects": {"type": "array", "items": object_schema, "maxItems": 180},
            "openings": {"type": "array", "items": opening_schema, "maxItems": 120},
            "surface_plan": surface_plan_schema,
            "work_scope": work_scope_schema,
            "intent": intent_schema,
        },
        "required": ["summary", "warnings", "objects", "openings", "surface_plan", "work_scope", "intent"],
        "additionalProperties": False,
    }

    user_text = (
        "Du bist der KAYI-Renovierungsplaner. Interpretiere die deutsche Arbeitsanweisung fachlich und "
        "bearbeite den vorhandenen 3D-Raum konservativ. Gib IMMER die vollständige neue Liste aller Objekte "
        "und Öffnungen zurück. Nicht erwähnte Elemente bleiben unverändert und bestehende IDs bleiben erhalten. "
        "Lösche ein Element nur bei einer ausdrücklichen Abbruch-/Entfernen-Anweisung. "
        "Die Raumhülle (Länge/Breite/Höhe) darf in diesem Schritt nicht verändert werden. "
        "WICHTIGE BEDEUTUNGSREGEL: 'austauschen', 'ersetzen', 'erneuern' oder 'neu' bei einem bereits vorhandenen "
        "Sanitärobjekt bedeutet standardmäßig Ersatz AM BESTEHENDEN ORT. Dabei bleiben ID, Position, Wandzuordnung, "
        "Ausrichtung und Höhe unverändert. Eine Umplatzierung ist nur erlaubt, wenn ausdrücklich 'versetzen', "
        "'verschieben', 'umplatzieren', 'neu anordnen', 'positionieren' oder eine konkrete neue Position genannt wird. "
        "Wenn nur eines der Sanitärobjekte versetzt werden soll, dürfen die anderen nicht mitverschoben werden. "
        "Nassbereich bedeutet bei Bad/Dusche primär die direkt zur Badewanne oder Dusche gehörenden Spritzwasserwände; "
        "nicht automatisch jede Wand mit irgendeinem Sanitärobjekt. Ist die genaue Nassbereich-Wand aus der aktuellen "
        "Geometrie nicht sicher ableitbar, verwende eine konservative Zuordnung nahe Badewanne/Dusche und nenne diese "
        "Annahme in warnings und surface_plan.wet_zone.basis. "
        "Arbeitsangaben zu Belägen, Fliesenformaten, Farben, Fliesenhöhen, Q3, Spachteln, Streichen sowie Türarbeiten "
        "dürfen nicht nur im Fließtext verschwinden: erfasse sie vollständig in surface_plan und work_scope. "
        "Koordinaten: x = links nach rechts entlang der Rückwand, z = Rückwand zur Vorderwand. "
        "Objekte dürfen sich möglichst nicht überschneiden und müssen innerhalb des Raums liegen. "
        "Alle sichtbaren Texte ausschließlich auf Deutsch.\n\n"
        f"Anweisung:\n{command}\n\n"
        f"Raumhülle:\n{json.dumps(current.get('room', {}), ensure_ascii=False)}\n\n"
        f"Aktuelle Renovierungsdaten:\n{json.dumps(current.get('renovation', {}), ensure_ascii=False)}\n\n"
        f"Aktuelle Öffnungen:\n{json.dumps(current.get('openings', []), ensure_ascii=False)}\n\n"
        f"Aktuelle Objekte:\n{json.dumps(current.get('objects', []), ensure_ascii=False)}"
    )

    response = _create_response(
        organization,
        input=[
            {"role": "developer", "content": SYSTEM_PROMPT},
            {"role": "user", "content": [{"type": "input_text", "text": user_text}]},
        ],
        text={"format": {"type": "json_schema", "name": "room_renovation_command", "schema": schema, "strict": True}},
        store=False,
    )
    result = json.loads(response.output_text)

    replacement_locked = _replacement_only_guard(command, current, result)

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

    next_state["renovation"] = {
        "intent": result.get("intent") or {},
        "surface_plan": result.get("surface_plan") or {},
        "work_scope": result.get("work_scope") or {},
        "source_command": command[:4000],
    }
    _apply_surface_plan_to_legacy_materials(next_state, next_state["renovation"]["surface_plan"])

    normalized = normalize_room_state(
        next_state,
        measurement,
        getattr(measurement, "native_scan", None) if measurement else None,
    )

    summary = str(result.get("summary") or "KI-Vorschlag erstellt.")
    if replacement_locked and "bestehenden ort" not in summary.lower():
        summary = f"{summary} Sanitärobjekte werden am bestehenden Ort ersetzt; ihre Positionen bleiben unverändert."

    return {
        "state": normalized,
        "summary": summary,
        "warnings": [str(item) for item in (result.get("warnings") or [])[:12]],
        "renovation": normalized.get("renovation", next_state.get("renovation", {})),
    }
