from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MARKER = "A+BAU TOOLTIME APPOINTMENT FIELD BRIDGE 2026-08-21"


def _function_block(text: str, name: str) -> tuple[int, int, str]:
    marker = f"def {name}("
    start = text.find(marker)
    if start < 0:
        raise RuntimeError(f"Appointment field bridge: {name} fehlt")
    decorator = text.find("\n\n@login_required", start + len(marker))
    end = decorator if decorator >= 0 else len(text)
    return start, end, text[start:end]


def run(module) -> None:
    rel = "erp/field_authorization_views.py"
    text = module.read(rel)

    # Earlier runtime layers may extend the rebuild_views import. Add our two
    # helpers semantically instead of depending on one exact import string.
    import_prefix = "from .rebuild_views import "
    import_pos = text.find(import_prefix)
    if import_pos < 0:
        raise RuntimeError("Appointment field bridge: rebuild_views import fehlt")
    import_end = text.find("\n", import_pos)
    if import_end < 0:
        raise RuntimeError("Appointment field bridge: rebuild_views import line malformed")
    import_line = text[import_pos:import_end]
    if "_appointment_apply_field_services" not in import_line:
        names = import_line[len(import_prefix):].strip()
        import_line = import_prefix + "_appointment_apply_field_services, _appointment_service_snapshot, " + names
        text = text[:import_pos] + import_line + text[import_end:]

    # Enrich only the normal project-backed field detail render. The existing
    # project-missing branch is intentionally left untouched; it is a warning
    # surface, not the signed completion flow.
    start, end, detail = _function_block(text, "field_job_detail")
    if '"service_groups": event.service_groups.prefetch_related' not in detail:
        render_pos = detail.rfind('return render(request, "rebuild/appointment_detail.html", {')
        if render_pos < 0:
            raise RuntimeError("Appointment field bridge: field_job_detail render fehlt")
        close_pos = detail.find("\n    })", render_pos)
        if close_pos < 0:
            raise RuntimeError("Appointment field bridge: field_job_detail context end fehlt")
        context_extra = '''
        "documented": completion is not None or m.Document.objects.filter(organization=org, metadata__event_id=event.pk, category="report").exists(),
        "service_groups": event.service_groups.prefetch_related("items__catalog_item").all().order_by("position", "id"),
        "appointment_catalog": m.CatalogItem.objects.filter(organization=org, active=True).order_by("name")[:500],'''
        detail = detail[:close_pos] + context_extra + detail[close_pos:]
    text = text[:start] + detail + text[end:]

    # Patch the real signed technician completion endpoint, not the legacy
    # appointment_document handler. This preserves Field Authorization while
    # persisting ToolTime-style structured service rows.
    start, end, complete = _function_block(text, "complete_job")
    if "_appointment_apply_field_services(event, request)" not in complete:
        report_anchor = '    report = (request.POST.get("report_text") or "").strip()\n'
        if report_anchor not in complete:
            raise RuntimeError("Appointment field bridge: complete_job report anchor fehlt")
        complete = complete.replace(
            report_anchor,
            "    # Store structured appointment positions. Prices remain server-side.\n"
            "    _appointment_apply_field_services(event, request)\n" + report_anchor,
            1,
        )
    if '"service_items": _appointment_service_snapshot(event)' not in complete:
        material_anchor = '        "material": material,\n'
        if material_anchor not in complete:
            raise RuntimeError("Appointment field bridge: completion snapshot material anchor fehlt")
        complete = complete.replace(
            material_anchor,
            material_anchor + '        "service_items": _appointment_service_snapshot(event),\n',
            1,
        )
    text = text[:start] + complete + text[end:]

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
