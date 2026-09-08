from pathlib import Path

from django.test import SimpleTestCase

ROOT = Path(__file__).resolve().parents[1]


class FinalRoomPlannerAndFieldFlowGuardTests(SimpleTestCase):
    def test_project_detail_uses_room_planner_pro_not_legacy_configurator(self):
        project = (ROOT / "templates/rebuild/project_detail.html").read_text(encoding="utf-8")
        self.assertIn("next-room-planner", project)
        self.assertNotIn("{% url 'configurator' %}?project={{ project.pk }}", project)
        self.assertNotIn('{% url "configurator" %}?project={{ project.pk }}', project)

    def test_project_detail_keeps_established_workflow_contracts_and_hides_finance_from_field(self):
        project = (ROOT / "templates/rebuild/project_detail.html").read_text(encoding="utf-8")
        for marker in (
            "Raum & 3D",
            "Aufmaß",
            "B&O Leistungsnachweis / Regiebericht",
            'data-tab="finance"',
            'data-tab-panel="finance"',
            "data-row-href",
            'data-action="open-offer"',
            'data-action="open-invoice"',
            "Herunterladen",
        ):
            self.assertIn(marker, project)
        finance_pos = project.find('data-tab-panel="finance"')
        kpi_pos = project.find("Umsatz (netto)")
        guard_pos = project.rfind("{% if not field_user %}", 0, finance_pos + 1)
        self.assertGreaterEqual(finance_pos, 0)
        self.assertGreaterEqual(kpi_pos, 0)
        self.assertGreaterEqual(guard_pos, 0)
        self.assertLess(guard_pos, finance_pos)
        self.assertLess(guard_pos, kpi_pos)

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
