from pathlib import Path
from django.test import SimpleTestCase

ROOT = Path(__file__).resolve().parents[1]

class ABBauMobileNavigationTests(SimpleTestCase):
    def test_mobile_drawer_overlay_and_accessibility_contract(self):
        base = (ROOT / "templates/rebuild/base.html").read_text(encoding="utf-8")
        self.assertIn('id="nx-mobile-sidebar"', base)
        self.assertIn('data-nx-menu-overlay', base)
        self.assertIn('aria-expanded="false"', base)
        self.assertIn('aria-controls="nx-mobile-sidebar"', base)

    def test_mobile_drawer_is_narrower_scrollable_and_locks_background(self):
        css = (ROOT / "static/css/kayi-next.css").read_text(encoding="utf-8")
        self.assertIn("width:min(86vw,340px)", css)
        self.assertIn("height:100dvh", css)
        self.assertIn("overflow-y:auto", css)
        self.assertIn("body.nx-body.nx-menu-open{overflow:hidden", css)
        self.assertIn(".nx-body.nx-menu-open .nx-menu-overlay", css)
        self.assertIn(".nx-body.nx-menu-open .nx-assistant-fab", css)

    def test_mobile_menu_closes_outside_escape_and_navigation(self):
        js = (ROOT / "static/js/kayi-next.js").read_text(encoding="utf-8")
        self.assertIn("A+BAU_MOBILE_NAV", js)
        self.assertIn("mobileMenuOverlay?.addEventListener('click'", js)
        self.assertIn("event.key === 'Escape'", js)
        self.assertIn("mobileSidebar?.querySelectorAll('a')", js)
        self.assertIn("aria-expanded", js)

    def test_brand_has_real_image_with_failure_fallback(self):
        base = (ROOT / "templates/rebuild/base.html").read_text(encoding="utf-8")
        js = (ROOT / "static/js/kayi-next.js").read_text(encoding="utf-8")
        css = (ROOT / "static/css/kayi-next.css").read_text(encoding="utf-8")
        self.assertIn("ab-brand-logo", base)
        self.assertIn("ab-brand-logo-only", base)
        self.assertNotIn("ab-brand-fallback", base)
        self.assertIn("data-ab-brand-image", base)
        self.assertIn("image.naturalWidth", js)
        self.assertIn(".ab-brand-logo.is-missing img", css)

    def test_mobile_main_content_cannot_push_document_width(self):
        css = (ROOT / "static/css/kayi-next.css").read_text(encoding="utf-8")
        self.assertIn("html,body{max-width:100%;overflow-x:hidden}", css)
        self.assertIn(".nx-table-wrap,.ab-item-table-wrap", css)
        self.assertIn("overflow-x:auto!important", css)
