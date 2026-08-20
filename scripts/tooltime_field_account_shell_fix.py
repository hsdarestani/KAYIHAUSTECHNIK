from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MARKER = "A+BAU FIELD ACCOUNT TOPBAR + LOGOUT 2026-08-20"


def read(rel: str) -> str:
    path = ROOT / rel
    if not path.exists():
        raise RuntimeError(f"Field-account shell target missing: {rel}")
    return path.read_text(encoding="utf-8")


def write(rel: str, text: str) -> None:
    path = ROOT / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def patch_profile_menu() -> None:
    rel = "templates/rebuild/base.html"
    text = read(rel)
    safe_block = '''            {% if request.user.profile.role == 'technician' or request.user.profile.is_mobile_worker %}<a href="{% url 'next-account' %}">◎ Konto</a>{% else %}<a href="{% url 'next-settings' %}">⚙ Einstellungen</a>{% endif %}\n'''
    old = '''            <a href="{% url 'next-settings' %}">⚙ Einstellungen</a>\n'''
    if safe_block not in text:
        if old not in text:
            raise RuntimeError("Profile-menu settings anchor missing")
        text = text.replace(old, safe_block, 1)
    if 'action="{% url \'next-logout\' %}"' not in text or "↪ Abmelden" not in text:
        raise RuntimeError("Existing secure POST logout action disappeared from app shell")
    write(rel, text)


def restore_mobile_topbar() -> None:
    rel = "static/css/kayi-next-field.css"
    text = read(rel)
    if MARKER not in text:
        text = text.rstrip() + r'''

/* A+BAU FIELD ACCOUNT TOPBAR + LOGOUT 2026-08-20 */
@media(max-width:900px){
  .nx-field-role .nx-topbar{display:flex!important;visibility:visible!important;opacity:1!important}
  .nx-field-role .nx-top-actions{display:flex!important;align-items:center!important;margin-left:auto!important}
  .nx-field-role .nx-top-actions .nx-profile{display:block!important;visibility:visible!important;opacity:1!important}
  .nx-field-role .nx-top-actions .nx-avatar,
  .nx-field-role .nx-top-actions .nx-avatar-button{display:grid!important;visibility:visible!important;opacity:1!important}
  .nx-field-role .nx-profile-menu{z-index:120!important}
}
@media(max-width:760px){
  .nx-field-role .nx-topbar{height:60px!important;min-height:60px!important;padding:0 12px!important;gap:10px!important}
  .nx-field-role .nx-ai-omnibox{display:flex!important;min-width:0!important;max-width:none!important}
  .nx-field-role .nx-ai-omnibox input{min-width:0!important;height:40px!important;padding-right:34px!important}
  .nx-field-role .nx-ai-omnibox button{display:block!important}
}
'''
    write(rel, text)


def add_account_logout_fallback() -> None:
    rel = "templates/rebuild/account.html"
    text = read(rel)
    if "data-account-logout" not in text:
        anchor = "<style>\n"
        if anchor not in text:
            raise RuntimeError("Account template style anchor missing")
        block = r'''<section class="account-safe-actions" data-account-actions>
  <div><span>KONTO</span><strong>Sitzung & Zugriff</strong><small>Sie können sich jederzeit sicher von diesem Gerät abmelden.</small></div>
  <form method="post" action="{% url 'next-logout' %}" data-account-logout>{% csrf_token %}<button type="submit">↪ Abmelden</button></form>
</section>
'''
        text = text.replace(anchor, block + anchor, 1)

        style_anchor = "</style>"
        css = r'''
.account-safe-actions{display:flex;align-items:center;justify-content:space-between;gap:18px;margin-top:16px;padding:20px 22px;border:1px solid #e7e8eb;border-radius:16px;background:#fff}.account-safe-actions>div{display:flex;flex-direction:column;gap:5px}.account-safe-actions span{font-size:10px;letter-spacing:.12em;color:#92979e;font-weight:900}.account-safe-actions strong{font-size:16px}.account-safe-actions small{color:#777f88;line-height:1.4}.account-safe-actions form{margin:0}.account-safe-actions button{min-height:42px;padding:9px 16px;border:1px solid #dedfe2;border-radius:11px;background:#fff;color:#23262b;font:inherit;font-size:12px;font-weight:850;cursor:pointer}.account-safe-actions button:hover{background:#f6f6f4}@media(max-width:620px){.account-safe-actions{align-items:stretch;flex-direction:column}.account-safe-actions button{width:100%}}
'''
        if style_anchor not in text:
            raise RuntimeError("Account template style close missing")
        text = text.replace(style_anchor, css + style_anchor, 1)
    write(rel, text)


def strengthen_browser_smoke() -> None:
    rel = "scripts/production_browser_smoke.py"
    text = read(rel)
    marker = "                if page.locator('[data-safe-account-page]').count() != 1:\n                    fail(\"Technician Konto no longer resolves to the safe personal account page\")\n"
    smoke_marker = "A+BAU FIELD TOPBAR LOGOUT BROWSER SMOKE"
    if smoke_marker not in text:
        if marker not in text:
            raise RuntimeError("Authenticated technician Konto browser-smoke anchor missing")
        extra = marker + r'''                # A+BAU FIELD TOPBAR LOGOUT BROWSER SMOKE
                # Reproduce the actual phone layout that originally hid the profile
                # control instead of validating only the desktop DOM.
                page.set_viewport_size({"width": 390, "height": 844})
                page.wait_for_timeout(160)
                topbar = page.locator('header.nx-topbar')
                if topbar.count() != 1 or not topbar.is_visible():
                    fail("Technician mobile app topbar is missing on Konto")
                profile_toggle = page.locator('[data-profile-toggle]')
                if profile_toggle.count() != 1 or not profile_toggle.is_visible():
                    fail("Technician profile/logout control is not visible in the topbar")
                profile_toggle.click()
                profile_menu = page.locator('[data-profile-menu]')
                if profile_menu.count() != 1 or not profile_menu.is_visible():
                    fail("Technician profile menu does not open")
                logout_form = profile_menu.locator('form[action$="/konto/abmelden/"]')
                if logout_form.count() != 1 or logout_form.locator('button[type="submit"]').count() != 1:
                    fail("Technician profile menu has no secure POST logout action")
                konto_link = profile_menu.locator('a[href$="/konto/"]')
                if konto_link.count() != 1:
                    fail("Technician profile menu has no safe Konto link")
                if profile_menu.locator('a[href$="/settings/next/"]').count() != 0:
                    fail("Technician profile menu still exposes company settings")
                profile_toggle.click()
                direct_logout = page.locator('[data-account-logout]')
                if direct_logout.count() != 1 or direct_logout.get_attribute("method").lower() != "post":
                    fail("Technician Konto page has no direct secure logout fallback")
'''
        text = text.replace(marker, extra, 1)
    write(rel, text)
    compile(text, str(ROOT / rel), "exec")


def install_contract_test() -> None:
    write("tests/test_field_account_shell_contract.py", r'''from pathlib import Path
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
''')


def guard() -> None:
    base = read("templates/rebuild/base.html")
    css = read("static/css/kayi-next-field.css")
    account = read("templates/rebuild/account.html")
    urls = read("erp/rebuild_urls.py")
    smoke = read("scripts/production_browser_smoke.py")
    for required in (
        "{% url 'next-account' %}",
        "{% url 'next-logout' %}",
        "↪ Abmelden",
    ):
        if required not in base:
            raise RuntimeError(f"Field account shell missing base contract: {required}")
    if MARKER not in css or ".nx-field-role .nx-topbar{display:flex!important" not in css:
        raise RuntimeError("Technician mobile topbar visibility override missing")
    if "data-account-logout" not in account:
        raise RuntimeError("Direct account logout fallback missing")
    if 'name="next-logout"' not in urls or 'name="next-account"' not in urls:
        raise RuntimeError("Account/logout route missing from final assembly")
    if "A+BAU FIELD TOPBAR LOGOUT BROWSER SMOKE" not in smoke:
        raise RuntimeError("Field topbar/logout browser smoke missing")
    if 'page.set_viewport_size({"width": 390, "height": 844})' not in smoke:
        raise RuntimeError("Field topbar/logout smoke is not validating the mobile viewport")
    compile(smoke, str(ROOT / "scripts/production_browser_smoke.py"), "exec")
    compile(read("tests/test_field_account_shell_contract.py"), str(ROOT / "tests/test_field_account_shell_contract.py"), "exec")


def run() -> None:
    patch_profile_menu()
    restore_mobile_topbar()
    add_account_logout_fallback()
    strengthen_browser_smoke()
    install_contract_test()
    guard()
    print(f"{MARKER}: Technician-Topbar/Profil wieder sichtbar, Firmen-Settings verborgen und sicherer Logout erreichbar.")


if __name__ == "__main__":
    run()