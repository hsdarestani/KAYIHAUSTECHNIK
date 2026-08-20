from __future__ import annotations

import runpy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MARKER = "A+BAU COMMERCIAL SETTINGS TABBED SMOKE 2026-08-20"


def read(rel: str) -> str:
    path = ROOT / rel
    if not path.exists():
        raise RuntimeError(f"Tabbed-settings smoke target missing: {rel}")
    return path.read_text(encoding="utf-8")


def write(rel: str, text: str) -> None:
    path = ROOT / rel
    path.write_text(text, encoding="utf-8")


def patch_settings_categories() -> None:
    """Classify generated Settings cards by stable data markers before titles.

    The Phase-2 documents card was renamed to "Webansicht & Zahlungsbedingungen".
    Title-only classification therefore sent it to the fallback master category,
    making the finance controls invisible even when Finanzen was selected. Stable
    data markers are the correct contract for generated cards whose headings evolve.
    """
    rel = "templates/rebuild/tooltime_settings.html"
    text = read(rel)
    marker = "card.matches('[data-phase2-documents],[data-phase2-tax]')"
    if marker not in text:
        anchor = "    const title=(card.querySelector('h2')?.textContent||card.querySelector('.tt-section-title')?.textContent||'').trim();\n"
        if anchor not in text:
            raise RuntimeError("Commercial settings category function anchor missing")
        stable = anchor + "    if(card.matches('[data-phase2-numbering],[data-phase2-datev],[data-phase2-legal-documents]'))return 'master';\n    if(card.matches('[data-phase2-documents],[data-phase2-tax]'))return 'finance';\n    if(card.matches('[data-phase6-communication]'))return 'communication';\n"
        text = text.replace(anchor, stable, 1)
    if marker not in text:
        raise RuntimeError("Phase-2 finance cards were not mapped to Finanzen")
    write(rel, text)


def patch_phase2_interactions(text: str) -> str:
    """Make historical Phase-2 interaction checks tab-aware.

    The old smoke predates the five-tab information architecture and directly
    fills controls that are now intentionally hidden until their category is
    active. Keep the real interaction checks, but activate the owning tab first.
    """
    master_marker = "            # A+BAU PHASE2 MASTER TAB SETUP\n"
    finance_marker = "            # A+BAU PHASE2 FINANCE TAB SETUP\n"

    quote_fill = '            quote_prefix.fill("ANG-")\n'
    if master_marker not in text:
        pos = text.find(quote_fill)
        if pos < 0:
            raise RuntimeError("Phase-2 quote-prefix interaction anchor missing")
        block = r'''            # A+BAU PHASE2 MASTER TAB SETUP
            phase2_master_tab = page.locator('[data-commercial-settings-tab="master"]')
            if phase2_master_tab.count() != 1:
                fail("Phase 2 settings smoke cannot find Stammdaten & Recht tab")
            phase2_master_tab.click()
            page.wait_for_timeout(120)
            if phase2_master_tab.get_attribute("aria-selected") != "true":
                fail("Phase 2 settings smoke could not activate Stammdaten & Recht")
'''
        text = text[:pos] + block + text[pos:]

    payment_select = '            payment_mode.select_option("custom")\n'
    if finance_marker not in text:
        pos = text.find(payment_select)
        if pos < 0:
            raise RuntimeError("Phase-2 payment-mode interaction anchor missing")
        block = r'''            # A+BAU PHASE2 FINANCE TAB SETUP
            phase2_finance_tab = page.locator('[data-commercial-settings-tab="finance"]')
            if phase2_finance_tab.count() != 1:
                fail("Phase 2 settings smoke cannot find Finanzen tab")
            phase2_finance_tab.click()
            page.wait_for_timeout(120)
            if phase2_finance_tab.get_attribute("aria-selected") != "true":
                fail("Phase 2 settings smoke could not activate Finanzen")
'''
        text = text[:pos] + block + text[pos:]

    return text


def patch_smoke() -> None:
    rel = "scripts/production_browser_smoke.py"
    text = read(rel)
    office_start = text.find("def run_office_surface(")
    field_start = text.find("\ndef run_field_surface(", office_start)
    if office_start < 0 or field_start < 0:
        raise RuntimeError("Office/field browser smoke anchors missing")

    office = text[office_start:field_start]
    finance_marker = "            # A+BAU COMMERCIAL SETTINGS FINANCE TAB BROWSER SMOKE\n"

    # The historical generic page audit expected the finance-card heading to be
    # visible immediately on /settings/next/. The redesigned page deliberately
    # shows only the active tab, so that assertion must target the new visible
    # shell heading instead. We still verify the finance heading below after a
    # real click on the Finanzen tab.
    before_finance_block = office.split(finance_marker, 1)[0]
    old_double = '"Zahlungen & Mahnwesen"'
    old_single = "'Zahlungen & Mahnwesen'"
    new_double = '"Dokumente & Finanzen konfigurieren"'
    new_single = "'Dokumente & Finanzen konfigurieren'"
    if old_double in before_finance_block:
        absolute = office_start + before_finance_block.find(old_double)
        text = text[:absolute] + new_double + text[absolute + len(old_double):]
    elif old_single in before_finance_block:
        absolute = office_start + before_finance_block.find(old_single)
        text = text[:absolute] + new_single + text[absolute + len(old_single):]
    elif new_double not in before_finance_block and new_single not in before_finance_block:
        raise RuntimeError("Legacy settings finance marker was not found in office smoke")

    # Preserve the old Phase-2 fill/select checks, but make them operate on the
    # same tabs a real office user now sees.
    text = patch_phase2_interactions(text)

    # Recalculate anchors after the replacements above.
    office_start = text.find("def run_office_surface(")
    field_start = text.find("\ndef run_field_surface(", office_start)
    office = text[office_start:field_start]
    if finance_marker not in office:
        close = "            context.close()\n"
        office_close = text.rfind(close, office_start, field_start)
        if office_close < 0:
            raise RuntimeError("Office browser context close missing for tabbed settings smoke")
        block = r'''            # A+BAU COMMERCIAL SETTINGS FINANCE TAB BROWSER SMOKE
            response = page.goto(urljoin(base_url, "settings/next/"), wait_until="domcontentloaded", timeout=30_000)
            if response is None or response.status != 200:
                fail(f"Commercial settings finance-tab smoke expected 200, got {response.status if response else 'no response'}")
            finance_tab = page.locator('[data-commercial-settings-tab="finance"]')
            if finance_tab.count() != 1:
                fail("Commercial settings is missing the Finanzen tab")
            finance_tab.click()
            page.wait_for_timeout(180)
            if finance_tab.get_attribute("aria-selected") != "true":
                fail("Commercial settings Finanzen tab did not become active")
            visible_finance_cards = page.locator('section.tt-card:visible')
            if visible_finance_cards.count() == 0:
                fail("Commercial settings Finanzen tab exposes no visible settings cards")
            finance_text = page.locator('body').inner_text()
            if "Zahlungen & Mahnwesen" not in finance_text:
                fail("Commercial settings Finanzen tab is missing 'Zahlungen & Mahnwesen'")

'''
        text = text[:office_close] + block + text[office_close:]

    # Security assertions from the field smoke must survive this compatibility
    # patch unchanged.
    if "A+BAU COMMERCIAL SETTINGS FIELD DENIAL BROWSER SMOKE" not in text:
        raise RuntimeError("Field-denial browser smoke disappeared while patching settings tabs")
    if 'response.status != 403' not in text:
        raise RuntimeError("Technician direct-settings 403 assertion disappeared")

    write(rel, text)
    compile(text, str(ROOT / rel), "exec")


def run() -> None:
    patch_settings_categories()
    patch_smoke()
    smoke = read("scripts/production_browser_smoke.py")
    settings = read("templates/rebuild/tooltime_settings.html")
    for required in (
        "A+BAU COMMERCIAL SETTINGS FINANCE TAB BROWSER SMOKE",
        "A+BAU PHASE2 MASTER TAB SETUP",
        "A+BAU PHASE2 FINANCE TAB SETUP",
        "Dokumente & Finanzen konfigurieren",
    ):
        if required not in smoke:
            raise RuntimeError(f"Tabbed commercial-settings smoke contract missing: {required}")
    if "card.matches('[data-phase2-documents],[data-phase2-tax]')" not in settings:
        raise RuntimeError("Stable Phase-2 finance category mapping missing")

    # Field/mobile account shell is applied after every Settings/browser patch so
    # no earlier compatibility layer can hide the technician profile/logout menu.
    runpy.run_path(str(ROOT / "scripts" / "tooltime_field_account_shell_fix.py"), run_name="__main__")
    print(f"{MARKER}: Settings-Kategorien markerbasiert stabilisiert, Browser-Interaktionen an fünf Tabs angepasst und Mitarbeiter-Topbar/Logout wiederhergestellt.")


if __name__ == "__main__":
    run()