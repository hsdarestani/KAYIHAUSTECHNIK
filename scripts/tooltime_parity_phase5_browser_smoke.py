from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REL = "scripts/production_browser_smoke.py"
path = ROOT / REL
text = path.read_text(encoding="utf-8")

# Earlier smoke layers may already extend this import. Add the required models
# semantically instead of depending on one exact historical import line.
match = re.search(r"^from erp\.models import ([^\n]+)$", text, flags=re.M)
if not match:
    raise RuntimeError("Phase 5 browser-smoke erp.models import missing")
names = [name.strip() for name in match.group(1).split(",") if name.strip()]
for required in ("Invoice", "Project", "Quote"):
    if required not in names:
        names.append(required)
replacement = "from erp.models import " + ", ".join(sorted(set(names)))
text = text[:match.start()] + replacement + text[match.end():]

# Playwright's synchronous API owns an asyncio loop internally. Django therefore
# rejects synchronous ORM calls made after entering sync_playwright() with
# SynchronousOnlyOperation. Resolve all tenant-scoped document IDs before that
# boundary and only use plain integers in the real browser assertions below.
data_marker = "# A+BAU PHASE 5 COMMUNICATION DB LOOKUP"
if data_marker not in text:
    anchor = "    old_password_hash = user.password\n"
    pos = text.find(anchor)
    if pos < 0:
        raise RuntimeError("Phase 5 browser-smoke pre-Playwright anchor missing")
    prelude = '''    # A+BAU PHASE 5 COMMUNICATION DB LOOKUP
    finalized_quote_pk = None
    finalized_invoice_pk = None
    if organization_id:
        finalized_quote_pk = (
            Quote.objects.filter(
                organization_id=organization_id,
                tooltime_meta__finalized_at__isnull=False,
            )
            .order_by("-pk")
            .values_list("pk", flat=True)
            .first()
        )
        finalized_invoice_pk = (
            Invoice.objects.filter(
                organization_id=organization_id,
                compliance__state__in=["finalized", "cancelled", "credited"],
                compliance__original_pdf_document__isnull=False,
            )
            .order_by("-pk")
            .values_list("pk", flat=True)
            .first()
        )

'''
    text = text[:pos] + prelude + text[pos:]

marker = "# A+BAU PHASE 5 COMMUNICATION BROWSER SMOKE"
if marker not in text:
    anchor = "            context.close()\n"
    pos = text.rfind(anchor)
    if pos < 0:
        raise RuntimeError("Phase 5 browser-smoke final context anchor missing")
    block = r'''            # A+BAU PHASE 5 COMMUNICATION BROWSER SMOKE
            response = page.goto(urljoin(base_url, "quotes/new/"), wait_until="domcontentloaded", timeout=30_000)
            if response is None or response.status >= 500:
                fail(f"neues Angebot returned {response.status if response else 'no response'}")
            if page.locator('[data-document-communication]').count():
                fail("Entwurf zeigt fälschlich PDF-/Versandaktionen vor Fertigstellung")

            if finalized_quote_pk:
                response = page.goto(urljoin(base_url, f"quotes/{finalized_quote_pk}/"), wait_until="domcontentloaded", timeout=30_000)
                if response is None or response.status >= 500:
                    fail(f"fertiggestelltes Angebot returned {response.status if response else 'no response'}")
                if page.locator('[data-document-communication]').count() != 1:
                    fail("fertiggestelltes Angebot hat keinen Kommunikationsbereich")
                if "PDF herunterladen" not in page.locator('[data-document-communication]').inner_text():
                    fail("fertiggestelltes Angebot hat keinen echten PDF-Download")
                open_mail = page.locator('[data-document-email-open]')
                if open_mail.count() != 1:
                    fail("fertiggestelltes Angebot hat keinen E-Mail-Versand")
                open_mail.click()
                mail_modal = page.locator('[data-document-email-modal]')
                if mail_modal.is_hidden():
                    fail("Angebots-E-Mail-Dialog öffnet nicht")
                action = mail_modal.locator("form").get_attribute("action") or ""
                if not action.endswith(f"/quotes/{finalized_quote_pk}/send-email/"):
                    fail(f"Angebots-E-Mail-Dialog hat falsches Ziel: {action!r}")
                mail_modal.locator('[data-document-email-close]').click()

            if finalized_invoice_pk:
                response = page.goto(urljoin(base_url, f"invoices/{finalized_invoice_pk}/"), wait_until="domcontentloaded", timeout=30_000)
                if response is None or response.status >= 500:
                    fail(f"finalisierte Rechnung returned {response.status if response else 'no response'}")
                communication = page.locator('[data-document-communication]')
                if communication.count() != 1:
                    fail("finalisierte Rechnung hat keinen Kommunikationsbereich")
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
                if not action.endswith(f"/invoices/{finalized_invoice_pk}/send-email/"):
                    fail(f"Rechnungs-E-Mail-Dialog hat falsches Ziel: {action!r}")
                for selector in ('input[name="recipient_email"]', 'input[name="subject"]', 'textarea[name="message"]'):
                    if mail_modal.locator(selector).count() != 1:
                        fail(f"Rechnungs-E-Mail-Feld fehlt: {selector}")
                mail_modal.locator('[data-document-email-close]').click()

'''
    text = text[:pos] + block + text[pos:]

path.write_text(text, encoding="utf-8")
compile(text, str(path), "exec")
print("ToolTime Phase 5 Browser-Smoke installiert: finalisierte PDF-/E-Mail-Kommunikation wird tenant-sicher im echten DOM geprüft.")