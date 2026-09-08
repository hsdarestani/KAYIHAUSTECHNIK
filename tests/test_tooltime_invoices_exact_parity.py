from pathlib import Path
from django.test import SimpleTestCase

ROOT = Path(__file__).resolve().parents[1]

class ToolTimeInvoicesExactParityContractTests(SimpleTestCase):
    def test_exact_invoice_surface_is_installed(self):
        template = (ROOT / "templates/rebuild/invoices.html").read_text(encoding="utf-8")
        for required in ("data-tooltime-invoices-exact", "data-invoice-kpi", "Rechnungsdatum", "Rechnungstitel", "Ausstehend", "Letzte Änderung", 'name="date_from"', 'name="date_to"', "data-invoice-page-size", "tti-row-menu"):
            self.assertIn(required, template)

    def test_invoice_route_uses_exact_parity_module(self):
        urls = (ROOT / "erp/rebuild_urls.py").read_text(encoding="utf-8")
        module = (ROOT / "erp/tooltime_invoices_exact.py").read_text(encoding="utf-8")
        self.assertIn("invoices_exact.invoice_list", urls)
        self.assertIn("tooltime_dunning_records", module)
        self.assertIn("tooltime_payment_transactions", module)
        self.assertIn("unpaid_amount += open_amount", module)
        self.assertIn("overdue_amount += open_amount", module)
        self.assertIn("dunning_amount += open_amount", module)
        self.assertIn('"last_change_desc"', module)

    def test_browser_smoke_covers_exact_invoice_surface(self):
        smoke = (ROOT / "scripts/production_browser_smoke.py").read_text(encoding="utf-8")
        self.assertIn("A+BAU TOOLTIME INVOICES EXACT PARITY BROWSER SMOKE", smoke)
        self.assertIn("[data-tooltime-invoices-exact]", smoke)
