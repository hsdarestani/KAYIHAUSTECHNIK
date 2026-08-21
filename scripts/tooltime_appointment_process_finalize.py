from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _move_script_inside_block(text: str, marker: str, *, after_existing_script: bool) -> str:
    start = text.find(marker)
    if start < 0:
        return text
    end = text.find("</script>", start)
    if end < 0:
        raise RuntimeError("Appointment parity finalize: script end fehlt")
    end += len("</script>")
    segment = text[start:end]
    text = text[:start] + text[end:]
    if after_existing_script:
        anchor = "</script>\n{% endblock %}"
        pos = text.rfind(anchor)
        if pos < 0:
            raise RuntimeError("Appointment parity finalize: scripts block anchor fehlt")
        insert_at = pos + len("</script>\n")
    else:
        anchor = "{% endblock %}"
        pos = text.rfind(anchor)
        if pos < 0:
            raise RuntimeError("Appointment parity finalize: content block anchor fehlt")
        insert_at = pos
    return text[:insert_at] + segment + "\n" + text[insert_at:]


def run(module) -> None:
    form_rel = "templates/rebuild/appointment_form.html"
    form = module.read(form_rel)
    form = _move_script_inside_block(
        form,
        "<script>\n(() => {\n  const root = document.querySelector('[data-service-editor]');",
        after_existing_script=True,
    )
    module.write(form_rel, form)

    detail_rel = "templates/rebuild/appointment_detail.html"
    detail = module.read(detail_rel)
    detail = _move_script_inside_block(
        detail,
        "<script>(()=>{const root=document.querySelector('[data-field-services]')",
        after_existing_script=False,
    )
    module.write(detail_rel, detail)

    legacy_test_rel = "tests/test_tooltime_phase10_appointments.py"
    legacy_test = module.read(legacy_test_rel)
    legacy_test = legacy_test.replace('"Wiederholt sich nicht"', '"Einmalig"')
    module.write(legacy_test_rel, legacy_test)
    compile(legacy_test, str(ROOT / legacy_test_rel), "exec")

    for rel, markers in {
        "erp/models.py": ("AppointmentServiceGroup", "AppointmentServiceItem", "work_report"),
        "erp/rebuild_views.py": ("appointment_from_quote", "appointment_to_quote", "appointment_to_invoice"),
        "templates/rebuild/appointment_form.html": ("Terminname", "Mitarbeiter hinzufügen", "Leistungsgruppe hinzufügen", "Arbeitsbericht"),
        "templates/rebuild/appointment_detail.html": ("Angebot erstellen", "Rechnung erstellen", "document_service_quantity"),
    }.items():
        body = module.read(rel)
        for marker in markers:
            if marker not in body:
                raise RuntimeError(f"Appointment parity finalize: {marker} fehlt in {rel}")

    compile(module.read("erp/rebuild_views.py"), str(ROOT / "erp/rebuild_views.py"), "exec")
    compile(module.read("erp/rebuild_urls.py"), str(ROOT / "erp/rebuild_urls.py"), "exec")
