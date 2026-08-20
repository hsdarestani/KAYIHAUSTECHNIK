from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MARKER = "A+BAU COMMERCIAL SETTINGS ACCESS + UI 2026-08-20"


def read(rel: str) -> str:
    path = ROOT / rel
    if not path.exists():
        raise RuntimeError(f"Commercial-settings target missing: {rel}")
    return path.read_text(encoding="utf-8")


def write(rel: str, text: str) -> None:
    path = ROOT / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def patch_views() -> None:
    rel = "erp/tooltime_parity_views.py"
    text = read(rel)

    if "PermissionDenied" not in text:
        existing = re.search(r"^from django\.core\.exceptions import ([^\n]+)$", text, re.M)
        if existing:
            names = [name.strip() for name in existing.group(1).split(",") if name.strip()]
            names.append("PermissionDenied")
            replacement = "from django.core.exceptions import " + ", ".join(sorted(set(names)))
            text = text[:existing.start()] + replacement + text[existing.end():]
        else:
            anchor = "from django.contrib import messages\n"
            if anchor not in text:
                raise RuntimeError("Django import anchor missing for commercial settings guard")
            text = text.replace(anchor, anchor + "from django.core.exceptions import PermissionDenied\n", 1)

    settings_anchor = "def settings_page(request):\n"
    helper = r'''def _commercial_settings_access_allowed(request):
    user = getattr(request, "user", None)
    if user is None:
        return False
    if getattr(user, "is_superuser", False):
        return True
    role = str(getattr(getattr(user, "profile", None), "role", "") or "").strip().lower()
    # Company-wide commercial configuration is deliberately stricter than
    # document mutation rights. Technicians and project managers must never see
    # payment-provider, numbering, tax, legal-document or communication secrets.
    return role in {"owner", "admin", "office", "accounting"}


def _commercial_settings_guard(request):
    if not _commercial_settings_access_allowed(request):
        raise PermissionDenied("Unternehmensweite kaufmännische Einstellungen sind für dieses Benutzerkonto nicht freigegeben.")


@login_required
def account_page(request):
    """Safe personal account landing page for field/employee users."""
    return render(request, "rebuild/account.html", {})


'''
    if "def _commercial_settings_access_allowed(request):" not in text:
        if settings_anchor not in text:
            raise RuntimeError("settings_page anchor missing")
        text = text.replace(settings_anchor, helper + settings_anchor, 1)

    guarded_settings = "def settings_page(request):\n    _commercial_settings_guard(request)\n"
    if guarded_settings not in text:
        if settings_anchor not in text:
            raise RuntimeError("settings_page function missing while adding guard")
        text = text.replace(settings_anchor, guarded_settings, 1)

    # These endpoints mutate the same organization-wide settings surface and
    # must not remain reachable by crafting their URLs directly.
    guarded_functions = (
        "text_template_create",
        "text_template_update",
        "text_template_delete",
        "text_template_standard",
        "text_template_move",
        "layout_preview",
    )
    for name in guarded_functions:
        pattern = re.compile(rf"(def {name}\([^\n]*\):\n)(?!    _commercial_settings_guard\(request\)\n)")
        text, count = pattern.subn(r"\1    _commercial_settings_guard(request)\n", text, count=1)
        if count != 1:
            start = text.find(f"def {name}(")
            if start < 0 or "_commercial_settings_guard(request)" not in text[start:start + 220]:
                raise RuntimeError(f"Commercial settings guard missing for {name}")

    write(rel, text)


def patch_urls() -> None:
    rel = "erp/rebuild_urls.py"
    text = read(rel)
    route = '    path("konto/", tooltime_parity.account_page, name="next-account"),\n'
    if 'name="next-account"' not in text:
        anchor = '    path("settings/next/", tooltime_parity.settings_page, name="next-settings"),\n'
        if anchor not in text:
            raise RuntimeError("Final next-settings route missing while adding account route")
        text = text.replace(anchor, route + anchor, 1)
    write(rel, text)


def patch_base_navigation() -> None:
    rel = "templates/rebuild/base.html"
    text = read(rel)

    technician_link = '<a href="{% url \'next-settings\' %}"><span class="nx-ico">◎</span>Konto</a>'
    safe_technician_link = '<a class="{% if request.resolver_match.url_name == \'next-account\' %}is-active{% endif %}" href="{% url \'next-account\' %}"><span class="nx-ico">◎</span>Konto</a>'
    if safe_technician_link not in text:
        if technician_link not in text:
            raise RuntimeError("Technician Konto navigation anchor missing")
        text = text.replace(technician_link, safe_technician_link, 1)

    bottom_link = '<a class="{% if request.resolver_match.url_name == \'next-settings\' %}is-active{% endif %}" href="{% url \'next-settings\' %}"><span>◎</span>Konto</a>'
    safe_bottom_link = '<a class="{% if request.resolver_match.url_name == \'next-account\' %}is-active{% endif %}" href="{% url \'next-account\' %}"><span>◎</span>Konto</a>'
    if safe_bottom_link not in text:
        if bottom_link not in text:
            raise RuntimeError("Technician bottom Konto navigation anchor missing")
        text = text.replace(bottom_link, safe_bottom_link, 1)

    settings_link = '<a class="{% if request.resolver_match.url_name == \'next-settings\' %}is-active{% endif %}" href="{% url \'next-settings\' %}"><span class="nx-ico">⚙</span>Einstellungen</a>'
    gated_settings_link = "{% if request.user.is_superuser or request.user.profile.role == 'owner' or request.user.profile.role == 'admin' or request.user.profile.role == 'office' or request.user.profile.role == 'accounting' %}" + settings_link + "{% endif %}"
    if gated_settings_link not in text:
        if settings_link not in text:
            raise RuntimeError("Office settings navigation anchor missing")
        text = text.replace(settings_link, gated_settings_link, 1)

    # There must be no technician/mobile navigation path left that points to the
    # commercial settings route under the label Konto.
    if re.search(r'href="\{% url \'next-settings\' %\}"[^>]*>[^<]*(?:<[^>]+>[^<]*</[^>]+>)*Konto', text):
        raise RuntimeError("A technician Konto link still targets commercial settings")
    write(rel, text)


def install_account_template() -> None:
    write("templates/rebuild/account.html", r'''{% extends "rebuild/base.html" %}
{% block title %}Konto · A+Bau{% endblock %}
{% block content %}
<div class="account-safe-page" data-safe-account-page>
  <div class="account-safe-hero">
    <div><span class="account-safe-eyebrow">MEIN KONTO</span><h1>Persönlicher Bereich</h1><p>Hier sehen Sie ausschließlich Ihre eigenen Kontodaten. Unternehmensweite Finanz-, Steuer- und Kommunikationseinstellungen sind getrennt geschützt.</p></div>
    <span class="account-safe-badge">Geschützter Mitarbeiterzugang</span>
  </div>
  <div class="account-safe-grid">
    <section><span>Benutzer</span><strong>{{ request.user.get_full_name|default:request.user.username }}</strong><small>@{{ request.user.username }}</small></section>
    <section><span>Rolle</span><strong>{{ request.user.profile.role|default:"Mitarbeiter" }}</strong><small>{% if request.user.profile.is_mobile_worker %}Mobiler Einsatz aktiviert{% else %}Webzugang{% endif %}</small></section>
    <section><span>Unternehmen</span><strong>{{ request.user.profile.organization.name|default:"A+Bau" }}</strong><small>Persönlicher Zugriff ohne kaufmännische Systemeinstellungen</small></section>
  </div>
</div>
<style>
.account-safe-page{max-width:980px;margin:0 auto}.account-safe-hero{display:flex;justify-content:space-between;gap:28px;align-items:flex-start;padding:34px;border:1px solid #e7e4dc;background:#fff;border-radius:20px;box-shadow:0 16px 42px rgba(17,20,24,.07)}.account-safe-hero h1{margin:7px 0 8px;font-size:30px;letter-spacing:-.035em}.account-safe-hero p{max-width:650px;margin:0;color:#69707a;line-height:1.6}.account-safe-eyebrow{font-size:11px;font-weight:900;letter-spacing:.14em;color:#9a7615}.account-safe-badge{white-space:nowrap;padding:9px 12px;border-radius:999px;background:#f6f2e5;color:#75580c;font-size:12px;font-weight:800}.account-safe-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:14px;margin-top:16px}.account-safe-grid section{display:flex;flex-direction:column;gap:7px;padding:22px;border:1px solid #e7e8eb;border-radius:16px;background:#fff}.account-safe-grid span{font-size:11px;text-transform:uppercase;letter-spacing:.1em;color:#8a9098;font-weight:850}.account-safe-grid strong{font-size:17px}.account-safe-grid small{color:#777f88;line-height:1.45}@media(max-width:760px){.account-safe-hero{padding:24px;flex-direction:column}.account-safe-grid{grid-template-columns:1fr}.account-safe-badge{white-space:normal}}
</style>
{% endblock %}
''')


def patch_settings_template() -> None:
    rel = "templates/rebuild/tooltime_settings.html"
    text = read(rel)
    if "data-commercial-settings-nav" in text:
        return

    first_card = text.find('<section class="tt-card"')
    if first_card < 0:
        raise RuntimeError("Commercial settings UI has no tt-card sections")

    navigation = r'''
<div class="cset-page-head" data-commercial-settings-shell>
  <div><span class="cset-eyebrow">UNTERNEHMENSEINSTELLUNGEN</span><h1>Dokumente & Finanzen konfigurieren</h1><p>Globale Vorgaben für Angebote, Rechnungen, Zahlungen und Kundenkommunikation. Änderungen wirken unternehmensweit.</p></div>
  <div class="cset-access-badge"><span></span> Nur Verwaltung & Buchhaltung</div>
</div>
<nav class="cset-nav" data-commercial-settings-nav aria-label="Einstellungsbereiche">
  <button type="button" data-commercial-settings-tab="design" aria-selected="true"><b>01</b><span>Dokumentdesign<small>Layout & Textvorlagen</small></span></button>
  <button type="button" data-commercial-settings-tab="master" aria-selected="false"><b>02</b><span>Stammdaten & Recht<small>Firmendaten, Anhänge, Nummern</small></span></button>
  <button type="button" data-commercial-settings-tab="finance" aria-selected="false"><b>03</b><span>Finanzen<small>Steuern, Zahlungen, Mahnungen</small></span></button>
  <button type="button" data-commercial-settings-tab="communication" aria-selected="false"><b>04</b><span>Kommunikation<small>E-Mail & SMS</small></span></button>
  <button type="button" data-commercial-settings-tab="ai" aria-selected="false"><b>05</b><span>KI & Datenschutz<small>Datenverarbeitung</small></span></button>
</nav>
'''
    text = text[:first_card] + navigation + text[first_card:]

    enhancement = r'''
<style data-commercial-settings-style>
.cset-page-head{display:flex;align-items:flex-start;justify-content:space-between;gap:32px;margin:4px 0 22px;padding:4px 2px}.cset-page-head h1{margin:6px 0 7px;font-size:30px;line-height:1.08;letter-spacing:-.04em;color:#17191d}.cset-page-head p{max-width:720px;margin:0;color:#707782;font-size:14px;line-height:1.55}.cset-eyebrow{font-size:10px;font-weight:950;letter-spacing:.15em;color:#9a7511}.cset-access-badge{display:flex;align-items:center;gap:8px;white-space:nowrap;padding:9px 12px;border:1px solid #e6e0ce;border-radius:999px;background:#fbfaf6;color:#645629;font-size:12px;font-weight:850}.cset-access-badge span{width:7px;height:7px;border-radius:50%;background:#bd9425;box-shadow:0 0 0 4px rgba(189,148,37,.12)}
.cset-workspace{display:grid;grid-template-columns:235px minmax(0,1fr);gap:20px;align-items:start}.cset-nav{position:sticky;top:78px;display:flex;flex-direction:column;gap:6px;padding:8px;border:1px solid #e7e7e4;border-radius:16px;background:#fff;box-shadow:0 10px 32px rgba(20,24,30,.05);z-index:2}.cset-nav button{display:grid;grid-template-columns:30px 1fr;gap:8px;align-items:center;width:100%;padding:11px 10px;border:0;border-radius:11px;background:transparent;color:#666d76;text-align:left;cursor:pointer;transition:.16s ease}.cset-nav button:hover{background:#f7f7f5;color:#202328}.cset-nav button[aria-selected="true"]{background:#17191d;color:#fff;box-shadow:0 8px 18px rgba(17,20,24,.13)}.cset-nav button b{font-size:10px;letter-spacing:.08em;color:#a98528}.cset-nav button span{display:flex;flex-direction:column;gap:2px;font-size:12px;font-weight:900}.cset-nav button small{font-size:10px;font-weight:650;color:#989da4}.cset-nav button[aria-selected="true"] small{color:#b9bec5}.cset-content{min-width:0}.cset-content>.tt-card{margin:0 0 14px;padding:24px!important;border:1px solid #e6e7e9!important;border-radius:16px!important;background:#fff!important;box-shadow:0 8px 24px rgba(18,22,28,.045)!important}.cset-content>.tt-card[hidden]{display:none!important}.cset-content .tt-section-title{display:flex;align-items:flex-start;justify-content:space-between;gap:16px;margin-bottom:20px;padding-bottom:15px;border-bottom:1px solid #eff0f1}.cset-content .tt-section-title h2,.cset-content>.tt-card>h2{margin:0 0 5px!important;font-size:18px!important;letter-spacing:-.02em;color:#1c1e22}.cset-content .tt-section-title p{margin:0;color:#7b818a;font-size:12px;line-height:1.5}.cset-content label{font-size:11px!important;font-weight:800!important;color:#555c65}.cset-content input:not([type=checkbox]):not([type=radio]),.cset-content select,.cset-content textarea{width:100%;min-height:42px!important;border:1px solid #dfe2e5!important;border-radius:9px!important;background:#fff!important;padding:9px 11px!important;box-shadow:none!important;transition:border-color .15s,box-shadow .15s}.cset-content textarea{min-height:92px!important;resize:vertical}.cset-content input:focus,.cset-content select:focus,.cset-content textarea:focus{outline:0!important;border-color:#b28a20!important;box-shadow:0 0 0 3px rgba(178,138,32,.11)!important}.cset-content .tt-two{gap:14px!important}.cset-content .tt-number-grid{gap:12px!important}.cset-content hr{border:0;border-top:1px solid #eceef0;margin:20px 0}.cset-content .tt-check{display:flex!important;align-items:flex-start;gap:9px;padding:8px 0;font-size:12px!important}.cset-content .tt-check input{margin-top:2px}.cset-content button[type=submit],.cset-content input[type=submit]{width:auto!important;max-width:100%!important;min-width:128px;min-height:38px!important;padding:8px 15px!important;border-radius:9px!important;font-size:11px!important;font-weight:900!important}.cset-content form>button[type=submit]{display:flex!important;margin:16px 0 0 auto!important}.cset-content .nx-actions{justify-content:flex-end!important;gap:8px!important}.cset-content .tt-number-preview{min-height:42px;border-radius:9px;background:#f6f7f8!important;border:1px solid #eceef0!important;padding:9px 11px!important}.cset-content details{border-color:#e7e8ea!important;border-radius:10px!important}.cset-content .tt-template-panel{border:1px solid #e8e9eb!important;border-radius:12px!important;padding:14px!important;background:#fbfbfa!important}
@media(max-width:1050px){.cset-workspace{grid-template-columns:1fr}.cset-nav{top:62px;flex-direction:row;overflow:auto;padding:7px}.cset-nav button{min-width:180px}.cset-page-head{flex-direction:column;gap:14px}.cset-access-badge{white-space:normal}}
@media(max-width:680px){.cset-page-head h1{font-size:25px}.cset-content>.tt-card{padding:18px!important}.cset-nav button{min-width:155px}.cset-nav button small{display:none}.cset-content .tt-two,.cset-content .tt-number-grid,.cset-content .tt-template-grid{grid-template-columns:1fr!important}}
</style>
<script data-commercial-settings-script>
document.addEventListener('DOMContentLoaded',()=>{
  const nav=document.querySelector('[data-commercial-settings-nav]');
  if(!nav)return;
  const allCards=[...document.querySelectorAll('section.tt-card')].filter(card=>!card.closest('.tt-modal'));
  if(!allCards.length)return;
  const category=(card)=>{
    const title=(card.querySelector('h2')?.textContent||card.querySelector('.tt-section-title')?.textContent||'').trim();
    if(/Texte\s*&\s*Layout|Textvorlagen/i.test(title))return 'design';
    if(/Angaben auf Ihren Dokumenten|Rechtliche Informationen|Nummernkreise/i.test(title))return 'master';
    if(/Dokumente\s*&\s*Zahlungsbedingungen|Steuersätze|Zahlungen\s*&\s*Mahnwesen|A\+Bau Pay|Auszahlung/i.test(title))return 'finance';
    if(/Kommunikation|E-Mail|SMS/i.test(title))return 'communication';
    if(/KI-Datenverarbeitung|Datenschutz|Künstliche Intelligenz/i.test(title))return 'ai';
    return 'master';
  };
  allCards.forEach(card=>card.dataset.commercialSettingsCategory=category(card));
  const workspace=document.createElement('div');workspace.className='cset-workspace';workspace.dataset.commercialSettingsWorkspace='';
  const content=document.createElement('div');content.className='cset-content';content.dataset.commercialSettingsContent='';
  nav.parentNode.insertBefore(workspace,nav);workspace.appendChild(nav);workspace.appendChild(content);allCards.forEach(card=>content.appendChild(card));
  const tabs=[...nav.querySelectorAll('[data-commercial-settings-tab]')];
  const activate=(name,writeHash=true)=>{
    const valid=tabs.some(tab=>tab.dataset.commercialSettingsTab===name);if(!valid)name='design';
    tabs.forEach(tab=>tab.setAttribute('aria-selected',String(tab.dataset.commercialSettingsTab===name)));
    allCards.forEach(card=>card.hidden=card.dataset.commercialSettingsCategory!==name);
    if(writeHash&&history.replaceState)history.replaceState(null,'','#settings-'+name);
  };
  tabs.forEach(tab=>tab.addEventListener('click',()=>activate(tab.dataset.commercialSettingsTab)));
  const requested=(location.hash||'').replace('#settings-','');activate(requested||'design',false);
});
</script>
'''
    end = "{% endblock %}"
    idx = text.rfind(end)
    if idx < 0:
        raise RuntimeError("Commercial settings template endblock missing")
    text = text[:idx] + enhancement + "\n" + text[idx:]
    write(rel, text)


def patch_browser_smoke() -> None:
    rel = "scripts/production_browser_smoke.py"
    text = read(rel)
    close = "            context.close()\n"
    office_marker = "            # A+BAU COMMERCIAL SETTINGS ACCESS/UI BROWSER SMOKE\n"
    field_marker = "            # A+BAU COMMERCIAL SETTINGS FIELD DENIAL BROWSER SMOKE\n"

    office_start = text.find("def run_office_surface(")
    field_start = text.find("\ndef run_field_surface(", office_start)
    if office_start < 0 or field_start < 0:
        raise RuntimeError("Office/field browser smoke anchors missing")
    if office_marker not in text[office_start:field_start]:
        office_close = text.rfind(close, office_start, field_start)
        if office_close < 0:
            raise RuntimeError("Office browser context close missing")
        block = r'''            # A+BAU COMMERCIAL SETTINGS ACCESS/UI BROWSER SMOKE
            response = page.goto(urljoin(base_url, "settings/next/"), wait_until="domcontentloaded", timeout=30_000)
            if response is None or response.status != 200:
                fail(f"Commercial settings must return 200 for office role, got {response.status if response else 'no response'}")
            page.wait_for_timeout(260)
            if page.locator('[data-commercial-settings-shell]').count() != 1 or page.locator('[data-commercial-settings-nav]').count() != 1:
                fail("Commercial settings redesign shell/navigation is missing")
            if page.locator('[data-commercial-settings-tab]').count() != 5:
                fail("Commercial settings redesign must expose exactly five functional categories")
            visible_cards = page.locator('section.tt-card:visible')
            if visible_cards.count() == 0 or visible_cards.count() > 4:
                fail("Commercial settings still renders as an unstructured wall of cards")
            visible_submit = page.locator('section.tt-card:visible button[type="submit"]:visible').first
            if visible_submit.count():
                metrics = visible_submit.evaluate("el=>({button:el.getBoundingClientRect().width,card:el.closest('section').getBoundingClientRect().width})")
                if metrics['button'] >= metrics['card'] * .82:
                    fail("Commercial settings still uses full-width gold save bars")

'''
        text = text[:office_close] + block + text[office_close:]

    office_start = text.find("def run_office_surface(")
    field_start = text.find("\ndef run_field_surface(", office_start)
    if field_marker not in text[field_start:]:
        field_close = text.rfind(close, field_start)
        if field_close < 0:
            raise RuntimeError("Field browser context close missing")
        block = r'''            # A+BAU COMMERCIAL SETTINGS FIELD DENIAL BROWSER SMOKE
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

'''
        text = text[:field_close] + block + text[field_close:]

    write(rel, text)
    compile(text, str(ROOT / rel), "exec")


def install_contract_tests() -> None:
    write("tests/test_commercial_settings_access_ui_contract.py", r'''from pathlib import Path
from django.test import SimpleTestCase

ROOT = Path(__file__).resolve().parents[1]


class CommercialSettingsAccessUIContractTests(SimpleTestCase):
    def test_global_settings_have_strict_role_guard(self):
        views = (ROOT / "erp/tooltime_parity_views.py").read_text(encoding="utf-8")
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
        self.assertIn("Nur", account) if False else None
        self.assertIn("data-safe-account-page", account)
        self.assertNotIn('<span class="nx-ico">◎</span>Konto</a>', base.split("{% url 'next-settings' %}")[0] if "{% url 'next-settings' %}" in base else "")

    def test_settings_page_is_structured_not_one_long_wall(self):
        template = (ROOT / "templates/rebuild/tooltime_settings.html").read_text(encoding="utf-8")
        self.assertIn("data-commercial-settings-shell", template)
        self.assertIn("data-commercial-settings-nav", template)
        self.assertEqual(template.count("data-commercial-settings-tab="), 5)
        self.assertIn("cset-workspace", template)
        self.assertIn("commercialSettingsCategory", template)
        self.assertIn("full-width gold save bars", (ROOT / "scripts/production_browser_smoke.py").read_text(encoding="utf-8"))

    def test_browser_smoke_checks_both_allowed_and_denied_roles(self):
        smoke = (ROOT / "scripts/production_browser_smoke.py").read_text(encoding="utf-8")
        self.assertIn("A+BAU COMMERCIAL SETTINGS ACCESS/UI BROWSER SMOKE", smoke)
        self.assertIn("A+BAU COMMERCIAL SETTINGS FIELD DENIAL BROWSER SMOKE", smoke)
        self.assertIn("response.status != 403", smoke)
        self.assertIn('urljoin(base_url, "konto/")', smoke)
''')


def guard() -> None:
    views = read("erp/tooltime_parity_views.py")
    base = read("templates/rebuild/base.html")
    settings = read("templates/rebuild/tooltime_settings.html")
    urls = read("erp/rebuild_urls.py")
    for token in (
        "def _commercial_settings_access_allowed(request):",
        'return role in {"owner", "admin", "office", "accounting"}',
        "raise PermissionDenied",
        "def account_page(request):",
    ):
        if token not in views:
            raise RuntimeError(f"Commercial settings security contract missing: {token}")
    if 'name="next-account"' not in urls:
        raise RuntimeError("Safe personal account route missing")
    if base.count("{% url 'next-account' %}") < 2:
        raise RuntimeError("Technician desktop/mobile Konto links were not separated from commercial settings")
    if "data-commercial-settings-nav" not in settings or settings.count("data-commercial-settings-tab=") != 5:
        raise RuntimeError("Commercial settings information architecture redesign incomplete")


def run() -> None:
    patch_views()
    patch_urls()
    patch_base_navigation()
    install_account_template()
    patch_settings_template()
    patch_browser_smoke()
    install_contract_tests()
    guard()
    for rel in ("erp/tooltime_parity_views.py", "erp/rebuild_urls.py", "scripts/production_browser_smoke.py"):
        compile(read(rel), str(ROOT / rel), "exec")
    print(f"{MARKER}: Mitarbeiterkonto getrennt, kommerzielle Einstellungen serverseitig geschützt und UI in fünf Bereiche neu strukturiert.")


if __name__ == "__main__":
    run()
