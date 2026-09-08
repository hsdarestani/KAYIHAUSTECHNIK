from pathlib import Path

from django.test import SimpleTestCase

ROOT = Path(__file__).resolve().parents[1]


class ABauV3Phase2Contract(SimpleTestCase):
    def read(self, rel):
        return (ROOT / rel).read_text(encoding="utf-8")

    def test_customer_directory_is_structural_v3_and_keeps_real_workflows(self):
        page = self.read("templates/rebuild/customers.html")
        for marker in (
            "data-ab-v3-customers",
            "ab-v3-directory-hero",
            "data-customer-modal",
            "data-customer-modal-show",
            "data-customer-row",
            "data-row-menu",
            "Debitorennummer",
            "Routing-ID",
            "Lieferanten-ID",
            "next-project-create",
        ):
            self.assertIn(marker, page)
        self.assertNotIn("Von ToolTime wechseln", page)

    def test_customer_cockpit_keeps_locations_commercial_and_document_context(self):
        page = self.read("templates/rebuild/customer_detail.html")
        for marker in (
            "data-ab-v3-customer-detail",
            "＋ Objekt hinzufügen",
            "Standardmäßig wird die Kundenadresse",
            'name="action" value="add_location"',
            "Umsatz (netto)",
            "Ausgaben (netto)",
            "Offener Rechnungsbetrag",
            "next-project-create",
            "next-expense-create",
            "next-quote-create",
            "next-invoice-create",
        ):
            self.assertIn(marker, page)
        self.assertNotIn("next-appointment-create", page)

    def test_project_directory_keeps_filters_create_and_column_controls(self):
        page = self.read("templates/rebuild/projects.html")
        for marker in (
            "data-ab-v3-projects",
            "data-tooltime-projects-exact",
            "data-project-table",
            "data-project-modal",
            "data-project-create-form",
            "data-column-toggle",
            "data-page-size",
            "tooltime-projects-exact.js",
            "next-project-detail",
            "next-appointment-create",
            "next-quote-create",
        ):
            self.assertIn(marker, page)

    def test_project_directory_has_phone_native_card_layout(self):
        css = self.read("static/css/ab-bau-v3-phase2-mobile.css")
        for marker in (
            "PHASE 2 MOBILE PROJECT REGISTER",
            "table[data-project-table] thead{display:none!important}",
            "tbody tr[data-project-row]",
            'td[data-col="address"]:before{content:"Einsatzort"}',
            "padding-bottom:calc(118px + env(safe-area-inset-bottom,0px))",
            "grid-template-columns:minmax(0,1.22fr) minmax(0,1.08fr) minmax(0,.9fr)",
        ):
            self.assertIn(marker, css)

    def test_project_cockpit_preserves_room_planner_field_and_finance_contracts(self):
        page = self.read("templates/rebuild/project_detail.html")
        for marker in (
            "data-ab-v3-project-detail",
            "data-tooltime-project-detail",
            "next-room-planner",
            "Raum & 3D",
            "Aufmaß",
            "B&O Leistungsnachweis / Regiebericht",
            'data-tab="overview"',
            'data-tab="tasks"',
            'data-tab="documents"',
            'data-tab="finance"',
            'data-tab-panel="finance"',
            'data-row-href',
            'data-action="open-offer"',
            'data-action="open-invoice"',
            "Herunterladen",
        ):
            self.assertIn(marker, page)
        self.assertNotIn("{% url 'configurator' %}?project={{ project.pk }}", page)
        finance_guard = "{% if not field_user %}\n        <div class=\"tt-pd-panel\" data-tab-panel=\"finance\">"
        self.assertIn(finance_guard, page)
        finance_block = page[page.index(finance_guard):]
        self.assertIn("Umsatz (netto)", finance_block)
        self.assertIn("Offener Betrag (brutto)", finance_block)

    def test_direct_customer_create_and_phase2_asset_are_live(self):
        form = self.read("templates/rebuild/customer_form.html")
        css = self.read("static/css/ab-bau-v3-phase2.css")
        mobile_css = self.read("static/css/ab-bau-v3-phase2-mobile.css")
        base = self.read("templates/rebuild/base.html")
        self.assertIn("data-ab-v3-customer-form", form)
        self.assertIn("A+BAU V3 — PHASE 2", css)
        self.assertIn("PHASE 2 MOBILE PROJECT REGISTER", mobile_css)
        self.assertIn("ab-bau-v3-phase2.css?v=20260908-v3-closeout1", base)
        self.assertIn("ab-bau-v3-phase2-mobile.css?v=20260908-v3-closeout1", base)
