from __future__ import annotations

import json
from django.conf import settings
from openai import OpenAI
from erp.models import IntegrationConfig
from erp.services.integrations import require_integration_enabled

SYSTEM_PROMPT = """Du bist der interne KI-Assistent von A+Bau. Antworte präzise auf Deutsch. Nutze nur bereitgestellten Kontext. Erfinde keine Preise, Kundendaten oder ausgeführten Arbeiten. Finanzielle Dokumente, Portal-Übermittlungen und E-Mails sind immer Entwürfe und benötigen menschliche Freigabe."""


def get_client(organization) -> OpenAI:
    require_integration_enabled(organization, IntegrationConfig.Provider.OPENAI)
    return OpenAI(api_key=settings.OPENAI_API_KEY)


def _model_access_error(exc: Exception) -> bool:
    body = getattr(exc, "body", None)
    error = body.get("error", body) if isinstance(body, dict) else {}
    code = error.get("code") if isinstance(error, dict) else None
    message = str(exc).lower()
    return (
        code == "model_not_found"
        or "organization must be verified" in message
        or "you do not have access to it" in message
        or "does not exist or you do not have access" in message
    )


def _create_response(organization, **kwargs):
    client = get_client(organization)
    configured = str(settings.OPENAI_MODEL).strip()
    fallback = str(getattr(settings, "OPENAI_FALLBACK_MODEL", "gpt-4.1-mini")).strip()
    models = [configured]
    if fallback and fallback not in models:
        models.append(fallback)
    last_exc = None
    for index, model in enumerate(models):
        try:
            return client.responses.create(model=model, **kwargs)
        except Exception as exc:
            last_exc = exc
            if index == len(models) - 1 or not _model_access_error(exc):
                raise
    raise last_exc


def chat(organization, messages: list[dict], context: str = "") -> tuple[str, dict]:
    input_messages = [{"role": "developer", "content": SYSTEM_PROMPT + (f"\n\nKontext:\n{context}" if context else "")}]
    input_messages.extend({"role": m["role"], "content": m["content"]} for m in messages[-30:])
    response = _create_response(organization, input=input_messages, store=False)
    usage = response.usage.model_dump() if getattr(response, "usage", None) else {}
    return response.output_text, usage


def structured_extract(organization, prompt: str, schema_name: str, schema: dict, context: str = "") -> dict:
    response = _create_response(
        organization,
        input=[
            {"role": "developer", "content": SYSTEM_PROMPT + (f"\nKontext:\n{context}" if context else "")},
            {"role": "user", "content": prompt},
        ],
        text={"format": {"type": "json_schema", "name": schema_name, "schema": schema, "strict": True}},
        store=False,
    )
    return json.loads(response.output_text)


def suggest_catalog_services(organization, request_text: str, catalog_context: str) -> dict:
    """Return only exact catalog codes that match a user's described work."""
    schema = {
        "type": "object",
        "properties": {
            "summary": {"type": "string"},
            "suggestions": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "code": {"type": "string"},
                        "reason": {"type": "string"},
                        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                    },
                    "required": ["code", "reason", "confidence"],
                    "additionalProperties": False,
                },
            },
            "warnings": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["summary", "suggestions", "warnings"],
        "additionalProperties": False,
    }
    return structured_extract(
        organization,
        (
            "Der Nutzer beschreibt gewünschte Arbeiten für ein Projekt. Wähle ausschließlich "
            "passende Positionen aus dem bereitgestellten Leistungskatalog. Gib nur Codes zurück, "
            "die exakt im Kontext vorkommen. Keine Preise oder Leistungen erfinden. Decke alle ausdrücklich "
            "verlangten Gewerke ab. Wenn die Anfrage Fliesen, verfliesen, Wandfliesen, Bodenfliesen oder "
            "gefliest ausdrücklich nennt, muss mindestens eine passende Fliesen-, Platten- oder Belagsposition "
            "gewählt werden, sofern ein exakt passender Code im bereitgestellten Kontext vorhanden ist. Dasselbe "
            "Coverage-Prinzip gilt für Sanitär, Maler/Spachtel, Türen und andere ausdrücklich verlangte Gewerke. "
            "Erst danach begrenze auf die kleinste sinnvolle Auswahl und nenne kurz den Grund.\n\nAnfrage:\n" + request_text
        ),
        "catalog_service_suggestions",
        schema,
        catalog_context,
    )


def suggest_room_model_state(organization, request_text: str, current_state: dict) -> dict:
    """Apply a natural-language design request to a complete editable room-model state."""
    color = {"type": "string", "pattern": "^#[0-9a-fA-F]{6}$"}
    opening = {
        "type": "object",
        "properties": {
            "id": {"type": "string"},
            "kind": {"type": "string", "enum": ["door", "window", "opening"]},
            "wall": {"type": "string", "enum": ["back", "left", "right", "front"]},
            "width_m": {"type": "number", "minimum": 0.05, "maximum": 10},
            "height_m": {"type": "number", "minimum": 0.05, "maximum": 10},
            "offset_m": {"type": "number", "minimum": 0, "maximum": 50},
            "sill_m": {"type": "number", "minimum": 0, "maximum": 10},
        },
        "required": ["id", "kind", "wall", "width_m", "height_m", "offset_m", "sill_m"],
        "additionalProperties": False,
    }
    fixture = {
        "type": "object",
        "properties": {
            "id": {"type": "string"},
            "kind": {"type": "string", "enum": ["shower", "vanity", "toilet", "bathtub", "radiator", "cabinet", "fixture"]},
            "x_m": {"type": "number", "minimum": 0, "maximum": 50},
            "z_m": {"type": "number", "minimum": 0, "maximum": 50},
            "width_m": {"type": "number", "minimum": 0.05, "maximum": 10},
            "depth_m": {"type": "number", "minimum": 0.05, "maximum": 10},
            "height_m": {"type": "number", "minimum": 0.05, "maximum": 10},
            "rotation_deg": {"type": "number", "minimum": 0, "maximum": 360},
            "color": color,
            "enabled": {"type": "boolean"},
        },
        "required": ["id", "kind", "x_m", "z_m", "width_m", "depth_m", "height_m", "rotation_deg", "color", "enabled"],
        "additionalProperties": False,
    }
    state_schema = {
        "type": "object",
        "properties": {
            "schema_version": {"type": "integer"},
            "room": {
                "type": "object",
                "properties": {
                    "length_m": {"type": "number", "minimum": 0.1, "maximum": 50},
                    "width_m": {"type": "number", "minimum": 0.1, "maximum": 50},
                    "height_m": {"type": "number", "minimum": 0.1, "maximum": 12},
                },
                "required": ["length_m", "width_m", "height_m"],
                "additionalProperties": False,
            },
            "openings": {"type": "array", "items": opening, "maxItems": 100},
            "objects": {"type": "array", "items": fixture, "maxItems": 100},
            "materials": {
                "type": "object",
                "properties": {
                    "floor": color, "wall": color, "ceiling": color, "accent": color, "grout_color": color,
                    "pattern": {"type": "string", "enum": ["straight", "diagonal", "herringbone"]},
                    "tile_width_cm": {"type": "number", "minimum": 1, "maximum": 300},
                    "tile_height_cm": {"type": "number", "minimum": 1, "maximum": 300},
                },
                "required": ["floor", "wall", "ceiling", "accent", "grout_color", "pattern", "tile_width_cm", "tile_height_cm"],
                "additionalProperties": False,
            },
            "lighting": {
                "type": "object",
                "properties": {
                    "brightness": {"type": "number", "minimum": 0.4, "maximum": 1.8},
                    "warmth": {"type": "number", "minimum": 0, "maximum": 100},
                },
                "required": ["brightness", "warmth"],
                "additionalProperties": False,
            },
            "view": {
                "type": "object",
                "properties": {
                    "mode": {"type": "string", "enum": ["perspective", "front", "top"]},
                    "rotation_deg": {"type": "number", "minimum": 0, "maximum": 360},
                },
                "required": ["mode", "rotation_deg"],
                "additionalProperties": False,
            },
        },
        "required": ["schema_version", "room", "openings", "objects", "materials", "lighting", "view"],
        "additionalProperties": False,
    }
    schema = {
        "type": "object",
        "properties": {
            "summary": {"type": "string"},
            "state": state_schema,
            "warnings": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["summary", "state", "warnings"],
        "additionalProperties": False,
    }
    return structured_extract(
        organization,
        (
            "Bearbeite das vorhandene parametrische Raummodell entsprechend der Nutzeranfrage. "
            "Gib immer den vollständigen Modellzustand zurück. Behalte alle nicht erwähnten Werte unverändert. "
            "Maße niemals aus einer bloßen Stilbeschreibung erfinden. Deutsche Dezimalkommas und Zentimeter exakt "
            "in Meter umrechnen. Relative Angaben wie 'Tür gegenüber dem Fenster' als gegenüberliegende Wand modellieren. "
            "Öffnungen und Objekte dürfen nur auf Wunsch hinzugefügt, entfernt oder verändert werden. Farben als Hex-Werte "
            "zurückgeben. Bei 'beide Fliesen 60x60 cm' gilt das Format für Wand- und Bodenfliesen. "
            "Alle für den Nutzer sichtbaren Texte in summary und warnings müssen vollständig auf Deutsch sein.\n\nAnfrage:\n" + request_text
        ),
        "room_model_design",
        schema,
        json.dumps(current_state, ensure_ascii=False),
    )


def suggest_invoice_items(organization, report_text: str, catalog_context: str) -> dict:
    schema = {
        "type": "object",
        "properties": {
            "summary": {"type": "string"},
            "items": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "code": {"type": "string"},
                        "description": {"type": "string"},
                        "quantity": {"type": "number"},
                        "unit": {"type": "string"},
                        "confidence": {"type": "number"},
                        "evidence": {"type": "string"},
                    },
                    "required": ["code", "description", "quantity", "unit", "confidence", "evidence"],
                    "additionalProperties": False,
                },
            },
            "warnings": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["summary", "items", "warnings"],
        "additionalProperties": False,
    }
    return structured_extract(
        organization,
        "Extrahiere ausschließlich belegte, abrechenbare Positionen aus diesem Arbeitsbericht. Keine Position automatisch freigeben.\n\n" + report_text,
        "invoice_item_suggestions",
        schema,
        catalog_context,
    )


def analyze_room_photos(organization, images, calibration: dict | None = None) -> dict:
    """Estimate room geometry from guided photos without presenting guesses as facts.

    The model may only return metric dimensions when a visible, known reference or
    reliable AR/LiDAR metadata is supplied. Results always require human review.
    """
    import base64
    import mimetypes

    calibration = calibration or {}
    content = [{
        "type": "input_text",
        "text": (
            "Analysiere die Aufnahmen als Aufmaß-Assistent für einen deutschen "
            "Haustechnikbetrieb. Erkenne Raumtyp, Wände, Boden, Decke, Türen, Fenster "
            "und sichtbare Installationen. Gib metrische Raummaße NUR aus, wenn eine "
            "eindeutig sichtbare Referenz mit bekannter Größe oder verlässliche AR/LiDAR-"
            "Metadaten vorhanden sind. Ohne belastbare Skalierung müssen length_m, width_m "
            "und height_m null sein. Keine scheinpräzisen Schätzungen erfinden. Nenne "
            "Unsicherheiten und fehlende Aufnahmen. Das Ergebnis ist immer ein prüfpflichtiger "
            "Entwurf und kein verbindliches Aufmaß.\n\n"
            f"Kalibrierung/Metadaten: {json.dumps(calibration, ensure_ascii=False)}"
        ),
    }]
    for image in list(images)[:10]:
        position = image.tell() if hasattr(image, "tell") else None
        raw = image.read()
        if position is not None:
            image.seek(position)
        mime = getattr(image, "content_type", "") or mimetypes.guess_type(getattr(image, "name", ""))[0] or "image/jpeg"
        content.append({
            "type": "input_image",
            "image_url": f"data:{mime};base64,{base64.b64encode(raw).decode('ascii')}",
            "detail": "high",
        })

    schema = {
        "type": "object",
        "properties": {
            "room_type": {"type": "string"},
            "length_m": {"type": ["number", "null"]},
            "width_m": {"type": ["number", "null"]},
            "height_m": {"type": ["number", "null"]},
            "deductions_area_m2": {"type": ["number", "null"]},
            "confidence": {"type": "number", "minimum": 0, "maximum": 1},
            "scale_verified": {"type": "boolean"},
            "method": {"type": "string", "enum": ["reference_photo", "ar_lidar", "visual_only", "insufficient"]},
            "summary": {"type": "string"},
            "evidence": {"type": "array", "items": {"type": "string"}},
            "warnings": {"type": "array", "items": {"type": "string"}},
            "missing_captures": {"type": "array", "items": {"type": "string"}},
            "openings": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "type": {"type": "string"},
                        "width_m": {"type": ["number", "null"]},
                        "height_m": {"type": ["number", "null"]},
                        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                    },
                    "required": ["type", "width_m", "height_m", "confidence"],
                    "additionalProperties": False,
                },
            },
        },
        "required": [
            "room_type", "length_m", "width_m", "height_m", "deductions_area_m2",
            "confidence", "scale_verified", "method", "summary", "evidence", "warnings",
            "missing_captures", "openings",
        ],
        "additionalProperties": False,
    }
    response = _create_response(
        organization,
        input=[
            {"role": "developer", "content": SYSTEM_PROMPT},
            {"role": "user", "content": content},
        ],
        text={"format": {"type": "json_schema", "name": "room_measurement_analysis", "schema": schema, "strict": True}},
        store=False,
    )
    return json.loads(response.output_text)
