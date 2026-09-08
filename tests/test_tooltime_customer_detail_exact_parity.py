from pathlib import Path
from django.test import SimpleTestCase

ROOT = Path(__file__).resolve().parents[1]


class ToolTimeCustomerDetailParityContract(SimpleTestCase):
    def test_customer_surface_contains_tooltime_sections_and_tabs(self):
        template = (ROOT / "templates/rebuild/customer_detail.html").read_text(encoding="utf-8")
        for marker in (
            "Umsatz (netto)", "Ausgaben (netto)", "Offener Rechnungsbetrag (inkl. MwSt.)",
            "Übersicht", "Aufgaben", "Dokumente", "Projekte", "Termine", "Angebote",
            "Rechnungen", "Belege", "Weitere Standorte & Kontakte",
        ):
            self.assertIn(marker, template)
        self.assertIn('?edit=1&tab={{ active_tab }}', template)
        self.assertIn('name="action" value="add_location"', template)

    def test_customer_view_scopes_operational_data_to_customer(self):
        views = (ROOT / "erp/rebuild_views.py").read_text(encoding="utf-8")
        self.assertIn('project__customer=customer', views)
        self.assertIn('Q(customer=customer) | Q(project__customer=customer)', views)
        self.assertIn('revenue_net', views)
        self.assertIn('open_invoice_gross', views)
        self.assertIn('expenditure_net', views)

    def test_surface_is_responsive_and_has_read_only_default(self):
        css_candidates = [ROOT / "static/css/kayi-readability.css", ROOT / "static/css/kayi-next.css"]
        css = next(path for path in css_candidates if path.exists()).read_text(encoding="utf-8")
        template = (ROOT / "templates/rebuild/customer_detail.html").read_text(encoding="utf-8")
        self.assertIn("KAYI TOOLTIME CUSTOMER DETAIL PARITY", css)
        self.assertIn("@media(max-width:860px)", css)
        self.assertIn("{% if edit_mode %}", template)
