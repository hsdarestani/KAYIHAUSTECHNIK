from pathlib import Path
from django.test import SimpleTestCase

ROOT = Path(__file__).resolve().parents[1]


class ToolTimePhase4LifecycleContractTests(SimpleTestCase):
    def test_routes_use_phase4_authoritative_views(self):
        urls = (ROOT / "erp/rebuild_urls.py").read_text(encoding="utf-8")
        self.assertIn('tooltime_parity.quote_list', urls)
        self.assertIn('tooltime_parity.invoice_list', urls)
        self.assertIn('tooltime_parity.invoice_payment', urls)

    def test_invoice_lifecycle_is_real_and_payment_safe(self):
        views = (ROOT / "erp/tooltime_parity_views.py").read_text(encoding="utf-8")
        self.assertIn('def _phase4_invoice_display', views)
        self.assertIn('def invoice_payment', views)
        self.assertIn('invoice.compliance.state', views)
        self.assertIn('amount > open_amount', views)
        self.assertIn('m.Payment.objects.create', views)
        self.assertIn('date.fromisoformat', views)

    def test_lists_have_real_filters_and_actions(self):
        quotes = (ROOT / "templates/rebuild/quotes.html").read_text(encoding="utf-8")
        invoices = (ROOT / "templates/rebuild/invoices.html").read_text(encoding="utf-8")
        for phrase in ('Suchen', 'Status', 'Sortieren', 'In Rechnung'):
            self.assertIn(phrase, quotes)
        for phrase in ('Ausstehend', 'Überfällig', 'Zahlung eintragen', 'Zahlungserinnerung'):
            self.assertIn(phrase, invoices)
        self.assertIn('data-payment-open', invoices)
        self.assertIn('next-invoice-payment', invoices)

    def test_no_fake_tooltime_pay_product_is_added(self):
        combined = '\n'.join((
            (ROOT / "erp/tooltime_parity_views.py").read_text(encoding="utf-8"),
            (ROOT / "templates/rebuild/invoices.html").read_text(encoding="utf-8"),
            (ROOT / "static/js/tooltime-parity-lifecycle.js").read_text(encoding="utf-8"),
        ))
        self.assertNotIn('ToolTime Pay', combined)

    def test_phase3_immutability_contract_remains(self):
        views = (ROOT / "erp/tooltime_parity_views.py").read_text(encoding="utf-8")
        self.assertIn('Ein bereits angenommenes Angebot bleibt aus Aufbewahrungsgründen gesperrt', views)
        self.assertIn('def quote_to_invoice', views)
