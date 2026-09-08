from __future__ import annotations

import base64
import json
import mimetypes
from typing import Any

from erp.services.ai import SYSTEM_PROMPT, _create_response
from erp.services.room_planner_state import ALLOWED_KINDS


def analyze_room_scene(organization, images, *, calibration: dict[str, Any] | None = None, current_state: dict[str, Any] | None = None) -> dict[str, Any]:
    calibration = calibration or {}
    current_state = current_state or {}
    content: list[dict[str, Any]] = [{
        "type": "input_text",
        "text": (
            "Analysiere diese Raumaufnahmen als professioneller 3D-Aufmaß-Assistent. Erzeuge eine konsistente, editierbare Raum-Szene. "
            "Ordne jede erkannte Tür, jedes Fenster und jedes relevante sichtbare Objekt einer Position im lokalen Raumkoordinatensystem zu: "
            "x verläuft von links nach rechts entlang der Rückwand, z von Rückwand zur Vorderwand. Nutze für nicht metrisch belegbare Positionen zusätzlich x_ratio/z_ratio von 0 bis 1. "
            "Wandnamen: back=Rückwand, front=gegenüberliegende Wand, left/right entsprechend Blick in den Raum. Bei mehreren Fotos gleiche Objekte nicht doppelt anlegen. "
            "Metrische Raummaße oder Objektmaße nur ausgeben, wenn Skalierung durch bekannte Referenz, vorhandene bestätigte Raummaße oder AR/LiDAR belastbar ist. "
            "Ohne belastbare Skalierung relative Positionen trotzdem so gut wie möglich modellieren, aber scale_verified=false setzen und Unsicherheit klar nennen. "
            "Erkenne insbesondere Sanitär, Heizkörper, Schränke, Küchenmodule, Geräte, Steckdosen/Schalter, technische Anlagen, Stützen/Schächte und Möbel. "
            "Objekttypen dürfen ausschließlich aus der erlaubten Liste stammen. Alle summary/warnings/evidence Texte auf Deutsch. Das Ergebnis bleibt prüfpflichtig.\n\n"
            f"Erlaubte Objekttypen: {', '.join(sorted(ALLOWED_KINDS))}\n"
            f"Kalibrierung: {json.dumps(calibration, ensure_ascii=False)}\n"
            f"Aktueller Raumzustand: {json.dumps(current_state.get('room', {}), ensure_ascii=False)}"
        ),
    }]
    for index, image in enumerate(list(images)[:12]):
        position = image.tell() if hasattr(image, "tell") else None
        raw = image.read()
        if position is not None:
            image.seek(position)
        mime = getattr(image, "content_type", "") or mimetypes.guess_type(getattr(image, "name", ""))[0] or "image/jpeg"
        content.append({"type": "input_text", "text": f"Aufnahme {index + 1}"})
        content.append({"type": "input_image", "image_url": f"data:{mime};base64,{base64.b64encode(raw).decode('ascii')}", "detail": "high"})

    nullable_number = {"type": ["number", "null"]}
    opening = {
        "type": "object",
        "properties": {
            "id": {"type": "string"}, "kind": {"type": "string", "enum": ["door", "window", "opening"]},
            "wall": {"type": "string", "enum": ["back", "front", "left", "right"]},
            "offset_ratio": {"type": "number", "minimum": 0, "maximum": 1}, "width_ratio": {"type": "number", "minimum": 0.01, "maximum": 1},
            "offset_m": nullable_number, "width_m": nullable_number, "height_m": nullable_number, "sill_m": nullable_number,
            "confidence": {"type": "number", "minimum": 0, "maximum": 1}, "evidence": {"type": "string"},
        },
        "required": ["id", "kind", "wall", "offset_ratio", "width_ratio", "offset_m", "width_m", "height_m", "sill_m", "confidence", "evidence"],
        "additionalProperties": False,
    }
    obj = {
        "type": "object",
        "properties": {
            "id": {"type": "string"}, "kind": {"type": "string", "enum": sorted(ALLOWED_KINDS)}, "label": {"type": "string"},
            "anchor": {"type": "string", "enum": ["floor", "wall"]}, "wall": {"type": ["string", "null"], "enum": ["back", "front", "left", "right", None]},
            "x_ratio": {"type": "number", "minimum": 0, "maximum": 1}, "z_ratio": {"type": "number", "minimum": 0, "maximum": 1},
            "x_m": nullable_number, "z_m": nullable_number, "elevation_m": nullable_number,
            "width_m": nullable_number, "depth_m": nullable_number, "height_m": nullable_number,
            "rotation_deg": {"type": "number", "minimum": 0, "maximum": 360},
            "confidence": {"type": "number", "minimum": 0, "maximum": 1}, "evidence": {"type": "string"},
        },
        "required": ["id", "kind", "label", "anchor", "wall", "x_ratio", "z_ratio", "x_m", "z_m", "elevation_m", "width_m", "depth_m", "height_m", "rotation_deg", "confidence", "evidence"],
        "additionalProperties": False,
    }
    schema = {
        "type": "object",
        "properties": {
            "room_type": {"type": "string"},
            "room": {"type": "object", "properties": {"length_m": nullable_number, "width_m": nullable_number, "height_m": nullable_number}, "required": ["length_m", "width_m", "height_m"], "additionalProperties": False},
            "scale_verified": {"type": "boolean"}, "method": {"type": "string", "enum": ["reference_photo", "existing_dimensions", "ar_lidar", "visual_only", "insufficient"]},
            "confidence": {"type": "number", "minimum": 0, "maximum": 1}, "summary": {"type": "string"},
            "warnings": {"type": "array", "items": {"type": "string"}}, "missing_captures": {"type": "array", "items": {"type": "string"}},
            "openings": {"type": "array", "items": opening, "maxItems": 80}, "objects": {"type": "array", "items": obj, "maxItems": 120},
        },
        "required": ["room_type", "room", "scale_verified", "method", "confidence", "summary", "warnings", "missing_captures", "openings", "objects"],
        "additionalProperties": False,
    }
    response = _create_response(
        organization,
        input=[{"role": "developer", "content": SYSTEM_PROMPT}, {"role": "user", "content": content}],
        text={"format": {"type": "json_schema", "name": "room_3d_scene_analysis", "schema": schema, "strict": True}},
        store=False,
    )
    return json.loads(response.output_text)
