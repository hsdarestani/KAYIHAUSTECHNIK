from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MARKER = "A+BAU FINAL ROOM PLANNER + FIELD FLOW GUARD 2026-08-21"


def read(rel: str) -> str:
    path = ROOT / rel
    if not path.exists():
        raise RuntimeError(f"Final flow guard target missing: {rel}")
    return path.read_text(encoding="utf-8")


def write(rel: str, text: str) -> None:
    path = ROOT / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def restore_room_planner_routes() -> None:
    """Keep the modern Room Planner Pro as the only primary 3D entry point.

    The legacy /configurator/ route stays available as a compatibility fallback,
    but ToolTime/rebuild pages must never send users there. That page uses the old
    shell and does not expose the complete Room Planner Pro object/vision workflow.
    """
    replacements = {
        "{% url 'configurator' %}?project={{ project.pk }}": "{% url 'next-room-planner' project.pk %}",
        '{% url "configurator" %}?project={{ project.pk }}': "{% url 'next-room-planner' project.pk %}",
        "{% url 'configurator' %}?project={{ event.project.pk }}": "{% url 'next-room-planner' event.project.pk %}",
        '{% url "configurator" %}?project={{ event.project.pk }}': "{% url 'next-room-planner' event.project.pk %}",
    }
    template_dir = ROOT / "templates" / "rebuild"
    patched = 0
    for path in template_dir.glob("*.html"):
        text = path.read_text(encoding="utf-8")
        original = text
        for old, new in replacements.items():
            text = text.replace(old, new)
        if text != original:
            path.write_text(text, encoding="utf-8")
            patched += 1

    project = read("templates/rebuild/project_detail.html")
    if "next-room-planner' project.pk" not in project and 'next-room-planner" project.pk' not in project:
        raise RuntimeError("Project detail is not connected to Room Planner Pro")
    if "configurator' %}?project={{ project.pk }}" in project or 'configurator" %}?project={{ project.pk }}' in project:
        raise RuntimeError("Project detail still points to the legacy configurator")

    appointment = read("templates/rebuild/appointment_detail.html")
    if "configurator' %}?project={{ event.project.pk }}" in appointment or 'configurator" %}?project={{ event.project.pk }}' in appointment:
        raise RuntimeError("Technician appointment still points to the legacy configurator")

    print(f"{MARKER}: restored modern 3D routes in {patched} rebuild template(s).")


def install_regression_test() -> None:
    write(
        "tests/test_final_room_planner_field_flow_guard.py",
        r'''from pathlib import Path

from django.test import SimpleTestCase

ROOT = Path(__file__).resolve().parents[1]


class FinalRoomPlannerAndFieldFlowGuardTests(SimpleTestCase):
    def test_project_detail_uses_room_planner_pro_not_legacy_configurator(self):
        project = (ROOT / "templates/rebuild/project_detail.html").read_text(encoding="utf-8")
        self.assertIn("next-room-planner", project)
        self.assertNotIn("{% url 'configurator' %}?project={{ project.pk }}", project)
        self.assertNotIn('{% url "configurator" %}?project={{ project.pk }}', project)

    def test_room_planner_pro_runtime_and_ai_vision_are_still_installed(self):
        template = (ROOT / "templates/rebuild/room_planner.html").read_text(encoding="utf-8")
        js = (ROOT / "static/js/room-planner.js").read_text(encoding="utf-8")
        views = (ROOT / "erp/room_planner_views.py").read_text(encoding="utf-8")
        for marker in ("data-rp-canvas", "data-rp-open-vision", "data-rp-add-object"):
            self.assertIn(marker, template)
        for marker in ("KAYI_ROOM_PLANNER_PRO", "WebGLRenderer"):
            self.assertIn(marker, js)
        self.assertIn("room_vision", views)

    def test_technician_voice_ai_signature_pdf_flow_survives_final_ui_layers(self):
        appointment = (ROOT / "templates/rebuild/appointment_detail.html").read_text(encoding="utf-8")
        field_home = (ROOT / "templates/rebuild/field_home.html").read_text(encoding="utf-8")
        field_views = (ROOT / "erp/field_authorization_views.py").read_text(encoding="utf-8")
        next_js = (ROOT / "static/js/kayi-next.js").read_text(encoding="utf-8")
        field_js = (ROOT / "static/js/field-authorization.js").read_text(encoding="utf-8")

        self.assertIn("Vor Ort in einem Ablauf", field_home)
        for marker in (
            "data-field-voice",
            "data-field-record",
            "data-field-transcribe",
            "data-customer-reviewed",
            "Kundenunterschrift zum Abschluss",
            "Einsatz abschließen & PDF erstellen",
            "data-handoff-result",
        ):
            self.assertIn(marker, appointment)
        for marker in ("KAYI_FINAL_CUSTOMER_HANDOFF", "field_voice_note", "customer_reviewed"):
            self.assertIn(marker, field_views)
        for marker in ("KAYIFieldHandoff", "MediaRecorder", "data-field-voice"):
            self.assertIn(marker, next_js)
        self.assertIn("KAYIFieldHandoff?.showResult", field_js)

    def test_technician_primary_3d_link_uses_same_pro_planner(self):
        appointment = (ROOT / "templates/rebuild/appointment_detail.html").read_text(encoding="utf-8")
        self.assertNotIn("{% url 'configurator' %}?project={{ event.project.pk }}", appointment)
        self.assertNotIn('{% url "configurator" %}?project={{ event.project.pk }}', appointment)
        if "Aufmaß & 3D" in appointment or "Raum & 3D" in appointment:
            self.assertIn("next-room-planner", appointment)
''',
    )


def guard_existing_tests() -> None:
    required_tests = [
        "tests/test_room_planner_pro.py",
        "tests/test_global_ai_field_handoff.py",
        "tests/test_android_voice_capture_hotfix.py",
        "tests/test_ai_role_permissions.py",
        "tests/test_technician_project_approval_flow.py",
        "tests/test_tooltime_appointment_field_bridge_contract.py",
        "tests/test_tooltime_appointment_process_parity.py",
    ]
    missing = [rel for rel in required_tests if not (ROOT / rel).exists()]
    if missing:
        raise RuntimeError(f"Critical regression suites disappeared from final assembly: {missing}")

    smoke = read("scripts/production_browser_smoke.py")
    for marker in (
        "KAYI Room Planner Pro browser smoke",
        "run_field_surface",
        "technician root did not redirect to /field/",
        "global KAYI KI assistant",
    ):
        if marker not in smoke:
            raise RuntimeError(f"Production browser smoke lost critical coverage: {marker}")


def main() -> None:
    restore_room_planner_routes()
    install_regression_test()
    guard_existing_tests()
    test_source = read("tests/test_final_room_planner_field_flow_guard.py")
    compile(test_source, str(ROOT / "tests/test_final_room_planner_field_flow_guard.py"), "exec")
    print(f"{MARKER}: Room Planner Pro, technician voice/KI/signature/PDF and regression coverage preserved.")


if __name__ == "__main__":
    main()
