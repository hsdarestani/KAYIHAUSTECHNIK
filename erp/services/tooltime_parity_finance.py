from __future__ import annotations

import secrets
from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.utils import timezone

from erp import models as m


def money(value):
    try:
        return Decimal(str(value or "0").replace(",", ".")).quantize(Decimal("0.01"))
    except (InvalidOperation, TypeError, ValueError):
        return Decimal("0.00")


def default_settings():
    return {
        "logo": {"show": True, "position": "right", "size": "large", "document_id": None},
        "letterhead": {"show": False, "document_id": None},
        "sender_line": {"show": True},
        "footer": {"show": True, "mode": "standard", "columns": []},
        "numbering": {
            "quote_prefix": "A-", "quote_start": 1, "quote_width": 1,
            "invoice_prefix": "R-", "invoice_start": 1, "invoice_width": 1,
            "credit_prefix": "GS-", "credit_start": 1, "credit_width": 1,
            "customer_auto": False, "customer_prefix": "K-", "customer_start": 1, "customer_width": 1,
            "debtor_creditor_enabled": False,
        },
        "datev": {"enabled": False, "mode": "automatic", "debtor_start": 10000, "creditor_start": 70000, "skr": "03"},
        "legal_documents": {"terms_document_id": None, "withdrawal_document_id": None, "attach_terms_quote": False, "attach_terms_invoice": False, "attach_withdrawal_quote": False, "attach_withdrawal_invoice": False},
        "web_view": {"quote_default": True, "acceptance_email": True},
        "payment_terms": {"mode": "immediately", "days": 0, "areas": "invoice"},
        "labour_share": {"quote_private": True, "quote_company": False, "invoice_private": True, "invoice_company": False},
        "tax_rates": [
            {"rate": "19", "title": "19 % Umsatzsteuer", "note": "", "active": True},
            {"rate": "7", "title": "7 % Umsatzsteuer", "note": "", "active": True},
            {"rate": "0", "title": "0 % gemäß § 19 UStG", "note": "Gemäß § 19 UStG wird keine Umsatzsteuer berechnet.", "active": True},
            {"rate": "0", "title": "0 % gemäß § 13b UStG", "note": "Steuerschuldnerschaft des Leistungsempfängers (§ 13b UStG).", "active": True},
        ],
        "dunning": {"reminder_days": 7, "first_days": 7, "first_fee": "3.00", "second_days": 7, "second_fee": "3.00", "automatic": False, "grace_days": 1},
        "pay": {"provider": "disabled", "endpoint": "", "card_limit": "2000.00", "qr_enabled": True, "payout_mode": "aggregated"},
        "communication": {
            "reply_email": "", "sender_name": "", "show_logo": True,
            "invoice_subject": "Ihre Rechnung von {{ company_name }} ({{ invoice_number }})",
            "invoice_body": "Sehr geehrte Damen und Herren,\n\nwie besprochen schicken wir Ihnen die Rechnung mit der Nummer {{ invoice_number }}. Sie finden das Dokument im Anhang.\n\nMit freundlichen Grüßen\n{{ company_name }}",
            "quote_subject": "Ihr Angebot von {{ company_name }} ({{ quote_number }})",
            "quote_body": "Sehr geehrte Damen und Herren,\n\nanbei erhalten Sie unser Angebot {{ quote_number }}.\n\nMit freundlichen Grüßen\n{{ company_name }}",
            "sms": "Hallo. Wir bestätigen Ihren Termin am {{ date }}, {{ time }}. {{ address }}",
            "sms_provider": "disabled", "sms_endpoint": "", "sms_sender_id": "",
        },
        "legal_documents": {"terms_document_id": None, "withdrawal_document_id": None},
    }


def profile_for(org):
    profile, _ = m.ToolTimeCommercialProfile.objects.get_or_create(organization=org, defaults={"settings": default_settings()})
    base = default_settings()
    current = profile.settings if isinstance(profile.settings, dict) else {}
    for key, value in current.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            base[key].update(value)
        else:
            base[key] = value
    if base != current:
        profile.settings = base
        profile.save(update_fields=["settings", "updated_at"])
    return profile


def phase2_settings(org):
    profile = profile_for(org)
    cfg = profile.settings
    changed = False
    defaults = {
        "datev": {"enabled": False, "mode": "automatic", "debtor_start": 10000, "creditor_start": 70000, "skr": "03"},
        "legal_documents": {"terms_document_id": None, "withdrawal_document_id": None, "attach_terms_quote": False, "attach_terms_invoice": False, "attach_withdrawal_quote": False, "attach_withdrawal_invoice": False},
    }
    for key, value in defaults.items():
        if key not in cfg or not isinstance(cfg.get(key), dict):
            cfg[key] = dict(value); changed = True
        else:
            for subkey, subvalue in value.items():
                if subkey not in cfg[key]: cfg[key][subkey] = subvalue; changed = True
    for rate in cfg.get("tax_rates", []):
        if "active" not in rate: rate["active"] = True; changed = True
        if "note" not in rate: rate["note"] = ""; changed = True
        if "datev_skr03" not in rate: rate["datev_skr03"] = ""; changed = True
        if "datev_skr04" not in rate: rate["datev_skr04"] = ""; changed = True
    if changed:
        profile.settings = cfg
        profile.save(update_fields=["settings", "updated_at"])
    return cfg


def default_legal_attachment_ids(org, kind):
    cfg = phase2_settings(org).get("legal_documents", {})
    result = []
    if cfg.get(f"attach_terms_{kind}") and cfg.get("terms_document_id"):
        result.append(int(cfg["terms_document_id"]))
    if cfg.get(f"attach_withdrawal_{kind}") and cfg.get("withdrawal_document_id"):
        result.append(int(cfg["withdrawal_document_id"]))
    return result


def meta_for(document, kind, create=True):
    if document is None:
        return None
    try:
        return document.tooltime_meta
    except Exception:
        if not create:
            return None
    lookup = {"quote": document} if kind == "quote" else {"invoice": document}
    cfg = phase2_settings(document.organization)
    customer = getattr(getattr(document, "project", None), "customer", None)
    is_company = bool(customer and getattr(customer, "type", "") in {"business", "insurance", "property_manager"})
    labour_key = ("quote_company" if is_company else "quote_private") if kind == "quote" else ("invoice_company" if is_company else "invoice_private")
    defaults = {
        "document_title": "Angebot" if kind == "quote" else "Rechnung",
        "salutation": "Sehr geehrte Damen und Herren,",
        "web_view_enabled": bool(cfg.get("web_view", {}).get("quote_default", True)) if kind == "quote" else False,
        "labour_cost_share_visible": bool(cfg.get("labour_share", {}).get(labour_key, True)),
        "default_attachment_ids": default_legal_attachment_ids(document.organization, kind),
    }
    meta, _ = m.ToolTimeDocumentMeta.objects.get_or_create(organization=document.organization, defaults=defaults, **lookup)
    return meta


def save_document_meta(document, request, kind):
    meta = meta_for(document, kind)
    if meta.finalized_at is None:
        meta.default_attachment_ids = default_legal_attachment_ids(document.organization, kind)
    profile = profile_for(document.organization).settings
    customer_id = (request.POST.get("customer_id") or "").strip()
    if customer_id.isdigit():
        meta.customer = m.Customer.objects.filter(organization=document.organization, active=True, pk=int(customer_id)).first()
    elif getattr(document, "project_id", None):
        meta.customer = getattr(document.project, "customer", None)
    meta.document_title = (request.POST.get("document_title") or meta.document_title or ("Angebot" if kind == "quote" else "Rechnung"))[:240]
    meta.salutation = (request.POST.get("document_salutation") or meta.salutation or "Sehr geehrte Damen und Herren,")[:240]
    meta.web_view_enabled = request.POST.get("web_view_enabled") in {"1", "on", "true", "yes"}
    if "web_view_enabled" not in request.POST and kind == "quote" and not meta.pk:
        meta.web_view_enabled = bool(profile.get("web_view", {}).get("quote_default", True))
    meta.labour_cost_share_visible = request.POST.get("labour_cost_share_visible") in {"1", "on", "true", "yes"}
    if kind == "invoice":
        meta.automatic_dunning_disabled = request.POST.get("automatic_dunning_disabled") == "on"
        invoice_type = (request.POST.get("invoice_type") or meta.invoice_type or "standard").strip()
        if invoice_type in {"standard", "advance", "partial", "final"}:
            meta.invoice_type = invoice_type
        meta.title_suffix = (request.POST.get("invoice_title_suffix") or meta.title_suffix or "")[:120]
    if not meta.web_token:
        meta.web_token = secrets.token_urlsafe(28)
    meta.save()
    return meta


def sync_position_extras(document, request, kind, user=None):
    items = list(document.items.order_by("position", "pk"))
    uploads = request.FILES.getlist("item_image")
    add_flags = request.POST.getlist("item_add_catalog")
    for index, item in enumerate(items):
        upload = uploads[index] if index < len(uploads) else None
        if upload and getattr(upload, "size", 0):
            doc = m.Document(organization=document.organization, customer=document.project.customer if document.project_id else None, project=document.project if document.project_id else None, title=upload.name, category="photo", mime_type=getattr(upload, "content_type", "") or "", size=getattr(upload, "size", 0) or 0, metadata={"source": "tooltime-position", "kind": kind, "position": item.position}, uploaded_by=user if getattr(user, "is_authenticated", False) else None)
            doc.file.save(upload.name, upload, save=False); doc.save()
            lookup = {"quote_item": item} if kind == "quote" else {"invoice_item": item}
            m.ToolTimePositionAsset.objects.update_or_create(organization=document.organization, defaults={"document": doc}, **lookup)
        flag = add_flags[index] if index < len(add_flags) else ""
        if flag in {"1", "on", "true"}:
            try: meta = item.commercial_meta
            except Exception: meta = None
            name = (item.description or "").strip()
            if name and not m.CatalogItem.objects.filter(organization=document.organization, name__iexact=name).exists():
                m.CatalogItem.objects.create(organization=document.organization, code="", name=name, description=getattr(meta, "detail_text", "") if meta else "", unit=item.unit or "Stk.", kind="service" if getattr(meta, "position_type", "") == "labour" else "material", purchase_price=getattr(meta, "purchase_price", 0) if meta else 0, sales_price=item.unit_price, tax_rate=item.tax_rate, active=True)


def _number_settings(org, kind):
    cfg = profile_for(org).settings.get("numbering", {})
    if kind == "quote": return str(cfg.get("quote_prefix") or "A-")[:30], int(cfg.get("quote_start") or 1), int(cfg.get("quote_width") or 1)
    if kind == "credit": return str(cfg.get("credit_prefix") or "GS-")[:30], int(cfg.get("credit_start") or 1), int(cfg.get("credit_width") or 1)
    return str(cfg.get("customer_prefix") or "K-")[:30], int(cfg.get("customer_start") or 1), int(cfg.get("customer_width") or 1)


def allocate_number(org, kind):
    prefix, start, width = _number_settings(org, kind)
    with transaction.atomic():
        seq, created = m.ToolTimeNumberSequence.objects.select_for_update().get_or_create(organization=org, kind=kind, defaults={"prefix": prefix, "next_value": max(1, start), "width": max(1, width)})
        if created is False and seq.prefix != prefix:
            seq.prefix = prefix
        if seq.next_value < start:
            seq.next_value = start
        value = seq.next_value
        seq.next_value = value + 1
        seq.width = max(1, width)
        seq.save(update_fields=["prefix", "next_value", "width", "updated_at"])
    return f"{prefix}{value:0{seq.width}d}"


def finalize_quote(quote):
    meta = meta_for(quote, "quote")
    if not quote.number:
        quote.number = allocate_number(quote.organization, "quote")
    meta.final_number = quote.number
    meta.finalized_at = meta.finalized_at or timezone.now()
    if not meta.web_token:
        meta.web_token = secrets.token_urlsafe(28)
    meta.save()
    if quote.status == "draft":
        quote.status = "sent"
    quote.sent_at = quote.sent_at or timezone.now()
    quote.save(update_fields=["number", "status", "sent_at", "updated_at"])
    return meta


def invoice_type_allowed(invoice, requested):
    if requested not in {"standard", "advance", "partial", "final"} or not invoice.project_id:
        return True, ""
    rows = m.ToolTimeDocumentMeta.objects.filter(organization=invoice.organization, invoice__project_id=invoice.project_id).exclude(invoice=invoice).exclude(invoice__status="cancelled")
    existing = set(rows.values_list("invoice_type", flat=True))
    if requested == "advance" and "partial" in existing:
        return False, "Abschlags- und Teilrechnungen können innerhalb desselben Projekts nicht kombiniert werden."
    if requested == "partial" and "advance" in existing:
        return False, "Abschlags- und Teilrechnungen können innerhalb desselben Projekts nicht kombiniert werden."
    return True, ""
