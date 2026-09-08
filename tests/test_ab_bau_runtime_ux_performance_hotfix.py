from pathlib import Path
from django.test import SimpleTestCase

ROOT = Path(__file__).resolve().parents[1]


class ABBauRuntimeHotfixTests(SimpleTestCase):
    def test_field_time_toggle_has_one_owner_and_csrf_cookie(self):
        field_js = (ROOT / "static/js/field-authorization.js").read_text(encoding="utf-8")
        global_js = (ROOT / "static/js/kayi-next.js").read_text(encoding="utf-8")
        views = (ROOT / "erp/field_authorization_views.py").read_text(encoding="utf-8")
        self.assertIn("global kayi-next.js owns Zeiterfassung", field_js)
        self.assertNotIn("bindCompletion(); bindTimeToggle();", field_js)
        self.assertIn("abTimeBound", global_js)
        self.assertIn("const raw = await response.text()", global_js)
        self.assertIn("@ensure_csrf_cookie\ndef field_job_detail", views)

    def test_offer_initial_render_does_not_resolve_500_catalog_prices(self):
        views = (ROOT / "erp/rebuild_views.py").read_text(encoding="utf-8")
        self.assertIn("def _fast_catalog_preview", views)
        self.assertGreaterEqual(views.count("_fast_catalog_preview(org)"), 2)
        self.assertNotIn("catalog_with_effective_prices(org, limit=500)", views)

    def test_catalog_search_is_async_and_bo_results_are_compact(self):
        urls = (ROOT / "erp/rebuild_urls.py").read_text(encoding="utf-8")
        template = (ROOT / "templates/rebuild/document_editor.html").read_text(encoding="utf-8")
        js = (ROOT / "static/js/kayi-next.js").read_text(encoding="utf-8")
        bo = (ROOT / "erp/bo_direct_search_views.py").read_text(encoding="utf-8")
        css = (ROOT / "static/css/kayi-next.css").read_text(encoding="utf-8")
        self.assertIn("next-catalog-quick-search", urls)
        self.assertIn("data-ab-catalog-search-url", template)
        self.assertIn("abCatalogController", js)
        self.assertIn("limit=12", bo)
        self.assertIn("max-height:360px", css)
        self.assertIn("A+BAU RUNTIME UX + PERFORMANCE HOTFIX", css)
