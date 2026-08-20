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
    new = '''        self.assertIn("{% url 'next-account' %}", base)
        self.assertIn("data-safe-account-page", account)
        self.assertIn('href="{% url \'next-account\' %}"><span class="nx-ico">◎</span>Konto</a>', base)
        self.assertIn('href="{% url \'next-account\' %}"><span>◎</span>Konto</a>', base)
        self.assertNotIn('href="{% url \'next-settings\' %}"><span class="nx-ico">◎</span>Konto</a>', base)
        self.assertNotIn('href="{% url \'next-settings\' %}"><span>◎</span>Konto</a>', base)
'''
    if new not in text:
        if old not in text:
            raise RuntimeError("Commercial settings faulty navigation assertion anchor changed")
        text = text.replace(old, new, 1)

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


def final_guard() -> None:
    views = read("erp/tooltime_parity_views.py")
    base = read("templates/rebuild/base.html")
    settings = read("templates/rebuild/tooltime_settings.html")
    urls = read("erp/rebuild_urls.py")
    tests = read("tests/test_commercial_settings_access_ui_contract.py")
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


def run() -> None:
    harden_mobile_worker_access()
    clean_legacy_page_heading()
    fix_contract_test()
    strengthen_browser_smoke()
    final_guard()
    compile(read("erp/tooltime_parity_views.py"), str(ROOT / "erp/tooltime_parity_views.py"), "exec")
    print(f"{MARKER}: Mobile Mitarbeiter werden explizit ausgeschlossen, Navigationstest korrigiert und alter Seitentitel entfernt.")


if __name__ == "__main__":
    run()
