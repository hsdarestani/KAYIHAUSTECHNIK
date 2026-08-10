from __future__ import annotations

import json
import logging
from decimal import Decimal, InvalidOperation

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Max
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_POST

from . import models as m
from .rebuild_projects import _projects_for
from .rebuild_views import _is_field_user, _org
from .services.permissions import can_write
from .services.room_planner_state import OBJECT_SPECS, blank_room_state, merge_vision_result, normalize_room_state, opening_area
from .services.room_vision import analyze_room_scene

logger = logging.getLogger(__name__)

CAPTURE_KINDS = [
    m.MeasurementCapture.Kind.DOORWAY,
    m.MeasurementCapture.Kind.WALL_1,
    m.MeasurementCapture.Kind.WALL_2,
    m.MeasurementCapture.Kind.WALL_3,
    m.MeasurementCapture.Kind.WALL_4,
    m.MeasurementCapture.Kind.FLOOR,
    m.MeasurementCapture.Kind.CEILING,
    m.MeasurementCapture.Kind.CONNECTIONS,
    m.MeasurementCapture.Kind.WINDOWS,
    m.MeasurementCapture.Kind.DAMAGE,
]


def _optional_decimal(value):
    if value in (None, ""):
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None


def _project(request, project_pk):
    org = _org(request)
    return org, get_object_or_404(_projects_for(request, org).select_related("customer", "object_location"), pk=project_pk)


def _measurement_for(project, org, measurement_id=None):
    qs = m.RoomMeasurement.objects.filter(organization=org, project=project).prefetch_related("captures").order_by("-updated_at", "-pk")
    if measurement_id:
        return qs.filter(pk=measurement_id).first()
    return qs.first()


def _state_for(measurement):
    if measurement is None:
        return blank_room_state(), None
    revision = measurement.model_revisions.order_by("-revision").first()
    scan = getattr(measurement, "native_scan", None)
    if revision:
        return normalize_room_state(revision.state, measurement, scan), revision
    payload = measurement.ai_payload if isinstance(measurement.ai_payload, dict) else {}
    draft = payload.get("planner_state") if isinstance(payload.get("planner_state"), dict) else None
    if draft:
        return normalize_room_state(draft, measurement, scan), None
    return normalize_room_state({}, measurement, scan), None


@login_required
def room_planner(request, project_pk):
    org, project = _project(request, project_pk)
    measurement_id = request.GET.get("measurement")
    measurement = _measurement_for(project, org, measurement_id)
    state, latest_revision = _state_for(measurement)
    requested_revision = request.GET.get("revision")
    if measurement and requested_revision:
        selected_revision = measurement.model_revisions.filter(pk=requested_revision).first()
        if selected_revision:
            state = normalize_room_state(selected_revision.state, measurement, getattr(measurement, "native_scan", None))
            latest_revision = selected_revision
    measurements = m.RoomMeasurement.objects.filter(organization=org, project=project).order_by("-updated_at", "-pk")
    revisions = measurement.model_revisions.select_related("created_by", "source_scan").order_by("-revision") if measurement else m.RoomModelRevision.objects.none()
    scans = project.native_room_scans.select_related("measurement").order_by("-created_at")[:20]
    category_labels = {
        "sanitary": "Sanitär", "heating": "Heizung & Technik", "kitchen": "Küche", "appliance": "Geräte",
        "furniture": "Möbel", "electrical": "Elektro", "technical": "Installationen", "structural": "Baukörper", "general": "Weitere",
    }
    grouped: dict[str, list[dict]] = {}
    for kind, spec in OBJECT_SPECS.items():
        if kind == "fixture":
            continue
        grouped.setdefault(spec["category"], []).append({"kind": kind, **spec})
    categories = [{"key": key, "label": category_labels.get(key, key), "items": items} for key, items in grouped.items()]
    return render(request, "rebuild/room_planner.html", {
        "project": project,
        "measurement": measurement,
        "measurements": measurements,
        "latest_revision": latest_revision,
        "revisions": revisions,
        "native_scans": scans,
        "planner_state": state,
        "object_categories": categories,
        "field_user": _is_field_user(request),
        "readonly": not can_write(request.user) or request.GET.get("view") == "1",
    })


@login_required
@require_POST
def room_planner_save(request, project_pk):
    if not can_write(request.user):
        raise PermissionDenied("Keine Schreibberechtigung.")
    org, project = _project(request, project_pk)
    try:
        payload = json.loads(request.body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return JsonResponse({"error": "Ungültige JSON-Daten."}, status=400)
    measurement = _measurement_for(project, org, payload.get("measurement_id")) if payload.get("measurement_id") else None
    scan = getattr(measurement, "native_scan", None) if measurement else None
    try:
        state = normalize_room_state(payload.get("state"), measurement, scan)
    except ValidationError as exc:
        return JsonResponse({"error": "3D-Modell konnte nicht gespeichert werden.", "details": getattr(exc, "message_dict", {})}, status=400)

    with transaction.atomic():
        if measurement is None:
            measurement = m.RoomMeasurement.objects.create(
                organization=org,
                project=project,
                name=str(payload.get("room_name") or "Raum")[:160],
                method=m.RoomMeasurement.Method.MANUAL,
                status=m.RoomMeasurement.Status.REVIEW,
                created_by=request.user,
            )
            scan = None
        else:
            measurement = m.RoomMeasurement.objects.select_for_update().get(pk=measurement.pk, organization=org, project=project)
            scan = getattr(measurement, "native_scan", None)
        next_revision = (m.RoomModelRevision.objects.filter(measurement=measurement).aggregate(value=Max("revision"))["value"] or 0) + 1
        revision = m.RoomModelRevision.objects.create(
            organization=org,
            project=project,
            measurement=measurement,
            source_scan=scan,
            revision=next_revision,
            label=str(payload.get("label") or payload.get("notes") or "")[:160],
            state=state,
            created_by=request.user,
        )
        room = state["room"]
        new_values = {
            "length_m": Decimal(room["length_m"]),
            "width_m": Decimal(room["width_m"]),
            "height_m": Decimal(room["height_m"]),
            "deductions_area_m2": opening_area(state),
        }
        geometry_changed = any(getattr(measurement, field) != value for field, value in new_values.items())
        for field, value in new_values.items():
            setattr(measurement, field, value)
        if geometry_changed or measurement.status != m.RoomMeasurement.Status.CONFIRMED:
            measurement.status = m.RoomMeasurement.Status.REVIEW
            measurement.confirmed_by = None
            measurement.confirmed_at = None
        measurement.ai_payload = {**(measurement.ai_payload if isinstance(measurement.ai_payload, dict) else {}), "planner_state": state}
        measurement.save()

    return JsonResponse({
        "saved": True,
        "measurement_id": measurement.pk,
        "revision": revision.revision,
        "revision_id": revision.pk,
        "status": measurement.status,
        "status_label": measurement.get_status_display(),
    }, status=201)


@login_required
@require_POST
def room_planner_vision(request, project_pk):
    if not can_write(request.user):
        raise PermissionDenied("Keine Schreibberechtigung.")
    org, project = _project(request, project_pk)
    images = request.FILES.getlist("images")
    if not images:
        return JsonResponse({"error": "Bitte mindestens ein Raumfoto auswählen."}, status=400)
    if len(images) > 12:
        return JsonResponse({"error": "Maximal 12 Aufnahmen pro Raumanalyse."}, status=400)
    total_size = 0
    for image in images:
        total_size += image.size
        if image.size > 12 * 1024 * 1024:
            return JsonResponse({"error": f"{image.name}: Datei ist größer als 12 MB."}, status=400)
        if getattr(image, "content_type", "") not in {"image/jpeg", "image/png", "image/webp"}:
            return JsonResponse({"error": f"{image.name}: Bildformat wird nicht unterstützt."}, status=400)
    if total_size > 50 * 1024 * 1024:
        return JsonResponse({"error": "Die Aufnahmen sind zusammen größer als 50 MB."}, status=400)

    measurement = _measurement_for(project, org, request.POST.get("measurement_id")) if request.POST.get("measurement_id") else None
    current_state, _ = _state_for(measurement)
    try:
        posted_state = json.loads(request.POST.get("state") or "{}")
        if isinstance(posted_state, dict) and posted_state.get("room"):
            current_state = normalize_room_state(posted_state, measurement, getattr(measurement, "native_scan", None) if measurement else None)
    except (json.JSONDecodeError, ValidationError):
        pass
    calibration = {
        "reference_type": str(request.POST.get("reference_type") or ""),
        "reference_width_cm": request.POST.get("reference_width_cm") or None,
        "reference_height_cm": request.POST.get("reference_height_cm") or None,
        "capture_sequence": request.POST.get("capture_sequence") or None,
        "existing_dimensions": current_state.get("room", {}),
        "existing_dimensions_confirmed": bool(measurement and measurement.status == m.RoomMeasurement.Status.CONFIRMED),
    }
    if calibration["reference_type"] == "a4":
        calibration["reference_width_cm"] = 21.0
        calibration["reference_height_cm"] = 29.7
    try:
        vision = analyze_room_scene(org, images, calibration=calibration, current_state=current_state)
        merged = merge_vision_result(current_state, vision)
        state = normalize_room_state(merged, measurement, getattr(measurement, "native_scan", None) if measurement else None)
    except Exception:
        logger.exception("KAYI Room Planner vision analysis failed")
        return JsonResponse({"error": "Die 3D-Raumerkennung ist momentan nicht erreichbar. Bitte erneut versuchen."}, status=502)

    with transaction.atomic():
        if measurement is None:
            measurement = m.RoomMeasurement.objects.create(
                organization=org,
                project=project,
                name=(vision.get("room_type") or "Raum")[:160],
                method=m.RoomMeasurement.Method.AI_PHOTO,
                status=m.RoomMeasurement.Status.REVIEW,
                created_by=request.user,
            )
        measurement.method = m.RoomMeasurement.Method.AI_PHOTO
        measurement.status = m.RoomMeasurement.Status.REVIEW
        measurement.confidence = Decimal(str(max(0, min(1, float(vision.get("confidence") or 0)))))
        measurement.ai_summary = str(vision.get("summary") or "")
        measurement.ai_warnings = list(vision.get("warnings") or []) + [f"Fehlende Aufnahme: {item}" for item in (vision.get("missing_captures") or [])]
        measurement.length_m = Decimal(state["room"]["length_m"])
        measurement.width_m = Decimal(state["room"]["width_m"])
        measurement.height_m = Decimal(state["room"]["height_m"])
        measurement.deductions_area_m2 = opening_area(state)
        measurement.reference_type = str(calibration.get("reference_type") or "")[:40]
        measurement.reference_width_cm = _optional_decimal(calibration.get("reference_width_cm"))
        measurement.reference_height_cm = _optional_decimal(calibration.get("reference_height_cm"))
        measurement.ai_payload = {**(measurement.ai_payload if isinstance(measurement.ai_payload, dict) else {}), "vision": vision, "planner_state": state}
        measurement.save(update_fields=["method", "status", "confidence", "ai_summary", "ai_warnings", "ai_payload", "length_m", "width_m", "height_m", "deductions_area_m2", "reference_type", "reference_width_cm", "reference_height_cm", "updated_at"])
        next_revision = (m.RoomModelRevision.objects.filter(measurement=measurement).aggregate(value=Max("revision"))["value"] or 0) + 1
        m.RoomModelRevision.objects.create(
            organization=org, project=project, measurement=measurement, source_scan=getattr(measurement, "native_scan", None),
            revision=next_revision, label="AI-Fotoerkennung", state=state, created_by=request.user,
        )
        for index, image in enumerate(images):
            if hasattr(image, "seek"):
                image.seek(0)
            m.MeasurementCapture.objects.create(
                measurement=measurement,
                kind=CAPTURE_KINDS[index] if index < len(CAPTURE_KINDS) else m.MeasurementCapture.Kind.OTHER,
                image=image,
                created_by=request.user,
                metadata={"planner_vision": True, "capture_index": index + 1},
            )

    return JsonResponse({
        "measurement_id": measurement.pk,
        "state": state,
        "summary": vision.get("summary") or "Raum erkannt.",
        "warnings": measurement.ai_warnings,
        "confidence": float(measurement.confidence),
        "scale_verified": bool(vision.get("scale_verified")),
        "recognized_objects": len(state.get("objects", [])),
        "recognized_openings": len(state.get("openings", [])),
    })
