from pathlib import Path
from django.test import TestCase

ROOT = Path(__file__).resolve().parents[1]


class ToolTimeFinanceParityContractTests(TestCase):
    def test_runtime_files_are_installed(self):
        self.assertIn("A+BAU TOOLTIME FINANCE PARITY", (ROOT / "static/css/tooltime-parity-finance.css").read_text())
        self.assertIn("Leistungsgruppe hinzufügen", (ROOT / "templates/rebuild/document_editor.html").read_text())
        self.assertIn("Artikel durchsuchen", (ROOT / "templates/rebuild/document_editor.html").read_text())
        self.assertIn("Mahnwesen", (ROOT / "templates/rebuild/tooltime_settings.html").read_text())

    def test_german_visible_copy(self):
        template = (ROOT / "templates/rebuild/document_editor.html").read_text()
        for phrase in ("Kunde und Projekt", "Angebotsdetails", "Einleitungstext", "Leistungen", "Zahlungsbedingungen", "Schlusstext", "Fertigstellen"):
            self.assertIn(phrase, template)

    def test_routes_use_parity_views(self):
        urls = (ROOT / "erp/rebuild_urls.py").read_text()
        self.assertIn("tooltime_parity.quote_editor", urls)
        self.assertIn("tooltime_parity.invoice_editor", urls)
        self.assertIn('name="next-article-search"', urls)
        self.assertIn('name="next-invoice-dunning"', urls)
        self.assertIn('name="next-public-quote"', urls)

    def test_quote_draft_numbering_is_not_persisted(self):
        views = (ROOT / "erp/tooltime_parity_views.py").read_text()
        self.assertIn('elif meta.finalized_at is None and quote.number:', views)
        self.assertIn('quote.number = ""', views)
        self.assertIn('if action == "finalize":', views)

    def test_completion_layer_is_installed(self):
        views = (ROOT / "erp/tooltime_parity_views.py").read_text()
        settings = (ROOT / "templates/rebuild/tooltime_settings.html").read_text()
        editor = (ROOT / "templates/rebuild/document_editor.html").read_text()
        self.assertIn("quick_customer_create", views)
        self.assertIn("quick_project_create", views)
        self.assertIn("Angaben auf Ihren Dokumenten", settings)
        self.assertIn("Rechtliche Informationen", settings)
        self.assertIn("Briefkopf hochladen", settings)
        self.assertIn("Neuen Kunden anlegen", editor)
        self.assertIn("Neues Projekt anlegen", editor)

    def test_legal_settings_reach_pdf_helper(self):
        views = (ROOT / "erp/tooltime_parity_views.py").read_text()
        helper = (ROOT / "erp/services/business_pdf_identity.py").read_text()
        self.assertIn('settings["legal"] = legal', views)
        self.assertIn('"tax_id"', helper)
        self.assertIn("kayi-custom-footer", helper)
        self.assertIn("kayi-document-logo", helper)

    def test_guided_invoice_wizard_exists(self):
        views = (ROOT / "erp/tooltime_parity_views.py").read_text()
        template = (ROOT / "templates/rebuild/invoice_wizard.html").read_text()
        self.assertIn("def quote_invoice_wizard", views)
        self.assertIn("_quote_item_billed_quantities", views)
        self.assertIn("Restmengen", template)
        self.assertIn("Abschlagsrechnung", template)
        self.assertIn("Teilrechnung", template)
        self.assertIn("Schlussrechnung", template)
        self.assertIn("maximal", views)

    def test_group_actions_are_real_controls(self):
        editor = (ROOT / "templates/rebuild/document_editor.html").read_text()
        js = (ROOT / "static/js/tooltime-parity-finance.js").read_text()
        self.assertIn('data-group-action="copy"', editor)
        self.assertIn('data-group-action="margin"', editor)
        self.assertIn('data-margin-modal', editor)
        self.assertNotIn("prompt('Aktion:", js)
        self.assertIn("draggedGroup", js)

    def test_invoice_number_has_no_forced_year_segment(self):
        service = (ROOT / "erp/services/invoice_compliance_service.py").read_text()
        self.assertIn("year=0", service)
        self.assertIn('return f"{prefix}{value:0{seq.digits}d}"', service)

    def test_invoice_type_mixing_guard_exists(self):
        service = (ROOT / "erp/services/tooltime_parity_finance.py").read_text()
        self.assertIn("Abschlags- und Teilrechnungen können innerhalb desselben Projekts nicht kombiniert werden.", service)
