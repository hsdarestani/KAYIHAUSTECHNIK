from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REL = "scripts/production_browser_smoke.py"
path = ROOT / REL
text = path.read_text(encoding="utf-8")

marker = "# A+BAU PHASE 6 COMMUNICATION SETTINGS BROWSER SMOKE"
if marker not in text:
    anchor = "            context.close()\n"
    pos = text.rfind(anchor)
    if pos < 0:
        raise RuntimeError("Phase 6 browser-smoke final context anchor missing")
    block = r'''            # A+BAU PHASE 6 COMMUNICATION SETTINGS BROWSER SMOKE
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
                fail("SMS-Provider bietet nicht Deaktiviert und HTTPS Webhook")
            if panel.locator('[data-phase6-preview]').count() < 4:
                fail("Live-Vorschau für Angebot und Rechnung fehlt")
            page.wait_for_timeout(150)
            quote_preview = panel.locator('[data-phase6-preview="quote-subject"]').inner_text().strip()
            if not quote_preview:
                fail("Live-Vorschau des Angebotsbetreffs ist leer")

'''
    text = text[:pos] + block + text[pos:]

path.write_text(text, encoding="utf-8")
compile(text, str(path), "exec")
print("ToolTime Phase 6 Browser-Smoke installiert: Kommunikationsfelder, Live-Vorschau und SMS-160-Zeichen-Guard werden im echten DOM geprüft.")
