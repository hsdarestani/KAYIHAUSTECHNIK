from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MARKER = "A+BAU COMMERCIAL SETTINGS FOLLOWUP 2026-08-20"


def read(rel: str) -> str:
    path = ROOT / rel
    if not path.exists():
        raise RuntimeError(f"Commercial settings follow-up target missing: {rel}")
    return path.read_text(encoding="utf-8")


def write(rel: str, text: str) -> None:
    path = ROOT / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def harden_mobile_worker_access() -> None:
    rel = "erp/tooltime_parity_views.py"
    text = read(rel)
    old = '''    if getattr(user, "is_superuser", False):
        return True
    role = str(getattr(getattr(user, "profile", None), "role", "") or "").strip().lower()
    # Company-wide commercial configuration is deliberately stricter than
    # document mutation rights. Technicians and project managers must never see
    # payment-provider, numbering, tax, legal-document or communication secrets.
    return role in {"owner", "admin", "office", "accounting"}
'''
    new = '''    if getattr(user, "is_superuser", False):
        return True
    profile = getattr(user, "profile", None)
    # A field/mobile-worker flag wins over a stale office-like role. This keeps
    # ordinary employees out even if historical user data was not normalized.
    if bool(getattr(profile, "is_mobile_worker", False)):
        return False
    role = str(getattr(profile, "role", "") or "").strip().lower()
    # Company-wide commercial configuration is deliberately stricter than
    # document mutation rights. Technicians and project managers must never see
    # payment-provider, numbering, tax, legal-document or communication secrets.
    return role in {"owner", "admin", "office", "accounting"}
'''
    if new not in text:
        if old not in text:
            raise RuntimeError("Commercial settings access helper anchor changed")
        text = text.replace(old, new, 1)
    write(rel, text)


def clean_legacy_page_heading() -> None:
    rel = "templates/rebuild/tooltime_settings.html"
    text = read(rel)
    marker = "data-commercial-settings-legacy-heading-cleanup"
    if marker in text:
        return
    script = r'''
<script data-commercial-settings-legacy-heading-cleanup>
document.addEventListener('DOMContentLoaded',()=>{
  const shell=document.querySelector('[data-commercial-settings-shell]');
  if(!shell)return;
  [...document.querySelectorAll('h1')].forEach(heading=>{
    if(heading.closest('[data-commercial-settings-shell]'))return;
    const value=(heading.textContent||'').replace(/\s+/g,' ').trim();
    if(!/^Angebote,\s*Rechnungen\s*&\s*Kommunikation$/i.test(value))return;
    const legacy=heading.closest('.tt-pagehead,.nx-pagehead,.page-header')||heading.parentElement;
    if(legacy){legacy.hidden=true;legacy.setAttribute('aria-hidden','true');}
  });
});
</script>
'''
    end = "{% endblock %}"
    idx = text.rfind(end)
    if idx < 0:
        raise RuntimeError("Commercial settings template endblock missing in follow-up")
    text = text[:idx] + script + "\n" + text[idx:]
    write(rel, text)


def fix_contract_test() -> None:
    rel = "tests/test_commercial_settings_access_ui_contract.py"
    text = read(rel)
    old = '''        self.assertIn("{% url 'next-account' %}", base)
        self.assertIn("Nur", account) if False else None
        self.assertIn("data-safe-account-page", account)
        self.assertNotIn('<span class="nx-ico">◎</span>Konto</a>', base.split("{% url 'next-settings' %}")[0] if "{% url 'next-settings' %}" in base else "")
'''
    broken = '''        self.assertIn("{% url 'next-account' %}", base)
        self.assertIn("data-safe-account-page", account)
        self.assertIn('href="{% url \'next-account\' %}"><span class="nx-ico">◎</span>Konto</a>', base)
        self.assertIn('href="{% url \'next-account\' %}"><span>◎</span>Konto</a>', base)
        self.assertNotIn('href="{% url \'next-settings\' %}"><span class="nx-ico">◎</span>Konto</a>', base)
        self.assertNotIn('href="{% url \'next-settings\' %}"><span>◎</span>Konto</a>', base)
'''
    new = '''        self.assertIn("{% url 'next-account' %}", base)
        self.assertIn("data-safe-account-page", account)
        self.assertIn("""href="{% url 'next-account' %}"><span class="nx-ico">◎</span>Konto</a>""", base)
        self.assertIn("""href="{% url 'next-account' %}"><span>◎</span>Konto</a>""", base)
        self.assertNotIn("""href="{% url 'next-settings' %}"><span class="nx-ico">◎</span>Konto</a>""", base)
        self.assertNotIn("""href="{% url 'next-settings' %}"><span>◎</span>Konto</a>""", base)
'''
    if new not in text:
        if broken in text:
            text = text.replace(broken, new, 1)
        elif old in text:
            text = text.replace(old, new, 1)
        else:
            raise RuntimeError("Commercial settings navigation assertion anchor changed")

    old_guard_assert = '''        self.assertIn('return role in {"owner", "admin", "office", "accounting"}', views)
        self.assertNotIn('return role in {"owner", "admin", "office", "project_manager", "accounting"}', views)
'''
    new_guard_assert = '''        self.assertIn('if bool(getattr(profile, "is_mobile_worker", False)):', views)
        self.assertIn('return role in {"owner", "admin", "office", "accounting"}', views)
        self.assertNotIn('return role in {"owner", "admin", "office", "project_manager", "accounting"}', views)
'''
    if new_guard_assert not in text:
        if old_guard_assert not in text:
            raise RuntimeError("Commercial settings guard assertion anchor changed")
        text = text.replace(old_guard_assert, new_guard_assert, 1)

    ui_assert = '        self.assertIn("commercialSettingsCategory", template)\n'
    ui_extra = ui_assert + '        self.assertIn("data-commercial-settings-legacy-heading-cleanup", template)\n'
    if "data-commercial-settings-legacy-heading-cleanup" not in text:
        if ui_assert not in text:
            raise RuntimeError("Commercial settings UI assertion anchor changed")
        text = text.replace(ui_assert, ui_extra, 1)
    write(rel, text)
    # This test file is generated during assembly. Compile it here so malformed
    # quoting or future patch drift fails the assembly step instead of wasting a
    # complete Django test run.
    compile(text, str(ROOT / rel), "exec")


def strengthen_browser_smoke() -> None:
    rel = "scripts/production_browser_smoke.py"
    text = read(rel)
    anchor = '''            if page.locator('[data-commercial-settings-tab]').count() != 5:
                fail("Commercial settings redesign must expose exactly five functional categories")
'''
    extra = anchor + '''            legacy_heading = page.get_by_role("heading", name="Angebote, Rechnungen & Kommunikation", exact=True)
            for legacy_index in range(legacy_heading.count()):
                if legacy_heading.nth(legacy_index).is_visible():
                    fail("Commercial settings still shows the obsolete duplicate page heading")
'''
    if "obsolete duplicate page heading" not in text:
        if anchor not in text:
            raise RuntimeError("Commercial settings browser heading assertion anchor changed")
        text = text.replace(anchor, extra, 1)
    write(rel, text)
    compile(text, str(ROOT / rel), "exec")


def authenticate_field_browser_smoke() -> None:
    """Run the field denial checks as a real authenticated employee.

    Konto is intentionally login-protected. The historical field smoke reaches
    its final block anonymously, so expecting a 200 there would test the wrong
    thing. Log in a temporary technician through the real login form, verify the
    personal page, then verify the commercial Settings URL still returns 403.
    User password/role/mobile flags are restored even when an assertion fails.
    """
    rel = "scripts/production_browser_smoke.py"
    text = read(rel)
    marker = "            # A+BAU COMMERCIAL SETTINGS FIELD DENIAL BROWSER SMOKE\n"
    auth_marker = "            # A+BAU FIELD AUTHENTICATED SESSION SETUP\n"
    close = "            context.close()\n"
    if auth_marker in text:
        return

    start = text.find(marker)
    if start < 0:
        raise RuntimeError("Commercial settings field browser marker missing")
    end = text.find(close, start)
    if end < 0:
        raise RuntimeError("Commercial settings field browser context close missing")

    block = r'''            # A+BAU COMMERCIAL SETTINGS FIELD DENIAL BROWSER SMOKE
            # A+BAU FIELD AUTHENTICATED SESSION SETUP
            import secrets as _field_secrets
            from django.contrib.auth import get_user_model as _field_get_user_model

            _FieldUser = _field_get_user_model()
            _field_user = (
                _FieldUser.objects.select_related("profile")
                .filter(is_active=True, profile__isnull=False)
                .exclude(is_superuser=True)
                .order_by("pk")
                .first()
            )
            if _field_user is None:
                fail("Technician browser smoke could not find an active employee account")
            _field_profile = _field_user.profile
            _field_old_role = str(getattr(_field_profile, "role", "") or "")
            _field_old_mobile = bool(getattr(_field_profile, "is_mobile_worker", False))
            _field_old_password = _field_user.password
            _field_password = "KayiFieldSmoke-" + _field_secrets.token_urlsafe(18)
            _field_profile.role = "technician"
            _field_profile.is_mobile_worker = True
            _field_profile.save(update_fields=["role", "is_mobile_worker"])
            _field_user.set_password(_field_password)
            _field_user.save(update_fields=["password"])
            try:
                # Start from a genuinely anonymous browser and authenticate via
                # Django's real login endpoint instead of forging a browser cookie.
                page.context.clear_cookies()
                login_response = page.goto(urljoin(base_url, "login/"), wait_until="domcontentloaded", timeout=30_000)
                if login_response is None or login_response.status != 200:
                    fail(f"Technician login page returned {login_response.status if login_response else 'no response'}")
                page.fill('input[name="username"]', _field_user.username)
                page.fill('input[name="password"]', _field_password)
                with page.expect_navigation(wait_until="domcontentloaded", timeout=30_000):
                    page.click('button[type="submit"], button.btn-primary')
                if "/login/" in page.url:
                    fail("Technician browser smoke could not establish an authenticated session")

                response = page.goto(urljoin(base_url, "konto/"), wait_until="domcontentloaded", timeout=30_000)
                if response is None or response.status != 200:
                    fail(f"Technician safe account page returned {response.status if response else 'no response'}")
                if page.locator('[data-safe-account-page]').count() != 1:
                    fail("Technician Konto no longer resolves to the safe personal account page")
                if "Zahlungen & Mahnwesen" in page.locator('body').inner_text():
                    fail("Technician personal account page leaks commercial settings content")

                response = page.goto(urljoin(base_url, "settings/next/"), wait_until="domcontentloaded", timeout=30_000)
                if response is None or response.status != 403:
                    fail(f"Technician direct commercial-settings URL must return 403, got {response.status if response else 'no response'}")
                if page.locator('[data-commercial-settings-shell]').count() != 0:
                    fail("Technician 403 response leaked the commercial settings shell")
            finally:
                _field_user.password = _field_old_password
                _field_user.save(update_fields=["password"])
                _field_profile.role = _field_old_role
                _field_profile.is_mobile_worker = _field_old_mobile
                _field_profile.save(update_fields=["role", "is_mobile_worker"])

'''
    text = text[:start] + block + text[end:]
    write(rel, text)
    compile(text, str(ROOT / rel), "exec")


def final_guard() -> None:
    views = read("erp/tooltime_parity_views.py")
    base = read("templates/rebuild/base.html")
    settings = read("templates/rebuild/tooltime_settings.html")
    urls = read("erp/rebuild_urls.py")
    tests = read("tests/test_commercial_settings_access_ui_contract.py")
    smoke = read("scripts/production_browser_smoke.py")
    if 'if bool(getattr(profile, "is_mobile_worker", False)):' not in views:
        raise RuntimeError("Field/mobile-worker override is not enforced on commercial settings")
    for forbidden in (
        'href="{% url \'next-settings\' %}"><span class="nx-ico">◎</span>Konto</a>',
        'href="{% url \'next-settings\' %}"><span>◎</span>Konto</a>',
    ):
        if forbidden in base:
            raise RuntimeError("A technician/mobile Konto link still targets commercial settings")
    for required in ('name="next-payments"', 'name="next-pay-provider-webhook"', 'name="next-settings"', 'name="next-account"'):
        if required not in urls:
            raise RuntimeError(f"Final URL assembly lost an existing route: {required}")
    if "data-commercial-settings-legacy-heading-cleanup" not in settings:
        raise RuntimeError("Legacy settings heading cleanup is missing")
    if "base.split(\"{% url 'next-settings' %}\")" in tests:
        raise RuntimeError("Faulty navigation contract assertion survived follow-up")
    if "A+BAU FIELD AUTHENTICATED SESSION SETUP" not in smoke:
        raise RuntimeError("Field browser smoke is not authenticated before testing Konto and Settings denial")
    if 'page.context.clear_cookies()' not in smoke or '_field_profile.is_mobile_worker = True' not in smoke:
        raise RuntimeError("Field browser smoke authentication setup is incomplete")
    compile(tests, str(ROOT / "tests/test_commercial_settings_access_ui_contract.py"), "exec")
    compile(smoke, str(ROOT / "scripts/production_browser_smoke.py"), "exec")


def run() -> None:
    harden_mobile_worker_access()
    clean_legacy_page_heading()
    fix_contract_test()
    strengthen_browser_smoke()
    authenticate_field_browser_smoke()
    final_guard()
    compile(read("erp/tooltime_parity_views.py"), str(ROOT / "erp/tooltime_parity_views.py"), "exec")
    print(f"{MARKER}: Mobile Mitarbeiter explizit ausgeschlossen, Mitarbeiter-Browser-Session authentifiziert, Navigationstest korrigiert und alter Seitentitel entfernt.")


if __name__ == "__main__":
    run()
