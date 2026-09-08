from pathlib import Path
from django.test import SimpleTestCase

ROOT = Path(__file__).resolve().parents[1]


class ToolTimePhase10AppointmentContractTests(SimpleTestCase):
    def test_create_form_matches_single_page_tooltime_information_architecture(self):
        template = (ROOT / "templates/rebuild/appointment_form.html").read_text(encoding="utf-8")
        for marker in (
            "Kunde oder Projekt auswählen", "Kunde suchen", "Projekt suchen", "data-address-card",
            "Terminart", "Einmalig", "Ganztägig", "Mitarbeiter suchen", "nur intern",
            "Leistungen", "Arbeitsbericht", "Bilder", "data-start-date", "data-end-time",
        ):
            self.assertIn(marker, template)
        self.assertIn('name="project"', template)
        self.assertIn('name="customer_filter"', template)

    def test_create_form_reuses_existing_persistent_calendar_fields(self):
        views = (ROOT / "erp/rebuild_views.py").read_text(encoding="utf-8")
        self.assertIn('fields = ["title", "type", "starts_at", "ends_at", "all_day", "location", "notes", "project", "attendees"]', views)
        self.assertIn("appointment_customers", views)
        self.assertIn("appointment_projects", views)
        self.assertNotIn("AppointmentRepeatRule", views)

    def test_phase10_is_responsive_and_does_not_fake_unimplemented_persistence(self):
        css = (ROOT / "static/css/tooltime-phase10-appointments.css").read_text(encoding="utf-8")
        template = (ROOT / "templates/rebuild/appointment_form.html").read_text(encoding="utf-8")
        self.assertIn("@media(max-width:700px)", css)
        self.assertIn("Nach dem Speichern", template)
        self.assertIn('name="repeat_rule"', template)
        self.assertIn('value="daily"', template)
        self.assertIn('value="weekly"', template)
        self.assertIn('value="monthly"', template)
        self.assertIn("data-repeat-count", template)
