from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(rel: str) -> str:
    path = ROOT / rel
    if not path.exists():
        raise RuntimeError(f"Phase 8 target missing: {rel}")
    return path.read_text(encoding="utf-8")


def write(rel: str, text: str) -> None:
    path = ROOT / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def patch_models_and_migration() -> None:
    rel = "erp/tooltime_parity_finance.py"
    text = read(rel)
    anchor = "    default_attachment_ids = models.JSONField(default=list, blank=True)\n"
    fields = anchor + "    acceptance_details = models.JSONField(default=dict, blank=True)\n    withdrawn_at = models.DateTimeField(null=True, blank=True)\n"
    if "acceptance_details = models.JSONField" not in text:
        if anchor not in text:
            raise RuntimeError("Phase 8 acceptance model anchor missing")
        text = text.replace(anchor, fields, 1)
        write(rel, text)

    write("erp/migrations/0019_tooltime_online_acceptance.py", r'''from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("erp", "0018_tooltime_pay")]
    operations = [
        migrations.AddField(
            model_name="tooltimedocumentmeta",
            name="acceptance_details",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name="tooltimedocumentmeta",
            name="withdrawn_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
''')


def patch_views() -> None:
    rel = "erp/tooltime_parity_views.py"
    text = read(rel)

    if "from django.conf import settings\n" not in text:
        text = text.replace("from django.contrib import messages\n", "from django.conf import settings\nfrom django.contrib import messages\n", 1)
    if "from django.core.mail import EmailMessage\n" not in text:
        text = text.replace("from django.core.files.base import ContentFile\n", "from django.core.files.base import ContentFile\nfrom django.core.mail import EmailMessage\n", 1)
    if "from datetime import timedelta\n" not in text:
        text = text.replace("from decimal import Decimal\n", "from decimal import Decimal\nfrom datetime import timedelta\n", 1)

    match = re.search(r"from \.services\.tooltime_parity_finance import ([^\n]+)", text)
    if not match:
        raise RuntimeError("Phase 8 finance service import missing")
    names = [name.strip() for name in match.group(1).split(",") if name.strip()]
    if "phase2_settings" not in names:
        names.append("phase2_settings")
        replacement = "from .services.tooltime_parity_finance import " + ", ".join(names)
        text = text[:match.start()] + replacement + text[match.end():]

    old_guard = '        if existing.status == "accepted" and meta and meta.finalized_at:\n'
    new_guard = '        if meta and meta.finalized_at and (existing.status == "accepted" or meta.accepted_at):\n'
    if new_guard not in text:
        if old_guard not in text:
            raise RuntimeError("Phase 8 immutable accepted-offer guard missing")
        text = text.replace(old_guard, new_guard, 1)

    helper_marker = '@require_http_methods(["GET", "POST"])\ndef public_quote(request, token):\n'
    helpers = r'''def _phase8_productive_mail_ready():
    backend = str(getattr(settings, "EMAIL_BACKEND", "") or "").lower()
    if not backend or any(part in backend for part in ("console", "locmem", "dummy", "filebased")):
        return False
    sender = str(getattr(settings, "DEFAULT_FROM_EMAIL", "") or getattr(settings, "EMAIL_HOST_USER", "") or "").strip()
    return bool(sender)


def _phase8_send_quote_notice(org, quote, customer, public_url, event):
    result = {"backend_ready": False, "customer_sent": False, "company_sent": False}
    if not _phase8_productive_mail_ready():
        return result
    result["backend_ready"] = True
    cfg = phase2_settings(org).get("web_view", {})
    sender = str(getattr(settings, "DEFAULT_FROM_EMAIL", "") or getattr(settings, "EMAIL_HOST_USER", "") or "").strip()
    accepted = event == "accepted"
    heading = "Angebot angenommen" if accepted else "Widerruf der Angebotsannahme"
    customer_subject = f"Bestätigung: {heading.lower()} · {quote.number}"
    company_subject = f"{heading}: {quote.number} · {customer.display_name}"
    customer_body = (
        f"Guten Tag,\n\nwir bestätigen die Annahme des Angebots {quote.number}.\n\n{public_url}\n\nMit freundlichen Grüßen\n{org.name}"
        if accepted
        else f"Guten Tag,\n\nwir bestätigen den Widerruf der Online-Annahme des Angebots {quote.number}.\n\n{public_url}\n\nMit freundlichen Grüßen\n{org.name}"
    )
    company_body = f"{heading}\n\nAngebot: {quote.number}\nKunde: {customer.display_name}\nWebansicht: {public_url}"

    customer_email = str(getattr(customer, "email", "") or "").strip()
    if customer_email:
        try:
            result["customer_sent"] = EmailMessage(customer_subject, customer_body, sender, [customer_email]).send(fail_silently=False) == 1
        except Exception:
            result["customer_sent"] = False

    company_email = str(getattr(org, "email", "") or "").strip()
    if company_email and bool(cfg.get("acceptance_email", True)):
        try:
            result["company_sent"] = EmailMessage(company_subject, company_body, sender, [company_email]).send(fail_silently=False) == 1
        except Exception:
            result["company_sent"] = False
    return result


'''
    if "def _phase8_productive_mail_ready():" not in text:
        pos = text.find(helper_marker)
        if pos < 0:
            raise RuntimeError("Phase 8 public quote helper anchor missing")
        text = text[:pos] + helpers + text[pos:]

    pattern = re.compile(
        r'@require_http_methods\(\["GET", "POST"\]\)\ndef public_quote\(request, token\):\n.*?^    return render\(request, "rebuild/public_quote\.html", \{"quote": quote, "meta": meta, "verified": verified, "totals": base\._quote_total\(quote\) if verified else None\}\)\n',
        re.S | re.M,
    )
    replacement = r'''@require_http_methods(["GET", "POST"])
def public_quote(request, token):
    meta = get_object_or_404(m.ToolTimeDocumentMeta.objects.select_related("quote__project__customer"), web_token=token, quote__isnull=False)
    quote = meta.quote
    if not meta.web_view_enabled or not meta.finalized_at:
        return render(request, "rebuild/public_quote.html", {"unavailable": True}, status=404)

    customer = quote.project.customer
    cfg = phase2_settings(quote.organization)
    legal_cfg = cfg.get("legal_documents", {}) if isinstance(cfg, dict) else {}

    def legal_document(key):
        raw = legal_cfg.get(key)
        try:
            document_id = int(raw)
        except (TypeError, ValueError):
            return None
        return m.Document.objects.filter(organization=quote.organization, pk=document_id).first()

    terms_document = legal_document("terms_document_id")
    withdrawal_document = legal_document("withdrawal_document_id")
    is_private = str(getattr(customer, "type", "") or "") == "private"
    customer_name = customer.display_name
    verified = request.session.get(f"quote_verified_{meta.pk}") is True

    if request.method == "POST" and not verified:
        postal = (request.POST.get("postal_code") or "").strip().replace(" ", "")
        expected = (getattr(customer, "postal_code", "") or "").strip().replace(" ", "")
        if expected and postal == expected:
            request.session[f"quote_verified_{meta.pk}"] = True
            verified = True
        else:
            messages.error(request, "Die Postleitzahl ist nicht korrekt.")

    withdraw_deadline = meta.accepted_at + timedelta(days=14) if meta.accepted_at else None
    can_withdraw = bool(
        verified
        and is_private
        and meta.accepted_at
        and not meta.withdrawn_at
        and withdrawal_document is not None
        and withdraw_deadline
        and timezone.now() <= withdraw_deadline
    )

    if request.method == "POST" and verified:
        decision = (request.POST.get("decision") or "").strip()
        already_decided = bool(meta.accepted_at or meta.rejected_at or meta.withdrawn_at)

        if decision == "accept":
            if already_decided:
                messages.error(request, "Für dieses Angebot wurde bereits eine verbindliche Entscheidung gespeichert.")
            else:
                signer_name = (request.POST.get("signer_name") or "").strip()[:240]
                identity_ok = request.POST.get("identity_confirmed") == "on" if is_private else bool(signer_name)
                terms_ok = terms_document is None or request.POST.get("terms_accepted") == "on"
                withdrawal_ok = withdrawal_document is None or request.POST.get("withdrawal_accepted") == "on"
                if not identity_ok:
                    messages.error(request, "Bitte bestätigen Sie zuerst Ihre Identität.")
                elif not terms_ok:
                    messages.error(request, "Bitte bestätigen Sie, dass Sie die AGB gelesen und akzeptiert haben.")
                elif not withdrawal_ok:
                    messages.error(request, "Bitte bestätigen Sie, dass Sie die Widerrufsbelehrung gelesen haben.")
                else:
                    now = timezone.now()
                    identity_name = customer_name if is_private else signer_name
                    quote.status = "accepted"
                    meta.accepted_at = now
                    meta.rejected_at = None
                    meta.withdrawn_at = None
                    details = {
                        "decision": "accepted",
                        "accepted_at": now.isoformat(),
                        "identity_mode": "customer_checkbox" if is_private else "signer_name",
                        "identity_name": identity_name,
                        "postal_code_verified": True,
                        "terms_document_id": terms_document.pk if terms_document else None,
                        "terms_accepted": bool(terms_document),
                        "withdrawal_document_id": withdrawal_document.pk if withdrawal_document else None,
                        "withdrawal_notice_confirmed": bool(withdrawal_document),
                        "user_agent": str(request.headers.get("User-Agent") or "")[:500],
                    }
                    public_url = request.build_absolute_uri(request.path)
                    details["notifications"] = _phase8_send_quote_notice(quote.organization, quote, customer, public_url, "accepted")
                    meta.acceptance_details = details
                    quote.save(update_fields=["status", "updated_at"])
                    meta.save(update_fields=["accepted_at", "rejected_at", "withdrawn_at", "acceptance_details", "updated_at"])
                    messages.success(request, "Vielen Dank. Ihre verbindliche Angebotsannahme wurde gespeichert.")

        elif decision == "reject":
            if already_decided:
                messages.error(request, "Für dieses Angebot wurde bereits eine verbindliche Entscheidung gespeichert.")
            else:
                now = timezone.now()
                quote.status = "rejected"
                meta.rejected_at = now
                meta.acceptance_details = {"decision": "rejected", "rejected_at": now.isoformat(), "postal_code_verified": True}
                quote.save(update_fields=["status", "updated_at"])
                meta.save(update_fields=["rejected_at", "acceptance_details", "updated_at"])
                messages.success(request, "Das Angebot wurde abgelehnt.")

        elif decision == "withdraw":
            if not can_withdraw:
                messages.error(request, "Ein digitaler Widerruf ist für dieses Angebot aktuell nicht verfügbar.")
            else:
                now = timezone.now()
                quote.status = "rejected"
                meta.withdrawn_at = now
                meta.rejected_at = now
                details = dict(meta.acceptance_details or {})
                details["withdrawn_at"] = now.isoformat()
                details["withdrawal_document_id"] = withdrawal_document.pk
                details["withdrawal_notification"] = _phase8_send_quote_notice(quote.organization, quote, customer, request.build_absolute_uri(request.path), "withdrawn")
                meta.acceptance_details = details
                quote.save(update_fields=["status", "updated_at"])
                meta.save(update_fields=["withdrawn_at", "rejected_at", "acceptance_details", "updated_at"])
                messages.success(request, "Der Widerruf Ihrer Online-Annahme wurde gespeichert.")

        withdraw_deadline = meta.accepted_at + timedelta(days=14) if meta.accepted_at else None
        can_withdraw = bool(
            is_private
            and meta.accepted_at
            and not meta.withdrawn_at
            and withdrawal_document is not None
            and withdraw_deadline
            and timezone.now() <= withdraw_deadline
        )

    return render(request, "rebuild/public_quote.html", {
        "quote": quote,
        "meta": meta,
        "verified": verified,
        "totals": base._quote_total(quote) if verified else None,
        "customer_name": customer_name,
        "is_private": is_private,
        "terms_document": terms_document,
        "withdrawal_document": withdrawal_document,
        "withdraw_deadline": withdraw_deadline,
        "can_withdraw": can_withdraw,
    })
'''
    text, count = pattern.subn(replacement, text, count=1)
    if count != 1:
        raise RuntimeError("Phase 8 public quote function replacement failed")
    write(rel, text)


def patch_public_template() -> None:
    write("templates/rebuild/public_quote.html", r'''<!doctype html>
<html lang="de">
<head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Angebot · A+Bau</title>
<style>
body{font-family:Arial,sans-serif;background:#f5f7fa;color:#1c2734;margin:0}.wrap{max-width:900px;margin:40px auto;padding:20px}.card{background:#fff;border:1px solid #e5e9ef;border-radius:14px;padding:28px;margin-bottom:16px}.row{display:flex;justify-content:space-between;gap:20px;padding:10px 0;border-bottom:1px solid #eef1f4}.btn{border:0;border-radius:8px;padding:12px 18px;cursor:pointer;font-weight:700}.primary{background:#1268e8;color:white}.danger{background:#f2f4f7;color:#273444}.success{background:#edf9f1;border-color:#c8ead4}.warning{background:#fff8e8;border-color:#f0dda7}input[type=text],input[inputmode]{padding:12px;border:1px solid #ccd3dc;border-radius:8px;width:100%;box-sizing:border-box}.check{display:flex;align-items:flex-start;gap:10px;margin:14px 0}.check input{margin-top:3px}.legal{display:grid;gap:10px;margin:18px 0;padding:16px;border:1px solid #e5e9ef;border-radius:10px}.actions{display:flex;gap:10px;flex-wrap:wrap;margin-top:18px}a{color:#0b63ce}@media(max-width:640px){.wrap{margin:12px auto;padding:12px}.card{padding:20px}.row{flex-direction:column;gap:5px}}
</style>
</head>
<body><div class="wrap">
{% if unavailable %}
<div class="card"><h1>Diese Webansicht ist nicht verfügbar.</h1></div>
{% elif not verified %}
<div class="card"><h1>Angebot geschützt</h1><p>Bitte geben Sie zur Identitätsprüfung Ihre Postleitzahl ein.</p><form method="post">{% csrf_token %}<input name="postal_code" inputmode="numeric" autocomplete="postal-code" required><button class="btn primary" type="submit" style="margin-top:12px">Angebot öffnen</button></form></div>
{% else %}
<div class="card"><h1>{{ meta.document_title|default:'Angebot' }} {{ quote.number }}</h1><p>{{ meta.salutation }}</p><p>{{ quote.intro_text }}</p></div>
<div class="card">{% for item in quote.items.all %}<div class="row"><span>{{ item.position }} · {{ item.description }}<br><small>{{ item.quantity }} {{ item.unit }}</small>{% if item.tooltime_asset %}<br><img src="{{ item.tooltime_asset.document.file.url }}" alt="Produktbild zu {{ item.description }}" style="max-width:160px;max-height:120px;margin-top:8px;border-radius:8px">{% endif %}</span><strong>{{ item.unit_price|floatformat:2 }} €</strong></div>{% endfor %}<div class="row"><strong>Gesamtbetrag</strong><strong>{{ totals.gross|floatformat:2 }} €</strong></div></div>

{% if meta.withdrawn_at %}
<div class="card warning"><h2>Online-Annahme widerrufen</h2><p>Der Widerruf wurde am {{ meta.withdrawn_at|date:'d.m.Y H:i' }} gespeichert. Das Angebot gilt in der Webansicht als abgelehnt.</p></div>
{% elif meta.accepted_at %}
<div class="card success"><h2>Angebot verbindlich angenommen</h2><p>Die Annahme wurde am {{ meta.accepted_at|date:'d.m.Y H:i' }} gespeichert{% if meta.acceptance_details.identity_name %} · bestätigt durch {{ meta.acceptance_details.identity_name }}{% endif %}.</p>{% if can_withdraw %}<div class="legal"><strong>Widerruf für Privatkunden</strong><span>Die Online-Annahme kann bis {{ withdraw_deadline|date:'d.m.Y H:i' }} über diese Webansicht widerrufen werden.</span>{% if withdrawal_document %}<a href="{{ withdrawal_document.file.url }}" target="_blank" rel="noopener">Widerrufsbelehrung öffnen</a>{% endif %}</div><form method="post">{% csrf_token %}<button class="btn danger" name="decision" value="withdraw" type="submit">Annahme widerrufen</button></form>{% endif %}</div>
{% elif meta.rejected_at %}
<div class="card"><h2>Angebot abgelehnt</h2><p>Die Entscheidung wurde am {{ meta.rejected_at|date:'d.m.Y H:i' }} gespeichert.</p></div>
{% else %}
<div class="card" data-online-quote-acceptance><h2>Angebot online annehmen</h2><p>Bitte bestätigen Sie Ihre Identität und – sofern hinterlegt – die rechtlichen Dokumente.</p>
<form method="post">{% csrf_token %}
{% if is_private %}<label class="check"><input type="checkbox" name="identity_confirmed" required><span>Ich bestätige, dass ich <strong>{{ customer_name }}</strong> bin bzw. für diesen Namen handele.</span></label>{% else %}<label>Name der annehmenden Person<input type="text" name="signer_name" autocomplete="name" required></label>{% endif %}
{% if terms_document or withdrawal_document %}<div class="legal">{% if terms_document %}<a href="{{ terms_document.file.url }}" target="_blank" rel="noopener">AGB öffnen</a><label class="check"><input type="checkbox" name="terms_accepted" required><span>Ich habe die AGB gelesen und akzeptiere sie.</span></label>{% endif %}{% if withdrawal_document %}<a href="{{ withdrawal_document.file.url }}" target="_blank" rel="noopener">Widerrufsbelehrung öffnen</a><label class="check"><input type="checkbox" name="withdrawal_accepted" required><span>Ich habe die Widerrufsbelehrung gelesen.</span></label>{% endif %}</div>{% endif %}
<div class="actions"><button class="btn primary" name="decision" value="accept" type="submit">Zahlungspflichtig bestellen</button><button class="btn danger" name="decision" value="reject" type="submit" formnovalidate>Angebot ablehnen</button></div>
</form></div>
{% endif %}
{% endif %}
</div></body></html>''')


def patch_browser_smoke() -> None:
    rel = "scripts/production_browser_smoke.py"
    text = read(rel)
    marker = "            # A+BAU TOOLTIME PAY BROWSER SMOKE\n"
    phase8_marker = "            # A+BAU TOOLTIME PHASE 8 ONLINE ACCEPTANCE\n"
    if phase8_marker not in text:
        marker_pos = text.find(marker)
        if marker_pos < 0:
            raise RuntimeError("Phase 8 could not find Pay office smoke marker")
        block_end = text.find("            context.close()\n", marker_pos)
        if block_end < 0:
            raise RuntimeError("Phase 8 could not find office smoke context end")
        block = r'''            # A+BAU TOOLTIME PHASE 8 ONLINE ACCEPTANCE
            from django.urls import reverse as phase8_reverse
            from django.utils import timezone as phase8_timezone
            from erp import models as phase8_models
            from erp.services.tooltime_parity_finance import finalize_quote as phase8_finalize_quote, meta_for as phase8_meta_for

            phase8_user = get_user_model().objects.select_related("profile").filter(username=username).first()
            phase8_org_id = getattr(getattr(phase8_user, "profile", None), "organization_id", None)
            phase8_quote = phase8_models.Quote.objects.filter(organization_id=phase8_org_id, project__isnull=False).select_related("project__customer").order_by("-pk").first()
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

            phase8_path = phase8_reverse("next-public-quote", args=[phase8_meta.web_token])
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

'''
        text = text[:block_end] + block + text[block_end:]
        write(rel, text)
    compile(text, str(ROOT / rel), "exec")


def install_contract_tests() -> None:
    write("tests/test_tooltime_phase8_online_acceptance_contract.py", r'''from pathlib import Path
from django.test import SimpleTestCase

ROOT = Path(__file__).resolve().parents[1]


class ToolTimePhase8OnlineAcceptanceContractTests(SimpleTestCase):
    def test_acceptance_is_persisted_and_migrated(self):
        models = (ROOT / "erp/tooltime_parity_finance.py").read_text(encoding="utf-8")
        migration = (ROOT / "erp/migrations/0019_tooltime_online_acceptance.py").read_text(encoding="utf-8")
        self.assertIn("acceptance_details = models.JSONField", models)
        self.assertIn("withdrawn_at = models.DateTimeField", models)
        self.assertIn('("erp", "0018_tooltime_pay")', migration)

    def test_public_acceptance_requires_identity_and_legal_consents(self):
        views = (ROOT / "erp/tooltime_parity_views.py").read_text(encoding="utf-8")
        template = (ROOT / "templates/rebuild/public_quote.html").read_text(encoding="utf-8")
        self.assertIn('request.POST.get("identity_confirmed") == "on"', views)
        self.assertIn('request.POST.get("terms_accepted") == "on"', views)
        self.assertIn('request.POST.get("withdrawal_accepted") == "on"', views)
        self.assertIn('name="signer_name"', template)
        self.assertIn("Zahlungspflichtig bestellen", template)
        self.assertIn("AGB öffnen", template)
        self.assertIn("Widerrufsbelehrung öffnen", template)

    def test_accepted_offer_stays_immutable_and_private_withdrawal_is_time_limited(self):
        views = (ROOT / "erp/tooltime_parity_views.py").read_text(encoding="utf-8")
        self.assertIn('(existing.status == "accepted" or meta.accepted_at)', views)
        self.assertIn("meta.accepted_at + timedelta(days=14)", views)
        self.assertIn('decision == "withdraw"', views)
        self.assertIn('quote.status = "rejected"', views)

    def test_notifications_never_fake_success(self):
        views = (ROOT / "erp/tooltime_parity_views.py").read_text(encoding="utf-8")
        self.assertIn("def _phase8_productive_mail_ready", views)
        self.assertIn('any(part in backend for part in ("console", "locmem", "dummy", "filebased"))', views)
        self.assertIn(".send(fail_silently=False) == 1", views)
        self.assertIn('result["customer_sent"] = False', views)
        self.assertIn('result["company_sent"] = False', views)

    def test_browser_smoke_exercises_real_public_acceptance(self):
        smoke = (ROOT / "scripts/production_browser_smoke.py").read_text(encoding="utf-8")
        self.assertIn("A+BAU TOOLTIME PHASE 8 ONLINE ACCEPTANCE", smoke)
        self.assertIn("Online-Annahme fehlt PLZ-Verifizierung", smoke)
        self.assertIn("Online-Annahme wurde nicht verbindlich gespeichert", smoke)
''')


def run() -> None:
    patch_models_and_migration()
    patch_views()
    patch_public_template()
    patch_browser_smoke()
    install_contract_tests()
    for rel in ("erp/tooltime_parity_views.py", "erp/tooltime_parity_finance.py", "scripts/production_browser_smoke.py"):
        compile(read(rel), str(ROOT / rel), "exec")
    print("ToolTime Phase 8 Online-Annahme installiert: PLZ, Identität, AGB/Widerruf, verbindliche Annahme, 14-Tage-Widerruf und echte Mail-Benachrichtigung.")


if __name__ == "__main__":
    run()
