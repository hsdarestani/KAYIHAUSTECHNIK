from pathlib import Path
from django.test import SimpleTestCase

ROOT = Path(__file__).resolve().parents[1]


class FieldAccountShellContractTests(SimpleTestCase):
    def test_field_profile_uses_safe_konto_and_logout(self):
        base = (ROOT / "templates/rebuild/base.html").read_text(encoding="utf-8")
        self.assertIn("{% url 'next-account' %}", base)
        self.assertIn("{% url 'next-logout' %}", base)
        self.assertIn("↪ Abmelden", base)
        self.assertIn("request.user.profile.is_mobile_worker", base)

    def test_mobile_topbar_and_profile_are_forced_visible(self):
        css = (ROOT / "static/css/kayi-next-field.css").read_text(encoding="utf-8")
        self.assertIn("A+BAU FIELD ACCOUNT TOPBAR + LOGOUT 2026-08-20", css)
        self.assertIn(".nx-field-role .nx-topbar{display:flex!important", css)
        self.assertIn(".nx-field-role .nx-top-actions .nx-avatar-button{display:grid!important", css)

    def test_account_has_direct_secure_logout_fallback(self):
        account = (ROOT / "templates/rebuild/account.html").read_text(encoding="utf-8")
        self.assertIn("data-account-logout", account)
        self.assertIn("method=\"post\"", account)
        self.assertIn("{% url 'next-logout' %}", account)
        self.assertIn("{% csrf_token %}", account)

    def test_browser_smoke_covers_real_mobile_topbar_and_logout_routes(self):
        smoke = (ROOT / "scripts/production_browser_smoke.py").read_text(encoding="utf-8")
        self.assertIn("A+BAU FIELD TOPBAR LOGOUT BROWSER SMOKE", smoke)
        self.assertIn('page.set_viewport_size({"width": 390, "height": 844})', smoke)
        self.assertIn('form[action$="/konto/abmelden/"]', smoke)
        self.assertIn('a[href$="/konto/"]', smoke)
        self.assertIn('a[href$="/settings/next/"]', smoke)
