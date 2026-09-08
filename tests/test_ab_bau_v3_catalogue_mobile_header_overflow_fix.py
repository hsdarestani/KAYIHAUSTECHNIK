from pathlib import Path
from django.test import SimpleTestCase

ROOT = Path(__file__).resolve().parents[1]


class ABauV3CatalogueMobileHeaderOverflowFixTests(SimpleTestCase):
    def test_mobile_catalogue_header_does_not_participate_in_layout(self):
        css = (ROOT / "static/css/ab-bau-v3-finance-mobile-pdf-hotfix.css").read_text(encoding="utf-8")
        self.assertIn("A+BAU V3 CATALOGUE MOBILE HEADER OVERFLOW FIX 2026-09-08", css)
        self.assertIn("body.ab-apex .ttc-table thead{display:none!important}", css)

    def test_desktop_catalogue_header_contract_still_exists(self):
        template = (ROOT / "templates/rebuild/catalogue.html").read_text(encoding="utf-8")
        self.assertIn("<thead>", template)
        self.assertIn("<th>Artikelnummer</th>", template)

    def test_layout_form_posts_uploaded_logo_as_multipart(self):
        template = (ROOT / "templates/rebuild/tooltime_settings.html").read_text(encoding="utf-8")
        marker = '<input type="hidden" name="section" value="layout">'
        marker_pos = template.index(marker)
        form_start = template.rfind("<form", 0, marker_pos)
        form_end = template.index(">", form_start)
        opening = template[form_start:form_end + 1]
        self.assertIn('enctype="multipart/form-data"', opening)
        self.assertIn('data-ab-logo-multipart-fix="20260908"', opening)

    def test_dashboard_hero_keeps_greeting_and_kpis_in_separate_flow_rows(self):
        css = (ROOT / "static/css/ab-bau-v3-finance-mobile-pdf-hotfix.css").read_text(encoding="utf-8")
        self.assertIn("A+BAU V3 DASHBOARD HERO FLOW FIX 2026-09-08", css)
        self.assertIn("grid-template-rows:auto auto!important", css)
        self.assertIn("body.ab-v3 .ab-v3-metrics", css)
        self.assertIn("position:relative!important", css)
        self.assertIn("inset:auto!important", css)

    def test_new_quote_menu_is_not_clipped_by_commercial_hero(self):
        css = (ROOT / "static/css/ab-bau-v3-finance-mobile-pdf-hotfix.css").read_text(encoding="utf-8")
        self.assertIn("A+BAU V3 QUOTES NEW MENU OVERFLOW FIX 2026-09-08", css)
        self.assertIn("body.ab-apex .ttq-topbar{", css)
        self.assertIn("overflow:visible!important", css)
        self.assertIn("z-index:30!important", css)
        self.assertIn("body.ab-apex .ttq-menu-card{", css)
        self.assertIn("top:calc(100% + 10px)!important", css)
        self.assertIn("z-index:60!important", css)

    def test_phone_quote_menu_stays_inside_full_width_trigger_column(self):
        css = (ROOT / "static/css/ab-bau-v3-finance-mobile-pdf-hotfix.css").read_text(encoding="utf-8")
        self.assertIn("@media(max-width:520px)", css)
        self.assertIn("left:0!important", css)
        self.assertIn("width:100%!important", css)
        self.assertIn("min-width:0!important", css)
        self.assertIn("max-width:100%!important", css)

    def test_position_service_model_is_readable_and_not_a_fourteenth_grid_cell(self):
        position = (ROOT / "templates/rebuild/_tooltime_position.html").read_text(encoding="utf-8")
        css = (ROOT / "static/css/ab-bau-v3-finance-mobile-pdf-hotfix.css").read_text(encoding="utf-8")
        self.assertIn("A+BAU V3 POSITION MODEL READABILITY FIX 2026-09-08", position)
        self.assertIn('class="tt-service-model-field"', position)
        self.assertIn('name="item_service_model"', position)
        self.assertLess(position.index('name="item_service_model"'), position.index('name="item_purchase_price"'))
        self.assertIn("body.ab-apex .tt-service-model{", css)
        self.assertIn("min-width:190px!important", css)

    def test_tooltime_calculation_breakdown_is_present(self):
        template = (ROOT / "templates/rebuild/document_editor.html").read_text(encoding="utf-8")
        self.assertIn('data-tooltime-summary-parity="20260908"', template)
        for field in (
            "data-summary-cost-material",
            "data-summary-cost-labour",
            "data-summary-cost-other",
            "data-summary-markup-material",
            "data-summary-markup-labour",
            "data-summary-markup-other",
        ):
            self.assertIn(field, template)

    def test_template_modal_is_single_owner_and_project_create_has_xhr_fallback(self):
        runtime = (ROOT / "static/js/tooltime-parity-finance.js").read_text(encoding="utf-8")
        self.assertIn("A+BAU V3 QUOTE EDITOR RUNTIME FIX 2026-09-08", runtime)
        self.assertIn("event.stopImmediatePropagation()", runtime)
        self.assertIn("new XMLHttpRequest()", runtime)
        self.assertIn("X-Requested-With", runtime)
        self.assertIn("data-summary-cost-material", runtime)
        self.assertIn("MutationObserver", runtime)

    def test_final_hotfix_css_is_cache_busted(self):
        base = (ROOT / "templates/rebuild/base.html").read_text(encoding="utf-8")
        self.assertIn("ab-bau-v3-finance-mobile-pdf-hotfix.css?v=20260908-finance-mobile-pdf-6", base)
