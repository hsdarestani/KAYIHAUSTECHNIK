from pathlib import Path
from django.test import SimpleTestCase

ROOT = Path(__file__).resolve().parents[1]


class ToolTimePhase7E2EFlowContractTests(SimpleTestCase):
    def test_order_confirmation_is_real_immutable_project_document(self):
        views = (ROOT / "erp/tooltime_parity_views.py").read_text(encoding="utf-8")
        urls = (ROOT / "erp/rebuild_urls.py").read_text(encoding="utf-8")
        self.assertIn("def quote_order_confirmation(request, pk):", views)
        self.assertIn('"kind": "order_confirmation"', views)
        self.assertIn('"immutable": True', views)
        self.assertIn('hashlib.sha256(payload).hexdigest()', views)
        self.assertIn('project.status = "confirmed"', views)
        self.assertIn('name="next-quote-order-confirmation"', urls)

    def test_invoice_conversion_requires_acceptance_and_order_confirmation_and_is_idempotent(self):
        views = (ROOT / "erp/tooltime_parity_views.py").read_text(encoding="utf-8")
        self.assertIn('if quote.status != "accepted":', views)
        self.assertIn('Bitte zuerst die Auftragsbestätigung erstellen.', views)
        self.assertIn('existing_invoice = m.Invoice.objects.filter(organization=org, quote=quote)', views)
        self.assertIn('quote.project.status = "invoiced"', views)
        self.assertIn('invoice.project.status = "completed"', views)

    def test_field_role_cannot_mutate_commercial_endpoints(self):
        views = (ROOT / "erp/tooltime_parity_views.py").read_text(encoding="utf-8")
        finance = (ROOT / "erp/tooltime_parity_finance.py").read_text(encoding="utf-8")
        self.assertIn('role in {"admin", "office", "project_manager", "accounting"}', views)
        self.assertIn('Diese kaufmännische Aktion ist nur für Büro', views)
        self.assertIn('Mahnungen sind nur für Büro', views)
        for function_name in ("quote_status", "quote_to_invoice", "invoice_payment"):
            start = views.index(f"def {function_name}")
            self.assertIn("_phase7_commercial_guard", views[start:start + 900])

    def test_flow_ui_connects_appointment_acceptance_confirmation_and_invoice(self):
        tags = (ROOT / "erp/templatetags/tooltime_parity.py").read_text(encoding="utf-8")
        template = (ROOT / "templates/rebuild/document_editor.html").read_text(encoding="utf-8")
        self.assertIn("m.CalendarEvent.objects.filter", tags)
        self.assertIn('data-phase7-flow', template)
        self.assertIn('data-phase7-order-confirmation', template)
        for label in ("Kunde", "Projekt", "Termin", "Annahme", "Auftragsbestätigung", "Rechnung"):
            self.assertIn(label, template)
