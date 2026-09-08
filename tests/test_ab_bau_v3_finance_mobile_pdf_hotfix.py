from pathlib import Path
from django.test import SimpleTestCase

ROOT = Path(__file__).resolve().parents[1]


class ABauV3FinanceMobilePdfHotfixTests(SimpleTestCase):
    def test_hotfix_assets_load_after_assembled_shell(self):
        base = (ROOT / "templates/rebuild/base.html").read_text(encoding="utf-8")
        self.assertIn("ab-bau-v3-finance-mobile-pdf-hotfix.css", base)
        self.assertIn("ab-bau-v3-finance-mobile-pdf-hotfix.js", base)

    def test_finance_surfaces_share_v3_visual_language(self):
        css = (ROOT / "static/css/ab-bau-v3-finance-mobile-pdf-hotfix.css").read_text(encoding="utf-8")
        for marker in (
            ".ttq-topbar", ".tti-topbar", ".ttc-topbar", ".tt-document-form",
            ".ttq-table-wrap", ".tti-kpis", "linear-gradient(135deg,#090b0e",
            "env(safe-area-inset-bottom)",
        ):
            self.assertIn(marker, css)
        self.assertIn(".ttc-table th{text-transform:none!important}", css)

    def test_mobile_more_owns_menu_state_and_fabs_do_not_overlap_dock(self):
        js = (ROOT / "static/js/ab-bau-v3-finance-mobile-pdf-hotfix.js").read_text(encoding="utf-8")
        css = (ROOT / "static/css/ab-bau-v3-finance-mobile-pdf-hotfix.css").read_text(encoding="utf-8")
        for marker in ("[data-ab-open-menu]", "stopImmediatePropagation", "nx-menu-open", "aria-expanded"):
            self.assertIn(marker, js)
        self.assertIn(".ab-v3-mobile-fab", css)
        self.assertIn(".nx-assistant-fab", css)
        self.assertIn("bottom:calc(88px + env(safe-area-inset-bottom))", css)
        self.assertIn("right:78px", css)

    def test_mobile_catalogue_keeps_semantic_headers_for_smoke_and_accessibility(self):
        css = (ROOT / "static/css/ab-bau-v3-finance-mobile-pdf-hotfix.css").read_text(encoding="utf-8")
        self.assertIn(".ttc-table thead{display:block!important;position:absolute!important", css)
        self.assertIn(".ttc-table thead th{display:inline-block!important", css)
        self.assertNotIn(":where(.ttq-table,.tti-table,.ttc-table) thead{display:none!important}", css)

    def test_logo_upload_auto_enables_and_pdf_embeds_storage_bytes(self):
        views = (ROOT / "erp/tooltime_parity_views.py").read_text(encoding="utf-8")
        helper = (ROOT / "erp/services/business_pdf_identity.py").read_text(encoding="utf-8")
        self.assertIn('cfg.setdefault("logo", {})["show"] = True', views)
        self.assertIn("def _file_data_uri(field):", helper)
        self.assertIn("base64.b64encode(payload)", helper)
        self.assertIn("logo_src = _file_data_uri(org.logo)", helper)
        self.assertNotIn('_e(org.logo.url)', helper)

    def test_hotfix_runs_after_v3_catalogue_parity_in_legacy_rebuild(self):
        legacy = (ROOT / "scripts/unpack-source-legacy.sh").read_text(encoding="utf-8")
        self.assertGreater(
            legacy.rfind("python3 scripts/ab_bau_v3_finance_mobile_pdf_hotfix.py"),
            legacy.rfind("python3 scripts/ab_bau_v3_catalogue_text_layout_parity.py"),
        )
