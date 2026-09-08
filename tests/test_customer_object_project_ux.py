from pathlib import Path
from django.test import SimpleTestCase

ROOT = Path(__file__).resolve().parents[1]


class CustomerObjectProjectUXContract(SimpleTestCase):
    def test_customer_detail_has_object_creation_and_no_duplicate_local_actions(self):
        template = (ROOT / "templates/rebuild/customer_detail.html").read_text(encoding="utf-8")
        self.assertIn("＋ Objekt hinzufügen", template)
        self.assertIn('name="action" value="add_location"', template)
        self.assertIn("Standardmäßig wird die Kundenadresse", template)
        self.assertNotIn("next-appointment-create", template)

    def test_project_object_locations_are_customer_scoped(self):
        views = (ROOT / "erp/rebuild_views.py").read_text(encoding="utf-8")
        urls = (ROOT / "erp/rebuild_urls.py").read_text(encoding="utf-8")
        template = (ROOT / "templates/rebuild/project_form.html").read_text(encoding="utf-8")
        self.assertIn('empty_label = "Kundenadresse verwenden (Standard)"', views)
        self.assertIn("locations.filter(customer_id=customer_id)", views)
        self.assertIn("def customer_locations_api", views)
        self.assertIn("next-customer-locations-api", urls)
        self.assertIn("＋ Einsatzort anlegen", template)
        self.assertIn("locations.json", template)
