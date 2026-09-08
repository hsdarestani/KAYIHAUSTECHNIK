#!/usr/bin/env python3
from __future__ import annotations

import os
import re
import secrets
import sys
from pathlib import Path
from urllib.parse import urljoin

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django

django.setup()

from django.contrib.auth import get_user_model
from erp.models import UserProfile

SCREENSHOT_PATH = Path("/tmp/kayi-next-browser-smoke.png")


def fail(message: str) -> None:
    raise RuntimeError(f"KAYI Next browser smoke failed: {message}")


def assert_page(page, base_url: str, path: str, markers: tuple[str, ...]) -> None:
    response = page.goto(urljoin(base_url, path.lstrip("/")), wait_until="domcontentloaded", timeout=30_000)
    if response is None or response.status >= 500:
        fail(f"{path} returned {response.status if response else 'no response'}")
    if "/login/" in page.url:
        fail(f"{path} unexpectedly redirected to login")
    html = page.content()
    visible_text = page.locator("body").inner_text()
    for marker in markers:
        if marker not in html and marker not in visible_text:
            fail(f"{path} is missing {marker!r}")
    # KAYI German-only visible UI audit. Check rendered text, not source code,
    # so technical identifiers and API field names are ignored.
    visible_text = page.locator("body").inner_text()
    forbidden_visible = re.compile(r"\b(?:Cancel|Save|Create|Edit|Delete|Upload|Provider|Wizard|Voice|Settings|Customer|Quote|Invoice|AI)\b")
    match = forbidden_visible.search(visible_text)
    if match:
        fail(f"{path} still exposes English UI text {match.group(0)!r}")
    for forbidden_phrase in ("Work OS", "Create a room from photos", "Take or select room photos", "Detect and place space"):
        if forbidden_phrase in visible_text:
            fail(f"{path} still exposes English UI text {forbidden_phrase!r}")


def login(page, base_url: str, username: str, password: str) -> None:
    response = page.goto(urljoin(base_url, "login/"), wait_until="domcontentloaded", timeout=30_000)
    if response is None or response.status >= 500:
        fail("login route is unavailable")
    page.fill('input[name="username"]', username)
    page.fill('input[name="password"]', password)
    with page.expect_navigation(wait_until="domcontentloaded", timeout=30_000):
        page.click('button[type="submit"], button.btn-primary')
    if "/login/" in page.url:
        fail("login did not establish an authenticated session")
    overlay = page.locator("[data-tutorial-overlay]")
    if overlay.count() and overlay.is_visible():
        skip = page.locator("[data-tutorial-skip]")
        if skip.count():
            skip.click()
            overlay.wait_for(state="hidden", timeout=5_000)


def run_office_surface(base_url: str, username: str, password: str, page_errors: list[str]) -> None:
    from playwright.sync_api import sync_playwright

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context(locale="de-DE", viewport={"width": 1440, "height": 1000})
        page = context.new_page()
        page.on("pageerror", lambda error: page_errors.append(f"{page.url}: {error}"))
        try:
            login(page, base_url, username, password)
            # KAYI global KI profile smoke
            if page.locator('[data-global-assistant-form]').count() != 1 or page.locator('[data-assistant-drawer]').count() != 1:
                fail("global KAYI KI assistant is missing from office surface")
            if page.locator('[data-profile-toggle]').count() != 1:
                fail("profile avatar is not interactive")
            page.locator('[data-profile-toggle]').click()
            if not page.locator('[data-profile-menu]').is_visible():
                fail("profile menu does not open")
            page.keyboard.press('Escape')
            office_checks = [
                ("/", ("data-ab-v3-dashboard", "Daten importieren", "kayi-next.css")),
                ("/customers/", ("Kunden", "Neuer Kunde")),
                ("/customers/new/", ("Neuer Kunde", "Details einblenden", "＋ Erstellen")),
                ("/projects/", ("Projekte", "Neues Projekt")),
                ("/projects/new/", ("Neues Projekt", "Kunde suchen", "Abweichenden Ausführungsort verwenden", "＋ Erstellen")),
                ("/appointments/", ("Termine", "Neuer Termin")),
                ("/appointments/new/", ("Neuer Termin", "Kunde oder Projekt auswählen", "Arbeitsbericht", "Bilder")),
                ("/time/", ("Zeiterfassung", "Arbeitszeiten")),
                ("/tasks/", ("Aufgaben", "Neue Aufgabe")),
                ("/tasks/new/", ("Neue Aufgabe", "Speichern")),
                ("/expenses/", ("Ausgaben", "Ausgabe erfassen")),
                ("/expenses/new/", ("Beleg erfassen", "data-receipt-dropzone", "Speichern")),
                ("/employees/", ("Mitarbeiter", "Mitarbeiter")),
                ("/employees/new/", ("Mitarbeiter anlegen", "Speichern")),
                ("/quotes/", ("Angebote", "Neues Angebot")),
                ("/quotes/new/", ("Kunde und Projekt", "Leistungsgruppe hinzufügen", "Artikel durchsuchen", "Zahlungsbedingungen", "Fertigstellen")),
                ("/invoices/", ("Rechnungen", "Neue Rechnung")),
                ("/invoices/new/", ("Kunde und Projekt", "Rechnungsart", "Abschlagsrechnung", "Kalkulationsübersicht", "Fertigstellen")),
                ("/settings/next/", ("Texte & Layout", "Angaben auf Ihren Dokumenten", "Nummernkreise für Dokumente", "Dokumente & Finanzen konfigurieren", "Kommunikation")),
                ("/migration/tooltime/", ("Von ToolTime zu A+Bau", "Import starten")),
                ("/settings/next/", ("Einstellungen", "KI-Datenverarbeitung", "Konto und Daten löschen")),
                ("/settings/", ("Einstellungen",)),
            ]
            for path, markers in office_checks:
                assert_page(page, base_url, path, markers)

            page.goto(urljoin(base_url, "projects/new/"), wait_until="domcontentloaded", timeout=30_000)
            html = page.content()
            if "9-Schritte-Projektassistent" in html or "wizard-step" in html:
                fail("legacy project wizard is still the primary creation flow")
            visible_controls = page.locator('form input:not([type="hidden"]), form select, form textarea')
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
            for selector in ('input[name="logo_file"]', 'input[name="tax_number"]', 'input[name="invoice_prefix"]', ):
                if page.locator(selector).count() != 1:
                    fail(f"Kaufmännische Einstellung {selector!r} fehlt")


            # TOOLTIME_PHASE2_SETTINGS_BROWSER_20260820
            # Nummernkreise: Vorschau muss live aus Präfix + numerischem Startwert
            # reagieren; sie ist kein statischer Hilfetext.
            if page.locator('[data-phase2-numbering]').count() != 1:
                fail("ToolTime Nummernkreise fehlen")
            quote_prefix = page.locator('[data-phase2-numbering] input[name="quote_prefix"]')
            quote_start = page.locator('[data-phase2-numbering] input[name="quote_start"]')
            quote_preview = page.locator('[data-number-preview="quote"]')
            # A+BAU PHASE2 MASTER TAB SETUP
            phase2_master_tab = page.locator('[data-commercial-settings-tab="master"]')
            if phase2_master_tab.count() != 1:
                fail("Phase 2 settings smoke cannot find Stammdaten & Recht tab")
            phase2_master_tab.click()
            page.wait_for_timeout(120)
            if phase2_master_tab.get_attribute("aria-selected") != "true":
                fail("Phase 2 settings smoke could not activate Stammdaten & Recht")
            quote_prefix.fill("ANG-")
            quote_start.fill("0007")
            quote_start.dispatch_event("input")
            if not quote_preview.inner_text().startswith("ANG-"):
                fail("Vorschau der nächsten Angebotsnummer reagiert nicht auf den Präfix")
            if len(quote_preview.inner_text().split("ANG-", 1)[-1]) < 4:
                fail("Führende Nullen im Nummernkreis werden nicht erhalten")

            # DATEV: alle drei in ToolTime dokumentierten Vergabemodi und die
            # getrennten fünfstelligen Debitor-/Kreditorbereiche müssen bedienbar sein.
            if page.locator('[data-phase2-datev]').count() != 1:
                fail("DATEV Debitoren-/Kreditoreneinstellungen fehlen")
            datev_mode = page.locator('[data-phase2-datev] select[name="datev_mode"]')
            datev_values = [datev_mode.locator("option").nth(i).get_attribute("value") for i in range(datev_mode.locator("option").count())]
            for required in ("automatic", "customer_number", "import"):
                if required not in datev_values:
                    fail(f"DATEV-Modus {required!r} fehlt")
            for selector in ('input[name="debtor_start"]', 'input[name="creditor_start"]', 'input[name="datev_file"]'):
                if page.locator(f'[data-phase2-datev] {selector}').count() != 1:
                    fail(f"DATEV-Steuerung {selector!r} fehlt")

            # AGB/Widerruf müssen je Dokumenttyp als echte Standardanhänge steuerbar
            # sein, nicht nur als zwei lose Uploadfelder.
            if page.locator('[data-phase2-legal-documents]').count() != 1:
                fail("Rechtliche Standardanhänge fehlen")
            for selector in ('input[name="terms_file"]', 'input[name="withdrawal_file"]', 'input[name="attach_terms_quote"]', 'input[name="attach_terms_invoice"]', 'input[name="attach_withdrawal_quote"]', 'input[name="attach_withdrawal_invoice"]'):
                if page.locator(f'[data-phase2-legal-documents] {selector}').count() != 1:
                    fail(f"Rechtliche Dokumentsteuerung {selector!r} fehlt")

            # Zahlungsziel: Benutzerdefiniert muss die Tagesangabe aktivieren und
            # die sichtbare Vorschau sofort aktualisieren.
            docs = page.locator('[data-phase2-documents]')
            if docs.count() != 1:
                fail("Angebots-/Rechnungsstandards fehlen")
            payment_mode = docs.locator('select[name="payment_mode"]')
            payment_days = docs.locator('input[name="payment_days"]')
            # A+BAU PHASE2 FINANCE TAB SETUP
            phase2_finance_tab = page.locator('[data-commercial-settings-tab="finance"]')
            if phase2_finance_tab.count() != 1:
                fail("Phase 2 settings smoke cannot find Finanzen tab")
            phase2_finance_tab.click()
            page.wait_for_timeout(120)
            if phase2_finance_tab.get_attribute("aria-selected") != "true":
                fail("Phase 2 settings smoke could not activate Finanzen")
            payment_mode.select_option("custom")
            payment_mode.dispatch_event("input")
            payment_days.fill("21")
            payment_days.dispatch_event("input")
            if "21 Tagen" not in docs.locator('[data-payment-preview]').inner_text():
                fail("Benutzerdefiniertes Zahlungsziel aktualisiert die Vorschau nicht")
            for selector in ('input[name="quote_private"]', 'input[name="quote_company"]', 'input[name="invoice_private"]', 'input[name="invoice_company"]', 'input[name="quote_web_default"]', 'input[name="acceptance_email"]'):
                if docs.locator(selector).count() != 1:
                    fail(f"Dokumentstandard {selector!r} fehlt")

            # Steuersätze müssen editierbar sein und eigene DATEV-Konten pro
            # Kontenrahmen tragen.
            tax = page.locator('[data-phase2-tax]')
            if tax.count() != 1 or tax.locator('input[name="tax_title"]').count() < 1:
                fail("Editierbare Steuersätze fehlen")
            for selector in ('input[name="tax_note"]', 'input[name="datev_skr03"]', 'input[name="datev_skr04"]'):
                if tax.locator(selector).count() < 1:
                    fail(f"Steuersatzfeld {selector!r} fehlt")

            # KAYI customer form and 3D KI polish smoke
            page.goto(urljoin(base_url, "customers/new/"), wait_until="domcontentloaded", timeout=30_000)
            if page.locator('[data-location-details]').count() != 1:
                fail("customer form is missing progressive execution-location disclosure")
            if page.locator('[data-location-details]').evaluate("el => el.open"):
                fail("optional execution location is expanded by default")
            customer_text = page.locator('body').inner_text()
            if 'Floor' in customer_text or 'Access notes' in customer_text:
                fail("customer form still exposes English location labels")
            if 'Abweichenden Einsatzort hinzufügen' not in customer_text:
                fail("customer form has no clear optional execution-location action")
            # Continue the existing project-form smoke on the page it expects.
            page.goto(urljoin(base_url, "projects/new/"), wait_until="domcontentloaded", timeout=30_000)
            if page.locator('[data-select-search]').count() != 1:
                fail("project customer selector has no search input")

            page.goto(urljoin(base_url, "appointments/new/"), wait_until="domcontentloaded", timeout=30_000)
            checkbox = page.locator('input[name="all_day"]')
            if checkbox.count() != 1:
                fail("appointment all-day checkbox is missing")
            box = checkbox.bounding_box()
            if not box or box["width"] > 30 or box["height"] > 30:
                fail(f"appointment checkbox is oversized: {box}")
            label = page.locator('label[for="id_all_day"]').inner_text()
            if "Ganztägig" not in label:
                fail("appointment checkbox label is not German")

            page.goto(urljoin(base_url, "quotes/new/"), wait_until="domcontentloaded", timeout=30_000)
            table = page.locator('[data-service-groups]').first
            add = page.locator('[data-add-position]:visible').first
            if table.count() == 0 or add.count() == 0:
                fail("quote position editor controls are missing")
            before = table.locator('[data-position]').count()
            add.click()
            after = table.locator('[data-position]').count()
            if after != before + 1:
                fail(f"+ Position did not add a row: {before} -> {after}")

            # catalog search Enter and selected-state smoke
            catalog_items = page.locator('[data-catalog-item]')
            if catalog_items.count():
                first_catalog = catalog_items.first
                catalog_name = first_catalog.get_attribute('data-name') or first_catalog.inner_text().split('\n', 1)[0]
                catalog_search = page.locator('[data-catalog-search]')
                catalog_search.fill(catalog_name)
                catalog_search.press('Enter')
                if '/quotes/new/' not in page.url:
                    fail(f"catalog Enter navigated away from quote editor: {page.url}")
                visible_catalog = page.locator('[data-catalog-item]:visible')
                if visible_catalog.count() < 1:
                    fail("catalog search hid the expected result")
                rows_before_catalog = table.locator('tbody tr').count()
                visible_catalog.first.click()
                page.wait_for_timeout(100)
                rows_after_catalog = table.locator('tbody tr').count()
                if rows_after_catalog != rows_before_catalog + 1:
                    fail("catalog click did not add a quote position")
                selected_text = page.locator('[data-catalog-selected]').inner_text()
                if catalog_name not in selected_text:
                    fail(f"catalog selection is not visible after adding {catalog_name!r}")

            # Open a real project and exercise the Room Planner photo dialog.
            page.goto(urljoin(base_url, "projects/"), wait_until="domcontentloaded", timeout=30_000)
            project_hrefs = page.locator('a[href^="/projects/"]').evaluate_all("els => els.map(e => e.getAttribute('href')).filter(h => /^\/projects\/\d+\/$/.test(h))")
            if not project_hrefs:
                fail("German UI smoke could not find a project for Room Planner")
            page.goto(urljoin(base_url, project_hrefs[0].lstrip("/")), wait_until="domcontentloaded", timeout=30_000)
            planner_link = page.locator('a[href$="/room-planner/"]').first
            if planner_link.count() != 1:
                fail("project detail is missing Room Planner link")
            planner_link.click()
            page.wait_for_load_state("domcontentloaded")
            trigger = page.locator('[data-rp-open-vision]').first
            if trigger.count() != 1:
                fail("Room Planner is missing photo recognition action")
            trigger.click()
            dialog = page.locator('[data-rp-vision-dialog][open]')
            dialog.wait_for(state="attached", timeout=5_000)
            dialog_text = dialog.inner_text()
            for required in ("Raum aus Fotos aufbauen", "Foto aufnehmen", "Aus Galerie auswählen", "Raum erkennen & platzieren"):
                if required not in dialog_text:
                    fail(f"German Room Planner photo dialog is missing {required!r}")
            room_forbidden = re.compile(r"\b(?:Cancel|Save|Create|Edit|Delete|Upload|Provider|Wizard|Voice|AI)\b")
            match = room_forbidden.search(dialog_text)
            if match:
                fail(f"Room Planner still exposes English text {match.group(0)!r}")
            for forbidden in ("Create a room from photos", "Take or select room photos", "Detect and place space"):
                if forbidden in dialog_text:
                    fail(f"Room Planner still exposes English text {forbidden!r}")
            if page.locator('[data-rp-camera-files]').count() != 1:
                fail("Room Planner is missing dedicated camera input")
            if page.locator('[data-rp-gallery-files][multiple]').count() != 1:
                fail("Room Planner is missing multi-select gallery input")
            page.locator('[data-rp-close-vision]').first.click()


            # KAYI Room Planner Pro browser smoke: enter a real project through the
            # production UI and require the WebGL engine to initialize without JS errors.
            page.goto(urljoin(base_url, "projects/"), wait_until="domcontentloaded", timeout=30_000)
            project_link = page.locator('a.nx-btn-ghost[href^="/projects/"]').first
            if project_link.count():
                project_href = project_link.get_attribute("href")
                page.goto(urljoin(base_url, (project_href or "").lstrip("/")), wait_until="domcontentloaded", timeout=30_000)
                planner_link = page.locator('a[href*="/room-planner/"]').first
                if planner_link.count() != 1:
                    fail("project workspace is missing the Raum & 3D action")
                planner_href = planner_link.get_attribute("href")
                response = page.goto(urljoin(base_url, (planner_href or "").lstrip("/")), wait_until="domcontentloaded", timeout=30_000)
                if response is None or response.status >= 500:
                    fail(f"Room Planner Pro returned {response.status if response else 'no response'}")
                if "Raumplanung 3D" not in page.content():
                    fail("Room Planner Pro is missing its primary heading")
                page.locator('[data-rp-canvas][data-ready="1"]').wait_for(state="attached", timeout=20_000)
                if page.locator('[data-rp-engine-error]:visible').count():
                    fail("Room Planner Pro WebGL engine displayed an initialization error")
                if page.locator('[data-rp-add-object]').count() < 20:
                    fail("Room Planner Pro object library is incomplete")
                if page.locator('[data-rp-ki-card]:visible').count() != 1:
                    fail("3D planner KI assistant is not clearly visible")
                if page.locator('[data-rp-ai-command]').count() != 1 or page.locator('[data-rp-run-ai]').count() != 1:
                    fail("3D planner KI command controls are incomplete")
                first_example = page.locator('[data-rp-ai-example]').first
                if first_example.count() != 1:
                    fail("3D planner KI examples are missing")
                first_example.click()
                if not page.locator('[data-rp-ai-command]').input_value().strip():
                    fail("3D planner KI example does not populate the command field")
                planner_text = page.locator('body').inner_text()
                for forbidden in ('Characteristics', 'Room overview', 'Doors & Windows', 'Save version', 'Live distances', 'AI sets'):
                    if forbidden in planner_text:
                        fail(f"3D planner still exposes English text: {forbidden}")
                panel_font = float(page.locator('.rp-panel-title b').first.evaluate("el => parseFloat(getComputedStyle(el).fontSize)"))
                object_font = float(page.locator('[data-rp-add-object] b').first.evaluate("el => parseFloat(getComputedStyle(el).fontSize)"))
                if panel_font < 14 or object_font < 11:
                    fail(f"3D planner typography is still too small: panel={panel_font}px object={object_font}px")
                csrf_cookies = [cookie for cookie in page.context.cookies() if cookie.get('name') == 'csrftoken']
                if not csrf_cookies:
                    fail("3D planner did not receive a CSRF cookie for safe save requests")
                vision_trigger = page.locator('[data-rp-open-vision]').first
                if vision_trigger.count() != 1:
                    fail("Room Planner Pro AI photo action is missing")
                vision_trigger.click()
                page.locator('[data-rp-vision-dialog][open]').wait_for(state="attached", timeout=5_000)
                if page.locator('[data-rp-run-vision]').count() != 1:
                    fail("Room Planner Pro AI analysis action is missing")
                page.locator('[data-rp-close-vision]').first.click()
            # A+BAU TOOLTIME PHASE 9 CORE CRUD BROWSER SMOKE
            page.goto(urljoin(base_url, "projects/new/"), wait_until="domcontentloaded", timeout=30_000)
            html = page.content()
            if "9-Schritte-Projektassistent" in html or "wizard-step" in html or "Aufmaß / 3D" in html or "Kein Wizard" in html:
                fail("legacy/non-ToolTime project creation content is still visible")
            if page.locator('input[name="title"]').count() != 1 or page.locator('select[name="customer"]').count() != 1:
                fail("ToolTime-like project title/customer controls are missing")
            alternate_toggle = page.locator('[data-alt-location-toggle]')
            alternate_panel = page.locator('[data-alt-location]')
            switch_row = page.locator('.tt-switch-row')
            if alternate_toggle.count() != 1 or alternate_panel.count() != 1 or switch_row.count() != 1:
                fail("project creation is missing the alternate-location switch")
            if alternate_panel.is_visible():
                fail("alternate location must be progressively disclosed")
            switch_row.click()
            page.wait_for_timeout(80)
            if not alternate_panel.is_visible() or not alternate_toggle.is_checked():
                fail("alternate-location switch does not reveal the location selector")
            switch_row.click()
            page.wait_for_timeout(80)
            if alternate_panel.is_visible() or alternate_toggle.is_checked():
                fail("alternate-location switch does not restore customer-address default")

            page.goto(urljoin(base_url, "customers/new/"), wait_until="domcontentloaded", timeout=30_000)
            customer_details = page.locator('[data-more-details]')
            location_details = page.locator('[data-location-details]')
            if customer_details.count() != 1 or location_details.count() != 1:
                fail("ToolTime-like customer progressive details are missing")
            if customer_details.get_attribute("open") is not None:
                fail("optional customer details should be collapsed initially")
            customer_details.locator('summary').click()
            page.wait_for_timeout(60)
            customer_number = page.locator('input[name="customer_number"]')
            if customer_number.count() != 1 or not customer_number.is_visible():
                fail("customer creation is missing the customer-number field")
            # A+BAU TOOLTIME PHASE 10 APPOINTMENT BROWSER SMOKE
            response = page.goto(urljoin(base_url, "appointments/new/"), wait_until="domcontentloaded", timeout=30_000)
            if response is None or response.status >= 500:
                fail(f"Phase 10 appointment create returned {response.status if response else 'no response'}")
            if page.locator('[data-appointment-create]').count() != 1:
                fail("Phase 10 appointment create shell is missing")
            if page.locator('[data-appointment-customer]').count() != 1 or page.locator('[data-appointment-project-select]').count() != 1:
                fail("Phase 10 customer/project selection controls are missing")
            if page.locator('[data-start-date]').count() != 1 or page.locator('[data-start-time]').count() != 1:
                fail("Phase 10 start date/time controls are missing")
            if page.locator('[data-end-date]').count() != 1 or page.locator('[data-end-time]').count() != 1:
                fail("Phase 10 end date/time controls are missing")
            if page.locator('[data-address-card]').count() != 1 or page.locator('[data-team-search]').count() != 1:
                fail("Phase 10 address/team controls are missing")
            phase10_text = page.locator("body").inner_text()
            for expected in ("Kunde oder Projekt auswählen", "Einmalig", "Arbeitsbericht", "Bilder"):
                if expected not in phase10_text:
                    fail(f"Phase 10 appointment create is missing {expected!r}")
        except Exception:
            try:
                page.screenshot(path=str(SCREENSHOT_PATH), full_page=True)
                print(f"Failure screenshot: {SCREENSHOT_PATH}", file=sys.stderr)
                print(f"Failure URL: {page.url}", file=sys.stderr)
            except Exception:
                pass
            raise
        finally:
            # A+BAU PHASE 4 LIFECYCLE BROWSER SMOKE
            response = page.goto(urljoin(base_url, "quotes/"), wait_until="domcontentloaded", timeout=30_000)
            if response is None or response.status >= 500:
                fail(f"Angebotsliste returned {response.status if response else 'no response'}")
            quote_text = page.locator("body").inner_text()
            # Sort is intentionally a compact/hidden desktop control in the exact
            # ToolTime surface and is asserted structurally below. Do not require
            # its label to be visibly rendered in body.inner_text().
            for required in ("Angebote", "Suchen", "Status", "Neues Angebot"):
                if required not in quote_text:
                    fail(f"Angebotsliste fehlt {required!r}")
            if page.locator('form.tt-list-toolbar select[name="status"]').count() != 1:
                fail("Angebots-Statusfilter fehlt")
            if page.locator('form.tt-list-toolbar select[name="sort"]').count() != 1:
                fail("Angebots-Sortierung fehlt")

            response = page.goto(urljoin(base_url, "invoices/"), wait_until="domcontentloaded", timeout=30_000)
            if response is None or response.status >= 500:
                fail(f"Rechnungsliste returned {response.status if response else 'no response'}")
            invoice_text = page.locator("body").inner_text()
            for required in ("Rechnungen", "Unbezahlt", "Überfällig", "Neue Rechnung"):
                if required not in invoice_text:
                    fail(f"Rechnungsliste fehlt {required!r}")
            if page.locator('[data-payment-modal]').count() != 1:
                fail("Zahlungsdialog fehlt")
            payment_modal = page.locator('[data-payment-modal]')
            for selector in ('input[name="paid_at"]', 'input[name="amount"]', 'select[name="method"]', 'input[name="reference"]'):
                if payment_modal.locator(selector).count() != 1:
                    fail(f"Zahlungsdialog-Feld fehlt: {selector}")
            pay_buttons = page.locator('[data-payment-open]')
            if pay_buttons.count():
                pay_buttons.first.click()
                if payment_modal.is_hidden():
                    fail("Zahlung eintragen öffnet den Zahlungsdialog nicht")
                if not payment_modal.locator('[data-payment-form]').get_attribute("action"):
                    fail("Zahlungsdialog hat kein echtes Buchungsziel")
                payment_modal.locator('[data-payment-close]').click()

            # A+BAU TOOLTIME PAY BROWSER SMOKE
            response = page.goto(urljoin(base_url, "settings/next/"), wait_until="domcontentloaded", timeout=30_000)
            if response is None or response.status >= 500: fail(f"Pay-Einstellungen returned {response.status if response else 'no response'}")
            pay_panel = page.locator('[data-tooltime-pay-settings]')
            if pay_panel.count() != 1: fail("A+Bau Pay Einstellungen fehlen")
            for selector in ('select[name="pay_provider"]','input[name="pay_endpoint"]','input[name="card_limit"]','select[name="payout_mode"]','input[name="automatic_dunning"]'):
                if pay_panel.locator(selector).count() != 1: fail(f"Pay-Einstellung fehlt: {selector}")
            for route, selector in (("payments/", "[data-tooltime-pay-overview]"), ("payouts/", "[data-tooltime-payout-overview]")):
                response = page.goto(urljoin(base_url, route), wait_until="domcontentloaded", timeout=30_000)
                if response is None or response.status >= 500: fail(f"{route} returned {response.status if response else 'no response'}")
                if page.locator(selector).count() != 1: fail(f"{route} zeigt nicht die echte A+Bau-Pay-Oberfläche")

            # A+BAU PHASE 6 COMMUNICATION SETTINGS BROWSER SMOKE
            response = page.goto(urljoin(base_url, "settings/next/"), wait_until="domcontentloaded", timeout=30_000)
            if response is None or response.status >= 500:
                fail(f"Kommunikationseinstellungen returned {response.status if response else 'no response'}")
            panel = page.locator('[data-phase6-communication]')
            if panel.count() != 1:
                fail("Kommunikationsbereich fehlt in den Einstellungen")
            for selector in (
                'input[name="sender_name"]',
                'input[name="reply_email"]',
                'input[name="quote_subject"]',
                'textarea[name="quote_body"]',
                'input[name="invoice_subject"]',
                'textarea[name="invoice_body"]',
                'select[name="sms_provider"]',
                'input[name="sms_endpoint"]',
                'input[name="sms_sender_id"]',
                'textarea[name="sms"]',
            ):
                if panel.locator(selector).count() != 1:
                    fail(f"Kommunikationseinstellung fehlt: {selector}")
            sms = panel.locator('textarea[name="sms"]')
            if sms.get_attribute("maxlength") != "160":
                fail("SMS-Vorlage erzwingt nicht exakt maximal 160 Zeichen")
            options = panel.locator('select[name="sms_provider"] option').evaluate_all("nodes => nodes.map(node => node.value)")
            if "disabled" not in options or "webhook" not in options:
                fail("SMS-Dienst bietet nicht Deaktiviert und HTTPS-Schnittstelle")
            if panel.locator('[data-phase6-preview]').count() < 4:
                fail("Live-Vorschau für Angebot und Rechnung fehlt")
            page.wait_for_timeout(150)
            quote_preview = panel.locator('[data-phase6-preview="quote-subject"]').inner_text().strip()
            if not quote_preview:
                fail("Live-Vorschau des Angebotsbetreffs ist leer")

            # A+BAU TOOLTIME PHASE 8 ONLINE ACCEPTANCE
            phase8_path = os.environ.get("KAYI_PHASE8_PUBLIC_PATH", "")
            if not phase8_path:
                fail("Online-Annahme-Smoke-Pfad wurde vor dem Browserstart nicht vorbereitet")
            response = page.goto(urljoin(base_url, phase8_path.lstrip("/")), wait_until="domcontentloaded", timeout=30_000)
            if response is None or response.status >= 500:
                fail(f"Online-Annahme-Webansicht returned {response.status if response else 'no response'}")
            if page.locator('input[name="postal_code"]').count() != 1:
                fail("Online-Annahme fehlt PLZ-Verifizierung")
            page.fill('input[name="postal_code"]', "60313")
            page.click('button[type="submit"]')
            page.wait_for_load_state("domcontentloaded")
            if page.locator('[data-online-quote-acceptance]').count() != 1:
                fail("Online-Annahme zeigt nach PLZ-Verifizierung nicht den verbindlichen Annahmebereich")
            if page.locator('input[name="identity_confirmed"]').count() != 1:
                fail("Privatkunden-Annahme fehlt Identitätsbestätigung")
            accept_button = page.locator('button[name="decision"][value="accept"]')
            if accept_button.count() != 1 or "Zahlungspflichtig bestellen" not in accept_button.inner_text():
                fail("Online-Annahme fehlt der verbindliche Bestellbutton")
            page.locator('input[name="identity_confirmed"]').check()
            for legal_name in ("terms_accepted", "withdrawal_accepted"):
                legal_box = page.locator(f'input[name="{legal_name}"]')
                if legal_box.count() == 1:
                    legal_box.check()
            accept_button.click()
            page.wait_for_load_state("domcontentloaded")
            if "Angebot verbindlich angenommen" not in page.locator("body").inner_text():
                fail("Online-Annahme wurde nicht verbindlich gespeichert")

            # A+BAU COMMERCIAL SETTINGS ACCESS/UI BROWSER SMOKE
            response = page.goto(urljoin(base_url, "settings/next/"), wait_until="domcontentloaded", timeout=30_000)
            if response is None or response.status != 200:
                fail(f"Commercial settings must return 200 for office role, got {response.status if response else 'no response'}")
            page.wait_for_timeout(260)
            if page.locator('[data-commercial-settings-shell]').count() != 1 or page.locator('[data-commercial-settings-nav]').count() != 1:
                fail("Commercial settings redesign shell/navigation is missing")
            if page.locator('[data-commercial-settings-tab]').count() != 5:
                fail("Commercial settings redesign must expose exactly five functional categories")
            legacy_heading = page.get_by_role("heading", name="Angebote, Rechnungen & Kommunikation", exact=True)
            for legacy_index in range(legacy_heading.count()):
                if legacy_heading.nth(legacy_index).is_visible():
                    fail("Commercial settings still shows the obsolete duplicate page heading")
            visible_cards = page.locator('section.tt-card:visible')
            if visible_cards.count() == 0 or visible_cards.count() > 4:
                fail("Commercial settings still renders as an unstructured wall of cards")
            visible_submit = page.locator('section.tt-card:visible button[type="submit"]:visible').first
            if visible_submit.count():
                metrics = visible_submit.evaluate("el=>({button:el.getBoundingClientRect().width,card:el.closest('section').getBoundingClientRect().width})")
                if metrics['button'] >= metrics['card'] * .82:
                    fail("Commercial settings still uses full-width gold save bars")

            # A+BAU COMMERCIAL SETTINGS FINANCE TAB BROWSER SMOKE
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

            # A+BAU TOOLTIME QUOTES EXACT PARITY BROWSER SMOKE
            response = page.goto(urljoin(base_url, "quotes/?amount=20&offset=0"), wait_until="domcontentloaded", timeout=30_000)
            if response is None or response.status >= 500:
                fail(f"ToolTime-Angebotsliste returned {response.status if response else 'no response'}")
            quote_page = page.locator("[data-tooltime-quotes-exact]")
            if quote_page.count() != 1:
                fail("ToolTime-Angebotslisten-Surface fehlt")
            # Use DOM text rather than rendered inner text because the exact
            # responsive ToolTime table intentionally hides lower-priority columns
            # at narrower Chromium viewports. Hidden responsive headers must still
            # exist in the semantic table contract.
            quote_header_text = quote_page.locator("thead").text_content() or ""
            for header in ("Angebotsdatum", "Nr.", "Status", "Angebotstitel", "Kunde", "Betrag", "Letzte Änderung"):
                if header not in quote_header_text:
                    fail(f"ToolTime-Angebotsspalte fehlt im DOM: {header}")
            if quote_page.locator('select[name="period"]').count() != 1:
                fail("Angebots-Zeitraumfilter fehlt")
            if quote_page.locator('select[name="status"]').count() != 1:
                fail("Angebots-Statusfilter fehlt")
            if quote_page.locator('input[name="q"][type="search"]').count() != 1:
                fail("Angebotssuche fehlt")
            if quote_page.locator('[data-last-change-sort]').count() != 1:
                fail("Sortierung nach letzter Änderung fehlt")
            if quote_page.locator('.ttq-new-menu').count() != 1:
                fail("Neues-Angebot-Dropdown fehlt")
            if quote_page.locator('[data-page-size]').input_value() != "20":
                fail("ToolTime-Standardseitengröße 20 fehlt")
            visible_rows = quote_page.locator('[data-quote-row]')
            if visible_rows.count() > 20:
                fail("Angebotsliste zeigt mehr als 20 Zeilen auf der Standardseite")
            if visible_rows.count() and quote_page.locator('.ttq-row-menu').count() != visible_rows.count():
                fail("Drei-Punkte-Menü fehlt an Angebotszeilen")

            # A+BAU TOOLTIME CATALOGUE EXACT PARITY BROWSER SMOKE
            response = page.goto(base_url.rstrip("/") + "/catalogue/", wait_until="domcontentloaded", timeout=30_000)
            if response is None or response.status != 200:
                fail(f"ToolTime catalogue parity expected 200, got {response.status if response else 'no response'}")
            if page.locator('[data-tooltime-catalogue]').count() != 1:
                fail("ToolTime catalogue shell is missing")
            if page.locator('input[aria-label="Katalog durchsuchen"]').count() != 1:
                fail("ToolTime catalogue search is missing")
            if page.locator('[data-catalogue-filters] select[name="type"]').count() != 1:
                fail("ToolTime catalogue article type filter is missing")
            headers = " ".join(page.locator('[data-catalogue-table] thead th').all_inner_texts())
            for expected_header in ("Artikelnummer", "Beschreibung", "Einheit", "Einkaufspreis", "Aufschlag", "Stückpreis", "Letzte Änderung"):
                if expected_header not in headers:
                    fail(f"ToolTime catalogue table header missing: {expected_header}")
            # A+BAU TOOLTIME INVOICES EXACT PARITY BROWSER SMOKE
            response = page.goto(base_url.rstrip("/") + "/invoices/", wait_until="domcontentloaded", timeout=30_000)
            if response is None or response.status != 200:
                fail(f"ToolTime invoices exact parity expected 200, got {response.status if response else 'no response'}")
            if page.locator('[data-tooltime-invoices-exact]').count() != 1:
                fail("ToolTime invoices exact parity shell is missing")
            if page.locator('[data-invoice-kpi]').count() != 4:
                fail("ToolTime invoices KPI strip must expose exactly four metrics")
            if page.locator('[data-invoice-filters] select[name="status"]').count() != 1:
                fail("ToolTime invoices status filter is missing")
            if page.locator('[data-invoice-filters] select[name="type"]').count() != 1:
                fail("ToolTime invoices type filter is missing")
            if page.locator('input[aria-label="Rechnungen suchen"]').count() != 1:
                fail("ToolTime invoices search is missing")
            invoice_headers = " ".join(page.locator('[data-invoice-table] thead th').all_inner_texts())
            invoice_headers_folded = invoice_headers.casefold()
            for expected_header in ("Rechnungsdatum", "Nr.", "Status", "Rechnungstitel", "Kunde", "Betrag", "Ausstehend", "Letzte Änderung"):
                if expected_header.casefold() not in invoice_headers_folded:
                    fail(f"ToolTime invoices table header missing: {expected_header}")
            context.close()
            browser.close()


def run_field_surface(base_url: str, username: str, password: str, page_errors: list[str]) -> None:
    from playwright.sync_api import sync_playwright

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context(locale="de-DE", viewport={"width": 390, "height": 844}, is_mobile=True)
        page = context.new_page()
        page.on("pageerror", lambda error: page_errors.append(f"{page.url}: {error}"))
        try:
            login(page, base_url, username, password)
            response = page.goto(base_url, wait_until="domcontentloaded", timeout=30_000)
            if response is None or response.status >= 500:
                fail("technician root is unavailable")
            if not page.url.rstrip("/").endswith("/field"):
                fail(f"technician root did not redirect to /field/: {page.url}")
            field_html = page.content()
            for marker in ("Meine Einsätze", "Geplant", "Überfällig", "Dokumentiert", "nx-field-bottom", "Vor Ort in einem Ablauf", "data-global-assistant-form"):
                if marker not in field_html:
                    fail(f"technician field surface is missing {marker!r}")
            if page.locator(".nx-mobile-tabs").count() != 1:
                fail("field home is missing ToolTime-style status tabs")
            sidebar = page.locator(".nx-sidebar")
            if sidebar.count():
                sidebar_text = sidebar.inner_text()
                if "Angebote" in sidebar_text or "Rechnungen" in sidebar_text:
                    fail("technician navigation exposes office finance modules")
            if page.locator(".nx-field-bottom a").count() != 3:
                fail("technician mobile navigation must contain exactly Termine, Zeit and Konto")
            field_text = page.locator("body").inner_text()
            field_forbidden = re.compile(r"\b(?:Cancel|Save|Create|Edit|Delete|Upload|Provider|Wizard|Voice|Settings|Customer|Quote|Invoice|AI)\b")
            match = field_forbidden.search(field_text)
            if match:
                fail(f"technician field surface still exposes English UI text {match.group(0)!r}")

            # KAYI signed field authorization browser smoke: the spontaneous-job entry
            # and short intake must remain reachable inside technician mode.
            if "Projekt aufnehmen" not in field_html:
                fail("technician field surface is missing price-free project intake")
            quick = page.locator('a[href="/field/jobs/new/"]:visible').first
            if quick.count() != 1:
                fail("technician field surface is missing a visible quick-job link")
            quick.click()
            page.wait_for_load_state("domcontentloaded")
            quick_html = page.content()
            for marker in ("Projekt aufnehmen", "Bestehender Kunde", "Neuer Kunde", "keine Preise"):
                if marker not in quick_html:
                    fail(f"quick-job flow is missing {marker!r}")
            if page.locator('button[type="submit"]:has-text("Zur Preisprüfung")').count() != 1:
                fail("project-intake flow is missing its office-review submit action")
        except Exception:
            try:
                page.screenshot(path=str(SCREENSHOT_PATH), full_page=True)
                print(f"Failure screenshot: {SCREENSHOT_PATH}", file=sys.stderr)
                print(f"Failure URL: {page.url}", file=sys.stderr)
            except Exception:
                pass
            raise
        finally:
            context.close()
            browser.close()


def main() -> None:
    base_url = (sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000").rstrip("/") + "/"
    # KAYI_STORE_PUBLIC_BROWSER_SMOKE: these URLs are used by App Store Connect,
    # Google Play Data Safety and users who no longer have the app installed.
    from playwright.sync_api import sync_playwright
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context(locale="de-DE", viewport={"width": 430, "height": 932}, is_mobile=True)
        page = context.new_page()
        try:
            for route, required in (("datenschutz/", "Datenschutzerklärung"), ("support/", "A+Bau Support"), ("konto-loeschen/", "Konto und Daten löschen")):
                response = page.goto(urljoin(base_url, route), wait_until="domcontentloaded", timeout=30_000)
                if response is None or response.status != 200 or required not in page.locator("body").inner_text():
                    fail(f"public store compliance page /{route} is unavailable or incomplete")
                if "/login/" in page.url:
                    fail(f"public store compliance page /{route} unexpectedly requires login")
        finally:
            # A+BAU PHASE 5 COMMUNICATION BROWSER SMOKE
            def phase5_open_first_communicable_document(list_path: str, detail_prefix: str):
                list_response = page.goto(urljoin(base_url, list_path), wait_until="domcontentloaded", timeout=30_000)
                if list_response is None or list_response.status >= 500:
                    fail(f"{list_path} returned {list_response.status if list_response else 'no response'}")
                hrefs = page.locator('a[href]').evaluate_all(
                    "els => els.map(el => el.getAttribute('href') || '').filter(Boolean)"
                )
                pattern = re.compile(rf"^/{re.escape(detail_prefix)}/\d+/$")
                candidates = []
                for href in hrefs:
                    clean = urlparse(urljoin(base_url, href)).path
                    if pattern.match(clean) and clean not in candidates:
                        candidates.append(clean)
                for href in candidates[:20]:
                    detail_response = page.goto(urljoin(base_url, href.lstrip("/")), wait_until="domcontentloaded", timeout=30_000)
                    if detail_response is None or detail_response.status >= 500:
                        fail(f"{href} returned {detail_response.status if detail_response else 'no response'}")
                    if page.locator('[data-document-communication]').count() == 1:
                        return href
                return None

            response = page.goto(urljoin(base_url, "quotes/new/"), wait_until="domcontentloaded", timeout=30_000)
            if response is None or response.status >= 500:
                fail(f"neues Angebot returned {response.status if response else 'no response'}")
            if page.locator('[data-document-communication]').count():
                fail("Entwurf zeigt fälschlich PDF-/Versandaktionen vor Fertigstellung")

            finalized_quote_href = phase5_open_first_communicable_document("quotes/", "quotes")
            if finalized_quote_href:
                communication = page.locator('[data-document-communication]')
                if "PDF herunterladen" not in communication.inner_text():
                    fail("fertiggestelltes Angebot hat keinen echten PDF-Download")
                open_mail = page.locator('[data-document-email-open]')
                if open_mail.count() != 1:
                    fail("fertiggestelltes Angebot hat keinen E-Mail-Versand")
                open_mail.click()
                mail_modal = page.locator('[data-document-email-modal]')
                if mail_modal.is_hidden():
                    fail("Angebots-E-Mail-Dialog öffnet nicht")
                action = mail_modal.locator("form").get_attribute("action") or ""
                expected_action = finalized_quote_href.rstrip("/") + "/send-email/"
                if urlparse(urljoin(base_url, action)).path != expected_action:
                    fail(f"Angebots-E-Mail-Dialog hat falsches Ziel: {action!r}")
                mail_modal.locator('[data-document-email-close]').click()

            finalized_invoice_href = phase5_open_first_communicable_document("invoices/", "invoices")
            if finalized_invoice_href:
                communication = page.locator('[data-document-communication]')
                if "Original-PDF herunterladen" not in communication.inner_text():
                    fail("finalisierte Rechnung verwendet nicht sichtbar das Original-PDF")
                open_mail = page.locator('[data-document-email-open]')
                if open_mail.count() != 1:
                    fail("finalisierte Rechnung hat keinen E-Mail-Versand")
                open_mail.click()
                mail_modal = page.locator('[data-document-email-modal]')
                if mail_modal.is_hidden():
                    fail("Rechnungs-E-Mail-Dialog öffnet nicht")
                action = mail_modal.locator("form").get_attribute("action") or ""
                expected_action = finalized_invoice_href.rstrip("/") + "/send-email/"
                if urlparse(urljoin(base_url, action)).path != expected_action:
                    fail(f"Rechnungs-E-Mail-Dialog hat falsches Ziel: {action!r}")
                for selector in ('input[name="recipient_email"]', 'input[name="subject"]', 'textarea[name="message"]'):
                    if mail_modal.locator(selector).count() != 1:
                        fail(f"Rechnungs-E-Mail-Feld fehlt: {selector}")
                mail_modal.locator('[data-document-email-close]').click()

            # A+BAU PHASE 7 E2E FLOW BROWSER SMOKE
            response = page.goto(urljoin(base_url, "quotes/"), wait_until="domcontentloaded", timeout=30_000)
            if response is None or response.status >= 500:
                fail(f"Phase-7-Angebotsliste returned {response.status if response else 'no response'}")
            hrefs = page.locator('a[href]').evaluate_all("els => els.map(el => el.getAttribute('href') || '').filter(Boolean)")
            quote_paths = []
            for href in hrefs:
                candidate = urlparse(urljoin(base_url, href)).path
                if re.match(r"^/quotes/\d+/$", candidate) and candidate not in quote_paths:
                    quote_paths.append(candidate)
            for quote_path in quote_paths[:20]:
                detail_response = page.goto(urljoin(base_url, quote_path.lstrip('/')), wait_until="domcontentloaded", timeout=30_000)
                if detail_response is None or detail_response.status >= 500:
                    fail(f"{quote_path} returned {detail_response.status if detail_response else 'no response'}")
                statusbar = page.locator('.tt-quote-statusbar')
                if statusbar.count() != 1:
                    continue
                if page.locator('[data-phase7-flow]').count() != 1:
                    fail("Finalisiertes Angebot zeigt keinen Ende-zu-Ende-Auftragsablauf")
                if "Angenommen" in statusbar.inner_text() and page.locator('[data-phase7-order-confirmation]').count() != 1:
                    fail("Angenommenes Angebot bietet keine Auftragsbestätigung an")
                break

            # A+BAU COMMERCIAL SETTINGS FIELD DENIAL BROWSER SMOKE
            # A+BAU FIELD AUTHENTICATED SESSION SETUP
            import os as _field_os
            import secrets as _field_secrets
            from django.contrib.auth import get_user_model as _field_get_user_model

            # Playwright's synchronous facade runs over an event loop. Django
            # therefore blocks synchronous ORM calls inside this smoke context by
            # default. This flag exists only in the isolated smoke-test process;
            # the application server/runtime remains unchanged.
            _field_os.environ["DJANGO_ALLOW_ASYNC_UNSAFE"] = "true"
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
                # A+BAU FIELD TOPBAR LOGOUT BROWSER SMOKE
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
                # A+BAU FIELD PROFILE REAL HIT-TEST
                if page.locator('script[data-field-profile-runtime]').count() != 1:
                    fail("Dedicated field profile runtime asset is missing")
                if page.locator('html').get_attribute("data-field-profile-runtime") != "1":
                    fail("Dedicated field profile runtime did not execute")
                profile_box = profile_toggle.bounding_box()
                if not profile_box:
                    fail("Technician profile control has no mobile hit box")
                profile_x = profile_box["x"] + profile_box["width"] / 2
                profile_y = profile_box["y"] + profile_box["height"] / 2
                profile_is_hit_target = page.evaluate(
                    "([x,y]) => { const el=document.elementFromPoint(x,y); return !!el && !!el.closest('[data-profile-toggle]'); }",
                    [profile_x, profile_y],
                )
                if not profile_is_hit_target:
                    fail("Technician profile control is covered by another mobile element")
                # Use the physical screen coordinate rather than locator.click(), so
                # overlays/pointer interception are caught like on a real phone.
                page.mouse.click(profile_x, profile_y)
                page.wait_for_timeout(100)
                profile_menu = page.locator('[data-profile-menu]')
                profile_root = page.locator('[data-profile]')
                if profile_root.get_attribute("data-profile-runtime-open") != "1":
                    fail("Dedicated field profile runtime did not receive the mobile click")
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

            # A+BAU TOOLTIME APPOINTMENT PROCESS BROWSER SMOKE
            from erp.models import Organization, UserProfile
            smoke_org = Organization.objects.filter(settings__is_demo=True).order_by("pk").first() or Organization.objects.order_by("pk").first()
            if smoke_org is None:
                fail("appointment parity smoke could not resolve an organization")
            smoke_username = f"appointment-office-smoke-{secrets.token_hex(5)}"
            smoke_password = secrets.token_urlsafe(24)
            SmokeUser = get_user_model()
            smoke_office_user = SmokeUser.objects.create_user(
                username=smoke_username,
                password=smoke_password,
                email=f"{smoke_username}@example.invalid",
            )
            smoke_profile, _ = UserProfile.objects.get_or_create(user=smoke_office_user)
            smoke_profile.organization = smoke_org
            smoke_profile.role = UserProfile.Role.OFFICE
            smoke_profile.is_mobile_worker = False
            smoke_profile.save()
            office_context = None
            try:
                office_context = browser.new_context(locale="de-DE", viewport={"width": 1440, "height": 1000})
                office_page = office_context.new_page()
                login_response = office_page.goto(urljoin(base_url, "login/"), wait_until="domcontentloaded", timeout=30_000)
                if login_response is None or login_response.status >= 500:
                    fail(f"appointment parity office login returned {login_response.status if login_response else 'no response'}")
                office_page.fill('input[name="username"]', smoke_username)
                office_page.fill('input[name="password"]', smoke_password)
                with office_page.expect_navigation(wait_until="domcontentloaded", timeout=30_000):
                    office_page.click('button[type="submit"], button.btn-primary')
                if "/login/" in office_page.url:
                    fail("appointment parity office login did not establish a session")
                response = office_page.goto(urljoin(base_url, "appointments/new/"), wait_until="domcontentloaded", timeout=30_000)
                if response is None or response.status >= 500:
                    fail(f"appointment parity create returned {response.status if response else 'no response'}")
                if "/login/" in office_page.url:
                    fail("appointment parity office smoke unexpectedly redirected to login")
                body = office_page.locator("body").inner_text()
                for label in ("Terminname", "Mitarbeiter hinzufügen", "Leistungsgruppe hinzufügen", "Arbeitsbericht"):
                    if label not in body:
                        fail(f"appointment parity is missing {label!r}")
                if office_page.locator('[data-service-editor]').count() != 1:
                    fail("appointment service editor is missing")
                office_page.click('[data-add-service-group]')
                if office_page.locator('[data-add-service-row]').count() < 1:
                    fail("appointment service group did not expose Position hinzufügen")
                if office_page.locator('[data-service-row]').count() < 1:
                    fail("appointment service group did not create an initial position row")
            finally:
                if office_context is not None:
                    office_context.close()
                smoke_office_user.delete()
            context.close()
            browser.close()
    username = os.environ.get("KAYI_SMOKE_USER", "demo")
    User = get_user_model()
    user = User.objects.select_related("profile").filter(username=username).first()
    if user is None:
        fail(f"smoke user {username!r} does not exist")
    profile = getattr(user, "profile", None)
    if profile is None:
        fail(f"smoke user {username!r} has no KAYI profile")

    # A+BAU TOOLTIME PHASE 8 ONLINE ACCEPTANCE FIXTURE
    from django.urls import reverse as phase8_reverse
    from django.utils import timezone as phase8_timezone
    from erp import models as phase8_models
    from erp.services.tooltime_parity_finance import finalize_quote as phase8_finalize_quote

    phase8_org_id = getattr(getattr(user, "profile", None), "organization_id", None)
    phase8_quote = (
        phase8_models.Quote.objects.filter(organization_id=phase8_org_id, project__isnull=False)
        .select_related("project__customer")
        .order_by("-pk")
        .first()
    )
    if phase8_quote is None:
        fail("Online-Annahme-Smoke benötigt mindestens ein Demo-Angebot")
    phase8_customer = phase8_quote.project.customer
    phase8_customer.postal_code = "60313"
    phase8_customer.type = "private"
    phase8_customer.save(update_fields=["postal_code", "type", "updated_at"])
    phase8_meta = phase8_finalize_quote(phase8_quote)
    phase8_quote.status = "sent"
    phase8_quote.save(update_fields=["status", "updated_at"])
    phase8_meta.web_view_enabled = True
    phase8_meta.accepted_at = None
    phase8_meta.rejected_at = None
    phase8_meta.withdrawn_at = None
    phase8_meta.acceptance_details = {}
    phase8_meta.finalized_at = phase8_meta.finalized_at or phase8_timezone.now()
    phase8_meta.save(update_fields=["web_view_enabled", "accepted_at", "rejected_at", "withdrawn_at", "acceptance_details", "finalized_at", "updated_at"])
    os.environ["KAYI_PHASE8_PUBLIC_PATH"] = phase8_reverse("next-public-quote", args=[phase8_meta.web_token])

    old_password_hash = user.password
    old_role = profile.role
    old_mobile_worker = profile.is_mobile_worker
    temporary_password = secrets.token_urlsafe(24)
    user.set_password(temporary_password)
    user.save(update_fields=["password"])
    page_errors: list[str] = []

    try:
        profile.role = UserProfile.Role.OFFICE
        profile.is_mobile_worker = False
        profile.save(update_fields=["role", "is_mobile_worker", "updated_at"])
        run_office_surface(base_url, username, temporary_password, page_errors)

        # Role transition occurs outside Playwright's greenlet/async-aware
        # execution context so Django ORM stays fully synchronous.
        profile.role = UserProfile.Role.TECHNICIAN
        profile.is_mobile_worker = True
        profile.save(update_fields=["role", "is_mobile_worker", "updated_at"])
        run_field_surface(base_url, username, temporary_password, page_errors)

        if page_errors:
            fail("browser page errors: " + " | ".join(page_errors[:8]))
    finally:
        user.password = old_password_hash
        user.save(update_fields=["password"])
        profile.role = old_role
        profile.is_mobile_worker = old_mobile_worker
        profile.save(update_fields=["role", "is_mobile_worker", "updated_at"])

    print("A+Bau Browser-Smoke bestanden: Büro, Projekte, Termine, Außendienst sowie ToolTime-paritäre Angebote, Rechnungen, Artikelsuche und Einstellungen.")


if __name__ == "__main__":
    main()
