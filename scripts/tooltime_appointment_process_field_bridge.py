from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MARKER = "A+BAU TOOLTIME APPOINTMENT FIELD BRIDGE 2026-08-21"


def run(module) -> None:
    rel = "erp/field_authorization_views.py"
    text = module.read(rel)

    old_import = "from .rebuild_views import _employee, _is_field_user, _org, _unique_number\n"
    new_import = "from .rebuild_views import _appointment_apply_field_services, _appointment_service_snapshot, _employee, _is_field_user, _org, _unique_number\n"
    if "_appointment_apply_field_services" not in text.split("\n", 35)[-1] or new_import not in text:
        if old_import in text:
            text = text.replace(old_import, new_import, 1)
        elif new_import not in text:
            raise RuntimeError("Appointment field bridge: rebuild_views import anchor fehlt")

    old_missing = '''    if event.project_id is None:
        return render(request, "rebuild/appointment_detail.html", {"event": event, "project_missing": True})
'''
    new_missing = '''    if event.project_id is None:
        documented = m.Document.objects.filter(organization=org, metadata__event_id=event.pk, category="report").exists()
        return render(request, "rebuild/appointment_detail.html", {
            "event": event,
            "project_missing": True,
            "documented": documented,
            "service_groups": event.service_groups.prefetch_related("items__catalog_item").all().order_by("position", "id"),
            "appointment_catalog": m.CatalogItem.objects.filter(organization=org, active=True).order_by("name")[:500],
        })
'''
    if new_missing not in text:
        if old_missing not in text:
            raise RuntimeError("Appointment field bridge: project-missing detail anchor fehlt")
        text = text.replace(old_missing, new_missing, 1)

    context_anchor = '''        "pricing_modes": [("fixed", "Festpreis"), ("estimate", "Kostenschätzung / Budgetfreigabe"), ("hourly", "Nach Aufwand")],
    })'''
    context_new = '''        "pricing_modes": [("fixed", "Festpreis"), ("estimate", "Kostenschätzung / Budgetfreigabe"), ("hourly", "Nach Aufwand")],
        "documented": completion is not None or m.Document.objects.filter(organization=org, metadata__event_id=event.pk, category="report").exists(),
        "service_groups": event.service_groups.prefetch_related("items__catalog_item").all().order_by("position", "id"),
        "appointment_catalog": m.CatalogItem.objects.filter(organization=org, active=True).order_by("name")[:500],
    })'''
    if context_new not in text:
        if context_anchor not in text:
            raise RuntimeError("Appointment field bridge: field_job_detail context anchor fehlt")
        text = text.replace(context_anchor, context_new, 1)

    completion_anchor = '''    if not isinstance(snapshot, dict):
        return JsonResponse({"ok": False, "error": "Die Freigabe enthält keinen gültigen Snapshot."}, status=409)
    report = (request.POST.get("report_text") or "").strip()
'''
    completion_new = '''    if not isinstance(snapshot, dict):
        return JsonResponse({"ok": False, "error": "Die Freigabe enthält keinen gültigen Snapshot."}, status=409)
    # Persist ToolTime-style appointment positions on the real technician
    # completion endpoint. Prices remain server-side on AppointmentServiceItem
    # and are never rendered in the field form.
    _appointment_apply_field_services(event, request)
    report = (request.POST.get("report_text") or "").strip()
'''
    if completion_new not in text:
        if completion_anchor not in text:
            raise RuntimeError("Appointment field bridge: complete_job anchor fehlt")
        text = text.replace(completion_anchor, completion_new, 1)

    snapshot_anchor = '''        "services": services,
        "material": material,
        "after_photos": [{"name": item["name"], "sha256": item["sha256"]} for item in after_photos],
'''
    snapshot_new = '''        "services": services,
        "material": material,
        "service_items": _appointment_service_snapshot(event),
        "after_photos": [{"name": item["name"], "sha256": item["sha256"]} for item in after_photos],
'''
    if snapshot_new not in text:
        if snapshot_anchor not in text:
            raise RuntimeError("Appointment field bridge: completion snapshot anchor fehlt")
        text = text.replace(snapshot_anchor, snapshot_new, 1)

    module.write(rel, text)
    compile(text, str(ROOT / rel), "exec")

    for marker in (
        "_appointment_apply_field_services(event, request)",
        '"service_items": _appointment_service_snapshot(event)',
        '"service_groups": event.service_groups.prefetch_related',
        '"appointment_catalog": m.CatalogItem.objects.filter',
    ):
        if marker not in text:
            raise RuntimeError(f"Appointment field bridge guard missing: {marker}")
    print(f"{MARKER}: real signed technician completion persists ToolTime appointment positions without exposing stored prices.")
