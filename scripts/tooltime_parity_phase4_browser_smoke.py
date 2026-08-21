from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REL = "scripts/production_browser_smoke.py"
path = ROOT / REL
text = path.read_text(encoding="utf-8")

marker = "# A+BAU PHASE 4 LIFECYCLE BROWSER SMOKE"
if marker not in text:
    # Earlier ToolTime/browser patches can move the page-error guard. The final
    # browser context close is stable and keeps this check inside the authenticated
    # Playwright session without depending on historical smoke layout.
    anchor = "            context.close()\n"
    if anchor not in text:
        raise RuntimeError("Phase 4 browser-smoke final context anchor missing")
    block = r'''            # A+BAU PHASE 4 LIFECYCLE BROWSER SMOKE
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
            for required in ("Rechnungen", "Ausstehend", "Unbezahlt", "Überfällig", "Neue Rechnung"):
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

'''
    text = text.replace(anchor, block + anchor, 1)

path.write_text(text, encoding="utf-8")
print("ToolTime Phase 4 Browser-Smoke installiert: Angebots-/Rechnungsfilter und Zahlungsdialog werden im echten DOM geprüft.")
