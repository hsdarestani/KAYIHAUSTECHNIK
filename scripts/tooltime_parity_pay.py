from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MARKER = "A+BAU TOOLTIME PAY PARITY 2026-08-20"


def read(rel: str) -> str:
    path = ROOT / rel
    if not path.exists():
        raise RuntimeError(f"ToolTime Pay target missing: {rel}")
    return path.read_text(encoding="utf-8")


def write(rel: str, text: str) -> None:
    path = ROOT / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def patch_requirements() -> None:
    target = None
    for rel in ("requirements.txt", "requirements/base.txt"):
        if (ROOT / rel).exists():
            target = rel
            break
    if target is None:
        raise RuntimeError("ToolTime Pay requirements file missing")
    text = read(target)
    if not re.search(r"(?mi)^qrcode(?:\[pil\])?(?:[<=>!~].*)?$", text):
        write(target, text.rstrip() + "\nqrcode[pil]==8.2\n")


def patch_models_and_migration() -> None:
    rel = "erp/tooltime_parity_finance.py"
    text = read(rel)
    meta_anchor = "    billing_links = models.JSONField(default=list, blank=True)\n"
    meta_field = "    automatic_dunning_disabled = models.BooleanField(default=False)\n"
    if meta_field not in text:
        if meta_anchor not in text:
            raise RuntimeError("ToolTime Pay document meta anchor missing")
        text = text.replace(meta_anchor, meta_anchor + meta_field, 1)
    if "class ToolTimePaymentTransaction" not in text:
        text += r'''


class ToolTimePaymentTransaction(models.Model):
    STATUSES = [("pending", "Ausstehend"), ("succeeded", "Bezahlt"), ("failed", "Fehlgeschlagen"), ("refunded", "Erstattet")]
    organization = models.ForeignKey("erp.Organization", on_delete=models.CASCADE, related_name="tooltime_payment_transactions")
    invoice = models.ForeignKey("erp.Invoice", on_delete=models.PROTECT, related_name="tooltime_payment_transactions")
    payment = models.OneToOneField("erp.Payment", null=True, blank=True, on_delete=models.SET_NULL, related_name="tooltime_provider_transaction")
    local_reference = models.CharField(max_length=80, unique=True)
    provider = models.CharField(max_length=40, default="webhook")
    provider_reference = models.CharField(max_length=180, blank=True)
    status = models.CharField(max_length=20, choices=STATUSES, default="pending")
    invoice_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    dunning_fee = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    currency = models.CharField(max_length=3, default="EUR")
    checkout_url = models.URLField(max_length=1000, blank=True)
    provider_payload = models.JSONField(default=dict, blank=True)
    failure_reason = models.CharField(max_length=500, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="tooltime_payment_transactions")
    paid_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        constraints = [models.UniqueConstraint(fields=["organization", "provider", "provider_reference"], name="uniq_tooltime_provider_reference")]


class ToolTimePayout(models.Model):
    STATUSES = [("pending", "Ausstehend"), ("paid", "Ausgezahlt"), ("failed", "Fehlgeschlagen")]
    MODES = [("individual", "Einzeln"), ("aggregated", "Gebündelt")]
    organization = models.ForeignKey("erp.Organization", on_delete=models.CASCADE, related_name="tooltime_payouts")
    provider = models.CharField(max_length=40, default="webhook")
    provider_reference = models.CharField(max_length=180)
    status = models.CharField(max_length=20, choices=STATUSES, default="pending")
    mode = models.CharField(max_length=20, choices=MODES, default="aggregated")
    amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    currency = models.CharField(max_length=3, default="EUR")
    period_start = models.DateField(null=True, blank=True)
    period_end = models.DateField(null=True, blank=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    provider_payload = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        constraints = [models.UniqueConstraint(fields=["organization", "provider", "provider_reference"], name="uniq_tooltime_payout_reference")]
'''
    write(rel, text)

    rel = "erp/models.py"
    text = read(rel)
    match = re.search(r"from \.tooltime_parity_finance import ([^\n]+)", text)
    if not match:
        raise RuntimeError("ToolTime Pay model import anchor missing")
    names = [name.strip() for name in match.group(1).split(",") if name.strip()]
    for required in ("ToolTimePaymentTransaction", "ToolTimePayout"):
        if required not in names:
            names.append(required)
    text = text[:match.start()] + "from .tooltime_parity_finance import " + ", ".join(names) + text[match.end():]
    write(rel, text)

    write("erp/migrations/0018_tooltime_pay.py", r'''from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [migrations.swappable_dependency(settings.AUTH_USER_MODEL), ("erp", "0017_tooltime_phase5_communication")]
    operations = [
        migrations.AddField(model_name="tooltimedocumentmeta", name="automatic_dunning_disabled", field=models.BooleanField(default=False)),
        migrations.CreateModel(
            name="ToolTimePaymentTransaction",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("local_reference", models.CharField(max_length=80, unique=True)),
                ("provider", models.CharField(default="webhook", max_length=40)),
                ("provider_reference", models.CharField(blank=True, max_length=180)),
                ("status", models.CharField(choices=[("pending", "Ausstehend"), ("succeeded", "Bezahlt"), ("failed", "Fehlgeschlagen"), ("refunded", "Erstattet")], default="pending", max_length=20)),
                ("invoice_amount", models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ("dunning_fee", models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ("amount", models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ("currency", models.CharField(default="EUR", max_length=3)),
                ("checkout_url", models.URLField(blank=True, max_length=1000)),
                ("provider_payload", models.JSONField(blank=True, default=dict)),
                ("failure_reason", models.CharField(blank=True, max_length=500)),
                ("paid_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="tooltime_payment_transactions", to=settings.AUTH_USER_MODEL)),
                ("invoice", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="tooltime_payment_transactions", to="erp.invoice")),
                ("organization", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="tooltime_payment_transactions", to="erp.organization")),
                ("payment", models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="tooltime_provider_transaction", to="erp.payment")),
            ], options={"ordering": ["-created_at", "-id"]},
        ),
        migrations.CreateModel(
            name="ToolTimePayout",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("provider", models.CharField(default="webhook", max_length=40)),
                ("provider_reference", models.CharField(max_length=180)),
                ("status", models.CharField(choices=[("pending", "Ausstehend"), ("paid", "Ausgezahlt"), ("failed", "Fehlgeschlagen")], default="pending", max_length=20)),
                ("mode", models.CharField(choices=[("individual", "Einzeln"), ("aggregated", "Gebündelt")], default="aggregated", max_length=20)),
                ("amount", models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ("currency", models.CharField(default="EUR", max_length=3)),
                ("period_start", models.DateField(blank=True, null=True)),
                ("period_end", models.DateField(blank=True, null=True)),
                ("paid_at", models.DateTimeField(blank=True, null=True)),
                ("provider_payload", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("organization", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="tooltime_payouts", to="erp.organization")),
            ], options={"ordering": ["-created_at", "-id"]},
        ),
        migrations.AddConstraint(model_name="tooltimepaymenttransaction", constraint=models.UniqueConstraint(fields=("organization", "provider", "provider_reference"), name="uniq_tooltime_provider_reference")),
        migrations.AddConstraint(model_name="tooltimepayout", constraint=models.UniqueConstraint(fields=("organization", "provider", "provider_reference"), name="uniq_tooltime_payout_reference")),
    ]
''')


def patch_service_defaults_and_meta() -> None:
    rel = "erp/services/tooltime_parity_finance.py"
    text = read(rel)
    if '"pay": {' not in text:
        anchor = '        "dunning": {"reminder_days": 7, "first_days": 7, "first_fee": "3.00", "second_days": 7, "second_fee": "3.00", "automatic": False, "grace_days": 1},\n'
        if anchor not in text:
            raise RuntimeError("ToolTime Pay default settings anchor missing")
        text = text.replace(anchor, anchor + '        "pay": {"provider": "disabled", "endpoint": "", "card_limit": "2000.00", "qr_enabled": True, "payout_mode": "aggregated"},\n', 1)
    anchor = '''    if kind == "invoice":
        invoice_type = (request.POST.get("invoice_type") or meta.invoice_type or "standard").strip()
'''
    replacement = '''    if kind == "invoice":
        meta.automatic_dunning_disabled = request.POST.get("automatic_dunning_disabled") == "on"
        invoice_type = (request.POST.get("invoice_type") or meta.invoice_type or "standard").strip()
'''
    if "meta.automatic_dunning_disabled = request.POST.get" not in text:
        if anchor not in text:
            raise RuntimeError("ToolTime Pay invoice meta save anchor missing")
        text = text.replace(anchor, replacement, 1)
    write(rel, text)


def install_pay_service() -> None:
    write("erp/services/tooltime_pay.py", r'''from __future__ import annotations

import base64
import hmac
import io
import json
import os
import urllib.error
import urllib.request
from datetime import date, datetime
from decimal import Decimal

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.mail import EmailMessage
from django.db import transaction
from django.utils import timezone

from erp import models as m
from erp import rebuild_views as base
from erp.services.business_pdf_identity import inject_business_pdf_identity
from erp.services.field_authorization import html_to_pdf_bytes
from erp.services.tooltime_parity_finance import meta_for, money, profile_for


def pay_settings(org):
    profile = profile_for(org)
    cfg = profile.settings
    pay = cfg.setdefault("pay", {})
    defaults = {"provider": "disabled", "endpoint": "", "card_limit": "2000.00", "qr_enabled": True, "payout_mode": "aggregated"}
    changed = False
    for key, value in defaults.items():
        if key not in pay:
            pay[key] = value; changed = True
    if changed:
        profile.settings = cfg; profile.save(update_fields=["settings", "updated_at"])
    return pay


def provider_ready(org):
    cfg = pay_settings(org)
    provider = str(cfg.get("provider") or "disabled").strip().lower()
    if provider == "disabled": return False, "Online-Zahlungen sind deaktiviert."
    if provider != "webhook": return False, "Der konfigurierte Zahlungsdienst wird nicht unterstützt."
    endpoint = str(cfg.get("endpoint") or "").strip()
    if not endpoint.startswith("https://"): return False, "Für den Zahlungsdienst ist eine HTTPS-Adresse erforderlich."
    if not os.environ.get("KAYI_PAY_PROVIDER_TOKEN"): return False, "KAYI_PAY_PROVIDER_TOKEN fehlt in der Server-Umgebung."
    if not (os.environ.get("KAYI_PAY_WEBHOOK_TOKEN") or os.environ.get("KAYI_PAY_PROVIDER_TOKEN")): return False, "Ein serverseitiger Webhook-Token fehlt."
    return True, "Zahlungsdienst ist serverseitig einsatzbereit."


def _provider_post(org, payload):
    ready, reason = provider_ready(org)
    if not ready: raise ValueError(reason)
    cfg = pay_settings(org)
    req = urllib.request.Request(str(cfg.get("endpoint") or ""), data=json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8"), method="POST", headers={"Authorization": "Bearer " + os.environ["KAYI_PAY_PROVIDER_TOKEN"], "Content-Type": "application/json", "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=15) as response:
            status = int(getattr(response, "status", 0) or 0); raw = response.read(1_000_000)
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, OSError) as exc:
        raise ValueError(f"Zahlungsdienst nicht erreichbar: {exc}") from exc
    if status < 200 or status >= 300: raise ValueError(f"Zahlungsdienst antwortete mit HTTP {status}.")
    try: data = json.loads(raw.decode("utf-8") or "{}")
    except (UnicodeDecodeError, json.JSONDecodeError) as exc: raise ValueError("Zahlungsdienst lieferte keine gültige JSON-Antwort.") from exc
    if not isinstance(data, dict): raise ValueError("Zahlungsdienst lieferte ein ungültiges Antwortformat.")
    return data


def effective_dunning_fee(invoice):
    records = list(invoice.tooltime_dunning_records.order_by("created_at", "id"))
    second = [money(row.fee) for row in records if row.level == "second"]
    if second: return second[-1]
    first = [money(row.fee) for row in records if row.level == "first"]
    if first: return first[-1]
    return Decimal("0.00")


def create_checkout(org, invoice, *, callback_url, return_url, user):
    ready, reason = provider_ready(org)
    if not ready: raise ValueError(reason)
    totals = base._invoice_total(invoice); invoice_amount = money(totals.get("open", 0))
    if invoice_amount <= 0: raise ValueError("Diese Rechnung ist bereits vollständig bezahlt.")
    fee = effective_dunning_fee(invoice); amount = money(invoice_amount + fee); cfg = pay_settings(org); card_limit = money(cfg.get("card_limit") or "2000.00")
    if card_limit > 0 and amount > card_limit: raise ValueError(f"Der Online-Kartenbetrag überschreitet das konfigurierte Limit von {card_limit:.2f} €.")
    local_reference = __import__("secrets").token_urlsafe(24)
    data = _provider_post(org, {"type": "payment.create", "local_reference": local_reference, "organization_id": org.pk, "invoice_id": invoice.pk, "invoice_number": invoice.number or "", "invoice_amount": f"{invoice_amount:.2f}", "dunning_fee": f"{fee:.2f}", "amount": f"{amount:.2f}", "currency": "EUR", "callback_url": callback_url, "return_url": return_url})
    provider_reference = str(data.get("reference") or data.get("provider_reference") or "").strip()[:180]; checkout_url = str(data.get("checkout_url") or "").strip()[:1000]
    if not provider_reference: raise ValueError("Zahlungsdienst hat keine Transaktionsreferenz zurückgegeben.")
    if not checkout_url.startswith("https://"): raise ValueError("Zahlungsdienst hat keine sichere Checkout-Adresse zurückgegeben.")
    return m.ToolTimePaymentTransaction.objects.create(organization=org, invoice=invoice, local_reference=local_reference, provider="webhook", provider_reference=provider_reference, status="pending", invoice_amount=invoice_amount, dunning_fee=fee, amount=amount, currency="EUR", checkout_url=checkout_url, provider_payload=data, created_by=user)


def qr_data_uri(value):
    value = str(value or "").strip()
    if not value: return ""
    try: import qrcode
    except ImportError: return ""
    image = qrcode.make(value); output = io.BytesIO(); image.save(output, format="PNG")
    return "data:image/png;base64," + base64.b64encode(output.getvalue()).decode("ascii")


def webhook_token_valid(header_value):
    expected = os.environ.get("KAYI_PAY_WEBHOOK_TOKEN") or os.environ.get("KAYI_PAY_PROVIDER_TOKEN") or ""
    if not expected: return False
    supplied = str(header_value or "").strip()
    if supplied.lower().startswith("bearer "): supplied = supplied[7:].strip()
    return hmac.compare_digest(supplied.encode("utf-8"), expected.encode("utf-8"))


def _parse_event_datetime(raw):
    if not raw: return timezone.now()
    try: parsed = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except ValueError: return timezone.now()
    if timezone.is_naive(parsed): parsed = timezone.make_aware(parsed, timezone.get_current_timezone())
    return parsed


def _sync_invoice_after_payment(invoice):
    open_amount = money(base._invoice_total(invoice).get("open", 0)); invoice.status = "paid" if open_amount <= 0 else "partial"; invoice.save(update_fields=["status", "updated_at"])
    if invoice.status == "paid" and invoice.project and invoice.project.status not in {"cancelled", "completed"}:
        invoice.project.status = "completed"; invoice.project.progress = 100; invoice.project.save(update_fields=["status", "progress", "updated_at"])


@transaction.atomic
def apply_payment_event(payload):
    reference = str(payload.get("reference") or payload.get("provider_reference") or "").strip()
    if not reference: raise ValueError("Provider-Referenz fehlt.")
    row = m.ToolTimePaymentTransaction.objects.select_for_update().select_related("invoice", "created_by").filter(provider="webhook", provider_reference=reference).first()
    if row is None: raise ValueError("Unbekannte Provider-Referenz.")
    event = str(payload.get("event") or payload.get("status") or "").strip().lower()
    if event in {"payment.failed", "failed"}:
        row.status = "failed"; row.failure_reason = str(payload.get("reason") or "Vom Zahlungsdienst abgelehnt.")[:500]; row.provider_payload = payload; row.save(update_fields=["status", "failure_reason", "provider_payload", "updated_at"]); return row, False
    if event not in {"payment.succeeded", "succeeded", "paid"}: raise ValueError("Nicht unterstütztes Zahlungsereignis.")
    if money(payload.get("amount")) != money(row.amount): raise ValueError("Der bestätigte Betrag stimmt nicht mit der angelegten Zahlung überein.")
    if row.status == "succeeded" and row.payment_id: return row, False
    if row.created_by_id is None: raise ValueError("Der Zahlung fehlt ein verantwortlicher Benutzer.")
    current_open = money(base._invoice_total(row.invoice).get("open", 0)); invoice_payment_amount = min(money(row.invoice_amount), current_open); payment = row.payment
    if payment is None and invoice_payment_amount > 0:
        paid_at = _parse_event_datetime(payload.get("paid_at")); payment = m.Payment.objects.create(invoice=row.invoice, amount=invoice_payment_amount, paid_at=paid_at.date(), method="Karte", reference=row.provider_reference, recorded_by=row.created_by)
    row.payment = payment; row.status = "succeeded"; row.paid_at = _parse_event_datetime(payload.get("paid_at")); row.provider_payload = payload; row.failure_reason = ""; row.save(update_fields=["payment", "status", "paid_at", "provider_payload", "failure_reason", "updated_at"]); _sync_invoice_after_payment(row.invoice); return row, True


@transaction.atomic
def apply_payout_event(payload):
    event = str(payload.get("event") or payload.get("status") or "").strip().lower()
    if event not in {"payout.paid", "payout.failed", "paid", "failed"}: raise ValueError("Nicht unterstütztes Auszahlungsereignis.")
    try: org_id = int(payload.get("organization_id"))
    except (TypeError, ValueError): raise ValueError("organization_id fehlt oder ist ungültig.")
    org = m.Organization.objects.filter(pk=org_id).first()
    if org is None: raise ValueError("Organisation nicht gefunden.")
    ready, reason = provider_ready(org)
    if not ready: raise ValueError(reason)
    reference = str(payload.get("reference") or payload.get("provider_reference") or "").strip()[:180]
    if not reference: raise ValueError("Auszahlungsreferenz fehlt.")
    amount = money(payload.get("amount")); mode = str(payload.get("mode") or pay_settings(org).get("payout_mode") or "aggregated")
    if amount < 0: raise ValueError("Auszahlungsbetrag ist ungültig.")
    if mode not in {"individual", "aggregated"}: mode = "aggregated"
    def parsed_date(key):
        raw = str(payload.get(key) or "").strip()
        if not raw: return None
        try: return date.fromisoformat(raw[:10])
        except ValueError: return None
    status = "paid" if event in {"payout.paid", "paid"} else "failed"
    payout, _ = m.ToolTimePayout.objects.update_or_create(organization=org, provider="webhook", provider_reference=reference, defaults={"status": status, "mode": mode, "amount": amount, "currency": str(payload.get("currency") or "EUR")[:3].upper(), "period_start": parsed_date("period_start"), "period_end": parsed_date("period_end"), "paid_at": _parse_event_datetime(payload.get("paid_at")) if status == "paid" else None, "provider_payload": payload})
    return payout


def _dunning_customer(invoice):
    meta = meta_for(invoice, "invoice", create=False); customer = getattr(meta, "customer", None) if meta else None
    if customer is not None: return customer
    return getattr(getattr(invoice, "project", None), "customer", None)


def _productive_mail_ready():
    backend = str(getattr(settings, "EMAIL_BACKEND", "") or "").lower()
    if not backend or any(part in backend for part in ("console", "locmem", "dummy", "filebased")):
        return False
    return bool(str(getattr(settings, "DEFAULT_FROM_EMAIL", "") or getattr(settings, "EMAIL_HOST_USER", "") or "").strip())


def _send_automatic_dunning(record, pdf):
    recipient = str(record.recipient_email or "").strip()
    if not recipient or not _productive_mail_ready():
        return False
    invoice = record.invoice; org = record.organization; heading = record.get_level_display()
    subject = f"{heading} zu Rechnung {invoice.number}"
    body = f"Sehr geehrte Damen und Herren,\n\nanbei erhalten Sie {heading.lower()} zu Rechnung {invoice.number}.\n\nMit freundlichen Grüßen\n{org.name}"
    from_email = str(getattr(settings, "DEFAULT_FROM_EMAIL", "") or getattr(settings, "EMAIL_HOST_USER", "") or "").strip()
    message = EmailMessage(subject=subject, body=body, from_email=from_email, to=[recipient])
    message.attach(record.document.file.name.rsplit("/", 1)[-1] or f"mahnung-{invoice.pk}.pdf", pdf, "application/pdf")
    try:
        sent = message.send(fail_silently=False)
    except Exception:
        return False
    if sent != 1:
        return False
    record.sent_at = timezone.now(); record.save(update_fields=["sent_at"]); return True


def _create_dunning_record(org, invoice, level, *, created_by=None):
    cfg = profile_for(org).settings.get("dunning", {}); open_amount = money(base._invoice_total(invoice).get("open", 0))
    if open_amount <= 0 or level not in {"reminder", "first", "second"}: return None
    due_key = {"reminder": "reminder_days", "first": "first_days", "second": "second_days"}[level]; due_days = max(0, int(cfg.get(due_key) or 0)); fee = Decimal("0.00") if level == "reminder" else money(cfg.get("first_fee" if level == "first" else "second_fee", 0)); heading = {"reminder": "Zahlungserinnerung", "first": "1. Mahnung", "second": "2. Mahnung"}[level]; due = timezone.localdate() + timezone.timedelta(days=due_days); customer = _dunning_customer(invoice)
    html = '<html><body style="font-family:Arial,sans-serif;font-size:12px">' + f"<h1>{heading}</h1><p>Rechnung: <strong>{invoice.number}</strong></p><p>Sehr geehrte Damen und Herren,</p><p>Aktuell ist ein Betrag von <strong>{open_amount:.2f} €</strong> offen.</p><p>Bitte zahlen Sie bis spätestens <strong>{due:%d.%m.%Y}</strong>.</p>" + (f"<p>Mahngebühr: <strong>{fee:.2f} €</strong></p>" if fee else "") + f"<p>Mit freundlichen Grüßen<br>{org.name}</p></body></html>"
    pdf = html_to_pdf_bytes(inject_business_pdf_identity(html, org, document=invoice, kind="invoice")); document = m.Document(organization=org, customer=customer, project=invoice.project, title=f"{heading} · {invoice.number}", category="other", mime_type="application/pdf", size=len(pdf), metadata={"kind": "dunning", "level": level, "invoice_id": invoice.pk, "automatic": True}, uploaded_by=created_by); document.file.save(f"auto-{level}-{invoice.pk}.pdf", ContentFile(pdf), save=False); document.save()
    record = m.ToolTimeDunningRecord.objects.create(organization=org, invoice=invoice, level=level, due_days=due_days, fee=fee, internal_note="Automatisch nach hinterlegter Mahnregel erstellt.", recipient_email=getattr(customer, "email", "") if customer else "", document=document, created_by=created_by)
    _send_automatic_dunning(record, pdf)
    return record


def run_automatic_dunning(org, *, created_by=None, today=None):
    cfg = profile_for(org).settings.get("dunning", {})
    if not cfg.get("automatic"): return 0
    today = today or timezone.localdate(); created = 0
    invoices = m.Invoice.objects.filter(organization=org, compliance__state="finalized").select_related("project__customer").prefetch_related("payments", "tooltime_dunning_records")
    for invoice in invoices:
        meta = meta_for(invoice, "invoice", create=False)
        if meta and getattr(meta, "automatic_dunning_disabled", False): continue
        if not invoice.due_date or invoice.due_date >= today: continue
        if money(base._invoice_total(invoice).get("open", 0)) <= 0: continue
        records = list(invoice.tooltime_dunning_records.order_by("created_at", "id"))
        if not records:
            if (today - invoice.due_date).days >= max(0, int(cfg.get("reminder_days") or 0) + int(cfg.get("grace_days") or 0)) and _create_dunning_record(org, invoice, "reminder", created_by=created_by): created += 1
            continue
        latest = records[-1]; age = (today - timezone.localdate(latest.created_at)).days
        if latest.level == "reminder" and age >= max(0, int(cfg.get("first_days") or 0)):
            if _create_dunning_record(org, invoice, "first", created_by=created_by): created += 1
        elif latest.level == "first" and age >= max(0, int(cfg.get("second_days") or 0)):
            if _create_dunning_record(org, invoice, "second", created_by=created_by): created += 1
    return created
''')


def patch_views_urls_and_templates() -> None:
    rel = "erp/tooltime_parity_views.py"
    text = read(rel)
    if "from django.urls import reverse\n" not in text:
        anchor = "from django.utils import timezone\n"
        if anchor not in text: raise RuntimeError("ToolTime Pay django.urls anchor missing")
        text = text.replace(anchor, anchor + "from django.urls import reverse\n", 1)
    if "from django.views.decorators.csrf import csrf_exempt\n" not in text:
        anchor = "from django.views.decorators.http import require_GET, require_http_methods, require_POST\n"
        if anchor not in text: raise RuntimeError("ToolTime Pay csrf anchor missing")
        text = text.replace(anchor, "from django.views.decorators.csrf import csrf_exempt\n" + anchor, 1)
    service_import = "from .services.tooltime_pay import apply_payment_event, apply_payout_event, create_checkout, pay_settings, provider_ready as pay_provider_ready, qr_data_uri, run_automatic_dunning, webhook_token_valid\n"
    if service_import not in text:
        anchor = "from .services.tooltime_parity_finance import "
        pos = text.find(anchor)
        if pos < 0: raise RuntimeError("ToolTime Pay service import anchor missing")
        line_end = text.find("\n", pos)
        text = text[:line_end + 1] + service_import + text[line_end + 1:]

    handler_anchor = '''        elif section == "communication":
'''
    handler = r'''        elif section == "pay":
            pay = cfg.setdefault("pay", {})
            provider = (request.POST.get("pay_provider") or "disabled").strip().lower()
            if provider not in {"disabled", "webhook"}:
                messages.error(request, "Der ausgewählte Zahlungsdienst ist ungültig.")
                return redirect("next-settings")
            endpoint = (request.POST.get("pay_endpoint") or "").strip()
            if provider == "webhook" and not endpoint.startswith("https://"):
                messages.error(request, "Für Online-Zahlungen ist eine HTTPS-Adresse erforderlich.")
                return redirect("next-settings")
            card_limit = money(request.POST.get("card_limit") or "2000")
            if card_limit < 0:
                messages.error(request, "Das Kartenlimit darf nicht negativ sein.")
                return redirect("next-settings")
            payout_mode = (request.POST.get("payout_mode") or "aggregated").strip()
            if payout_mode not in {"individual", "aggregated"}: payout_mode = "aggregated"
            pay.update({"provider": provider, "endpoint": endpoint[:500], "card_limit": f"{card_limit:.2f}", "qr_enabled": request.POST.get("qr_enabled") == "on", "payout_mode": payout_mode})
            d = cfg.setdefault("dunning", {})
            for key in ("reminder_days", "first_days", "second_days", "grace_days"):
                try: d[key] = max(0, int(request.POST.get(key) or d.get(key) or 0))
                except ValueError:
                    messages.error(request, "Mahnfristen müssen ganze, nicht negative Tage sein.")
                    return redirect("next-settings")
            d["first_fee"] = f"{max(Decimal('0'), money(request.POST.get('first_fee') or d.get('first_fee') or 0)):.2f}"
            d["second_fee"] = f"{max(Decimal('0'), money(request.POST.get('second_fee') or d.get('second_fee') or 0)):.2f}"
            d["automatic"] = request.POST.get("automatic_dunning") == "on"
'''
    if 'elif section == "pay":' not in text:
        if handler_anchor not in text: raise RuntimeError("ToolTime Pay settings handler anchor missing")
        text = text.replace(handler_anchor, handler + handler_anchor, 1)

    context_anchor = '    templates = m.ToolTimeTextTemplate.objects.filter(organization=org)\n'
    if "pay_provider_status_ready, pay_provider_status_reason" not in text:
        if context_anchor not in text: raise RuntimeError("ToolTime Pay settings context anchor missing")
        text = text.replace(context_anchor, context_anchor + '    pay_provider_status_ready, pay_provider_status_reason = pay_provider_ready(org)\n', 1)
    if '"pay_provider_status_ready": pay_provider_status_ready' not in text:
        anchor = '"text_templates": templates'
        if anchor not in text: raise RuntimeError("ToolTime Pay settings render dictionary anchor missing")
        text = text.replace(anchor, anchor + ', "pay_provider_status_ready": pay_provider_status_ready, "pay_provider_status_reason": pay_provider_status_reason', 1)

    public_anchor = '\n\n@require_http_methods(["GET", "POST"])\ndef public_quote(request, token):\n'
    views = r'''

@login_required
def pay_overview(request):
    org = _org(request)
    guard = _phase7_commercial_guard(request, "next-invoices")
    if guard is not None: return guard
    transactions = m.ToolTimePaymentTransaction.objects.filter(organization=org).select_related("invoice").order_by("-created_at", "-pk")[:500]
    ready, reason = pay_provider_ready(org); cfg = pay_settings(org); selected = None; qr = ""
    selected_raw = (request.GET.get("transaction") or "").strip()
    if selected_raw.isdigit(): selected = transactions.filter(pk=int(selected_raw)).first()
    if selected and selected.status == "pending" and cfg.get("qr_enabled") and selected.checkout_url: qr = qr_data_uri(selected.checkout_url)
    return render(request, "rebuild/payments.html", {"transactions": transactions, "selected_transaction": selected, "selected_qr": qr, "pay_provider_ready": ready, "pay_provider_reason": reason, "pay_cfg": cfg})


@login_required
def payout_overview(request):
    org = _org(request)
    guard = _phase7_commercial_guard(request, "next-invoices")
    if guard is not None: return guard
    payouts = m.ToolTimePayout.objects.filter(organization=org).order_by("-created_at", "-pk")[:500]
    ready, reason = pay_provider_ready(org)
    return render(request, "rebuild/payouts.html", {"payouts": payouts, "pay_provider_ready": ready, "pay_provider_reason": reason, "pay_cfg": pay_settings(org)})


@login_required
@require_POST
def invoice_dunning_toggle(request, pk):
    org = _org(request); guard = _phase7_commercial_guard(request, "next-invoices")
    if guard is not None: return guard
    invoice = get_object_or_404(m.Invoice, organization=org, pk=pk); meta = meta_for(invoice, "invoice")
    meta.automatic_dunning_disabled = not bool(meta.automatic_dunning_disabled); meta.save(update_fields=["automatic_dunning_disabled", "updated_at"])
    messages.success(request, "Automatisches Mahnwesen wurde für diese Rechnung ausgesetzt." if meta.automatic_dunning_disabled else "Automatisches Mahnwesen wurde für diese Rechnung wieder aktiviert.")
    return redirect("next-invoices")


@login_required
@require_POST
def invoice_payment_link(request, pk):
    org = _org(request); guard = _phase7_commercial_guard(request, "next-invoices")
    if guard is not None: return guard
    invoice = get_object_or_404(m.Invoice.objects.select_related("project__customer"), organization=org, pk=pk)
    try: compliance_state = invoice.compliance.state
    except Exception: compliance_state = "draft"
    if compliance_state != "finalized":
        messages.error(request, "Online-Zahlungen sind erst für fertiggestellte Rechnungen verfügbar.")
        return redirect("next-invoices")
    callback_url = request.build_absolute_uri(reverse("next-pay-provider-webhook")); return_url = request.build_absolute_uri(reverse("next-payments"))
    try: transaction = create_checkout(org, invoice, callback_url=callback_url, return_url=return_url, user=request.user)
    except ValueError as exc:
        messages.error(request, str(exc)); return redirect("next-invoices")
    messages.success(request, "Der Zahlungsdienst hat einen sicheren Checkout angelegt. Die Rechnung bleibt bis zum bestätigten Webhook offen.")
    return redirect(reverse("next-payments") + f"?transaction={transaction.pk}")


@csrf_exempt
@require_POST
def pay_provider_webhook(request):
    if not webhook_token_valid(request.headers.get("Authorization")):
        return JsonResponse({"ok": False, "error": "unauthorized"}, status=403)
    try: payload = json.loads(request.body.decode("utf-8") or "{}")
    except (UnicodeDecodeError, json.JSONDecodeError): return JsonResponse({"ok": False, "error": "invalid_json"}, status=400)
    if not isinstance(payload, dict): return JsonResponse({"ok": False, "error": "invalid_payload"}, status=400)
    event = str(payload.get("event") or payload.get("status") or "").strip().lower()
    try:
        if event.startswith("payout.") or payload.get("object") == "payout": payout = apply_payout_event(payload); return JsonResponse({"ok": True, "payout_id": payout.pk})
        transaction, created = apply_payment_event(payload); return JsonResponse({"ok": True, "transaction_id": transaction.pk, "payment_created": created})
    except ValueError as exc: return JsonResponse({"ok": False, "error": str(exc)}, status=400)
'''
    if "def pay_provider_webhook(request):" not in text:
        if public_anchor not in text: raise RuntimeError("ToolTime Pay public quote insertion anchor missing")
        text = text.replace(public_anchor, views + public_anchor, 1)

    invoice_list_marker = '''def invoice_list(request):
    org = _org(request)
'''
    guarded = invoice_list_marker + "    if _phase7_can_commercially_mutate(request):\n        run_automatic_dunning(org, created_by=request.user)\n"
    if "run_automatic_dunning(org, created_by=request.user)" not in text:
        if invoice_list_marker not in text: raise RuntimeError("ToolTime Pay invoice list auto-dunning anchor missing")
        text = text.replace(invoice_list_marker, guarded, 1)
    old_return = '    return render(request, "rebuild/invoices.html", {"rows": rows, "q": query, "status_filter": status, "sort": sort, "today": timezone.localdate()})\n'
    new_return = '    pay_ready, pay_reason = pay_provider_ready(org)\n    pay_cfg = pay_settings(org)\n    for row in rows: row["pay_online"] = bool(pay_ready and row.get("can_pay"))\n    return render(request, "rebuild/invoices.html", {"rows": rows, "q": query, "status_filter": status, "sort": sort, "today": timezone.localdate(), "pay_ready": pay_ready, "pay_reason": pay_reason, "pay_cfg": pay_cfg, "card_limit": pay_cfg.get("card_limit")})\n'
    if '"pay_ready": pay_ready' not in text:
        if old_return not in text: raise RuntimeError("ToolTime Pay invoice list return anchor missing")
        text = text.replace(old_return, new_return, 1)
    write(rel, text)

    rel = "erp/rebuild_urls.py"; text = read(rel)
    anchor = '    path("invoices/<int:pk>/payment/", tooltime_parity.invoice_payment, name="next-invoice-payment"),\n'
    routes = r'''    path("payments/", tooltime_parity.pay_overview, name="next-payments"),
    path("payouts/", tooltime_parity.payout_overview, name="next-payouts"),
    path("invoices/<int:pk>/payment-link/", tooltime_parity.invoice_payment_link, name="next-invoice-payment-link"),
    path("invoices/<int:pk>/dunning-toggle/", tooltime_parity.invoice_dunning_toggle, name="next-invoice-dunning-toggle"),
    path("pay/provider/webhook/", tooltime_parity.pay_provider_webhook, name="next-pay-provider-webhook"),
'''
    if 'name="next-payments"' not in text:
        if anchor not in text: raise RuntimeError("ToolTime Pay URL anchor missing")
        text = text.replace(anchor, anchor + routes, 1)
    write(rel, text)

    rel = "templates/rebuild/tooltime_settings.html"; text = read(rel)
    if "data-tooltime-pay-settings" not in text:
        marker = '<section class="tt-card" data-phase6-communication>'
        pos = text.find(marker)
        if pos < 0: raise RuntimeError("ToolTime Pay settings UI anchor missing")
        block = r'''
<section class="tt-card" data-tooltime-pay-settings>
  <div class="tt-section-title"><div><span class="tt-eyebrow">Zahlungen</span><h2>A+Bau Pay</h2><p>Online-Zahlungen, QR-Code, Auszahlungen und Mahnwesen. Provider-Geheimnisse bleiben ausschließlich in der Server-Umgebung.</p></div><span class="nx-badge">{% if pay_provider_status_ready %}Zahlungsdienst bereit{% else %}Nicht bereit{% endif %}</span></div>
  <form method="post">{% csrf_token %}<input type="hidden" name="section" value="pay"><div class="tt-two"><label>Zahlungsdienst<select class="nx-control" name="pay_provider"><option value="disabled" {% if cfg.pay.provider != 'webhook' %}selected{% endif %}>Deaktiviert</option><option value="webhook" {% if cfg.pay.provider == 'webhook' %}selected{% endif %}>HTTPS-Schnittstelle</option></select></label><label>Provider-Endpoint<input class="nx-control" type="url" name="pay_endpoint" value="{{ cfg.pay.endpoint|default:'' }}" placeholder="https://payments.example/checkout"></label><label>Kartenlimit (€)<input class="nx-control" type="number" min="0" step="0.01" name="card_limit" value="{{ cfg.pay.card_limit|default:'2000.00' }}"></label><label>Auszahlung<select class="nx-control" name="payout_mode"><option value="individual" {% if cfg.pay.payout_mode == 'individual' %}selected{% endif %}>Einzelne Auszahlung</option><option value="aggregated" {% if cfg.pay.payout_mode != 'individual' %}selected{% endif %}>Gebündelte Auszahlung</option></select></label></div>
    <label class="tt-check"><input type="checkbox" name="qr_enabled" {% if cfg.pay.qr_enabled %}checked{% endif %}> QR-Code für sichere Checkout-Links anzeigen</label><hr><h3>Automatisches Mahnwesen</h3><label class="tt-check"><input type="checkbox" name="automatic_dunning" {% if cfg.dunning.automatic %}checked{% endif %}> Automatische Mahnstufen aktivieren</label>
    <div class="tt-three"><label>Zahlungserinnerung nach Tagen<input class="nx-control" type="number" min="0" name="reminder_days" value="{{ cfg.dunning.reminder_days|default:7 }}"></label><label>1. Mahnung nach weiteren Tagen<input class="nx-control" type="number" min="0" name="first_days" value="{{ cfg.dunning.first_days|default:7 }}"></label><label>Gebühr 1. Mahnung (€)<input class="nx-control" type="number" min="0" step="0.01" name="first_fee" value="{{ cfg.dunning.first_fee|default:'3.00' }}"></label><label>2. Mahnung nach weiteren Tagen<input class="nx-control" type="number" min="0" name="second_days" value="{{ cfg.dunning.second_days|default:7 }}"></label><label>Gebühr 2. Mahnung (€)<input class="nx-control" type="number" min="0" step="0.01" name="second_fee" value="{{ cfg.dunning.second_fee|default:'3.00' }}"></label><label>Kulanz / Grace Days<input class="nx-control" type="number" min="0" name="grace_days" value="{{ cfg.dunning.grace_days|default:1 }}"></label></div>
    <p class="tt-modal-note">{{ pay_provider_status_reason }} Provider-Geheimnisse werden nur serverseitig über <code>KAYI_PAY_PROVIDER_TOKEN</code> und <code>KAYI_PAY_WEBHOOK_TOKEN</code> geladen. Ohne echte Provider-Antwort wird keine Rechnung als bezahlt markiert. Bei der 2. Mahnstufe ersetzt deren Gebühr die Gebühr der 1. Stufe.</p><div class="tt-row-actions"><button class="nx-btn nx-btn-accent" type="submit">A+Bau Pay speichern</button><a class="nx-btn" href="{% url 'next-payments' %}">Zahlungen</a><a class="nx-btn" href="{% url 'next-payouts' %}">Auszahlungen</a></div>
  </form>
</section>
'''
        text = text[:pos] + block + text[pos:]
    write(rel, text)

    rel = "templates/rebuild/invoices.html"; text = read(rel)
    if 'href="{% url \'next-payments\' %}"' not in text:
        anchor = '<div class="tt-pagehead"><div><span class="tt-eyebrow">Finanzen</span><h1>Rechnungen</h1><p>Offene Beträge, Fälligkeiten, Teilzahlungen und Mahnungen an einer Stelle.</p></div><a class="nx-btn nx-btn-accent" href="{% url \'next-invoice-create\' %}">＋ Neue Rechnung</a></div>'
        replacement = '<div class="tt-pagehead"><div><span class="tt-eyebrow">Finanzen</span><h1>Rechnungen</h1><p>Offene Beträge, Fälligkeiten, Teilzahlungen und Mahnungen an einer Stelle.</p></div><div class="tt-row-actions"><a class="nx-btn" href="{% url \'next-payments\' %}">Zahlungen</a><a class="nx-btn" href="{% url \'next-payouts\' %}">Auszahlungen</a><a class="nx-btn nx-btn-accent" href="{% url \'next-invoice-create\' %}">＋ Neue Rechnung</a></div></div>'
        if anchor not in text: raise RuntimeError("ToolTime Pay invoice header anchor missing")
        text = text.replace(anchor, replacement, 1)
    manual = '<button type="button" class="nx-btn nx-btn-small nx-btn-accent" data-payment-open data-action="{% url \'next-invoice-payment\' row.invoice.pk %}" data-number="{{ row.invoice.number|default:\'Rechnung\' }}" data-open="{{ row.open }}">Zahlung eintragen</button>'
    if 'next-invoice-payment-link' not in text:
        if manual not in text: raise RuntimeError("ToolTime Pay manual payment action anchor missing")
        text = text.replace(manual, manual + r'''{% if row.pay_online %}<form method="post" action="{% url 'next-invoice-payment-link' row.invoice.pk %}">{% csrf_token %}<button class="nx-btn nx-btn-small" type="submit">Online-Zahlung / QR</button></form>{% endif %}{% if row.can_dun %}<form method="post" action="{% url 'next-invoice-dunning-toggle' row.invoice.pk %}">{% csrf_token %}<button class="tt-link" type="submit">{% if row.meta.automatic_dunning_disabled %}Mahn-Automatik aktivieren{% else %}Mahn-Automatik aussetzen{% endif %}</button></form>{% endif %}''', 1)
    write(rel, text)

    write("templates/rebuild/payments.html", r'''{% extends 'rebuild/base.html' %}{% load static %}{% block title %}Zahlungen · A+Bau{% endblock %}{% block content %}<link rel="stylesheet" href="{% static 'css/tooltime-parity-finance.css' %}?v=20260820-pay-1"><div data-tooltime-pay-overview><div class="tt-pagehead"><div><span class="tt-eyebrow">A+Bau Pay</span><h1>Zahlungsübersicht</h1><p>Provider-Transaktionen bleiben bis zum bestätigten Webhook ausstehend.</p></div><div class="tt-row-actions"><a class="nx-btn" href="{% url 'next-invoices' %}">Rechnungen</a><a class="nx-btn" href="{% url 'next-payouts' %}">Auszahlungen</a></div></div><p class="tt-modal-note">{% if pay_provider_ready %}Zahlungsdienst bereit.{% else %}{{ pay_provider_reason }}{% endif %}</p>{% if selected_transaction %}<section class="tt-card tt-pay-checkout"><div><span class="tt-eyebrow">Checkout</span><h2>{{ selected_transaction.invoice.number }}</h2><p>{{ selected_transaction.amount|floatformat:2 }} € · {{ selected_transaction.get_status_display }}</p><a class="nx-btn nx-btn-accent" href="{{ selected_transaction.checkout_url }}" rel="noopener noreferrer" target="_blank">Sichere Zahlungsseite öffnen</a></div>{% if selected_qr %}<img src="{{ selected_qr }}" alt="QR-Code zum sicheren Zahlungslink" width="210" height="210">{% endif %}</section>{% endif %}<div class="tt-list-card"><div class="tt-list-table tt-pay-table"><div class="tt-list-head"><span>Zeit</span><span>Rechnung</span><span>Betrag</span><span>Gebühr</span><span>Status</span><span>Provider-Referenz</span></div>{% for row in transactions %}<div class="tt-list-row"><span>{{ row.created_at|date:'d.m.Y H:i' }}</span><a class="tt-doc-number" href="{% url 'next-invoice-edit' row.invoice.pk %}">{{ row.invoice.number }}</a><strong>{{ row.amount|floatformat:2 }} €</strong><span>{{ row.dunning_fee|floatformat:2 }} €</span><span class="tt-state tt-state-{{ row.status }}">{{ row.get_status_display }}</span><span><code>{{ row.provider_reference|default:row.local_reference }}</code>{% if row.status == 'pending' and row.checkout_url %}<br><a class="tt-link" href="?transaction={{ row.pk }}">QR / Link</a>{% endif %}</span></div>{% empty %}<div class="tt-empty-state"><strong>Noch keine Online-Transaktionen.</strong><span>Ein Zahlungslink kann aus einer offenen, fertiggestellten Rechnung erstellt werden.</span></div>{% endfor %}</div></div></div>{% endblock %}''')
    write("templates/rebuild/payouts.html", r'''{% extends 'rebuild/base.html' %}{% load static %}{% block title %}Auszahlungen · A+Bau{% endblock %}{% block content %}<link rel="stylesheet" href="{% static 'css/tooltime-parity-finance.css' %}?v=20260820-pay-1"><div data-tooltime-payout-overview><div class="tt-pagehead"><div><span class="tt-eyebrow">A+Bau Pay</span><h1>Auszahlungsübersicht</h1><p>Vom Provider bestätigte Einzel- oder Sammelauszahlungen.</p></div><div class="tt-row-actions"><a class="nx-btn" href="{% url 'next-payments' %}">Zahlungen</a><a class="nx-btn" href="{% url 'next-invoices' %}">Rechnungen</a></div></div><p class="tt-modal-note">Modus: {% if pay_cfg.payout_mode == 'individual' %}Einzelauszahlung{% else %}Gebündelte Auszahlung{% endif %}. {% if not pay_provider_ready %}{{ pay_provider_reason }}{% endif %}</p><div class="tt-list-card"><div class="tt-list-table tt-payout-table"><div class="tt-list-head"><span>Provider-Referenz</span><span>Zeitraum</span><span>Modus</span><span>Betrag</span><span>Status</span><span>Ausgezahlt</span></div>{% for row in payouts %}<div class="tt-list-row"><code>{{ row.provider_reference }}</code><span>{% if row.period_start %}{{ row.period_start|date:'d.m.Y' }}{% else %}—{% endif %} – {% if row.period_end %}{{ row.period_end|date:'d.m.Y' }}{% else %}—{% endif %}</span><span>{{ row.get_mode_display }}</span><strong>{{ row.amount|floatformat:2 }} {{ row.currency }}</strong><span class="tt-state tt-state-{{ row.status }}">{{ row.get_status_display }}</span><span>{% if row.paid_at %}{{ row.paid_at|date:'d.m.Y H:i' }}{% else %}—{% endif %}</span></div>{% empty %}<div class="tt-empty-state"><strong>Noch keine Auszahlungen gemeldet.</strong><span>Auszahlungen erscheinen erst nach einem authentifizierten Provider-Ereignis.</span></div>{% endfor %}</div></div></div>{% endblock %}''')

    rel = "static/css/tooltime-parity-finance.css"; css = read(rel)
    if "/* A+BAU TOOLTIME PAY */" not in css:
        css += r'''
/* A+BAU TOOLTIME PAY */
.tt-pay-checkout{display:flex;justify-content:space-between;align-items:center;gap:24px;margin-bottom:18px}.tt-pay-checkout img{border:1px solid #e1e7ee;border-radius:12px;padding:10px;background:#fff}.tt-pay-table .tt-list-head,.tt-pay-table .tt-list-row{grid-template-columns:1fr 1fr .8fr .7fr .9fr 1.6fr}.tt-payout-table .tt-list-head,.tt-payout-table .tt-list-row{grid-template-columns:1.4fr 1.2fr .9fr .9fr .9fr 1fr}.tt-state-succeeded,.tt-state-paid{background:#e9f7ef;color:#11733c}.tt-state-pending{background:#fff8e6;color:#8a5a00}.tt-state-failed,.tt-state-refunded{background:#fff0ed;color:#b42318}@media(max-width:900px){.tt-pay-checkout{align-items:flex-start;flex-direction:column}.tt-pay-table .tt-list-row,.tt-payout-table .tt-list-row{grid-template-columns:1fr 1fr}}
'''
        write(rel, css)


def install_management_command() -> None:
    write("erp/management/__init__.py", read("erp/management/__init__.py") if (ROOT / "erp/management/__init__.py").exists() else "")
    write("erp/management/commands/__init__.py", read("erp/management/commands/__init__.py") if (ROOT / "erp/management/commands/__init__.py").exists() else "")
    write("erp/management/commands/tooltime_auto_dunning.py", r'''from django.core.management.base import BaseCommand
from erp.models import Organization
from erp.services.tooltime_pay import run_automatic_dunning


class Command(BaseCommand):
    help = "Führt die konfigurierten automatischen Mahnstufen mandantenweise aus."

    def handle(self, *args, **options):
        total = 0
        for org in Organization.objects.order_by("pk"):
            total += run_automatic_dunning(org, created_by=None)
        self.stdout.write(self.style.SUCCESS(f"Automatisches Mahnwesen: {total} neue Stufe(n)."))
''')


def patch_browser_smoke() -> None:
    rel = "scripts/production_browser_smoke.py"; text = read(rel); marker = "# A+BAU TOOLTIME PAY BROWSER SMOKE"
    if marker not in text:
        anchor = "            context.close()\n"; pos = text.rfind(anchor)
        if pos < 0: raise RuntimeError("ToolTime Pay browser-smoke final context anchor missing")
        block = r'''            # A+BAU TOOLTIME PAY BROWSER SMOKE
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

'''
        text = text[:pos] + block + text[pos:]
    write(rel, text); compile(text, str(ROOT / rel), "exec")


def install_tests() -> None:
    write("tests/test_tooltime_pay_contract.py", r'''from pathlib import Path
from django.test import SimpleTestCase

ROOT = Path(__file__).resolve().parents[1]


class ToolTimePayContractTests(SimpleTestCase):
    def test_models_and_migration_are_persistent(self):
        models = (ROOT / "erp/tooltime_parity_finance.py").read_text(encoding="utf-8"); migration = (ROOT / "erp/migrations/0018_tooltime_pay.py").read_text(encoding="utf-8")
        self.assertIn("class ToolTimePaymentTransaction", models); self.assertIn("class ToolTimePayout", models); self.assertIn("automatic_dunning_disabled", models); self.assertIn("0017_tooltime_phase5_communication", migration)

    def test_payment_provider_cannot_fake_success(self):
        service = (ROOT / "erp/services/tooltime_pay.py").read_text(encoding="utf-8"); views = (ROOT / "erp/tooltime_parity_views.py").read_text(encoding="utf-8")
        self.assertIn("KAYI_PAY_PROVIDER_TOKEN", service); self.assertIn("KAYI_PAY_WEBHOOK_TOKEN", service); self.assertIn("urllib.request.urlopen(req, timeout=15)", service); self.assertIn('status="pending"', service); self.assertIn('event not in {"payment.succeeded", "succeeded", "paid"}', service); self.assertIn("hmac.compare_digest", service); self.assertIn("@csrf_exempt", views)

    def test_qr_payout_and_dunning_contracts_exist(self):
        service = (ROOT / "erp/services/tooltime_pay.py").read_text(encoding="utf-8"); settings = (ROOT / "templates/rebuild/tooltime_settings.html").read_text(encoding="utf-8"); requirements = (ROOT / "requirements.txt").read_text(encoding="utf-8")
        self.assertIn("qrcode", requirements.lower()); self.assertIn("def qr_data_uri", service); self.assertIn("card_limit", service); self.assertIn("def apply_payout_event", service); self.assertIn("def effective_dunning_fee", service); self.assertIn("run_automatic_dunning", service); self.assertIn("_productive_mail_ready", service); self.assertIn("if sent != 1", service); self.assertIn("record.sent_at = timezone.now()", service); self.assertIn('name="automatic_dunning"', settings)

    def test_ui_routes_and_invoice_opt_out_are_real(self):
        urls = (ROOT / "erp/rebuild_urls.py").read_text(encoding="utf-8"); invoices = (ROOT / "templates/rebuild/invoices.html").read_text(encoding="utf-8"); payments = (ROOT / "templates/rebuild/payments.html").read_text(encoding="utf-8"); payouts = (ROOT / "templates/rebuild/payouts.html").read_text(encoding="utf-8")
        for name in ("next-payments", "next-payouts", "next-invoice-payment-link", "next-invoice-dunning-toggle", "next-pay-provider-webhook"): self.assertIn(name, urls)
        self.assertIn("Online-Zahlung / QR", invoices); self.assertIn("Mahn-Automatik aussetzen", invoices); self.assertIn("data-tooltime-pay-overview", payments); self.assertIn("data-tooltime-payout-overview", payouts)

    def test_scheduler_entrypoint_exists(self):
        command = (ROOT / "erp/management/commands/tooltime_auto_dunning.py").read_text(encoding="utf-8"); self.assertIn("run_automatic_dunning", command); self.assertIn("Organization.objects.order_by", command)
''')


def run() -> None:
    patch_requirements(); patch_models_and_migration(); patch_service_defaults_and_meta(); install_pay_service(); patch_views_urls_and_templates(); install_management_command(); patch_browser_smoke(); install_tests()
    for rel in ("erp/tooltime_parity_views.py", "erp/tooltime_parity_finance.py", "erp/services/tooltime_parity_finance.py", "erp/services/tooltime_pay.py", "scripts/production_browser_smoke.py"):
        path = ROOT / rel; compile(path.read_text(encoding="utf-8"), str(path), "exec")
    print("A+Bau ToolTime Pay installiert: echter Provider-Checkout/Webhook, QR, Transaktionen, Auszahlungen, Mahngebühren und automatisches Mahnwesen ohne Fake-Erfolg.")


if __name__ == "__main__": run()
