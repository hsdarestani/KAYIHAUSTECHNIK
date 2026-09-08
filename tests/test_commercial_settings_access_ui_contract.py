from pathlib import Path
from django.test import SimpleTestCase

ROOT = Path(__file__).resolve().parents[1]


class CommercialSettingsAccessUIContractTests(SimpleTestCase):
    def test_global_settings_have_strict_role_guard(self):
        views = (ROOT / "erp/tooltime_parity_views.py").read_text(encoding="utf-8")
        self.assertIn('if bool(getattr(profile, "is_mobile_worker", False)):', views)
        self.assertIn('return role in {"owner", "admin", "office", "accounting"}', views)
        self.assertNotIn('return role in {"owner", "admin", "office", "project_manager", "accounting"}', views)
        start = views.index("def settings_page(request):")
        self.assertIn("_commercial_settings_guard(request)", views[start:start + 180])
        for name in ("text_template_create", "text_template_update", "text_template_delete", "text_template_standard", "text_template_move", "layout_preview"):
            pos = views.index(f"def {name}(")
            self.assertIn("_commercial_settings_guard(request)", views[pos:pos + 220])
        self.assertIn("raise PermissionDenied", views)

    def test_technician_konto_is_separate_from_commercial_settings(self):
        base = (ROOT / "templates/rebuild/base.html").read_text(encoding="utf-8")
        urls = (ROOT / "erp/rebuild_urls.py").read_text(encoding="utf-8")
        account = (ROOT / "templates/rebuild/account.html").read_text(encoding="utf-8")
        self.assertIn('name="next-account"', urls)
        self.assertIn("{% url 'next-account' %}", base)
        self.assertIn("data-safe-account-page", account)
        self.assertIn("""href="{% url 'next-account' %}"><span class="nx-ico">◎</span>Konto</a>""", base)
        self.assertIn("""href="{% url 'next-account' %}"><span>◎</span>Konto</a>""", base)
        self.assertNotIn("""href="{% url 'next-settings' %}"><span class="nx-ico">◎</span>Konto</a>""", base)
        self.assertNotIn("""href="{% url 'next-settings' %}"><span>◎</span>Konto</a>""", base)

    def test_settings_page_is_structured_not_one_long_wall(self):
        template = (ROOT / "templates/rebuild/tooltime_settings.html").read_text(encoding="utf-8")
        self.assertIn("data-commercial-settings-shell", template)
        self.assertIn("data-commercial-settings-nav", template)
        self.assertEqual(template.count("data-commercial-settings-tab="), 5)
        self.assertIn("cset-workspace", template)
        self.assertIn("commercialSettingsCategory", template)
        self.assertIn("data-commercial-settings-legacy-heading-cleanup", template)
        self.assertIn("full-width gold save bars", (ROOT / "scripts/production_browser_smoke.py").read_text(encoding="utf-8"))

    def test_browser_smoke_checks_both_allowed_and_denied_roles(self):
        smoke = (ROOT / "scripts/production_browser_smoke.py").read_text(encoding="utf-8")
        self.assertIn("A+BAU COMMERCIAL SETTINGS ACCESS/UI BROWSER SMOKE", smoke)
        self.assertIn("A+BAU COMMERCIAL SETTINGS FIELD DENIAL BROWSER SMOKE", smoke)
        self.assertIn("response.status != 403", smoke)
        self.assertIn('urljoin(base_url, "konto/")', smoke)
