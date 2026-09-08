from __future__ import annotations

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
