from __future__ import annotations

import json
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from django.core.exceptions import ValidationError
from django.db import transaction

from erp.models import NativeRoomScan, Project, RoomMeasurement

MAX_MODEL_SIZE = 80 * 1024 * 1024
ALLOWED_MODEL_EXTENSIONS = {".usdz", ".usd", ".obj", ".glb", ".gltf", ".json"}
ALLOWED_MODEL_MIMES = {
    "model/vnd.usdz+zip", "model/gltf-binary", "model/gltf+json", "text/plain",
    "application/octet-stream", "application/json", "model/obj",
}


def _decimal(value: Any, name: str, *, minimum: Decimal, maximum: Decimal) -> Decimal:
    try:
        result = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        raise ValidationError({name: "Ungültiger Zahlenwert."})
    if not result.is_finite() or result < minimum or result > maximum:
        raise ValidationError({name: f"Wert muss zwischen {minimum} und {maximum} liegen."})
    return result.quantize(Decimal("0.001"))


def _list(value: Any, name: str, *, maximum: int = 500) -> list[dict[str, Any]]:
    if value is None:
        return []
    if not isinstance(value, list) or len(value) > maximum:
        raise ValidationError({name: "Ungültige oder zu große Geometrieliste."})
    return [item for item in value if isinstance(item, dict)]


def parse_payload(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        payload = value
    else:
        try:
            payload = json.loads(value or "{}")
        except (TypeError, ValueError):
            raise ValidationError({"payload": "Ungültiges JSON."})
    if not isinstance(payload, dict):
        raise ValidationError({"payload": "JSON-Objekt erwartet."})
    encoded = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    if len(encoded) > 5 * 1024 * 1024:
        raise ValidationError({"payload": "Scan-Daten sind größer als 5 MB."})
    return payload


def validate_model_upload(upload, provider: str) -> None:
    if not upload:
        return
    if upload.size > MAX_MODEL_SIZE:
        raise ValidationError({"model_file": "3D-Modell ist größer als 80 MB."})
    extension = Path(upload.name).suffix.lower()
    content_type = getattr(upload, "content_type", "") or "application/octet-stream"
    if extension not in ALLOWED_MODEL_EXTENSIONS or content_type not in ALLOWED_MODEL_MIMES:
        raise ValidationError({"model_file": "Nicht unterstütztes 3D-Modellformat."})
    if provider == NativeRoomScan.Provider.APPLE_ROOMPLAN and extension not in {".usdz", ".usd"}:
        raise ValidationError({"model_file": "RoomPlan erwartet eine USD/USDZ-Datei."})


def normalize_native_scan(payload: dict[str, Any], provider: str) -> dict[str, Any]:
    schema_version = str(payload.get("schema_version", "1.0"))
    room = payload.get("room") if isinstance(payload.get("room"), dict) else {}
    bounds = room.get("bounds") if isinstance(room.get("bounds"), dict) else {}
    dimensions = room.get("dimensions") if isinstance(room.get("dimensions"), dict) else room

    length = dimensions.get("length_m", bounds.get("length_m"))
    width = dimensions.get("width_m", bounds.get("width_m"))
    height = dimensions.get("height_m", bounds.get("height_m"))
    length_d = _decimal(length, "length_m", minimum=Decimal("0.20"), maximum=Decimal("100"))
    width_d = _decimal(width, "width_m", minimum=Decimal("0.20"), maximum=Decimal("100"))
    height_d = _decimal(height, "height_m", minimum=Decimal("1.20"), maximum=Decimal("20"))

    walls = _list(payload.get("walls"), "walls")
    doors = _list(payload.get("doors"), "doors")
    windows = _list(payload.get("windows"), "windows")
    openings = _list(payload.get("openings"), "openings")
    objects = _list(payload.get("objects"), "objects", maximum=1000)
    corners = _list(payload.get("corners"), "corners")

    deductions = Decimal("0")
    for item in doors + windows + openings:
        dims = item.get("dimensions") if isinstance(item.get("dimensions"), dict) else item
        item_width = dims.get("width_m")
        item_height = dims.get("height_m")
        if item_width is None or item_height is None:
            continue
        try:
            deductions += _decimal(item_width, "opening_width", minimum=Decimal("0"), maximum=Decimal("20")) * _decimal(item_height, "opening_height", minimum=Decimal("0"), maximum=Decimal("20"))
        except ValidationError:
            continue
    max_deduction = Decimal("2") * (length_d + width_d) * height_d
    deductions = min(deductions, max_deduction).quantize(Decimal("0.001"))

    raw_confidence = payload.get("confidence", payload.get("tracking_confidence", 0.75 if provider == NativeRoomScan.Provider.APPLE_ROOMPLAN else 0.60))
    confidence = _decimal(raw_confidence, "confidence", minimum=Decimal("0"), maximum=Decimal("1"))
    warnings = [str(w)[:400] for w in payload.get("warnings", []) if isinstance(w, (str, int, float))][:50]
    if provider == NativeRoomScan.Provider.ANDROID_ARCORE_DEPTH:
        warnings.append("ARCore-Depth-Aufmaß muss wegen geräteabhängiger Tiefenqualität manuell geprüft werden.")

    return {
        "schema_version": schema_version,
        "provider": provider,
        "capture_mode": str(payload.get("capture_mode") or "native_scan")[:40],
        "room": {
            "name": str(room.get("name") or payload.get("room_name") or "Raum")[:160],
            "dimensions": {"length_m": str(length_d), "width_m": str(width_d), "height_m": str(height_d)},
            "deductions_area_m2": str(deductions),
        },
        "walls": walls,
        "doors": doors,
        "windows": windows,
        "openings": openings,
        "objects": objects,
        "corners": corners,
        "confidence": str(confidence),
        "coordinate_system": str(payload.get("coordinate_system") or "right_handed_y_up")[:80],
        "warnings": warnings,
        "requires_confirmation": True,
    }


def create_native_scan(*, organization, project: Project, user, client_scan_id, provider: str, payload: dict[str, Any], model_file=None, preview_file=None, app_version="", device_model="", operating_system="") -> tuple[NativeRoomScan, bool]:
    if provider not in NativeRoomScan.Provider.values:
        raise ValidationError({"provider": "Unbekannter Scanner-Anbieter."})
    validate_model_upload(model_file, provider)
    normalized = normalize_native_scan(payload, provider)
    dimensions = normalized["room"]["dimensions"]
    with transaction.atomic():
        existing = NativeRoomScan.objects.select_related("measurement").filter(organization=organization, client_scan_id=client_scan_id).first()
        if existing:
            if existing.project_id != project.pk:
                raise ValidationError({"client_scan_id": "Scan-ID gehört bereits zu einem anderen Projekt."})
            return existing, False
        manual_fallback = normalized.get("capture_mode") == "manual_fallback"
        measurement = RoomMeasurement.objects.create(
            organization=organization,
            project=project,
            name=normalized["room"]["name"],
            method=RoomMeasurement.Method.MANUAL if manual_fallback else RoomMeasurement.Method.AR_LIDAR,
            status=RoomMeasurement.Status.REVIEW,
            length_m=Decimal(dimensions["length_m"]),
            width_m=Decimal(dimensions["width_m"]),
            height_m=Decimal(dimensions["height_m"]),
            deductions_area_m2=Decimal(normalized["room"]["deductions_area_m2"]),
            confidence=Decimal(normalized["confidence"]),
            ai_summary=(
                "Manuelles iOS-Ersatzaufmaß auf einem Gerät ohne LiDAR. Benutzerprüfung erforderlich."
                if manual_fallback
                else f"Natives Raumaufmaß über {NativeRoomScan.Provider(provider).label}. Benutzerprüfung erforderlich."
            ),
            ai_warnings=normalized["warnings"],
            ai_payload=normalized,
            created_by=user,
        )
        scan = NativeRoomScan.objects.create(
            organization=organization,
            project=project,
            measurement=measurement,
            client_scan_id=client_scan_id,
            provider=provider,
            status=NativeRoomScan.Status.REVIEW,
            room_name=normalized["room"]["name"],
            app_version=str(app_version)[:40],
            device_model=str(device_model)[:120],
            operating_system=str(operating_system)[:80],
            confidence=Decimal(normalized["confidence"]),
            raw_payload=payload,
            normalized_payload=normalized,
            model_file=model_file,
            preview_file=preview_file,
            warnings=normalized["warnings"],
            created_by=user,
        )
    return scan, True
