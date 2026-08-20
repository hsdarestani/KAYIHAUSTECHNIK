from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
path = ROOT / "scripts" / "production_browser_smoke.py"
text = path.read_text(encoding="utf-8")
MARKER = "TOOLTIME_PHASE2_SETTINGS_BROWSER_20260820"

if MARKER not in text:
    anchor = '''            for selector in ('input[name="logo_file"]', 'input[name="tax_number"]', 'input[name="invoice_prefix"]', 'textarea[name="invoice_body"]'):
                if page.locator(selector).count() != 1:
                    fail(f"Kaufmännische Einstellung {selector!r} fehlt")
'''
    extra = anchor + '''

            # TOOLTIME_PHASE2_SETTINGS_BROWSER_20260820
            # Nummernkreise: Vorschau muss live aus Präfix + numerischem Startwert
            # reagieren; sie ist kein statischer Hilfetext.
            if page.locator('[data-phase2-numbering]').count() != 1:
                fail("ToolTime Nummernkreise fehlen")
            quote_prefix = page.locator('[data-phase2-numbering] input[name="quote_prefix"]')
            quote_start = page.locator('[data-phase2-numbering] input[name="quote_start"]')
            quote_preview = page.locator('[data-number-preview="quote"]')
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
'''
    if anchor not in text:
        raise RuntimeError("Phase 2 Browser-Smoke-Anker wurde nicht gefunden")
    text = text.replace(anchor, extra, 1)

path.write_text(text, encoding="utf-8")
compile(text, str(path), "exec")
print("ToolTime Phase 2 Browser-Smoke installiert: Nummern, DATEV, Rechtsanhänge, Zahlungsziele und Steuern werden interaktiv geprüft.")
