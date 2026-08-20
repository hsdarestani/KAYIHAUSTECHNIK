from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REL = "scripts/production_browser_smoke.py"
path = ROOT / REL
text = path.read_text(encoding="utf-8")

# page.content() HTML-escapes visible ampersands (for example "Texte & Layout"
# becomes "Texte &amp; Layout"). Test user-visible copy against body.inner_text as
# well so the smoke remains strict without producing false negatives for valid DOM.
old_assert = '''    html = page.content()
    for marker in markers:
        if marker not in html:
            fail(f"{path} is missing {marker!r}")
'''
new_assert = '''    html = page.content()
    visible_text = page.locator("body").inner_text()
    for marker in markers:
        if marker not in html and marker not in visible_text:
            fail(f"{path} is missing {marker!r}")
'''
if new_assert not in text:
    if old_assert not in text:
        raise RuntimeError("ToolTime-Browser-Smoke: assert_page-Anker fehlt.")
    text = text.replace(old_assert, new_assert, 1)

if '"/quotes/new/"' not in text:
    quote_line = '                ("/quotes/", ("Angebote", "Neues Angebot")),\n'
    if quote_line not in text:
        raise RuntimeError("ToolTime-Browser-Smoke: Angebotslisten-Anker fehlt.")
    text = text.replace(
        quote_line,
        quote_line + '                ("/quotes/new/", ("Kunde und Projekt", "Leistungsgruppe hinzufügen", "Artikel durchsuchen", "Zahlungsbedingungen", "Fertigstellen")),\n',
        1,
    )
if '"/invoices/new/"' not in text:
    invoice_line = '                ("/invoices/", ("Rechnungen", "Neue Rechnung")),\n'
    if invoice_line not in text:
        raise RuntimeError("ToolTime-Browser-Smoke: Rechnungsliste-Anker fehlt.")
    text = text.replace(
        invoice_line,
        invoice_line + '                ("/invoices/new/", ("Kunde und Projekt", "Rechnungsart", "Abschlagsrechnung", "Kalkulationsübersicht", "Fertigstellen")),\n                ("/settings/next/", ("Texte & Layout", "Angaben auf Ihren Dokumenten", "Nummernkreise für Dokumente", "Zahlungen & Mahnwesen", "Kommunikation")),\n',
        1,
    )

anchor = '''            visible_controls = page.locator('form input:not([type="hidden"]), form select, form textarea')
            if visible_controls.count() < 4:
                fail("new project flow has too few controls and appears broken")
'''
interaction = '''            visible_controls = page.locator('form input:not([type="hidden"]), form select, form textarea')
            if visible_controls.count() < 4:
                fail("new project flow has too few controls and appears broken")

            # Die kaufmännische Oberfläche wird nicht nur gerendert, sondern geklickt.
            page.goto(urljoin(base_url, "quotes/new/"), wait_until="domcontentloaded", timeout=30_000)
            initial_groups = page.locator("[data-service-group]").count()
            page.click("[data-add-group]")
            if page.locator("[data-service-group]").count() != initial_groups + 1:
                fail("Leistungsgruppe hinzufügen funktioniert nicht")
            last_group = page.locator("[data-service-group]").last
            before_positions = last_group.locator("[data-position]").count()
            last_group.locator("[data-add-position]").click()
            if last_group.locator("[data-position]").count() != before_positions + 1:
                fail("Position hinzufügen funktioniert nicht")
            last_group.locator("[data-browse-articles]").first.click()
            if not page.locator("[data-article-modal]").is_visible():
                fail("Artikel durchsuchen öffnet die erweiterte Suche nicht")
            page.locator("[data-article-modal] [data-close-modal]").click()
            if page.locator("[data-margin-modal]").count() != 1:
                fail("Margen-Dialog fehlt")
            if page.locator("[data-new-customer]").count() != 1 or page.locator("[data-new-project]").count() != 1:
                fail("Schnellanlage für Kunde/Projekt fehlt")

            page.goto(urljoin(base_url, "invoices/new/"), wait_until="domcontentloaded", timeout=30_000)
            invoice_types = page.locator('select[name="invoice_type"] option')
            labels = [invoice_types.nth(i).inner_text() for i in range(invoice_types.count())]
            for required in ("Standardrechnung", "Abschlagsrechnung", "Teilrechnung", "Schlussrechnung"):
                if required not in labels:
                    fail(f"Rechnungsart {required!r} fehlt")

            page.goto(urljoin(base_url, "settings/next/"), wait_until="domcontentloaded", timeout=30_000)
            for selector in ('input[name="logo_file"]', 'input[name="tax_number"]', 'input[name="invoice_prefix"]', 'textarea[name="invoice_body"]'):
                if page.locator(selector).count() != 1:
                    fail(f"Kaufmännische Einstellung {selector!r} fehlt")
'''
if interaction not in text:
    if anchor not in text:
        raise RuntimeError("ToolTime-Browser-Smoke: Interaktionsanker fehlt.")
    text = text.replace(anchor, interaction, 1)

text = text.replace(
    'print("KAYI Next browser smoke passed: office flow, project creation, planning, technician role, tasks, expenses, team, commercial documents and ToolTime migration.")',
    'print("A+Bau Browser-Smoke bestanden: Büro, Projekte, Termine, Außendienst sowie ToolTime-paritäre Angebote, Rechnungen, Artikelsuche und Einstellungen.")',
)
path.write_text(text, encoding="utf-8")
print("ToolTime-Finanz-Browser-Smoke installiert: DOM-sichere Textprüfung plus echte Interaktionen.")
