from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REL = "scripts/production_browser_smoke.py"
path = ROOT / REL
text = path.read_text(encoding="utf-8")

old = '''                ("/quotes/", ("Angebote", "Neues Angebot")),
                ("/invoices/", ("Rechnungen", "Neue Rechnung")),
                ("/migration/tooltime/", ("Von ToolTime zu KAYI", "Import starten")),
'''
new = '''                ("/quotes/", ("Angebote", "Neues Angebot")),
                ("/quotes/new/", ("Kunde und Projekt", "Leistungsgruppe hinzufügen", "Artikel durchsuchen", "Zahlungsbedingungen", "Fertigstellen")),
                ("/invoices/", ("Rechnungen", "Neue Rechnung")),
                ("/invoices/new/", ("Kunde und Projekt", "Rechnungsart", "Abschlagsrechnung", "Kalkulationsübersicht", "Fertigstellen")),
                ("/settings/next/", ("Texte & Layout", "Angaben auf Ihren Dokumenten", "Nummernkreise für Dokumente", "Zahlungen & Mahnwesen", "Kommunikation")),
                ("/migration/tooltime/", ("Von ToolTime zu A+Bau", "Import starten")),
'''
if old in text:
    text = text.replace(old, new, 1)
elif '"/quotes/new/"' not in text:
    raise RuntimeError("ToolTime-Browser-Smoke: Office-Checks-Anker fehlt.")

anchor = '''            visible_controls = page.locator('form input:not([type="hidden"]), form select, form textarea')
            if visible_controls.count() < 4:
                fail("new project flow has too few controls and appears broken")
'''
interaction = '''            visible_controls = page.locator('form input:not([type="hidden"]), form select, form textarea')
            if visible_controls.count() < 4:
                fail("new project flow has too few controls and appears broken")

            # Commercial document interactions are exercised, not only rendered.
            page.goto(urljoin(base_url, "quotes/new/"), wait_until="domcontentloaded", timeout=30_000)
            initial_groups = page.locator("[data-service-group]").count()
            page.click("[data-add-group]")
            if page.locator("[data-service-group]").count() != initial_groups + 1:
                fail("Leistungsgruppe hinzufügen does not add a group")
            last_group = page.locator("[data-service-group]").last
            before_positions = last_group.locator("[data-position]").count()
            last_group.locator("[data-add-position]").click()
            if last_group.locator("[data-position]").count() != before_positions + 1:
                fail("Position hinzufügen does not add a position")
            last_group.locator("[data-browse-articles]").first.click()
            if not page.locator("[data-article-modal]").is_visible():
                fail("Artikel durchsuchen does not open the advanced search")
            page.locator("[data-article-modal] [data-close-modal]").click()
            if page.locator("[data-margin-modal]").count() != 1:
                fail("Margen-Dialog is missing")
            if page.locator("[data-new-customer]").count() != 1 or page.locator("[data-new-project]").count() != 1:
                fail("quick customer/project creation controls are missing")

            page.goto(urljoin(base_url, "invoices/new/"), wait_until="domcontentloaded", timeout=30_000)
            invoice_types = page.locator('select[name="invoice_type"] option')
            labels = [invoice_types.nth(i).inner_text() for i in range(invoice_types.count())]
            for required in ("Standardrechnung", "Abschlagsrechnung", "Teilrechnung", "Schlussrechnung"):
                if required not in labels:
                    fail(f"invoice type {required!r} is missing")

            page.goto(urljoin(base_url, "settings/next/"), wait_until="domcontentloaded", timeout=30_000)
            for selector in ('input[name="logo_file"]', 'input[name="tax_number"]', 'input[name="invoice_prefix"]', 'textarea[name="invoice_body"]'):
                if page.locator(selector).count() != 1:
                    fail(f"commercial setting {selector!r} is missing")
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
print("ToolTime-Finanz-Browser-Smoke installiert.")
