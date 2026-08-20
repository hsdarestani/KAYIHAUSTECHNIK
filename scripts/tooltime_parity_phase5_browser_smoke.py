from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REL = "scripts/production_browser_smoke.py"
path = ROOT / REL
text = path.read_text(encoding="utf-8")

# The smoke test must behave like a real user. Do not query Django models from
# inside Playwright's synchronous event-loop: that triggers SynchronousOnlyOperation
# and also couples a browser contract to ORM implementation details. Discover
# finalized documents through their real list/detail UI instead.
legacy_lookup = re.compile(
    r"\n    # A\+BAU PHASE 5 COMMUNICATION DB LOOKUP\n.*?(?=\n    old_password_hash = user\.password\n)",
    re.S,
)
text = legacy_lookup.sub("\n", text)

marker = "# A+BAU PHASE 5 COMMUNICATION BROWSER SMOKE"
block = r'''            # A+BAU PHASE 5 COMMUNICATION BROWSER SMOKE
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

'''

existing = re.compile(
    r"            # A\+BAU PHASE 5 COMMUNICATION BROWSER SMOKE\n.*?(?=            context\.close\(\)\n)",
    re.S,
)
if existing.search(text):
    text = existing.sub(block, text, count=1)
else:
    anchor = "            context.close()\n"
    pos = text.rfind(anchor)
    if pos < 0:
        raise RuntimeError("Phase 5 browser-smoke final context anchor missing")
    text = text[:pos] + block + text[pos:]

path.write_text(text, encoding="utf-8")
compile(text, str(path), "exec")
print("ToolTime Phase 5 Browser-Smoke installiert: PDF-/E-Mail-Kommunikation wird ohne ORM-Zugriff über die echte Dokument-UI geprüft.")