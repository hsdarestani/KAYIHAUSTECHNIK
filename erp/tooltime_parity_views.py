from __future__ import annotations

from django.views.decorators.clickjacking import xframe_options_sameorigin

import hashlib
import json
import os
import urllib.error
import urllib.request
import html
import io

import csv
import io

import re
from decimal import Decimal
from email.utils import formataddr
from datetime import date
from datetime import timedelta

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.base import ContentFile
from django.core.mail import EmailMessage
from django.core.validators import validate_email
from django.db import transaction
from django.db.models import Q
from django.http import FileResponse, Http404, HttpResponse, HttpResponseBadRequest, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from . import models as m
from . import rebuild_views as base
from .services.business_pdf_identity import inject_business_pdf_identity
from .services.field_authorization import html_to_pdf_bytes
from .services.invoice_compliance_service import audit as invoice_compliance_audit, get_compliance
from .services.tooltime_parity_finance import allocate_number, finalize_quote, invoice_type_allowed, meta_for, money, phase2_settings, profile_for, save_document_meta, sync_position_extras
from .services.tooltime_pay import apply_payment_event, apply_payout_event, create_checkout, pay_settings, provider_ready as pay_provider_ready, qr_data_uri, run_automatic_dunning, webhook_token_valid


def _org(request): return base._org(request)


def _sequence_number_for_customer(org, posted=""):
    cfg = profile_for(org).settings.get("numbering", {})
    if cfg.get("customer_auto"):
        return allocate_number(org, "customer")
    manual = (posted or "").strip()[:30]
    if manual and not m.Customer.objects.filter(organization=org, number=manual).exists():
        return manual
    return base._unique_number(m.Customer, org, "K")


def _ensure_document_project(request, org):
    if request.method != "POST" or request.POST.get("project"):
        return
    customer_id = (request.POST.get("selected_customer") or "").strip()
    if not customer_id.isdigit():
        return
    customer = m.Customer.objects.filter(organization=org, active=True, pk=int(customer_id)).first()
    if customer is None:
        return
    project = m.Project.objects.filter(organization=org, customer=customer, archived=False, title="Allgemeiner Auftrag").first()
    if project is None:
        project = m.Project.objects.create(
            organization=org,
            customer=customer,
            number=base._unique_number(m.Project, org, "P"),
            title="Allgemeiner Auftrag",
            status="inquiry",
        )
    post = request.POST.copy()
    post["project"] = str(project.pk)
    request.POST = post


def _save_upload_document(org, request, upload, title, kind):
    if not upload:
        return None
    document = m.Document(
        organization=org,
        title=title,
        category="contract" if kind in {"terms", "withdrawal"} else "other",
        mime_type=getattr(upload, "content_type", "") or "application/octet-stream",
        size=getattr(upload, "size", 0) or 0,
        metadata={"kind": kind, "source": "einstellungen"},
        uploaded_by=request.user,
    )
    document.file.save(upload.name, upload, save=False)
    document.save()
    return document


def _redirect_pk(response):
    location = response.get("Location", "") if hasattr(response, "get") else ""
    match = re.search(r"/(?:quotes|invoices)/(\d+)/?", location)
    return int(match.group(1)) if match else None


def _phase3_prepare_direct_customer(request, org):
    if request.method != "POST":
        return None
    data = request.POST.copy()
    project_id = (data.get("project") or "").strip()
    customer_id = (data.get("customer_id") or "").strip()
    if project_id.isdigit():
        project = m.Project.objects.filter(organization=org, pk=int(project_id)).select_related("customer").first()
        if project:
            data["customer_id"] = str(project.customer_id)
            request.POST = data
        return None
    if not customer_id.isdigit():
        request.POST = data
        return None
    customer = m.Customer.objects.filter(organization=org, active=True, pk=int(customer_id)).first()
    if customer is None:
        request.POST = data
        return None
    title = f"Direktdokumente · Kunde {customer.pk}"
    project = m.Project.objects.filter(organization=org, customer=customer, title=title).order_by("id").first()
    if project is None:
        project = m.Project.objects.create(
            organization=org,
            customer=customer,
            number=base._unique_number(m.Project, org, "P"),
            title=title,
            status="inquiry",
            archived=False,
        )
    elif project.archived:
        project.archived = False
        project.save(update_fields=["archived", "updated_at"])
    data["project"] = str(project.pk)
    data["customer_id"] = str(customer.pk)
    request.POST = data
    return project


def _phase3_rearchive_direct_project(project):
    if project is not None and not project.archived:
        project.archived = True
        project.save(update_fields=["archived", "updated_at"])


def _phase5_customer(document, kind):
    meta = meta_for(document, kind, create=False)
    customer = getattr(meta, "customer", None) if meta else None
    if customer is not None:
        return customer
    project = getattr(document, "project", None)
    return getattr(project, "customer", None) if project else None


def _phase6_render_communication_template(raw, document, kind):
    customer = _phase5_customer(document, kind)
    project = getattr(document, "project", None)
    issue_date = getattr(document, "issue_date", None)
    values = {
        "company_name": getattr(document.organization, "name", "") or "",
        "document_number": getattr(document, "number", "") or "",
        "quote_number": getattr(document, "number", "") if kind == "quote" else "",
        "invoice_number": getattr(document, "number", "") if kind == "invoice" else "",
        "customer_name": getattr(customer, "display_name", "") if customer else "",
        "project_name": getattr(project, "name", "") if project else "",
        "date": issue_date.strftime("%d.%m.%Y") if issue_date else "",
    }
    rendered = str(raw or "")
    for key, value in values.items():
        rendered = rendered.replace("{{ " + key + " }}", str(value or ""))
        rendered = rendered.replace("{{" + key + "}}", str(value or ""))
        rendered = rendered.replace("{" + key + "}", str(value or ""))
    return rendered


def _phase6_document_message(document, kind):
    cfg = profile_for(document.organization).settings.get("communication", {})
    label = "Angebot" if kind == "quote" else "Rechnung"
    subject_key = "quote_subject" if kind == "quote" else "invoice_subject"
    body_key = "quote_body" if kind == "quote" else "invoice_body"
    fallback_subject = f"{label} {document.number} · {document.organization.name}"
    fallback_body = f"Sehr geehrte Damen und Herren,\n\nanbei erhalten Sie {'unser Angebot' if kind == 'quote' else 'unsere Rechnung'} {document.number} als PDF.\n\nMit freundlichen Grüßen\n{document.organization.name}"
    subject = _phase6_render_communication_template(cfg.get(subject_key) or fallback_subject, document, kind).strip()[:300]
    body = _phase6_render_communication_template(cfg.get(body_key) or fallback_body, document, kind).strip()
    return subject, body, cfg


def _phase6_sms_provider_ready(org):
    cfg = profile_for(org).settings.get("communication", {})
    provider = str(cfg.get("sms_provider") or "disabled").strip().lower()
    if provider == "disabled":
        return False, "SMS-Versand ist deaktiviert."
    if provider != "webhook":
        return False, "Der konfigurierte SMS-Dienst wird nicht unterstützt."
    endpoint = str(cfg.get("sms_endpoint") or "").strip()
    if not endpoint.startswith("https://"):
        return False, "Für die SMS-Schnittstelle ist eine HTTPS-Adresse erforderlich."
    if not os.environ.get("KAYI_SMS_PROVIDER_TOKEN"):
        return False, "Der SMS-Zugangstoken fehlt in der Server-Umgebung."
    return True, "SMS-Dienst ist serverseitig einsatzbereit."


def _phase6_send_sms(org, phone, body):
    ready, reason = _phase6_sms_provider_ready(org)
    if not ready:
        return False, reason
    phone = str(phone or "").strip()
    body = str(body or "").strip()
    if not phone:
        return False, "Eine Mobilnummer ist erforderlich."
    if not body:
        return False, "Die SMS-Nachricht ist leer."
    if len(body) > 160:
        return False, "Die SMS-Nachricht darf maximal 160 Zeichen enthalten."
    cfg = profile_for(org).settings.get("communication", {})
    payload = json.dumps({"to": phone, "message": body, "sender": str(cfg.get("sms_sender_id") or "")[:32]}).encode("utf-8")
    request = urllib.request.Request(
        str(cfg.get("sms_endpoint") or ""),
        data=payload,
        method="POST",
        headers={
            "Authorization": "Bearer " + os.environ["KAYI_SMS_PROVIDER_TOKEN"],
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=12) as response:
            status = int(getattr(response, "status", 0) or 0)
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, OSError) as exc:
        return False, f"SMS-Versand fehlgeschlagen: {exc}"
    if status < 200 or status >= 300:
        return False, f"SMS-Provider antwortete mit HTTP {status}."
    return True, "SMS wurde vom Provider angenommen."


def _phase5_email_backend_ready():
    backend = str(getattr(settings, "EMAIL_BACKEND", "") or "").lower()
    non_delivery = ("console", "locmem", "dummy", "filebased")
    if any(part in backend for part in non_delivery):
        return False, "Es ist kein produktiver E-Mail-Versand konfiguriert. Bitte SMTP in den Einstellungen hinterlegen."
    return True, ""


def _phase5_quote_pdf_bytes(quote, *, require_finalized=True):
    meta = meta_for(quote, "quote")
    if require_finalized and not meta.finalized_at:
        raise ValueError("Der Versand ist erst nach dem Fertigstellen des Angebots verfügbar.")
    customer = _phase5_customer(quote, "quote")
    totals = base._quote_total(quote)
    net = money(totals.get("net", 0)); gross = money(totals.get("gross", net)); tax = money(totals.get("tax", gross - net))
    rows = []
    for item in quote.items.all().order_by("position", "pk"):
        quantity = getattr(item, "quantity", 0) or 0
        unit_price = money(getattr(item, "unit_price", 0))
        line_total = money(quantity * unit_price)
        rows.append(
            "<tr>"
            f"<td>{html.escape(str(getattr(item, 'position', '') or ''))}</td>"
            f"<td>{html.escape(str(getattr(item, 'description', '') or ''))}</td>"
            f"<td style='text-align:right'>{html.escape(str(quantity))} {html.escape(str(getattr(item, 'unit', '') or ''))}</td>"
            f"<td style='text-align:right'>{unit_price:.2f} €</td>"
            f"<td style='text-align:right'>{line_total:.2f} €</td>"
            "</tr>"
        )
    customer_name = getattr(customer, "display_name", "") if customer else ""
    address = " · ".join(filter(None, [getattr(customer, "street", "") if customer else "", " ".join(filter(None, [getattr(customer, "postal_code", "") if customer else "", getattr(customer, "city", "") if customer else ""]))]))
    intro = html.escape(str(getattr(quote, "intro_text", "") or "")).replace("\n", "<br>")
    outro = html.escape(str(getattr(quote, "outro_text", "") or "")).replace("\n", "<br>")
    org = quote.organization
    project = getattr(quote, "project", None)
    project_label = " · ".join(filter(None, [str(getattr(project, "number", "") or ""), str(getattr(project, "title", "") or "")]))
    price_source = getattr(project, "price_source", None) if project else None
    price_basis = str(getattr(price_source, "name", "") or "")
    document_number = quote.number or meta.final_number or "ENTWURF"
    draft_notice = "" if meta.finalized_at else (
        "<div style='margin:0 0 16px;padding:9px 12px;border:1px solid #d6b15e;background:#fff8e8'>"
        "<strong>ENTWURF · Angebotsvorschau</strong><br>"
        "Diese Vorschau besitzt noch keine endgültige Angebotsnummer und ist nicht zum Versand freigegeben."
        "</div>"
    )
    customer_details = "<br>".join(filter(None, [
        html.escape(str(customer_name)),
        ("Kundennummer: " + html.escape(str(getattr(customer, "number", "")))) if customer and getattr(customer, "number", "") else "",
        html.escape(str(getattr(customer, "company", "") or "")) if customer and getattr(customer, "company", "") != customer_name else "",
        ("USt-IdNr.: " + html.escape(str(getattr(customer, "vat_id", "")))) if customer and getattr(customer, "vat_id", "") else "",
        html.escape(str(getattr(customer, "email", "") or "")) if customer else "",
        html.escape(str(getattr(customer, "phone", "") or getattr(customer, "mobile", "") or "")) if customer else "",
    ]))
    company_details = " · ".join(filter(None, [
        str(getattr(org, "legal_name", "") or getattr(org, "name", "") or ""),
        str(getattr(org, "address", "") or "").replace("\n", ", "),
        ("E-Mail: " + str(getattr(org, "email", ""))) if getattr(org, "email", "") else "",
        ("Tel.: " + str(getattr(org, "phone", ""))) if getattr(org, "phone", "") else "",
    ]))
    legal_details = " · ".join(filter(None, [
        ("Steuernummer/USt.-ID: " + str(getattr(org, "tax_id", ""))) if getattr(org, "tax_id", "") else "",
        ("IBAN: " + str(getattr(org, "iban", ""))) if getattr(org, "iban", "") else "",
    ]))
    context_block = (
        draft_notice
        + "<table style='width:100%;margin:0 0 16px;border-collapse:collapse'><tr>"
        + "<td style='vertical-align:top;width:55%'><strong>Kunde</strong><br>" + customer_details + ("<br>" + html.escape(address) if address else "") + "</td>"
        + "<td style='vertical-align:top'><strong>Dokument</strong><br>Nr.: " + html.escape(str(document_number))
        + ("<br>Projekt: " + html.escape(project_label) if project_label else "")
        + ("<br>Preisgrundlage: " + html.escape(price_basis) if price_basis else "")
        + f"<br>Datum: {quote.issue_date:%d.%m.%Y}</td></tr></table>"
    )
    intro = context_block + ("<div style='margin:0 0 16px'>" + intro + "</div>" if intro else "")
    document_note = (
        "<div style='margin-top:18px;padding:9px 11px;background:#f6f6f6;font-size:9px;color:#555'>"
        "<strong>Dokumenthinweis:</strong> Positionen, Mengen, Einzelpreise, Steuern und Gesamtsumme "
        "entsprechen dem aktuellen Stand dieses Angebots."
        "</div>"
    )
    footer_details = "<div style='margin-top:24px;padding-top:10px;border-top:1px solid #ddd;font-size:9px;color:#555'>" + html.escape(company_details)
    if legal_details:
        footer_details += "<br>" + html.escape(legal_details)
    footer_details += "<br>Alle Beträge in EUR."
    footer_details += "</div>"
    outro = ("<div style='margin-top:18px'>" + outro + "</div>" if outro else "") + document_note + footer_details
    body = f"""<html><body style="font-family:Arial,sans-serif;font-size:11px;color:#202428">
<h1 style="margin-bottom:4px">{html.escape(meta.document_title or 'Angebot')} {html.escape(str(document_number))}</h1>
<p style="margin-top:0">Angebotsdatum: {quote.issue_date:%d.%m.%Y}</p>
<div style="margin:20px 0"><strong>{html.escape(str(customer_name))}</strong><br>{html.escape(address)}</div>
<p>{intro}</p>
<table style="width:100%;border-collapse:collapse" cellpadding="6"><thead><tr style="border-bottom:1px solid #bbb"><th>Pos.</th><th style="text-align:left">Leistung</th><th style="text-align:right">Menge</th><th style="text-align:right">Einzelpreis</th><th style="text-align:right">Gesamt</th></tr></thead><tbody>{''.join(rows)}</tbody></table>
<div style="margin:18px 0 18px auto;width:260px"><p>Nettobetrag <strong style="float:right">{net:.2f} €</strong></p><p>Umsatzsteuer <strong style="float:right">{tax:.2f} €</strong></p><p style="font-size:13px;border-top:1px solid #bbb;padding-top:7px">Gesamtbetrag <strong style="float:right">{gross:.2f} €</strong></p></div>
<p>{outro}</p>
</body></html>"""
    return html_to_pdf_bytes(inject_business_pdf_identity(body, org=quote.organization, document_kind="Angebot"))


def _phase5_store_quote_delivery_pdf(quote, payload, user):
    customer = _phase5_customer(quote, "quote")
    filename = f"angebot-{quote.number or quote.pk}.pdf"
    doc = m.Document(
        organization=quote.organization,
        project=quote.project,
        customer=customer,
        uploaded_by=user if getattr(user, "is_authenticated", False) else None,
        title=filename,
        category="quote",
        mime_type="application/pdf",
        size=len(payload),
        sha256=hashlib.sha256(payload).hexdigest(),
        metadata={"source": "tooltime_email_delivery", "quote_id": quote.pk, "final_number": quote.number or ""},
    )
    doc.file.save(filename, ContentFile(payload), save=False)
    doc.save()
    return doc


def _phase5_legal_attachments(document, kind, skip_document_id=None):
    meta = meta_for(document, kind, create=False)
    ids = list(getattr(meta, "default_attachment_ids", []) or []) if meta else []
    if not ids:
        return []
    result = []
    for attachment in m.Document.objects.filter(organization=document.organization, pk__in=ids):
        if skip_document_id and attachment.pk == skip_document_id:
            continue
        if not getattr(attachment, "file", None):
            continue
        try:
            with attachment.file.open("rb") as handle:
                payload = handle.read()
        except (OSError, ValueError):
            continue
        result.append((attachment.title or f"anlage-{attachment.pk}", payload, attachment.mime_type or "application/octet-stream"))
    return result


def _phase5_delivery_failure(*, document, kind, recipient, subject, body, error, user, pdf_document=None):
    return m.ToolTimeDocumentDelivery.objects.create(
        organization=document.organization,
        quote=document if kind == "quote" else None,
        invoice=document if kind == "invoice" else None,
        document=pdf_document,
        channel="email",
        status="failed",
        recipient_email=recipient,
        subject=subject[:300],
        body_excerpt=body[:1000],
        error_message=str(error)[:500],
        created_by=user,
    )


def _phase5_send_email(request, document, kind):
    meta = meta_for(document, kind, create=False)
    if kind == "quote":
        if not meta or not meta.finalized_at:
            messages.error(request, "Angebote können erst nach dem Fertigstellen versendet werden.")
            return False
        pdf = _phase5_quote_pdf_bytes(document)
        pdf_document = _phase5_store_quote_delivery_pdf(document, pdf, request.user)
        filename = pdf_document.title
        extra_attachments = _phase5_legal_attachments(document, kind, skip_document_id=pdf_document.pk)
        xml_attachment = None
    else:
        compliance = get_compliance(document)
        if not compliance or compliance.state == "draft" or not compliance.original_pdf_document_id:
            messages.error(request, "Rechnungen können nur mit dem finalisierten Original-PDF versendet werden.")
            return False
        pdf_document = compliance.original_pdf_document
        try:
            with pdf_document.file.open("rb") as handle:
                pdf = handle.read()
        except (OSError, ValueError):
            messages.error(request, "Das finalisierte Original-PDF ist nicht lesbar. Der Versand wurde abgebrochen.")
            return False
        filename = pdf_document.title or f"rechnung-{compliance.final_number}.pdf"
        extra_attachments = _phase5_legal_attachments(document, kind, skip_document_id=pdf_document.pk)
        xml_attachment = None
        if compliance.original_xml_document_id and compliance.e_invoice_status == "valid":
            xml_doc = compliance.original_xml_document
            try:
                with xml_doc.file.open("rb") as handle:
                    xml_attachment = (xml_doc.title or f"xrechnung-{compliance.final_number}.xml", handle.read(), xml_doc.mime_type or "application/xml")
            except (OSError, ValueError):
                xml_attachment = None

    customer = _phase5_customer(document, kind)
    default_recipient = getattr(customer, "email", "") if customer else ""
    if kind == "invoice" and customer:
        try:
            default_recipient = customer.invoice_profile.invoice_email or default_recipient
        except (AttributeError, m.CustomerInvoiceProfile.DoesNotExist):
            pass
    recipient = (request.POST.get("recipient_email") or default_recipient or "").strip()
    default_subject, default_body, communication_cfg = _phase6_document_message(document, kind)
    subject = (request.POST.get("subject") or default_subject).strip()[:300]
    body = (request.POST.get("message") or default_body).strip()
    try:
        validate_email(recipient)
    except ValidationError:
        _phase5_delivery_failure(document=document, kind=kind, recipient=recipient or "invalid@example.invalid", subject=subject, body=body, error="Ungültige Empfängeradresse", user=request.user, pdf_document=pdf_document)
        messages.error(request, "Bitte eine gültige Empfänger-E-Mail-Adresse eingeben.")
        return False

    ready, reason = _phase5_email_backend_ready()
    if not ready:
        _phase5_delivery_failure(document=document, kind=kind, recipient=recipient, subject=subject, body=body, error=reason, user=request.user, pdf_document=pdf_document)
        messages.error(request, reason)
        return False

    delivery = m.ToolTimeDocumentDelivery.objects.create(
        organization=document.organization,
        quote=document if kind == "quote" else None,
        invoice=document if kind == "invoice" else None,
        document=pdf_document,
        channel="email",
        status="failed",
        recipient_email=recipient,
        subject=subject,
        body_excerpt=body[:1000],
        created_by=request.user,
    )
    try:
        from_address = str(getattr(settings, "DEFAULT_FROM_EMAIL", "") or getattr(settings, "EMAIL_HOST_USER", "") or "").strip() or None
        sender_name = str(communication_cfg.get("sender_name") or document.organization.name or "").strip()
        if from_address and sender_name:
            from_address = formataddr((sender_name, from_address))
        message = EmailMessage(subject=subject, body=body, from_email=from_address, to=[recipient])
        reply_email = str(communication_cfg.get("reply_email") or getattr(document.organization, "email", "") or "").strip()
        if reply_email:
            message.reply_to = [reply_email]
        message.attach(filename, pdf, "application/pdf")
        for attachment_name, attachment_payload, attachment_mime in extra_attachments:
            message.attach(attachment_name, attachment_payload, attachment_mime)
        if xml_attachment:
            message.attach(*xml_attachment)
        message.send(fail_silently=False)
    except Exception as exc:
        delivery.error_message = str(exc)[:500]
        delivery.save(update_fields=["error_message"])
        messages.error(request, "Der E-Mail-Versand ist fehlgeschlagen. Es wurde kein Versandserfolg gespeichert.")
        return False

    delivery.status = "sent"
    delivery.sent_at = timezone.now()
    delivery.error_message = ""
    delivery.save(update_fields=["status", "sent_at", "error_message"])
    if kind == "invoice":
        invoice_compliance_audit(
            document,
            "invoice.emailed",
            user=request.user,
            request=request,
            new={"recipient": recipient, "delivery_id": delivery.pk},
            metadata={"original_pdf_document_id": pdf_document.pk},
        )
    messages.success(request, f"{'Angebot' if kind == 'quote' else 'Rechnung'} wurde per E-Mail an {recipient} gesendet.")
    return True


@login_required
@require_GET
def quote_pdf(request, pk):
    org = _org(request)
    quote = get_object_or_404(m.Quote, organization=org, pk=pk)
    try:
        # A draft PDF is a preview only. It does not allocate/finalize a number and
        # it is never eligible for the e-mail delivery workflow below.
        payload = _phase5_quote_pdf_bytes(quote, require_finalized=False)
    except ValueError as exc:
        messages.error(request, str(exc))
        return redirect("next-quote-edit", pk=quote.pk)
    response = HttpResponse(payload, content_type="application/pdf")
    disposition = "inline" if request.GET.get("preview") == "1" else "attachment"
    response["Content-Disposition"] = f'{disposition}; filename="angebot-{quote.number or quote.pk}.pdf"'
    return response


@login_required
@require_POST
def quote_send_email(request, pk):
    org = _org(request)
    quote = get_object_or_404(m.Quote.objects.select_related("project__customer"), organization=org, pk=pk)
    _phase5_send_email(request, quote, "quote")
    return redirect("next-quote-edit", pk=quote.pk)


@login_required
@require_POST
def invoice_send_email(request, pk):
    org = _org(request)
    invoice = get_object_or_404(m.Invoice.objects.select_related("project__customer"), organization=org, pk=pk)
    _phase5_send_email(request, invoice, "invoice")
    return redirect("next-invoice-edit", pk=invoice.pk)


@login_required
@require_http_methods(["GET", "POST"])
def quote_editor(request, pk=None):
    org = _org(request)
    if request.method == "POST":
        phase7_guard = _phase7_commercial_guard(request, "next-quotes")
        if phase7_guard is not None:
            return phase7_guard
    direct_project = _phase3_prepare_direct_customer(request, org)
    existing = get_object_or_404(m.Quote, pk=pk, organization=org) if pk else None
    _ensure_document_project(request, org)
    if request.method == "POST" and existing is not None:
        meta = meta_for(existing, "quote", create=False)
        if meta and meta.finalized_at and (existing.status == "accepted" or meta.accepted_at):
            messages.error(request, "Ein angenommenes Angebot ist aufbewahrungspflichtig und kann inhaltlich nicht mehr bearbeitet werden.")
            return redirect("next-quote-edit", pk=existing.pk)
    response = base.quote_editor(request, pk)
    _phase3_rearchive_direct_project(direct_project)
    if request.method != "POST" or getattr(response, "status_code", 200) not in {301, 302}:
        return response
    obj_id = pk or _redirect_pk(response)
    if not obj_id: return response
    quote = m.Quote.objects.filter(pk=obj_id, organization=org).first()
    if not quote: return response
    meta = save_document_meta(quote, request, "quote")
    sync_position_extras(quote, request, "quote", request.user)
    action = request.POST.get("action") or "save"
    if action == "finalize":
        finalize_quote(quote)
        messages.success(request, "Angebot wurde fertiggestellt und hat eine fortlaufende Angebotsnummer erhalten.")
    elif meta.finalized_at is None and quote.number:
        quote.number = ""
        quote.status = "draft"
        quote.sent_at = None
        quote.save(update_fields=["number", "status", "sent_at", "updated_at"])
    return redirect("next-quote-edit", pk=quote.pk)


@login_required
@require_POST
def quote_status(request, pk):
    org = _org(request)
    phase7_guard = _phase7_commercial_guard(request, "next-quotes")
    if phase7_guard is not None:
        return phase7_guard
    quote = get_object_or_404(m.Quote, pk=pk, organization=org)
    meta = meta_for(quote, "quote")
    action = (request.POST.get("action") or "").strip()
    if meta.finalized_at is None:
        finalize_quote(quote)
        meta = meta_for(quote, "quote")
    if action == "accepted":
        quote.status = "accepted"
        meta.accepted_at = meta.accepted_at or timezone.now()
        meta.rejected_at = None
        meta.save(update_fields=["accepted_at", "rejected_at", "updated_at"])
        quote.save(update_fields=["status", "updated_at"])
        messages.success(request, "Angebot wurde als angenommen markiert.")
    elif action == "rejected":
        quote.status = "rejected"
        meta.rejected_at = timezone.now()
        meta.save(update_fields=["rejected_at", "updated_at"])
        quote.save(update_fields=["status", "updated_at"])
        messages.success(request, "Angebot wurde als abgelehnt markiert.")
    elif action == "pending":
        if meta.accepted_at:
            messages.error(request, "Ein bereits angenommenes Angebot bleibt aus Aufbewahrungsgründen gesperrt. Erstelle bei Änderungen ein neues Angebot.")
        else:
            quote.status = "sent"
            meta.rejected_at = None
            meta.save(update_fields=["rejected_at", "updated_at"])
            quote.save(update_fields=["status", "updated_at"])
            messages.success(request, "Angebotsstatus wurde auf ausstehend zurückgesetzt.")
    return redirect("next-quote-edit", pk=quote.pk)


@login_required
@require_POST
def quote_to_invoice(request, pk):
    org = _org(request)
    phase7_guard = _phase7_commercial_guard(request, "next-quotes")
    if phase7_guard is not None:
        return phase7_guard
    quote = get_object_or_404(m.Quote.objects.prefetch_related("items", "items__tooltime_mixed_subitems"), pk=pk, organization=org)
    quote_meta = meta_for(quote, "quote")
    if quote.status != "accepted":
        messages.error(request, "Eine Rechnung kann erst nach Annahme des Angebots erstellt werden.")
        return redirect("next-quote-edit", pk=quote.pk)
    order_confirmation = None
    for candidate in m.Document.objects.filter(organization=org, project=quote.project, category="contract").order_by("-pk")[:50]:
        metadata = candidate.metadata or {}
        if metadata.get("kind") == "order_confirmation" and str(metadata.get("quote_id")) == str(quote.pk):
            order_confirmation = candidate
            break
    if order_confirmation is None:
        messages.error(request, "Bitte zuerst die Auftragsbestätigung erstellen.")
        return redirect("next-quote-edit", pk=quote.pk)
    existing_invoice = m.Invoice.objects.filter(organization=org, quote=quote).order_by("pk").first()
    if existing_invoice is not None:
        messages.info(request, "Für dieses Angebot existiert bereits eine Rechnung. Sie wurde geöffnet.")
        return redirect("next-invoice-edit", pk=existing_invoice.pk)
    if quote_meta.finalized_at is None:
        quote_meta = finalize_quote(quote)
    today = timezone.localdate()
    try:
        quote_settings = quote.commercial_settings
        due_days = int(quote_settings.payment_due_days or 0)
    except Exception:
        quote_settings = None
        due_days = int(phase2_settings(org).get("payment_terms", {}).get("days") or 0)
    invoice = m.Invoice.objects.create(
        organization=org,
        project=quote.project,
        quote=quote,
        number="",
        status="draft",
        issue_date=today,
        due_date=today + timedelta(days=max(0, due_days)),
        service_date=today,
        intro_text=quote.intro_text,
        outro_text=quote.outro_text,
        notes=quote.notes,
        created_by=request.user,
    )
    invoice_meta = meta_for(invoice, "invoice")
    invoice_meta.customer = quote_meta.customer or getattr(quote.project, "customer", None)
    invoice_meta.document_title = "Rechnung"
    invoice_meta.labour_cost_share_visible = quote_meta.labour_cost_share_visible
    invoice_meta.save(update_fields=["customer", "document_title", "labour_cost_share_visible", "updated_at"])
    if quote_settings is not None:
        m.CommercialDocumentSettings.objects.create(
            organization=org,
            invoice=invoice,
            tax_code=quote_settings.tax_code,
            tax_rate=quote_settings.tax_rate,
            discount_type=quote_settings.discount_type,
            discount_value=quote_settings.discount_value,
            payment_due_days=quote_settings.payment_due_days,
            early_payment_discount_percent=quote_settings.early_payment_discount_percent,
            early_payment_discount_days=quote_settings.early_payment_discount_days,
            closing_text=quote_settings.closing_text,
        )
    for source in quote.items.select_related("catalog_item").order_by("position", "pk"):
        target = m.InvoiceItem.objects.create(
            invoice=invoice,
            position=source.position,
            description=source.description,
            quantity=source.quantity,
            unit=source.unit,
            unit_price=source.unit_price,
            tax_rate=source.tax_rate,
            catalog_item=source.catalog_item,
        )
        try:
            source_meta = source.commercial_meta
        except Exception:
            source_meta = None
        if source_meta is not None:
            m.CommercialItemMeta.objects.create(
                organization=org,
                invoice_item=target,
                position_type=source_meta.position_type,
                purchase_price=source_meta.purchase_price,
                markup_percent=source_meta.markup_percent,
                service_model=source_meta.service_model,
                detail_text=source_meta.detail_text,
                group_title=source_meta.group_title,
                show_subitems_in_pdf=source_meta.show_subitems_in_pdf,
            )
        for sub in source.tooltime_mixed_subitems.all().order_by("sort_order", "id"):
            m.ToolTimeMixedSubitem.objects.create(
                organization=org,
                invoice_item=target,
                item_type=sub.item_type,
                description=sub.description,
                quantity=sub.quantity,
                unit=sub.unit,
                purchase_price=sub.purchase_price,
                sales_price=sub.sales_price,
                sort_order=sub.sort_order,
            )
    links = list(quote_meta.billing_links or [])
    token = {"kind": "invoice", "id": invoice.pk}
    if token not in links:
        links.append(token)
        quote_meta.billing_links = links
        quote_meta.save(update_fields=["billing_links", "updated_at"])
    if quote.project and quote.project.status not in {"cancelled", "completed"}:
        quote.project.status = "invoiced"
        quote.project.save(update_fields=["status", "updated_at"])
    messages.success(request, "Rechnungsentwurf wurde aus dem Angebot übernommen. Positionen, Gruppen, Kalkulation und Mischpositionen wurden kopiert.")
    return redirect("next-invoice-edit", pk=invoice.pk)


@login_required
@require_http_methods(["GET", "POST"])
def quote_order_confirmation(request, pk):
    org = _org(request)
    phase7_guard = _phase7_commercial_guard(request, "next-quotes")
    if phase7_guard is not None:
        return phase7_guard
    quote = get_object_or_404(m.Quote.objects.select_related("project__customer"), organization=org, pk=pk)
    meta = meta_for(quote, "quote")
    if quote.status != "accepted" or not meta.finalized_at:
        messages.error(request, "Eine Auftragsbestätigung ist erst für ein fertiggestelltes und angenommenes Angebot verfügbar.")
        return redirect("next-quote-edit", pk=quote.pk)
    document = None
    for candidate in m.Document.objects.filter(organization=org, project=quote.project, category="contract").order_by("-pk")[:50]:
        metadata = candidate.metadata or {}
        if metadata.get("kind") == "order_confirmation" and str(metadata.get("quote_id")) == str(quote.pk):
            document = candidate
            break
    if request.method == "POST" and document is None:
        document, created = _phase7_order_confirmation_document(quote, request.user)
        if created:
            messages.success(request, "Auftragsbestätigung wurde erstellt und revisionssicher im Projekt gespeichert.")
    if document is None:
        messages.info(request, "Für dieses Angebot wurde noch keine Auftragsbestätigung erstellt.")
        return redirect("next-quote-edit", pk=quote.pk)
    if not document.file:
        raise Http404("Auftragsbestätigung nicht verfügbar")
    response = FileResponse(document.file.open("rb"), content_type="application/pdf", as_attachment=True, filename=f"auftragsbestaetigung-{quote.number or quote.pk}.pdf")
    response["X-Content-Type-Options"] = "nosniff"
    return response


@login_required
@require_http_methods(["GET", "POST"])
def invoice_editor(request, pk=None):
    org = _org(request)
    if request.method == "POST":
        phase7_guard = _phase7_commercial_guard(request, "next-invoices")
        if phase7_guard is not None:
            return phase7_guard
    direct_project = _phase3_prepare_direct_customer(request, org)
    existing = get_object_or_404(m.Invoice, pk=pk, organization=org) if pk else None
    _ensure_document_project(request, org)
    if request.method == "POST" and existing is not None:
        try:
            if existing.compliance.state in {"finalized", "cancelled", "credited"}:
                return base.invoice_editor(request, pk)
        except Exception:
            pass
        requested = request.POST.get("invoice_type") or "standard"
        ok, reason = invoice_type_allowed(existing, requested)
        if not ok:
            messages.error(request, reason)
            return redirect("next-invoice-edit", pk=existing.pk)
    response = base.invoice_editor(request, pk)
    _phase3_rearchive_direct_project(direct_project)
    if request.method != "POST" or getattr(response, "status_code", 200) not in {301, 302}:
        return response
    obj_id = pk or _redirect_pk(response)
    if not obj_id: return response
    invoice = m.Invoice.objects.filter(pk=obj_id, organization=org).first()
    if not invoice: return response
    requested = request.POST.get("invoice_type") or "standard"
    ok, reason = invoice_type_allowed(invoice, requested)
    if not ok:
        messages.error(request, reason)
        return redirect("next-invoice-edit", pk=invoice.pk)
    save_document_meta(invoice, request, "invoice")
    sync_position_extras(invoice, request, "invoice", request.user)
    return redirect("next-invoice-edit", pk=invoice.pk)


def _quote_item_billed_quantities(quote):
    billed = {}
    metas = m.ToolTimeDocumentMeta.objects.filter(
        organization=quote.organization,
        invoice__project=quote.project,
        invoice__quote=quote,
        invoice_type="partial",
    ).exclude(invoice__status="cancelled")
    for meta in metas:
        for link in meta.billing_links or []:
            try:
                item_id = int(link.get("quote_item_id") or 0)
                quantity = Decimal(str(link.get("quantity") or "0"))
            except Exception:
                continue
            billed[item_id] = billed.get(item_id, Decimal("0")) + quantity
    return billed


def _available_invoice_types(quote):
    existing = set(m.ToolTimeDocumentMeta.objects.filter(
        organization=quote.organization,
        invoice__project=quote.project,
        invoice__quote=quote,
    ).exclude(invoice__status="cancelled").values_list("invoice_type", flat=True))
    result = []
    if "partial" not in existing:
        result.append(("advance", "Abschlagsrechnung", "Anzahlung oder Vorschuss ohne konkrete Leistungszuordnung."))
    if "advance" not in existing:
        result.append(("partial", "Teilrechnung", "Bereits vollständig oder teilweise erbrachte, klar abgegrenzte Leistungen abrechnen."))
    result.append(("final", "Schlussrechnung", "Gesamtabrechnung unter Berücksichtigung bereits erstellter Abschlags- oder Teilrechnungen."))
    return result


def _copy_quote_item_to_invoice(invoice, quote_item, quantity, position):
    item = m.InvoiceItem.objects.create(
        invoice=invoice,
        position=position,
        code=quote_item.code,
        description=quote_item.description,
        quantity=quantity,
        unit=quote_item.unit,
        unit_price=quote_item.unit_price,
        tax_rate=quote_item.tax_rate,
        catalog_item=quote_item.catalog_item,
        ai_generated=False,
        approved=True,
    )
    try:
        src = quote_item.commercial_meta
        m.CommercialItemMeta.objects.create(
            organization=invoice.organization,
            invoice_item=item,
            position_type=src.position_type,
            purchase_price=src.purchase_price,
            markup_percent=src.markup_percent,
            service_model=src.service_model,
            detail_text=src.detail_text,
            group_title=src.group_title,
        )
    except Exception:
        pass
    return item


@login_required
@require_http_methods(["GET", "POST"])
def quote_invoice_wizard(request, pk):
    org = _org(request)
    quote = get_object_or_404(m.Quote.objects.select_related("project", "project__customer"), organization=org, pk=pk)
    quote_meta = meta_for(quote, "quote")
    if not quote_meta.finalized_at:
        messages.error(request, "Bitte das Angebot zuerst fertigstellen.")
        return redirect("next-quote-edit", pk=quote.pk)
    available_types = _available_invoice_types(quote)
    allowed = {row[0] for row in available_types}
    billed = _quote_item_billed_quantities(quote)
    item_rows = []
    for item in quote.items.select_related("catalog_item").order_by("position", "pk"):
        already = billed.get(item.pk, Decimal("0"))
        remaining = max(Decimal("0"), Decimal(str(item.quantity)) - already)
        item.ui_billed_quantity = already
        item.ui_remaining_quantity = remaining
        item_rows.append(item)
    previous = []
    for meta in m.ToolTimeDocumentMeta.objects.filter(organization=org, invoice__project=quote.project, invoice__quote=quote).exclude(invoice__status="cancelled").select_related("invoice").order_by("invoice__issue_date", "invoice__pk"):
        previous.append({"meta": meta, "invoice": meta.invoice, "total": base._invoice_total(meta.invoice)})

    if request.method == "POST":
        invoice_type = (request.POST.get("invoice_type") or "").strip()
        if invoice_type not in allowed:
            messages.error(request, "Diese Rechnungsart ist für den aktuellen Projektstand nicht verfügbar.")
            return redirect("next-quote-invoice-wizard", pk=quote.pk)
        issue_date = timezone.localdate()
        due_days = int(profile_for(org).settings.get("payment_terms", {}).get("days") or 0)
        invoice = m.Invoice.objects.create(
            organization=org,
            project=quote.project,
            quote=quote,
            number="",
            status="draft",
            issue_date=issue_date,
            due_date=issue_date + timedelta(days=due_days),
            service_date=issue_date,
            intro_text="",
            outro_text="",
            notes="",
            created_by=request.user,
        )
        try:
            qsettings = quote.commercial_settings
            settings = m.CommercialDocumentSettings.objects.create(
                organization=org,
                invoice=invoice,
                tax_code=qsettings.tax_code,
                tax_rate=qsettings.tax_rate,
                discount_type="percent",
                discount_value=0,
                payment_due_days=due_days,
                early_payment_discount_percent=qsettings.early_payment_discount_percent,
                early_payment_discount_days=qsettings.early_payment_discount_days,
                closing_text=qsettings.closing_text,
            )
        except Exception:
            settings = m.CommercialDocumentSettings.objects.create(organization=org, invoice=invoice, payment_due_days=due_days)
        meta = m.ToolTimeDocumentMeta.objects.create(
            organization=org,
            invoice=invoice,
            document_title={"advance":"Abschlagsrechnung", "partial":"Teilrechnung", "final":"Schlussrechnung"}[invoice_type],
            salutation="Sehr geehrte Damen und Herren,",
            invoice_type=invoice_type,
            title_suffix=(request.POST.get("title_suffix") or "")[:120],
            web_view_enabled=False,
            labour_cost_share_visible=True,
        )
        links = []
        position = 1
        if invoice_type == "advance":
            quote_total = base._quote_total(quote)["net"]
            mode = request.POST.get("advance_mode") or "percent"
            value = money(request.POST.get("advance_value"))
            amount = quote_total * value / Decimal("100") if mode == "percent" else value
            amount = max(Decimal("0"), min(quote_total, amount)).quantize(Decimal("0.01"))
            if amount <= 0:
                invoice.delete()
                messages.error(request, "Bitte einen gültigen Abschlagsbetrag eingeben.")
                return redirect("next-quote-invoice-wizard", pk=quote.pk)
            m.InvoiceItem.objects.create(invoice=invoice, position=1, code="", description=f"Abschlagszahlung zu Angebot {quote.number}", quantity=1, unit="Pauschal", unit_price=amount, tax_rate=settings.tax_rate, ai_generated=False, approved=True)
            links = [{"kind": "advance", "amount": str(amount), "quote_id": quote.pk}]
        elif invoice_type == "partial":
            selected_any = False
            for row in item_rows:
                raw = request.POST.get(f"quantity_{row.pk}") or "0"
                qty = max(Decimal("0"), Decimal(str(raw).replace(",", ".")))
                if qty <= 0:
                    continue
                remaining = row.ui_remaining_quantity
                if qty > remaining:
                    invoice.delete()
                    messages.error(request, f"Position {row.position}: maximal {remaining} {row.unit} sind noch abrechenbar.")
                    return redirect("next-quote-invoice-wizard", pk=quote.pk)
                _copy_quote_item_to_invoice(invoice, row, qty, position)
                links.append({"kind":"partial", "quote_item_id": row.pk, "quantity": str(qty)})
                position += 1; selected_any = True
            if not selected_any:
                invoice.delete()
                messages.error(request, "Bitte mindestens eine noch offene Leistung auswählen.")
                return redirect("next-quote-invoice-wizard", pk=quote.pk)
        else:
            for row in item_rows:
                _copy_quote_item_to_invoice(invoice, row, row.quantity, position); position += 1
            deductions = []
            for prev in previous:
                if prev["meta"].invoice_type not in {"advance", "partial"}:
                    continue
                net = prev["total"]["net"]
                if net <= 0:
                    continue
                label = "Abschlag" if prev["meta"].invoice_type == "advance" else "Bereits abgerechnete Teilleistung"
                m.InvoiceItem.objects.create(invoice=invoice, position=position, code="", description=f"{label} · {prev['invoice'].number or 'Entwurf'}", quantity=1, unit="Pauschal", unit_price=-net, tax_rate=settings.tax_rate, ai_generated=False, approved=True)
                deductions.append({"invoice_id": prev["invoice"].pk, "amount": str(net), "type": prev["meta"].invoice_type})
                position += 1
            links = [{"kind": "final", "quote_id": quote.pk, "deductions": deductions}]
        meta.billing_links = links; meta.save(update_fields=["billing_links", "updated_at"])
        messages.success(request, f"{meta.get_invoice_type_display()} wurde als Entwurf erstellt. Es wurde noch keine Rechnungsnummer vergeben.")
        return redirect("next-invoice-edit", pk=invoice.pk)

    return render(request, "rebuild/invoice_wizard.html", {"quote": quote, "available_types": available_types, "items": item_rows, "previous": previous, "quote_total": base._quote_total(quote)})


@login_required
@require_http_methods(["GET", "POST"])
def _template_for_org(org, pk):
    return get_object_or_404(m.ToolTimeTextTemplate, organization=org, pk=pk)


def _normalize_template_orders(org, document_kind, text_kind):
    rows = list(m.ToolTimeTextTemplate.objects.filter(
        organization=org,
        document_kind=document_kind,
        text_kind=text_kind,
    ).order_by("sort_order", "id"))
    for index, row in enumerate(rows, 1):
        if row.sort_order != index:
            row.sort_order = index
            row.save(update_fields=["sort_order", "updated_at"])


def _ensure_standard_text_templates(org):
    for document_kind in ("quote", "invoice"):
        for text_kind in ("intro", "closing"):
            qs = m.ToolTimeTextTemplate.objects.filter(
                organization=org,
                document_kind=document_kind,
                text_kind=text_kind,
            )
            standard = qs.filter(is_standard=True).order_by("id").first()
            if standard is None:
                first = qs.order_by("sort_order", "id").first()
                if first is None:
                    first = m.ToolTimeTextTemplate.objects.create(
                        organization=org,
                        document_kind=document_kind,
                        text_kind=text_kind,
                        title="Standard",
                        salutation="Sehr geehrte Damen und Herren," if text_kind == "intro" else "",
                        body="",
                        is_standard=True,
                        sort_order=1,
                    )
                else:
                    first.is_standard = True
                    first.save(update_fields=["is_standard", "updated_at"])
            for duplicate in qs.filter(is_standard=True).exclude(pk=first.pk if standard is None else standard.pk):
                duplicate.is_standard = False
                duplicate.save(update_fields=["is_standard", "updated_at"])
            _normalize_template_orders(org, document_kind, text_kind)


@require_POST
def text_template_create(request):
    _commercial_settings_guard(request)
    org = base._org(request)
    document_kind = request.POST.get("document_kind") or "quote"
    text_kind = request.POST.get("text_kind") or "intro"
    if document_kind not in {"quote", "invoice"} or text_kind not in {"intro", "closing"}:
        return HttpResponseBadRequest("Ungültige Vorlagenart.")
    title = (request.POST.get("title") or "Neue Vorlage").strip()[:120] or "Neue Vorlage"
    row = m.ToolTimeTextTemplate.objects.create(
        organization=org,
        document_kind=document_kind,
        text_kind=text_kind,
        title=title,
        salutation=(request.POST.get("salutation") or "").strip()[:240],
        body=request.POST.get("body") or "",
        is_standard=not m.ToolTimeTextTemplate.objects.filter(
            organization=org, document_kind=document_kind, text_kind=text_kind
        ).exists(),
        sort_order=m.ToolTimeTextTemplate.objects.filter(
            organization=org, document_kind=document_kind, text_kind=text_kind
        ).count() + 1,
    )
    _ensure_standard_text_templates(org)
    messages.success(request, f"Vorlage „{row.title}“ wurde angelegt.")
    return redirect("next-settings")


@require_POST
def text_template_update(request, pk):
    _commercial_settings_guard(request)
    org = base._org(request)
    row = _template_for_org(org, pk)
    row.title = (request.POST.get("title") or row.title).strip()[:120] or row.title
    row.salutation = (request.POST.get("salutation") or "").strip()[:240]
    row.body = request.POST.get("body") or ""
    row.save(update_fields=["title", "salutation", "body", "updated_at"])
    messages.success(request, f"Vorlage „{row.title}“ wurde gespeichert.")
    return redirect("next-settings")


@require_POST
def text_template_delete(request, pk):
    _commercial_settings_guard(request)
    org = base._org(request)
    row = _template_for_org(org, pk)
    if row.is_standard:
        messages.error(request, "Die Standardvorlage kann nicht gelöscht werden. Wähle zuerst eine andere Standardvorlage.")
        return redirect("next-settings")
    document_kind, text_kind = row.document_kind, row.text_kind
    row.delete()
    _normalize_template_orders(org, document_kind, text_kind)
    messages.success(request, "Vorlage wurde gelöscht.")
    return redirect("next-settings")


@require_POST
def text_template_standard(request, pk):
    _commercial_settings_guard(request)
    org = base._org(request)
    row = _template_for_org(org, pk)
    with transaction.atomic():
        m.ToolTimeTextTemplate.objects.filter(
            organization=org,
            document_kind=row.document_kind,
            text_kind=row.text_kind,
            is_standard=True,
        ).exclude(pk=row.pk).update(is_standard=False)
        if not row.is_standard:
            row.is_standard = True
            row.save(update_fields=["is_standard", "updated_at"])
    messages.success(request, f"„{row.title}“ ist jetzt die Standardvorlage.")
    return redirect("next-settings")


@require_POST
def text_template_move(request, pk):
    _commercial_settings_guard(request)
    org = base._org(request)
    row = _template_for_org(org, pk)
    direction = request.POST.get("direction")
    rows = list(m.ToolTimeTextTemplate.objects.filter(
        organization=org,
        document_kind=row.document_kind,
        text_kind=row.text_kind,
    ).order_by("sort_order", "id"))
    try:
        index = rows.index(row)
    except ValueError:
        return redirect("next-settings")
    target_index = index - 1 if direction == "up" else index + 1 if direction == "down" else index
    if 0 <= target_index < len(rows) and target_index != index:
        target = rows[target_index]
        row.sort_order, target.sort_order = target.sort_order, row.sort_order
        row.save(update_fields=["sort_order", "updated_at"])
        target.save(update_fields=["sort_order", "updated_at"])
        _normalize_template_orders(org, row.document_kind, row.text_kind)
    return redirect("next-settings")


def layout_preview(request):
    _commercial_settings_guard(request)
    org = base._org(request)
    cfg = profile_for(org).settings
    _ensure_standard_text_templates(org)
    intro = m.ToolTimeTextTemplate.objects.filter(
        organization=org, document_kind="quote", text_kind="intro", is_standard=True
    ).first()
    closing = m.ToolTimeTextTemplate.objects.filter(
        organization=org, document_kind="quote", text_kind="closing", is_standard=True
    ).first()
    return render(request, "rebuild/tooltime_layout_preview.html", {
        "organization": org,
        "cfg": cfg,
        "intro": intro,
        "closing": closing,
    })


def _phase2_number_preview(org, cfg):
    num = cfg.get("numbering", {})
    def commercial(kind, prefix_key, start_key, width_key):
        start = max(1, int(num.get(start_key) or 1)); width = max(1, int(num.get(width_key) or len(str(start))))
        seq = m.ToolTimeNumberSequence.objects.filter(organization=org, kind=kind).first()
        value = max(start, int(seq.next_value)) if seq else start
        return {"prefix": str(num.get(prefix_key) or ""), "value": value, "width": width, "formatted": f"{str(num.get(prefix_key) or '')}{value:0{width}d}"}
    invoice_start = max(1, int(num.get("invoice_start") or 1)); invoice_width = max(1, int(num.get("invoice_width") or len(str(invoice_start))))
    invoice_prefix = str(num.get("invoice_prefix") or "")
    invoice_seq = m.InvoiceNumberSequence.objects.filter(organization=org, year=0, prefix=invoice_prefix).first()
    invoice_value = max(invoice_start, int(invoice_seq.next_value)) if invoice_seq else invoice_start
    return {
        "quote": commercial("quote", "quote_prefix", "quote_start", "quote_width"),
        "invoice": {"prefix": invoice_prefix, "value": invoice_value, "width": invoice_width, "formatted": f"{invoice_prefix}{invoice_value:0{invoice_width}d}"},
        "credit": commercial("credit", "credit_prefix", "credit_start", "credit_width"),
        "customer": commercial("customer", "customer_prefix", "customer_start", "customer_width"),
    }


def _datev_valid(number, party_type):
    value = str(number or "").strip()
    if len(value) != 5 or not value.isdigit(): return False
    numeric = int(value)
    return 10000 <= numeric <= 69999 if party_type == "customer" else 70000 <= numeric <= 99999


def _next_free_datev(org, party_type, start):
    low, high = (10000, 69999) if party_type == "customer" else (70000, 99999)
    value = max(low, min(int(start), high))
    used = set(m.ToolTimeDatevAccount.objects.filter(organization=org).values_list("account_number", flat=True))
    while value <= high and f"{value:05d}" in used: value += 1
    if value > high: raise ValueError("Der DATEV-Nummernkreis ist ausgeschöpft.")
    return f"{value:05d}"


def _assign_datev_accounts(org, cfg):
    datev = cfg.get("datev", {})
    mode = datev.get("mode") or "automatic"
    created = 0
    for customer in m.Customer.objects.filter(organization=org, active=True).order_by("id"):
        key = str(customer.pk)
        if m.ToolTimeDatevAccount.objects.filter(organization=org, party_type="customer", party_key=key).exists(): continue
        if mode == "customer_number":
            number = str(customer.number or "").strip()
            if not _datev_valid(number, "customer") or m.ToolTimeDatevAccount.objects.filter(organization=org, account_number=number).exists(): continue
        else:
            number = _next_free_datev(org, "customer", datev.get("debtor_start") or 10000)
        m.ToolTimeDatevAccount.objects.create(organization=org, party_type="customer", party_key=key, party_name=customer.display_name, account_number=number, source="customer_number" if mode == "customer_number" else "automatic")
        created += 1
    # A+Bau currently stores suppliers on catalog items. Treat each distinct supplier
    # as a real creditor party until a dedicated supplier master record is selected.
    suppliers = m.CatalogItem.objects.filter(organization=org, active=True).exclude(supplier="").values_list("supplier", flat=True).distinct()
    for supplier in suppliers:
        name = str(supplier or "").strip()
        if not name: continue
        key = name.casefold()[:120]
        if m.ToolTimeDatevAccount.objects.filter(organization=org, party_type="supplier", party_key=key).exists(): continue
        number = _next_free_datev(org, "supplier", datev.get("creditor_start") or 70000)
        m.ToolTimeDatevAccount.objects.create(organization=org, party_type="supplier", party_key=key, party_name=name[:240], account_number=number, source="automatic")
        created += 1
    return created


def _import_datev_csv(org, upload):
    if not upload or upload.size > 2_000_000: raise ValueError("Bitte eine DATEV-CSV mit maximal 2 MB auswählen.")
    raw = upload.read().decode("utf-8-sig", errors="replace")
    sample = raw[:4096]
    try: dialect = csv.Sniffer().sniff(sample, delimiters=";,\t")
    except csv.Error: dialect = csv.excel_semicolon
    rows = csv.DictReader(io.StringIO(raw), dialect=dialect)
    assigned = skipped = 0
    customers_by_number = {str(c.number).strip(): c for c in m.Customer.objects.filter(organization=org, active=True)}
    customers_by_name = {c.display_name.strip().casefold(): c for c in m.Customer.objects.filter(organization=org, active=True)}
    for raw_row in rows:
        row = {str(k or "").strip().lower().replace(" ", "_"): str(v or "").strip() for k, v in raw_row.items()}
        debtor = row.get("debitorennummer") or row.get("debitor") or row.get("debitor_nr")
        creditor = row.get("kreditorennummer") or row.get("kreditor") or row.get("kreditor_nr")
        if debtor:
            customer = customers_by_number.get(row.get("kundennummer") or row.get("kunden_nr") or "") or customers_by_name.get((row.get("kunde") or row.get("name") or "").casefold())
            if customer and _datev_valid(debtor, "customer") and not m.ToolTimeDatevAccount.objects.filter(organization=org, account_number=debtor).exclude(party_type="customer", party_key=str(customer.pk)).exists():
                m.ToolTimeDatevAccount.objects.update_or_create(organization=org, party_type="customer", party_key=str(customer.pk), defaults={"party_name": customer.display_name, "account_number": debtor, "source": "import"}); assigned += 1
            else: skipped += 1
        elif creditor:
            name = row.get("lieferant") or row.get("name") or ""
            if name and _datev_valid(creditor, "supplier") and not m.ToolTimeDatevAccount.objects.filter(organization=org, account_number=creditor).exclude(party_type="supplier", party_key=name.casefold()[:120]).exists():
                m.ToolTimeDatevAccount.objects.update_or_create(organization=org, party_type="supplier", party_key=name.casefold()[:120], defaults={"party_name": name[:240], "account_number": creditor, "source": "import"}); assigned += 1
            else: skipped += 1
    return assigned, skipped


def _commercial_settings_access_allowed(request):
    user = getattr(request, "user", None)
    if user is None:
        return False
    if getattr(user, "is_superuser", False):
        return True
    profile = getattr(user, "profile", None)
    # A field/mobile-worker flag wins over a stale office-like role. This keeps
    # ordinary employees out even if historical user data was not normalized.
    if bool(getattr(profile, "is_mobile_worker", False)):
        return False
    role = str(getattr(profile, "role", "") or "").strip().lower()
    # Company-wide commercial configuration is deliberately stricter than
    # document mutation rights. Technicians and project managers must never see
    # payment-provider, numbering, tax, legal-document or communication secrets.
    return role in {"owner", "admin", "office", "accounting"}


def _commercial_settings_guard(request):
    if not _commercial_settings_access_allowed(request):
        raise PermissionDenied("Unternehmensweite kaufmännische Einstellungen sind für dieses Benutzerkonto nicht freigegeben.")


@login_required
def account_page(request):
    """Safe personal account landing page for field/employee users."""
    return render(request, "rebuild/account.html", {})


def settings_page(request):
    _commercial_settings_guard(request)
    org = _org(request)
    profile = profile_for(org)
    cfg = phase2_settings(org)
    integrations = m.IntegrationConfig.objects.filter(organization=org).order_by("provider")
    if request.method == "POST":
        section = request.POST.get("section") or "all"
        if section == "phase2_numbering":
            num = cfg.setdefault("numbering", {})
            for key in ("quote_prefix", "invoice_prefix", "credit_prefix", "customer_prefix"):
                num[key] = (request.POST.get(key) or "")[:30]
            for key in ("quote_start", "invoice_start", "credit_start", "customer_start"):
                raw = (request.POST.get(key) or "1").strip()
                if not raw.isdigit() or int(raw) < 1:
                    messages.error(request, "„Beginnt bei“ muss eine positive Zahl sein."); return redirect("next-settings")
                num[key] = int(raw); num[key.replace("_start", "_width")] = min(max(len(raw), 1), 12)
            num["customer_auto"] = request.POST.get("customer_auto") == "on"
            profile.settings = cfg; profile.save(update_fields=["settings", "updated_at"])
            messages.success(request, "Nummernkreise wurden gespeichert."); return redirect("next-settings")
        if section == "phase2_datev":
            datev = cfg.setdefault("datev", {})
            enabled = request.POST.get("datev_enabled") == "on"; mode = request.POST.get("datev_mode") or "automatic"
            if mode not in {"automatic", "customer_number", "import"}: mode = "automatic"
            try: debtor_start = int(request.POST.get("debtor_start") or 10000); creditor_start = int(request.POST.get("creditor_start") or 70000)
            except ValueError: messages.error(request, "DATEV-Startnummern müssen numerisch sein."); return redirect("next-settings")
            if not _datev_valid(f"{debtor_start:05d}", "customer") or not _datev_valid(f"{creditor_start:05d}", "supplier"):
                messages.error(request, "Debitoren müssen 10000–69999 und Kreditoren 70000–99999 verwenden."); return redirect("next-settings")
            datev.update({"enabled": enabled, "mode": mode, "debtor_start": debtor_start, "creditor_start": creditor_start, "skr": "04" if request.POST.get("skr") == "04" else "03"})
            profile.settings = cfg; profile.save(update_fields=["settings", "updated_at"])
            assigned = _assign_datev_accounts(org, cfg) if enabled and mode in {"automatic", "customer_number"} else 0
            messages.success(request, f"DATEV-Einstellungen gespeichert. {assigned} Konten wurden neu zugeordnet." if assigned else "DATEV-Einstellungen wurden gespeichert."); return redirect("next-settings")
        if section == "phase2_datev_import":
            if not cfg.get("datev", {}).get("enabled"):
                messages.error(request, "Bitte DATEV zuerst aktivieren."); return redirect("next-settings")
            try: assigned, skipped = _import_datev_csv(org, request.FILES.get("datev_file"))
            except ValueError as exc: messages.error(request, str(exc)); return redirect("next-settings")
            messages.success(request, f"DATEV-Import: {assigned} Konten zugeordnet, {skipped} Zeilen nicht zugeordnet."); return redirect("next-settings")
        if section == "phase2_legal_documents":
            docs = cfg.setdefault("legal_documents", {})
            for field, title, kind, key in (("terms_file", "Allgemeine Geschäftsbedingungen", "terms", "terms_document_id"), ("withdrawal_file", "Widerrufsbelehrung und Muster-Widerrufsformular", "withdrawal", "withdrawal_document_id")):
                upload = request.FILES.get(field)
                if upload:
                    if not upload.name.lower().endswith(".pdf") or upload.size > 1_800_000:
                        messages.error(request, "Rechtliche Dokumente müssen PDF-Dateien mit maximal 1,8 MB sein."); return redirect("next-settings")
                    document = _save_upload_document(org, request, upload, title, kind); docs[key] = document.pk
            for key in ("attach_terms_quote", "attach_terms_invoice", "attach_withdrawal_quote", "attach_withdrawal_invoice"):
                docs[key] = request.POST.get(key) == "on"
            profile.settings = cfg; profile.save(update_fields=["settings", "updated_at"])
            messages.success(request, "Rechtliche Dokumente und Standardanhänge wurden gespeichert."); return redirect("next-settings")
        if section == "phase2_documents":
            cfg.setdefault("web_view", {}).update({"quote_default": request.POST.get("quote_web_default") == "on", "acceptance_email": request.POST.get("acceptance_email") == "on"})
            mode = request.POST.get("payment_mode") or "immediately"
            if mode not in {"none", "immediately", "7", "14", "custom"}: mode = "immediately"
            if mode == "none" or mode == "immediately": days = 0
            elif mode in {"7", "14"}: days = int(mode)
            else:
                try: days = max(0, min(int(request.POST.get("payment_days") or 0), 3650))
                except ValueError: messages.error(request, "Das benutzerdefinierte Zahlungsziel ist ungültig."); return redirect("next-settings")
            areas = request.POST.get("payment_areas") or "invoice"
            if areas not in {"quote", "invoice", "both"}: areas = "invoice"
            cfg.setdefault("payment_terms", {}).update({"mode": mode, "days": days, "areas": areas})
            labour = cfg.setdefault("labour_share", {})
            for key in ("quote_private", "quote_company", "invoice_private", "invoice_company"): labour[key] = request.POST.get(key) == "on"
            profile.settings = cfg; profile.save(update_fields=["settings", "updated_at"])
            messages.success(request, "Webansicht, Zahlungsbedingungen und Lohnkostenanteil wurden gespeichert."); return redirect("next-settings")
        if section == "phase2_tax":
            rates = cfg.setdefault("tax_rates", [])
            action = request.POST.get("tax_action") or "add"
            try: index = int(request.POST.get("tax_index") or -1)
            except ValueError: index = -1
            if action == "delete" and 0 <= index < len(rates):
                rates.pop(index)
            elif action in {"save", "toggle"} and 0 <= index < len(rates):
                row = rates[index]
                if action == "toggle": row["active"] = not bool(row.get("active", True))
                else:
                    title = (request.POST.get("tax_title") or "").strip(); rate = (request.POST.get("tax_rate") or "").strip().replace(",", ".")
                    if not title or not rate: messages.error(request, "Titel und Steuersatz sind erforderlich."); return redirect("next-settings")
                    try: float(rate)
                    except ValueError: messages.error(request, "Der Steuersatz muss numerisch sein."); return redirect("next-settings")
                    row.update({"title": title[:160], "rate": rate[:20], "note": (request.POST.get("tax_note") or "")[:400], "datev_skr03": (request.POST.get("datev_skr03") or "")[:12], "datev_skr04": (request.POST.get("datev_skr04") or "")[:12], "active": request.POST.get("tax_active") == "on"})
            elif action == "add":
                title = (request.POST.get("tax_title") or "").strip(); rate = (request.POST.get("tax_rate") or "").strip().replace(",", ".")
                if not title or not rate: messages.error(request, "Titel und Steuersatz sind erforderlich."); return redirect("next-settings")
                try: float(rate)
                except ValueError: messages.error(request, "Der Steuersatz muss numerisch sein."); return redirect("next-settings")
                rates.append({"title": title[:160], "rate": rate[:20], "note": (request.POST.get("tax_note") or "")[:400], "datev_skr03": (request.POST.get("datev_skr03") or "")[:12], "datev_skr04": (request.POST.get("datev_skr04") or "")[:12], "active": True})
            profile.settings = cfg; profile.save(update_fields=["settings", "updated_at"])
            messages.success(request, "Steuersätze wurden aktualisiert."); return redirect("next-settings")
        if section == "layout":
            cfg["logo"].update({"show": request.POST.get("logo_show") == "on", "position": request.POST.get("logo_position") or "right", "size": request.POST.get("logo_size") or "large"})
            logo = request.FILES.get("logo_file")
            if logo:
                ext = (logo.name.rsplit(".", 1)[-1] if "." in logo.name else "").lower()
                if ext not in {"png", "jpg", "jpeg"} or logo.size > 409600:
                    messages.error(request, "Das Logo muss eine PNG- oder JPG-Datei mit maximal 0,4 MB sein.")
                    return redirect("next-settings")
                org.logo.save(logo.name, logo, save=True)
                cfg.setdefault("logo", {})["show"] = True
            letterhead = request.FILES.get("letterhead_file")
            if letterhead:
                doc = _save_upload_document(org, request, letterhead, "Briefkopf", "letterhead")
                cfg.setdefault("letterhead", {})["document_id"] = doc.pk
                cfg["letterhead"]["show"] = True
            cfg["sender_line"]["show"] = request.POST.get("sender_line_show") == "on"
            columns = []
            for index in range(1, 5):
                heading = (request.POST.get(f"footer_heading_{index}") or "").strip()[:80]
                lines = [line.strip()[:160] for line in (request.POST.get(f"footer_lines_{index}") or "").splitlines() if line.strip()][:6]
                align = request.POST.get(f"footer_align_{index}") or "left"
                if heading or lines:
                    columns.append({"heading": heading, "lines": lines, "align": align if align in {"left", "center", "right"} else "left"})
            cfg["footer"].update({"show": request.POST.get("footer_show") == "on", "mode": request.POST.get("footer_mode") or "standard", "columns": columns})
            org_settings = org.settings if isinstance(org.settings, dict) else {}
            org_settings["document_layout"] = {
                "logo": cfg.get("logo", {}),
                "letterhead": cfg.get("letterhead", {}),
                "sender_line": cfg.get("sender_line", {}),
                "footer": cfg.get("footer", {}),
            }
            if letterhead:
                org_settings["document_layout"]["letterhead"]["url"] = doc.file.url
            org.settings = org_settings
            org.save(update_fields=["settings", "updated_at"])
        elif section == "numbering":
            num = cfg["numbering"]
            for key in ("quote_prefix", "invoice_prefix", "credit_prefix", "customer_prefix"):
                num[key] = (request.POST.get(key) or num.get(key) or "")[:30]
            for key in ("quote_start", "invoice_start", "credit_start", "customer_start"):
                raw = (request.POST.get(key) or str(num.get(key) or 1)).strip()
                try:
                    num[key] = max(1, int(raw))
                    num[key.replace("_start", "_width")] = max(1, min(len(raw), 12))
                except ValueError:
                    pass
            num["customer_auto"] = request.POST.get("customer_auto") == "on"
            num["debtor_creditor_enabled"] = request.POST.get("debtor_creditor_enabled") == "on"
            org_settings = getattr(org, "settings", None)
            if isinstance(org_settings, dict):
                org_settings["invoice_number_prefix"] = num["invoice_prefix"].rstrip("-") or "R"
                org_settings["invoice_number_start"] = num["invoice_start"]
                org.settings = org_settings
                try: org.save(update_fields=["settings"])
                except Exception: pass
        elif section == "documents":
            cfg["web_view"].update({"quote_default": request.POST.get("quote_web_default") == "on", "acceptance_email": request.POST.get("acceptance_email") == "on"})
            cfg["payment_terms"].update({"mode": request.POST.get("payment_mode") or "immediately", "areas": request.POST.get("payment_areas") or "invoice"})
            try: cfg["payment_terms"]["days"] = max(0, int(request.POST.get("payment_days") or 0))
            except ValueError: pass
            labour = cfg["labour_share"]
            for key in ("quote_private", "quote_company", "invoice_private", "invoice_company"):
                labour[key] = request.POST.get(key) == "on"
        elif section == "legal":
            org.legal_name = (request.POST.get("legal_name") or org.legal_name or org.name)[:220]
            org.email = (request.POST.get("company_email") or "").strip()
            org.phone = (request.POST.get("company_phone") or "").strip()[:60]
            org.address = (request.POST.get("company_address") or "").strip()
            org.tax_id = (request.POST.get("tax_number") or "").strip()[:80]
            org.iban = (request.POST.get("iban") or "").strip()[:60]
            settings = org.settings if isinstance(org.settings, dict) else {}
            legal = settings.get("legal") if isinstance(settings.get("legal"), dict) else {}
            for field in ("vat_id", "website", "bic", "bank_name", "register_court", "register_number", "managing_director", "legal_form", "mobile"):
                legal[field] = (request.POST.get(field) or "").strip()
            legal["tax_number"] = org.tax_id
            legal["street"] = org.address
            settings["legal"] = legal
            settings["invoice_legal"] = legal
            org.settings = settings
            org.save(update_fields=["legal_name", "email", "phone", "address", "tax_id", "iban", "settings", "updated_at"])
        elif section == "legal_documents":
            docs = cfg.setdefault("legal_documents", {})
            for field, title, kind in (("terms_file", "Allgemeine Geschäftsbedingungen", "terms"), ("withdrawal_file", "Widerrufsbelehrung und Muster-Widerrufsformular", "withdrawal")):
                upload = request.FILES.get(field)
                if upload:
                    if not upload.name.lower().endswith(".pdf") or upload.size > 1800000:
                        messages.error(request, "Rechtliche Dokumente müssen PDF-Dateien mit maximal 1,8 MB sein.")
                        return redirect("next-settings")
                    document = _save_upload_document(org, request, upload, title, kind)
                    docs["terms_document_id" if kind == "terms" else "withdrawal_document_id"] = document.pk
        elif section == "dunning":
            d = cfg["dunning"]
            for key in ("reminder_days", "first_days", "second_days", "grace_days"):
                try: d[key] = max(0, int(request.POST.get(key) or d.get(key) or 0))
                except ValueError: pass
            d["first_fee"] = str(money(request.POST.get("first_fee")))
            d["second_fee"] = str(money(request.POST.get("second_fee")))
            d["automatic"] = request.POST.get("automatic_dunning") == "on"
        elif section == "pay":
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
        elif section == "communication":
            c = cfg["communication"]
            reply_email = (request.POST.get("reply_email") or "").strip()
            if reply_email:
                try:
                    validate_email(reply_email)
                except ValidationError:
                    messages.error(request, "Bitte eine gültige Antwort-E-Mail-Adresse eingeben.")
                    return redirect("next-settings")
            sms_text = (request.POST.get("sms") or "").strip()
            if len(sms_text) > 160:
                messages.error(request, "Die SMS-Vorlage darf maximal 160 Zeichen enthalten.")
                return redirect("next-settings")
            sms_provider = (request.POST.get("sms_provider") or "disabled").strip().lower()
            if sms_provider not in {"disabled", "webhook"}:
                messages.error(request, "Der ausgewählte SMS-Dienst ist ungültig.")
                return redirect("next-settings")
            sms_endpoint = (request.POST.get("sms_endpoint") or "").strip()
            if sms_provider == "webhook" and not sms_endpoint.startswith("https://"):
                messages.error(request, "Für die SMS-Schnittstelle ist eine HTTPS-Adresse erforderlich.")
                return redirect("next-settings")
            c.update({
                "reply_email": reply_email[:254],
                "sender_name": (request.POST.get("sender_name") or "").strip()[:120],
                "invoice_subject": (request.POST.get("invoice_subject") or "").strip()[:300],
                "invoice_body": request.POST.get("invoice_body") or "",
                "quote_subject": (request.POST.get("quote_subject") or "").strip()[:300],
                "quote_body": request.POST.get("quote_body") or "",
                "sms": sms_text,
                "sms_provider": sms_provider,
                "sms_endpoint": sms_endpoint[:500],
                "sms_sender_id": (request.POST.get("sms_sender_id") or "").strip()[:32],
                "show_logo": request.POST.get("email_show_logo") == "on",
            })
        elif section == "template":
            template_id = request.POST.get("template_id")
            obj = m.ToolTimeTextTemplate.objects.filter(organization=org, pk=template_id).first() if template_id else None
            if obj is None:
                obj = m.ToolTimeTextTemplate(organization=org, document_kind=request.POST.get("document_kind") or "quote", text_kind=request.POST.get("text_kind") or "intro")
            obj.title = (request.POST.get("template_title") or "Standard")[:120]
            obj.salutation = (request.POST.get("template_salutation") or "")[:240]
            obj.body = request.POST.get("template_body") or ""
            obj.save()
        elif section == "tax":
            title = (request.POST.get("tax_title") or "").strip(); rate = (request.POST.get("tax_rate") or "").strip(); note = (request.POST.get("tax_note") or "").strip()
            if title and rate:
                cfg["tax_rates"].append({"rate": rate, "title": title, "note": note, "active": True})
        profile.settings = cfg; profile.save(update_fields=["settings", "updated_at"])
        messages.success(request, "Einstellungen wurden gespeichert.")
        return redirect("next-settings")
    templates = m.ToolTimeTextTemplate.objects.filter(organization=org)
    pay_provider_status_ready, pay_provider_status_reason = pay_provider_ready(org)
    sms_provider_ready, sms_provider_reason = _phase6_sms_provider_ready(org)
    legal = (org.settings or {}).get("legal", {}) if isinstance(org.settings, dict) else {}
    terms = m.Document.objects.filter(organization=org, pk=cfg.get("legal_documents", {}).get("terms_document_id")).first()
    number_previews = _phase2_number_preview(org, cfg)
    datev_stats = {"debtors": m.ToolTimeDatevAccount.objects.filter(organization=org, party_type="customer").count(), "creditors": m.ToolTimeDatevAccount.objects.filter(organization=org, party_type="supplier").count()}
    withdrawal = m.Document.objects.filter(organization=org, pk=cfg.get("legal_documents", {}).get("withdrawal_document_id")).first()
    return render(request, "rebuild/tooltime_settings.html", {"organization": org, "integrations": integrations, "profile": profile, "text_templates": list(m.ToolTimeTextTemplate.objects.filter(organization=org).order_by("document_kind", "text_kind", "sort_order", "id")), "text_template_document_kinds": [("quote", "Angebote"), ("invoice", "Rechnungen")], "text_template_text_kinds": [("intro", "Einleitungstext"), ("closing", "Schlusstext")], "cfg": cfg, "text_templates": templates, "pay_provider_status_ready": pay_provider_status_ready, "pay_provider_status_reason": pay_provider_status_reason, "sms_provider_ready": sms_provider_ready, "sms_provider_reason": sms_provider_reason, "legal": legal, "terms_document": terms, "withdrawal_document": withdrawal, "number_previews": number_previews, "datev_stats": datev_stats})


@login_required
@require_POST
def quick_customer_create(request):
    org = _org(request)
    number = _sequence_number_for_customer(org, request.POST.get("customer_number"))
    customer = m.Customer.objects.create(
        organization=org,
        number=number,
        type=request.POST.get("customer_type") if request.POST.get("customer_type") in {"private", "business", "insurance", "property_manager"} else "private",
        company=(request.POST.get("company") or "")[:180],
        salutation=(request.POST.get("salutation") or "")[:30],
        first_name=(request.POST.get("first_name") or "")[:100],
        last_name=(request.POST.get("last_name") or "")[:100],
        email=(request.POST.get("email") or "").strip(),
        phone=(request.POST.get("phone") or "")[:60],
        mobile=(request.POST.get("mobile") or "")[:60],
        street=(request.POST.get("street") or "")[:180],
        postal_code=(request.POST.get("postal_code") or "")[:20],
        city=(request.POST.get("city") or "")[:120],
        country=(request.POST.get("country") or "DE")[:2].upper(),
    )
    return JsonResponse({"ok": True, "customer": {"id": customer.pk, "number": customer.number, "name": customer.display_name, "address": f"{customer.street}, {customer.postal_code} {customer.city}".strip(", ")}})


@login_required
@require_POST
def quick_project_create(request):
    org = _org(request)
    customer_id = (request.POST.get("customer_id") or "").strip()
    customer = m.Customer.objects.filter(organization=org, active=True, pk=customer_id).first() if customer_id.isdigit() else None
    if customer is None:
        return JsonResponse({"ok": False, "error": "Bitte zuerst einen Kunden auswählen."}, status=400)
    title = (request.POST.get("title") or "").strip()
    if not title:
        return JsonResponse({"ok": False, "error": "Bitte einen Projekttitel eingeben."}, status=400)
    project = m.Project.objects.create(organization=org, customer=customer, number=base._unique_number(m.Project, org, "P"), title=title[:220], status="inquiry")
    return JsonResponse({"ok": True, "project": {"id": project.pk, "number": project.number, "title": project.title, "customer_id": customer.pk, "address": f"{customer.street}, {customer.postal_code} {customer.city}".strip(", ")}})


@login_required
@require_GET
def article_search(request):
    org = _org(request)
    if base._is_field_user(request): return JsonResponse({"ok": False, "error": "Keine Preisberechtigung."}, status=403)
    q = (request.GET.get("q") or "").strip(); source = (request.GET.get("source") or "all").strip(); ptype = (request.GET.get("type") or "all").strip()
    results = []
    if source in {"all", "catalog"}:
        qs = m.CatalogItem.objects.filter(organization=org, active=True)
        if q: qs = qs.filter(Q(name__icontains=q) | Q(code__icontains=q) | Q(description__icontains=q))
        if ptype in {"material", "service"}: qs = qs.filter(kind=ptype)
        for row in qs.order_by("name")[:30]:
            results.append({"source": "Katalog", "kind": "catalog", "id": row.pk, "code": row.code or "", "name": row.name or "", "description": row.description or "", "unit": row.unit or "Stk.", "purchase": str(row.purchase_price or 0), "sales": str(row.sales_price or row.purchase_price or 0), "type": row.kind or "material"})
    if source in {"all", "used"}:
        used = {}
        for model in (m.QuoteItem, m.InvoiceItem):
            qs = model.objects.filter(**({"quote__organization": org} if model is m.QuoteItem else {"invoice__organization": org}))
            if q: qs = qs.filter(description__icontains=q)
            for row in qs.order_by("-pk")[:40]:
                key = (row.description or "").casefold()
                if key and key not in used:
                    used[key] = {"source": "Zuletzt verwendet", "kind": "used", "id": row.pk, "code": row.code or "", "name": row.description or "", "description": "", "unit": row.unit or "Stk.", "purchase": str(row.unit_price or 0), "sales": str(row.unit_price or 0), "type": "material"}
        results.extend(list(used.values())[:30])
    if source in {"all", "own", "reference"} and hasattr(m, "PriceItem"):
        qs = m.PriceItem.objects.filter(organization=org, source__active=True).select_related("source").filter(Q(sales_price__gt=0) | Q(purchase_price__gt=0))
        if q: qs = qs.filter(Q(code__icontains=q) | Q(description__icontains=q))
        for row in qs.order_by("source__name", "description")[:50]:
            label = (getattr(row.source, "name", "") or "Preisliste")
            is_reference = any(token in label.casefold() for token in ("b&o", "b+o", "b und o", "va04", "referenz"))
            if source == "reference" and not is_reference: continue
            if source == "own" and is_reference: continue
            price = row.sales_price if row.sales_price and row.sales_price > 0 else row.purchase_price
            results.append({"source": label, "kind": "price", "id": row.pk, "code": row.code or "", "name": row.description or "", "description": row.description or "", "unit": row.unit or "Stk.", "purchase": str(row.purchase_price or price or 0), "sales": str(price or 0), "type": "material"})
    return JsonResponse({"ok": True, "results": results[:80]})


@login_required
@require_POST
def invoice_dunning(request, pk):
    org = _org(request)
    role = str(getattr(getattr(request.user, "profile", None), "role", "") or "")
    if not (getattr(request.user, "is_superuser", False) or role in {"admin", "office", "project_manager", "accounting"}):
        messages.error(request, "Mahnungen sind nur für Büro, Projektleitung oder Buchhaltung freigegeben.")
        return redirect("next-invoices")
    invoice = get_object_or_404(m.Invoice, organization=org, pk=pk)
    totals = base._invoice_total(invoice); open_amount = totals.get("open", Decimal("0"))
    if open_amount <= 0:
        messages.error(request, "Für eine vollständig bezahlte Rechnung kann keine Mahnung erstellt werden.")
        return redirect("next-invoice-edit", pk=pk)
    level = request.POST.get("level") or "reminder"
    if level not in {"reminder", "first", "second"}: level = "reminder"
    cfg = profile_for(org).settings["dunning"]
    due_days = int(request.POST.get("due_days") or cfg.get({"reminder":"reminder_days","first":"first_days","second":"second_days"}[level], 7))
    fee = Decimal("0") if level == "reminder" else money(request.POST.get("fee") or cfg.get("first_fee" if level == "first" else "second_fee", 0))
    customer = invoice.project.customer
    heading = {"reminder":"Zahlungserinnerung","first":"1. Mahnung","second":"2. Mahnung"}[level]
    due = timezone.localdate() + timedelta(days=due_days)

    fee_html = f"<p>Mahngebühr: <strong>{fee:.2f} €</strong></p>" if fee else ""
    html = (
        f"<html><body style=\"font-family:Arial,sans-serif;font-size:12px\"><h1>{heading}</h1>"
        f"<p>Rechnung: <strong>{invoice.number}</strong></p><p>Sehr geehrte Damen und Herren,</p>"
        f"<p>für die oben genannte Rechnung ist aktuell ein offener Betrag von <strong>{open_amount:.2f} €</strong> vorhanden.</p>"
        f"<p>Bitte überweisen Sie den offenen Betrag bis spätestens <strong>{due:%d.%m.%Y}</strong>.</p>"
        + fee_html
        + f"<p>Mit freundlichen Grüßen<br>{org.name}</p></body></html>"
    )

    pdf = html_to_pdf_bytes(inject_business_pdf_identity(html, org, document=invoice, kind="invoice"))
    doc = m.Document(organization=org, customer=customer, project=invoice.project, title=f"{heading} · {invoice.number}", category="other", mime_type="application/pdf", size=len(pdf), metadata={"kind":"dunning","level":level,"invoice_id":invoice.pk}, uploaded_by=request.user)
    doc.file.save(f"{heading.lower().replace(' ', '-')}-{invoice.pk}.pdf", ContentFile(pdf), save=False); doc.save()
    email = getattr(customer, "email", "") or ""
    record = m.ToolTimeDunningRecord.objects.create(organization=org, invoice=invoice, level=level, due_days=due_days, fee=fee, internal_note=request.POST.get("internal_note") or "", recipient_email=email, document=doc, created_by=request.user)
    if request.POST.get("delivery") == "email":
        if not email:
            messages.error(request, "Beim Kunden ist keine E-Mail-Adresse hinterlegt. Das Mahnschreiben wurde gespeichert, aber nicht versendet.")
        else:
            try:
                message = EmailMessage(subject=f"{heading} zu Rechnung {invoice.number}", body=f"Sehr geehrte Damen und Herren,\n\nanbei erhalten Sie {heading.lower()} zu Rechnung {invoice.number}.\n\nMit freundlichen Grüßen\n{org.name}", to=[email])
                message.attach(f"{heading}-{invoice.number}.pdf", pdf, "application/pdf")
                message.send(fail_silently=False)
                record.sent_at = timezone.now(); record.save(update_fields=["sent_at"])
                messages.success(request, f"{heading} wurde erstellt und per E-Mail versendet.")
                return redirect("next-invoice-edit", pk=pk)
            except Exception:
                messages.error(request, "Das Mahnschreiben wurde gespeichert, konnte aber nicht per E-Mail versendet werden.")
    messages.success(request, f"{heading} wurde erstellt und bei der Rechnung gespeichert.")
    return redirect("next-invoice-edit", pk=pk)


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


def _phase8_productive_mail_ready():
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


@require_http_methods(["GET", "POST"])
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


# A+BAU TOOLTIME PHASE 4 LIFECYCLE 2026-08-20

def _phase7_can_commercially_mutate(request):
    if getattr(request.user, "is_superuser", False):
        return True
    role = str(getattr(getattr(request.user, "profile", None), "role", "") or "")
    return role in {"admin", "office", "project_manager", "accounting"}


def _phase7_commercial_guard(request, redirect_name="next-quotes"):
    if _phase7_can_commercially_mutate(request):
        return None
    messages.error(request, "Diese kaufmännische Aktion ist nur für Büro, Projektleitung oder Buchhaltung freigegeben.")
    return redirect(redirect_name)


def _phase7_order_confirmation_document(quote, user):
    for existing in m.Document.objects.filter(
        organization=quote.organization,
        project=quote.project,
        category="contract",
    ).order_by("-pk")[:50]:
        metadata = existing.metadata or {}
        if metadata.get("kind") == "order_confirmation" and str(metadata.get("quote_id")) == str(quote.pk):
            return existing, False

    customer = _phase5_customer(quote, "quote")
    totals = base._quote_total(quote)
    gross = money(totals.get("gross", totals.get("net", 0)) or 0)
    rows = []
    for item in quote.items.all().order_by("position", "pk"):
        quantity = getattr(item, "quantity", 0) or 0
        unit_price = money(getattr(item, "unit_price", 0) or 0)
        line_total = money(quantity * unit_price)
        rows.append(
            "<tr>"
            f"<td>{html.escape(str(getattr(item, 'position', '') or ''))}</td>"
            f"<td>{html.escape(str(getattr(item, 'description', '') or ''))}</td>"
            f"<td style='text-align:right'>{html.escape(str(quantity))} {html.escape(str(getattr(item, 'unit', '') or ''))}</td>"
            f"<td style='text-align:right'>{line_total:.2f} €</td>"
            "</tr>"
        )
    customer_name = getattr(customer, "display_name", "") if customer else ""
    project_label = f"{quote.project.number} · {quote.project.title}" if quote.project_id else ""
    accepted_at = meta_for(quote, "quote").accepted_at
    accepted_label = timezone.localtime(accepted_at).strftime("%d.%m.%Y %H:%M") if accepted_at else timezone.localtime().strftime("%d.%m.%Y %H:%M")
    body = f"""<html><body style="font-family:Arial,sans-serif;font-size:11px;color:#202428">
<h1>Auftragsbestätigung</h1>
<p>Angebot: <strong>{html.escape(quote.number or '')}</strong></p>
<p>Kunde: <strong>{html.escape(str(customer_name))}</strong></p>
<p>Projekt: {html.escape(project_label)}</p>
<p>Wir bestätigen die Beauftragung auf Grundlage des angenommenen Angebots. Annahme: {html.escape(accepted_label)}.</p>
<table style="width:100%;border-collapse:collapse" cellpadding="6"><thead><tr style="border-bottom:1px solid #bbb"><th>Pos.</th><th style="text-align:left">Leistung</th><th style="text-align:right">Menge</th><th style="text-align:right">Gesamt</th></tr></thead><tbody>{''.join(rows)}</tbody></table>
<p style="font-size:13px;margin-top:18px">Auftragssumme <strong style="float:right">{gross:.2f} €</strong></p>
<p style="margin-top:36px">Mit freundlichen Grüßen<br>{html.escape(quote.organization.name)}</p>
</body></html>"""
    payload = html_to_pdf_bytes(inject_business_pdf_identity(body, org=quote.organization, document_kind="Auftragsbestätigung"))
    filename = f"auftragsbestaetigung-{quote.number or quote.pk}.pdf"
    document = m.Document(
        organization=quote.organization,
        project=quote.project,
        customer=customer,
        title=f"Auftragsbestätigung · {quote.number or quote.pk}",
        category="contract",
        mime_type="application/pdf",
        size=len(payload),
        sha256=hashlib.sha256(payload).hexdigest(),
        metadata={
            "kind": "order_confirmation",
            "quote_id": quote.pk,
            "quote_number": quote.number or "",
            "immutable": True,
            "accepted_at": accepted_at.isoformat() if accepted_at else "",
        },
        uploaded_by=user,
    )
    document.file.save(filename, ContentFile(payload), save=False)
    document.save()
    project = quote.project
    if project and project.status not in {"cancelled", "completed", "invoiced"}:
        project.status = "confirmed"
        project.save(update_fields=["status", "updated_at"])
    m.ActivityLog.objects.create(
        organization=quote.organization,
        user=user,
        verb="quote.order_confirmation.created",
        entity_type="quote",
        entity_id=str(quote.pk),
        description=f"Auftragsbestätigung für Angebot {quote.number or quote.pk} erstellt.",
        metadata={"document_id": document.pk, "project_id": quote.project_id},
    )
    return document, True


def _phase4_customer(document, meta=None):
    if meta is not None and getattr(meta, "customer_id", None):
        return meta.customer
    project = getattr(document, "project", None)
    return getattr(project, "customer", None)


def _phase4_project_label(document):
    project = getattr(document, "project", None)
    if project is None:
        return "Ohne Projekt"
    title = (getattr(project, "title", "") or "").strip()
    if title.startswith("Direktdokumente · Kunde") or title == "Allgemeiner Auftrag":
        return "Ohne Projekt"
    number = (getattr(project, "number", "") or "").strip()
    return f"{number} · {title}" if number else (title or "Ohne Projekt")


def _phase4_invoice_compliance_state(invoice):
    try:
        return invoice.compliance.state or "draft"
    except Exception:
        return "draft"


def _phase4_invoice_display(invoice, totals):
    state = _phase4_invoice_compliance_state(invoice)
    if state == "cancelled":
        return "Storniert", "cancelled"
    if state == "credited":
        return "Gutgeschrieben", "credited"
    if state != "finalized":
        return "Entwurf", "draft"
    open_amount = totals.get("open", Decimal("0")) or Decimal("0")
    if open_amount <= 0:
        return "Bezahlt", "paid"
    if invoice.due_date and invoice.due_date < timezone.localdate():
        return "Überfällig", "overdue"
    return "Unbezahlt", "unpaid"


@login_required
def quote_list(request):
    org = _org(request)
    query = (request.GET.get("q") or "").strip()
    status = (request.GET.get("status") or "all").strip()
    sort = (request.GET.get("sort") or "date_desc").strip()
    qs = m.Quote.objects.filter(organization=org).select_related("project__customer").order_by("-created_at")
    if query:
        qs = qs.filter(
            Q(number__icontains=query)
            | Q(project__number__icontains=query)
            | Q(project__title__icontains=query)
            | Q(project__customer__company__icontains=query)
            | Q(project__customer__first_name__icontains=query)
            | Q(project__customer__last_name__icontains=query)
        )
    if status in {"draft", "sent", "accepted", "rejected"}:
        qs = qs.filter(status=status)
    rows = []
    for quote in qs[:500]:
        totals = base._quote_total(quote)
        meta = meta_for(quote, "quote", create=False)
        customer = _phase4_customer(quote, meta)
        rows.append({
            "quote": quote,
            "meta": meta,
            "customer": customer,
            "project_label": _phase4_project_label(quote),
            "total": totals.get("gross", totals.get("net", Decimal("0"))) or Decimal("0"),
            "finalized": bool(meta and meta.finalized_at),
        })
    if sort == "amount_desc":
        rows.sort(key=lambda row: row["total"], reverse=True)
    elif sort == "amount_asc":
        rows.sort(key=lambda row: row["total"])
    elif sort == "date_asc":
        rows.sort(key=lambda row: (row["quote"].issue_date, row["quote"].pk))
    return render(request, "rebuild/quotes.html", {"rows": rows, "q": query, "status_filter": status, "sort": sort})


@login_required
def invoice_list(request):
    org = _org(request)
    if _phase7_can_commercially_mutate(request):
        run_automatic_dunning(org, created_by=request.user)
    query = (request.GET.get("q") or "").strip()
    status = (request.GET.get("status") or "all").strip()
    sort = (request.GET.get("sort") or "date_desc").strip()
    qs = m.Invoice.objects.filter(organization=org).select_related("project__customer").order_by("-created_at")
    if query:
        qs = qs.filter(
            Q(number__icontains=query)
            | Q(project__number__icontains=query)
            | Q(project__title__icontains=query)
            | Q(project__customer__company__icontains=query)
            | Q(project__customer__first_name__icontains=query)
            | Q(project__customer__last_name__icontains=query)
        )
    rows = []
    for invoice in qs[:500]:
        totals = base._invoice_total(invoice)
        meta = meta_for(invoice, "invoice", create=False)
        display_status, status_key = _phase4_invoice_display(invoice, totals)
        if status in {"draft", "unpaid", "overdue", "paid", "cancelled", "credited"} and status_key != status:
            continue
        customer = _phase4_customer(invoice, meta)
        rows.append({
            "invoice": invoice,
            "meta": meta,
            "customer": customer,
            "project_label": _phase4_project_label(invoice),
            "gross": totals.get("gross", totals.get("net", Decimal("0"))) or Decimal("0"),
            "open": totals.get("open", Decimal("0")) or Decimal("0"),
            "status": display_status,
            "status_key": status_key,
            "can_pay": status_key in {"unpaid", "overdue"},
            "can_dun": status_key in {"unpaid", "overdue"},
        })
    if sort == "open_desc":
        rows.sort(key=lambda row: row["open"], reverse=True)
    elif sort == "open_asc":
        rows.sort(key=lambda row: row["open"])
    elif sort == "amount_desc":
        rows.sort(key=lambda row: row["gross"], reverse=True)
    elif sort == "amount_asc":
        rows.sort(key=lambda row: row["gross"])
    elif sort == "date_asc":
        rows.sort(key=lambda row: (row["invoice"].issue_date, row["invoice"].pk))
    pay_ready, pay_reason = pay_provider_ready(org)
    pay_cfg = pay_settings(org)
    for row in rows: row["pay_online"] = bool(pay_ready and row.get("can_pay"))
    return render(request, "rebuild/invoices.html", {"rows": rows, "q": query, "status_filter": status, "sort": sort, "today": timezone.localdate(), "pay_ready": pay_ready, "pay_reason": pay_reason, "pay_cfg": pay_cfg, "card_limit": pay_cfg.get("card_limit")})


@login_required
@require_POST
def invoice_payment(request, pk):
    org = _org(request)
    phase7_guard = _phase7_commercial_guard(request, "next-invoices")
    if phase7_guard is not None:
        return phase7_guard
    invoice = get_object_or_404(m.Invoice.objects.select_related("project__customer"), organization=org, pk=pk)
    if _phase4_invoice_compliance_state(invoice) != "finalized":
        messages.error(request, "Zahlungen können nur für fertiggestellte Rechnungen erfasst werden.")
        return redirect("next-invoices")
    totals = base._invoice_total(invoice)
    open_amount = totals.get("open", Decimal("0")) or Decimal("0")
    if open_amount <= 0:
        messages.error(request, "Diese Rechnung ist bereits vollständig bezahlt.")
        return redirect("next-invoices")
    try:
        amount = money(request.POST.get("amount") or "0")
    except Exception:
        amount = Decimal("0")
    if amount <= 0:
        messages.error(request, "Bitte einen positiven Zahlbetrag eingeben.")
        return redirect("next-invoices")
    if amount > open_amount:
        messages.error(request, "Der Zahlbetrag darf den aktuell ausstehenden Betrag nicht überschreiten.")
        return redirect("next-invoices")
    paid_raw = (request.POST.get("paid_at") or "").strip()
    if paid_raw:
        try:
            paid_at = date.fromisoformat(paid_raw)
        except ValueError:
            messages.error(request, "Das Zahlungsdatum ist ungültig.")
            return redirect("next-invoices")
    else:
        paid_at = timezone.localdate()
    method = (request.POST.get("method") or "Überweisung").strip()[:40]
    if method not in {"Überweisung", "Bar", "Karte", "Lastschrift", "Sonstiges"}:
        method = "Sonstiges"
    reference = (request.POST.get("reference") or "").strip()[:240]
    m.Payment.objects.create(
        invoice=invoice,
        amount=amount,
        paid_at=paid_at,
        method=method,
        reference=reference,
        recorded_by=request.user,
    )
    after = base._invoice_total(invoice)
    invoice.status = "paid" if (after.get("open", Decimal("0")) or Decimal("0")) <= 0 else "partial"
    invoice.save(update_fields=["status", "updated_at"])
    if invoice.status == "paid" and invoice.project and invoice.project.status not in {"cancelled", "completed"}:
        invoice.project.status = "completed"
        invoice.project.progress = 100
        invoice.project.save(update_fields=["status", "progress", "updated_at"])
    messages.success(request, "Zahlung wurde verbucht. Teilzahlungen können jederzeit ergänzt werden.")
    return redirect("next-invoices")


# A+BAU TOOLTIME QUOTES EXACT PARITY 2026-08-21

def _tt_quote_title(quote, meta=None):
    """Return a stable visible quote title without requiring a schema migration."""
    candidates = []
    for source in (quote, meta):
        if source is None:
            continue
        for attr in ("title", "subject", "document_title", "heading", "name"):
            value = getattr(source, attr, None)
            if isinstance(value, str) and value.strip():
                candidates.append(value.strip())
    if candidates:
        return candidates[0]
    return "Kostenvoranschlag" if getattr(quote, "number", "") else "Angebot"


def _tt_quote_customer_label(customer):
    if customer is None:
        return ""
    display = getattr(customer, "display_name", None)
    if callable(display):
        try:
            display = display()
        except TypeError:
            pass
    if isinstance(display, str) and display.strip():
        return display.strip()
    company = (getattr(customer, "company", "") or "").strip()
    person = " ".join(
        value.strip()
        for value in (getattr(customer, "first_name", "") or "", getattr(customer, "last_name", "") or "")
        if value.strip()
    )
    return company or person or ""


def _tt_quote_last_change(quote):
    return getattr(quote, "updated_at", None) or getattr(quote, "created_at", None)


def _tt_quote_relative_change(value):
    if value is None:
        return "—"
    try:
        now = timezone.now()
        if timezone.is_naive(value):
            value = timezone.make_aware(value, timezone.get_current_timezone())
        seconds = max(0, int((now - value).total_seconds()))
    except Exception:
        return "—"
    if seconds < 60:
        return "gerade eben"
    minutes = seconds // 60
    if minutes < 60:
        return f"vor {minutes} Min."
    hours = minutes // 60
    if hours < 24:
        return f"vor {hours} Std."
    days = hours // 24
    if days == 1:
        return "vor einem Tag"
    if days < 14:
        return f"vor {days} Tagen"
    return value.strftime("%d.%m.%Y")


def _tt_quote_status(quote):
    raw = (getattr(quote, "status", "") or "draft").lower()
    if raw == "draft":
        return "Entwurf", "draft"
    if raw in {"sent", "pending"}:
        return "Ausstehend", "pending"
    if raw == "accepted":
        return "Angenommen", "accepted"
    if raw in {"rejected", "declined", "expired"}:
        return "Abgelehnt", "rejected"
    return getattr(quote, "get_status_display", lambda: raw.title())(), raw


def _tt_quote_sort_key(row, key):
    if key.startswith("amount"):
        return row["total"]
    if key.startswith("date"):
        return row["quote"].issue_date
    return row["last_change"] or row["quote"].issue_date


@login_required
def quote_list(request):
    """ToolTime-style quote index: status/period filters, last-change sorting and offset paging."""
    from datetime import date as _date, timedelta as _timedelta
    from urllib.parse import urlencode

    org = _org(request)
    query = (request.GET.get("q") or "").strip()
    status = (request.GET.get("status") or "all").strip().lower()
    period = (request.GET.get("period") or "any").strip().lower()
    sort = (request.GET.get("sort") or "last_change_desc").strip().lower()

    try:
        amount = int(request.GET.get("amount") or 20)
    except (TypeError, ValueError):
        amount = 20
    if amount not in {20, 50, 100}:
        amount = 20
    try:
        offset = max(0, int(request.GET.get("offset") or 0))
    except (TypeError, ValueError):
        offset = 0

    qs = m.Quote.objects.filter(organization=org).select_related("project__customer").order_by("-created_at", "-pk")
    if status == "draft":
        qs = qs.filter(status="draft")
    elif status == "pending":
        qs = qs.filter(status__in=("sent", "pending"))
    elif status == "accepted":
        qs = qs.filter(status="accepted")
    elif status == "rejected":
        qs = qs.filter(status__in=("rejected", "declined", "expired"))

    today = timezone.localdate()
    if period == "7d":
        qs = qs.filter(issue_date__gte=today - _timedelta(days=7))
    elif period == "30d":
        qs = qs.filter(issue_date__gte=today - _timedelta(days=30))
    elif period == "90d":
        qs = qs.filter(issue_date__gte=today - _timedelta(days=90))
    elif period == "year":
        qs = qs.filter(issue_date__gte=_date(today.year, 1, 1), issue_date__lte=today)

    rows = []
    # Sorting by amount and quote title is computed from commercial metadata, so the
    # bounded set is intentionally materialized before the final 20/50/100-row page.
    for quote in qs[:2000]:
        totals = base._quote_total(quote)
        meta = meta_for(quote, "quote", create=False)
        customer = _phase4_customer(quote, meta)
        status_label, status_key = _tt_quote_status(quote)
        last_change = _tt_quote_last_change(quote)
        row = {
            "quote": quote,
            "meta": meta,
            "customer": customer,
            "customer_label": _tt_quote_customer_label(customer),
            "quote_title": _tt_quote_title(quote, meta),
            "total": totals.get("gross", totals.get("net", Decimal("0"))) or Decimal("0"),
            "status": status_label,
            "status_key": status_key,
            "last_change": last_change,
            "last_change_label": _tt_quote_relative_change(last_change),
            "finalized": bool(meta and getattr(meta, "finalized_at", None)),
        }
        if query:
            project = getattr(quote, "project", None)
            searchable = " ".join(
                str(value or "")
                for value in (
                    getattr(quote, "number", ""),
                    row["quote_title"],
                    row["customer_label"],
                    getattr(project, "number", "") if project else "",
                    getattr(project, "title", "") if project else "",
                )
            ).casefold()
            if query.casefold() not in searchable:
                continue
        rows.append(row)

    reverse = not sort.endswith("_asc")
    if sort not in {"last_change_desc", "last_change_asc", "date_desc", "date_asc", "amount_desc", "amount_asc"}:
        sort = "last_change_desc"
        reverse = True
    rows.sort(key=lambda row: (_tt_quote_sort_key(row, sort), row["quote"].pk), reverse=reverse)

    total_count = len(rows)
    if offset >= total_count and total_count:
        offset = max(0, ((total_count - 1) // amount) * amount)
    page_rows = rows[offset: offset + amount]
    first_item = offset + 1 if total_count else 0
    last_item = min(offset + amount, total_count)
    prev_offset = max(0, offset - amount)
    next_offset = offset + amount if offset + amount < total_count else None

    params = {
        "q": query,
        "status": status,
        "period": period,
        "sort": sort,
        "amount": amount,
    }
    query_tail = urlencode({key: value for key, value in params.items() if value not in ("", "all", "any")})
    last_change_next_sort = "last_change_asc" if sort == "last_change_desc" else "last_change_desc"
    last_change_params = dict(params)
    last_change_params["sort"] = last_change_next_sort
    last_change_query = urlencode({key: value for key, value in last_change_params.items() if value not in ("", "all", "any")})

    return render(
        request,
        "rebuild/quotes.html",
        {
            "rows": page_rows,
            "q": query,
            "status_filter": status,
            "period_filter": period,
            "sort": sort,
            "amount": amount,
            "offset": offset,
            "total_count": total_count,
            "first_item": first_item,
            "last_item": last_item,
            "prev_offset": prev_offset,
            "next_offset": next_offset,
            "query_tail": query_tail,
            "last_change_query": last_change_query,
            "last_change_next_sort": last_change_next_sort,
        },
    )


# A+BAU TOOLTIME QUOTE POST-DRAFT DETAIL 2026-09-07

def _quote_detail_decimal(value):
    try:
        return Decimal(str(value or 0)).quantize(Decimal("0.01"))
    except Exception:
        return Decimal("0.00")


def _quote_detail_status(quote):
    raw = str(getattr(quote, "status", "") or "draft").lower()
    labels = {
        "draft": ("Entwurf", "draft"),
        "sent": ("Ausstehend", "pending"),
        "pending": ("Ausstehend", "pending"),
        "accepted": ("Angenommen", "accepted"),
        "rejected": ("Abgelehnt", "rejected"),
        "declined": ("Abgelehnt", "rejected"),
        "expired": ("Abgelaufen", "rejected"),
    }
    return labels.get(raw, (raw.replace("_", " ").title(), raw))


def _quote_detail_customer_name(customer):
    if customer is None:
        return "—"
    display = getattr(customer, "display_name", "")
    if callable(display):
        try:
            display = display()
        except TypeError:
            pass
    if str(display or "").strip():
        return str(display).strip()
    company = str(getattr(customer, "company", "") or "").strip()
    person = " ".join(filter(None, [str(getattr(customer, "first_name", "") or "").strip(), str(getattr(customer, "last_name", "") or "").strip()]))
    return company or person or "—"


def _quote_detail_context(quote, meta):
    totals = base._quote_total(quote)
    net = _quote_detail_decimal(totals.get("net", 0))
    gross = _quote_detail_decimal(totals.get("gross", net))
    tax = _quote_detail_decimal(totals.get("tax", gross - net))
    customer = _phase4_customer(quote, meta)
    project = getattr(quote, "project", None)
    status_label, status_key = _quote_detail_status(quote)

    rows = []
    for item in quote.items.all().order_by("position", "pk"):
        quantity = getattr(item, "quantity", 0) or 0
        unit_price = _quote_detail_decimal(getattr(item, "unit_price", 0))
        try:
            line_total = _quote_detail_decimal(quantity * unit_price)
        except Exception:
            line_total = Decimal("0.00")
        rows.append({
            "item": item,
            "quantity": quantity,
            "unit_price": unit_price,
            "line_total": line_total,
            "tax_rate": getattr(item, "tax_rate", 0) or 0,
        })

    try:
        commercial = quote.commercial_settings
    except Exception:
        commercial = None
    payment_due_days = getattr(commercial, "payment_due_days", None) if commercial else None
    early_percent = getattr(commercial, "early_payment_discount_percent", None) if commercial else None
    early_days = getattr(commercial, "early_payment_discount_days", None) if commercial else None
    discount_type = str(getattr(commercial, "discount_type", "") or "") if commercial else ""
    discount_value = getattr(commercial, "discount_value", None) if commercial else None

    deliveries = []
    if hasattr(m, "ToolTimeDocumentDelivery"):
        deliveries = list(
            m.ToolTimeDocumentDelivery.objects.filter(organization=quote.organization, quote=quote)
            .select_related("document")
            .order_by("-created_at", "-id")[:8]
        )

    customer_address = " · ".join(filter(None, [
        str(getattr(customer, "street", "") or "").strip() if customer else "",
        " ".join(filter(None, [
            str(getattr(customer, "postal_code", "") or "").strip() if customer else "",
            str(getattr(customer, "city", "") or "").strip() if customer else "",
        ])),
    ]))
    project_label = _phase4_project_label(quote)
    if project_label == "Ohne Projekt":
        project = None

    return {
        "quote": quote,
        "document": quote,
        "meta": meta,
        "items": rows,
        "net": net,
        "tax": tax,
        "gross": gross,
        "customer": customer,
        "customer_name": _quote_detail_customer_name(customer),
        "customer_address": customer_address,
        "project": project,
        "project_label": project_label,
        "status_label": status_label,
        "status_key": status_key,
        "commercial": commercial,
        "payment_due_days": payment_due_days,
        "early_percent": early_percent,
        "early_days": early_days,
        "discount_type": discount_type,
        "discount_value": discount_value,
        "deliveries": deliveries,
        "recipient_email": str(getattr(customer, "email", "") or "") if customer else "",
        "document_title": str(getattr(meta, "document_title", "") or "Angebot") if meta else "Angebot",
        "finalized_at": getattr(meta, "finalized_at", None) if meta else None,
    }


@login_required
@require_http_methods(["GET", "POST"])
def quote_workspace(request, pk):
    """Keep drafts in the ToolTime editor and render every post-draft quote as a document."""
    org = _org(request)
    quote = get_object_or_404(
        m.Quote.objects.select_related("project__customer").prefetch_related("items"),
        organization=org,
        pk=pk,
    )
    meta = meta_for(quote, "quote", create=False)
    is_editable_draft = str(getattr(quote, "status", "") or "draft").lower() == "draft" and not bool(meta and meta.finalized_at)
    if is_editable_draft:
        return quote_editor(request, pk)
    if request.method != "GET":
        messages.info(request, "Fertiggestellte Angebote werden als Dokument angezeigt und nicht mehr im Entwurfseditor bearbeitet.")
        return redirect("next-quote-edit", pk=quote.pk)
    return render(request, "rebuild/quote_detail.html", _quote_detail_context(quote, meta))


# A+BAU TOOLTIME DOCUMENT WORKSPACE FINAL 2026-09-08

def _tt_document_decimal(value):
    try:
        return Decimal(str(value or 0)).quantize(Decimal("0.01"))
    except Exception:
        return Decimal("0.00")


def _tt_customer_label(customer):
    if customer is None:
        return "—"
    display = getattr(customer, "display_name", "")
    if callable(display):
        try:
            display = display()
        except TypeError:
            pass
    display = str(display or "").strip()
    if display:
        return display
    company = str(getattr(customer, "company", "") or "").strip()
    person = " ".join(filter(None, [
        str(getattr(customer, "first_name", "") or "").strip(),
        str(getattr(customer, "last_name", "") or "").strip(),
    ]))
    return company or person or "—"


def _tt_customer_address(customer):
    if customer is None:
        return ""
    street = str(getattr(customer, "street", "") or "").strip()
    city = " ".join(filter(None, [
        str(getattr(customer, "postal_code", "") or "").strip(),
        str(getattr(customer, "city", "") or "").strip(),
    ]))
    return " · ".join(filter(None, [street, city]))


@login_required
@require_GET
@xframe_options_sameorigin
def quote_preview(request, pk):
    """Dedicated same-origin inline preview. The normal PDF route remains a download."""
    org = _org(request)
    quote = get_object_or_404(m.Quote, organization=org, pk=pk)
    try:
        payload = _phase5_quote_pdf_bytes(quote, require_finalized=False)
    except ValueError as exc:
        raise Http404(str(exc)) from exc
    response = HttpResponse(payload, content_type="application/pdf")
    response["Content-Disposition"] = f'inline; filename="angebot-{quote.number or quote.pk}.pdf"'
    response["Cache-Control"] = "private, no-store"
    return response


@login_required
@require_GET
@xframe_options_sameorigin
def invoice_preview(request, pk):
    """Serve the immutable compliance PDF inline without touching the download endpoint."""
    org = _org(request)
    invoice = get_object_or_404(m.Invoice, organization=org, pk=pk)
    compliance = get_compliance(invoice)
    if not compliance or compliance.state == "draft" or not compliance.original_pdf_document_id:
        raise Http404("Für diese Rechnung ist noch kein finalisiertes Original-PDF vorhanden.")
    document = compliance.original_pdf_document
    if not document or not getattr(document, "file", None):
        raise Http404("Das Original-PDF ist nicht verfügbar.")
    try:
        with document.file.open("rb") as handle:
            payload = handle.read()
    except (OSError, ValueError) as exc:
        raise Http404("Das Original-PDF konnte nicht gelesen werden.") from exc
    filename = document.title or f"rechnung-{compliance.final_number or invoice.number or invoice.pk}.pdf"
    response = HttpResponse(payload, content_type="application/pdf")
    response["Content-Disposition"] = f'inline; filename="{filename.replace(chr(34), "")}"'
    response["Cache-Control"] = "private, no-store"
    return response


def _tt_invoice_detail_context(invoice, compliance):
    totals = base._invoice_total(invoice)
    net = _tt_document_decimal(totals.get("net", 0))
    gross = _tt_document_decimal(totals.get("gross", net))
    tax = _tt_document_decimal(totals.get("tax", gross - net))
    paid = _tt_document_decimal(totals.get("paid", 0))
    open_amount = _tt_document_decimal(totals.get("open", gross - paid))
    meta = meta_for(invoice, "invoice", create=False)
    customer = _phase4_customer(invoice, meta)
    project = getattr(invoice, "project", None)
    project_label = _phase4_project_label(invoice)
    if project_label == "Ohne Projekt":
        project = None
    status_label, status_key = _phase4_invoice_display(invoice, totals)

    deliveries = []
    if hasattr(m, "ToolTimeDocumentDelivery"):
        deliveries = list(
            m.ToolTimeDocumentDelivery.objects.filter(organization=invoice.organization, invoice=invoice)
            .select_related("document")
            .order_by("-created_at", "-id")[:8]
        )

    try:
        commercial = invoice.commercial_settings
    except Exception:
        commercial = None

    payments = []
    payment_manager = getattr(invoice, "payments", None)
    if payment_manager is not None:
        try:
            payments = list(payment_manager.all().order_by("-paid_at", "-pk")[:10])
        except Exception:
            payments = []

    return {
        "invoice": invoice,
        "document": invoice,
        "meta": meta,
        "compliance": compliance,
        "customer": customer,
        "customer_name": _tt_customer_label(customer),
        "customer_address": _tt_customer_address(customer),
        "project": project,
        "project_label": project_label,
        "status_label": status_label,
        "status_key": status_key,
        "net": net,
        "tax": tax,
        "gross": gross,
        "paid": paid,
        "open_amount": open_amount,
        "commercial": commercial,
        "payments": payments,
        "deliveries": deliveries,
        "recipient_email": str(getattr(customer, "email", "") or "") if customer else "",
        "today": timezone.localdate(),
    }


@login_required
@require_http_methods(["GET", "POST"])
def invoice_workspace(request, pk):
    """ToolTime lifecycle: only drafts are editable; finalized invoices are documents."""
    org = _org(request)
    invoice = get_object_or_404(
        m.Invoice.objects.select_related("project__customer"),
        organization=org,
        pk=pk,
    )
    compliance = get_compliance(invoice)
    compliance_state = getattr(compliance, "state", "draft") if compliance else "draft"
    if compliance_state == "draft":
        return invoice_editor(request, pk)
    if request.method != "GET":
        messages.info(request, "Finalisierte Rechnungen werden als unveränderliches Dokument angezeigt.")
        return redirect("next-invoice-edit", pk=invoice.pk)
    return render(request, "rebuild/invoice_detail.html", _tt_invoice_detail_context(invoice, compliance))
