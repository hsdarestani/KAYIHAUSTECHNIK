from pathlib import Path
from django.test import SimpleTestCase

ROOT = Path(__file__).resolve().parents[1]


class ToolTimeCustomerContactsParityContract(SimpleTestCase):
    def test_customer_schema_and_migration(self):
        models = (ROOT / "erp/models.py").read_text(encoding="utf-8")
        migration = (ROOT / "erp/migrations/0024_tooltime_customer_contacts.py").read_text(encoding="utf-8")
        for needle in ("debtor_number = models.CharField", "routing_id = models.CharField", "supplier_id = models.CharField"):
            self.assertIn(needle, models)
        for needle in ("debtor_number", "routing_id", "supplier_id", "0023_appointment_process_parity"):
            self.assertIn(needle, migration)

    def test_customer_list_is_tooltime_operational(self):
        views = (ROOT / "erp/rebuild_views.py").read_text(encoding="utf-8")
        template = (ROOT / "templates/rebuild/customers.html").read_text(encoding="utf-8")
        urls = (ROOT / "erp/rebuild_urls.py").read_text(encoding="utf-8")
        base = (ROOT / "templates/rebuild/base.html").read_text(encoding="utf-8")
        for needle in ("projects_count=Count(\"projects\", distinct=True)", "sortType", "sortOrder", "offset", "def supplier_list"):
            self.assertIn(needle, views)
        for needle in ("data-customer-modal", "Debitorennummer", "Routing-ID", "Lieferanten-ID", "Projekte", "Zuletzt geändert", "data-row-menu"):
            self.assertIn(needle, template)
        self.assertIn('name="next-suppliers"', urls)
        self.assertIn("data-contacts-group", base)
        self.assertIn("Kontakte", base)
        self.assertIn("Lieferanten", base)

    def test_customer_interactions_are_real(self):
        js = (ROOT / "static/js/kayi-next.js").read_text(encoding="utf-8")
        css = (ROOT / "static/css/kayi-next.css").read_text(encoding="utf-8")
        self.assertIn("data-customer-modal-show", js)
        self.assertIn("data-customer-row", js)
        self.assertIn("data-contacts-toggle", js)
        self.assertIn("A+Bau ToolTime customer contacts parity 20260821", css)
