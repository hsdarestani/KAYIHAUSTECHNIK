from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MARKER = "A+BAU TOOLTIME FINANCE PARITY 2026-08-20"


def read(rel: str) -> str:
    path = ROOT / rel
    if not path.exists():
        raise RuntimeError(f"ToolTime-Parität: Datei fehlt: {rel}")
    return path.read_text(encoding="utf-8")


def write(rel: str, text: str) -> None:
    path = ROOT / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def install_models() -> None:
    write("erp/tooltime_parity_finance.py", r'''from __future__ import annotations

from django.conf import settings
from django.db import models


class ToolTimeCommercialProfile(models.Model):
    organization = models.OneToOneField("erp.Organization", on_delete=models.CASCADE, related_name="tooltime_commercial_profile")
    settings = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class ToolTimeDocumentMeta(models.Model):
    INVOICE_TYPES = [
        ("standard", "Standardrechnung"),
        ("advance", "Abschlagsrechnung"),
        ("partial", "Teilrechnung"),
        ("final", "Schlussrechnung"),
    ]
    organization = models.ForeignKey("erp.Organization", on_delete=models.CASCADE, related_name="tooltime_document_meta")
    quote = models.OneToOneField("erp.Quote", null=True, blank=True, on_delete=models.CASCADE, related_name="tooltime_meta")
    invoice = models.OneToOneField("erp.Invoice", null=True, blank=True, on_delete=models.CASCADE, related_name="tooltime_meta")
    document_title = models.CharField(max_length=240, blank=True)
    salutation = models.CharField(max_length=240, blank=True)
    web_view_enabled = models.BooleanField(default=True)
    labour_cost_share_visible = models.BooleanField(default=True)
    invoice_type = models.CharField(max_length=20, choices=INVOICE_TYPES, default="standard")
    title_suffix = models.CharField(max_length=120, blank=True)
    final_number = models.CharField(max_length=80, blank=True)
    finalized_at = models.DateTimeField(null=True, blank=True)
    web_token = models.CharField(max_length=80, blank=True, unique=True, null=True)
    accepted_at = models.DateTimeField(null=True, blank=True)
    rejected_at = models.DateTimeField(null=True, blank=True)
    billing_links = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class ToolTimeNumberSequence(models.Model):
    KINDS = [("quote", "Angebot"), ("credit", "Gutschrift"), ("customer", "Kunde")]
    organization = models.ForeignKey("erp.Organization", on_delete=models.CASCADE, related_name="tooltime_number_sequences")
    kind = models.CharField(max_length=20, choices=KINDS)
    prefix = models.CharField(max_length=30, blank=True)
    next_value = models.PositiveBigIntegerField(default=1)
    width = models.PositiveSmallIntegerField(default=1)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["organization", "kind"], name="uniq_tooltime_number_sequence")]


class ToolTimeTextTemplate(models.Model):
    DOCUMENTS = [("quote", "Angebote"), ("invoice", "Rechnungen")]
    KINDS = [("intro", "Einleitungstext"), ("closing", "Schlusstext")]
    organization = models.ForeignKey("erp.Organization", on_delete=models.CASCADE, related_name="tooltime_text_templates")
    document_kind = models.CharField(max_length=20, choices=DOCUMENTS)
    text_kind = models.CharField(max_length=20, choices=KINDS)
    title = models.CharField(max_length=120, default="Standard")
    salutation = models.CharField(max_length=240, blank=True)
    body = models.TextField(blank=True)
    is_standard = models.BooleanField(default=False)
    sort_order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["document_kind", "text_kind", "sort_order", "id"]


class ToolTimeDunningRecord(models.Model):
    LEVELS = [("reminder", "Zahlungserinnerung"), ("first", "1. Mahnung"), ("second", "2. Mahnung")]
    organization = models.ForeignKey("erp.Organization", on_delete=models.CASCADE, related_name="tooltime_dunning_records")
    invoice = models.ForeignKey("erp.Invoice", on_delete=models.PROTECT, related_name="tooltime_dunning_records")
    level = models.CharField(max_length=20, choices=LEVELS)
    due_days = models.PositiveIntegerField(default=7)
    fee = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    internal_note = models.TextField(blank=True)
    recipient_email = models.EmailField(blank=True)
    document = models.ForeignKey("erp.Document", null=True, blank=True, on_delete=models.PROTECT, related_name="tooltime_dunning_records")
    sent_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="tooltime_dunning_created")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "id"]


class ToolTimePositionAsset(models.Model):
    organization = models.ForeignKey("erp.Organization", on_delete=models.CASCADE, related_name="tooltime_position_assets")
    quote_item = models.OneToOneField("erp.QuoteItem", null=True, blank=True, on_delete=models.CASCADE, related_name="tooltime_asset")
    invoice_item = models.OneToOneField("erp.InvoiceItem", null=True, blank=True, on_delete=models.CASCADE, related_name="tooltime_asset")
    document = models.ForeignKey("erp.Document", on_delete=models.CASCADE, related_name="tooltime_position_assets")
    created_at = models.DateTimeField(auto_now_add=True)
''')

    rel = "erp/models.py"
    text = read(rel)
    line = "from .tooltime_parity_finance import ToolTimeCommercialProfile, ToolTimeDocumentMeta, ToolTimeNumberSequence, ToolTimeTextTemplate, ToolTimeDunningRecord, ToolTimePositionAsset"
    if line not in text:
        text = text.rstrip() + "\n\n# ToolTime-Funktionsparität für kaufmännische Dokumente.\n" + line + "\n"
        write(rel, text)

    write("erp/migrations/0013_tooltime_finance_parity.py", r'''from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("erp", "0012_invoice_germany_compliance"),
    ]
    operations = [
        migrations.CreateModel(name="ToolTimeCommercialProfile", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ("settings", models.JSONField(blank=True, default=dict)),
            ("created_at", models.DateTimeField(auto_now_add=True)),
            ("updated_at", models.DateTimeField(auto_now=True)),
            ("organization", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="tooltime_commercial_profile", to="erp.organization")),
        ]),
        migrations.CreateModel(name="ToolTimeNumberSequence", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ("kind", models.CharField(choices=[("quote", "Angebot"), ("credit", "Gutschrift"), ("customer", "Kunde")], max_length=20)),
            ("prefix", models.CharField(blank=True, max_length=30)),
            ("next_value", models.PositiveBigIntegerField(default=1)),
            ("width", models.PositiveSmallIntegerField(default=1)),
            ("updated_at", models.DateTimeField(auto_now=True)),
            ("organization", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="tooltime_number_sequences", to="erp.organization")),
        ]),
        migrations.CreateModel(name="ToolTimeTextTemplate", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ("document_kind", models.CharField(choices=[("quote", "Angebote"), ("invoice", "Rechnungen")], max_length=20)),
            ("text_kind", models.CharField(choices=[("intro", "Einleitungstext"), ("closing", "Schlusstext")], max_length=20)),
            ("title", models.CharField(default="Standard", max_length=120)),
            ("salutation", models.CharField(blank=True, max_length=240)),
            ("body", models.TextField(blank=True)),
            ("is_standard", models.BooleanField(default=False)),
            ("sort_order", models.PositiveIntegerField(default=0)),
            ("created_at", models.DateTimeField(auto_now_add=True)),
            ("updated_at", models.DateTimeField(auto_now=True)),
            ("organization", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="tooltime_text_templates", to="erp.organization")),
        ], options={"ordering": ["document_kind", "text_kind", "sort_order", "id"]}),
        migrations.CreateModel(name="ToolTimeDocumentMeta", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ("document_title", models.CharField(blank=True, max_length=240)),
            ("salutation", models.CharField(blank=True, max_length=240)),
            ("web_view_enabled", models.BooleanField(default=True)),
            ("labour_cost_share_visible", models.BooleanField(default=True)),
            ("invoice_type", models.CharField(choices=[("standard", "Standardrechnung"), ("advance", "Abschlagsrechnung"), ("partial", "Teilrechnung"), ("final", "Schlussrechnung")], default="standard", max_length=20)),
            ("title_suffix", models.CharField(blank=True, max_length=120)),
            ("final_number", models.CharField(blank=True, max_length=80)),
            ("finalized_at", models.DateTimeField(blank=True, null=True)),
            ("web_token", models.CharField(blank=True, max_length=80, null=True, unique=True)),
            ("accepted_at", models.DateTimeField(blank=True, null=True)),
            ("rejected_at", models.DateTimeField(blank=True, null=True)),
            ("billing_links", models.JSONField(blank=True, default=list)),
            ("created_at", models.DateTimeField(auto_now_add=True)),
            ("updated_at", models.DateTimeField(auto_now=True)),
            ("invoice", models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="tooltime_meta", to="erp.invoice")),
            ("organization", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="tooltime_document_meta", to="erp.organization")),
            ("quote", models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="tooltime_meta", to="erp.quote")),
        ]),
        migrations.CreateModel(name="ToolTimeDunningRecord", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ("level", models.CharField(choices=[("reminder", "Zahlungserinnerung"), ("first", "1. Mahnung"), ("second", "2. Mahnung")], max_length=20)),
            ("due_days", models.PositiveIntegerField(default=7)),
            ("fee", models.DecimalField(decimal_places=2, default=0, max_digits=12)),
            ("internal_note", models.TextField(blank=True)),
            ("recipient_email", models.EmailField(blank=True, max_length=254)),
            ("sent_at", models.DateTimeField(blank=True, null=True)),
            ("created_at", models.DateTimeField(auto_now_add=True)),
            ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="tooltime_dunning_created", to=settings.AUTH_USER_MODEL)),
            ("document", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="tooltime_dunning_records", to="erp.document")),
            ("invoice", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="tooltime_dunning_records", to="erp.invoice")),
            ("organization", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="tooltime_dunning_records", to="erp.organization")),
        ], options={"ordering": ["created_at", "id"]}),
        migrations.CreateModel(name="ToolTimePositionAsset", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ("created_at", models.DateTimeField(auto_now_add=True)),
            ("document", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="tooltime_position_assets", to="erp.document")),
            ("invoice_item", models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="tooltime_asset", to="erp.invoiceitem")),
            ("organization", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="tooltime_position_assets", to="erp.organization")),
            ("quote_item", models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="tooltime_asset", to="erp.quoteitem")),
        ]),
        migrations.AddConstraint(model_name="tooltimenumbersequence", constraint=models.UniqueConstraint(fields=("organization", "kind"), name="uniq_tooltime_number_sequence")),
    ]
''')


def install_service() -> None:
    write("erp/services/tooltime_parity_finance.py", r'''from __future__ import annotations

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
        "sender_line": {"show": True},
        "footer": {"show": True, "mode": "standard", "columns": []},
        "numbering": {
            "quote_prefix": "A-", "quote_start": 1,
            "invoice_prefix": "R-", "invoice_start": 1,
            "credit_prefix": "GS-", "credit_start": 1,
            "customer_auto": False, "customer_prefix": "K-", "customer_start": 1,
            "debtor_creditor_enabled": False,
        },
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
        "communication": {
            "reply_email": "", "show_logo": True,
            "invoice_subject": "Ihre Rechnung von {{ company_name }} ({{ invoice_number }})",
            "invoice_body": "Sehr geehrte Damen und Herren,\n\nwie besprochen schicken wir Ihnen die Rechnung mit der Nummer {{ invoice_number }}. Sie finden das Dokument im Anhang.\n\nMit freundlichen Grüßen\n{{ company_name }}",
            "quote_subject": "Ihr Angebot von {{ company_name }} ({{ quote_number }})",
            "quote_body": "Sehr geehrte Damen und Herren,\n\nanbei erhalten Sie unser Angebot {{ quote_number }}.\n\nMit freundlichen Grüßen\n{{ company_name }}",
            "sms": "Hallo. Wir bestätigen Ihren Termin am {{ date }}, {{ time }}. {{ address }}",
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


def meta_for(document, kind, create=True):
    if document is None:
        return None
    try:
        return document.tooltime_meta
    except Exception:
        if not create:
            return None
    lookup = {"quote": document} if kind == "quote" else {"invoice": document}
    defaults = {"document_title": "Angebot" if kind == "quote" else "Rechnung", "salutation": "Sehr geehrte Damen und Herren,"}
    meta, _ = m.ToolTimeDocumentMeta.objects.get_or_create(organization=document.organization, defaults=defaults, **lookup)
    return meta


def save_document_meta(document, request, kind):
    meta = meta_for(document, kind)
    profile = profile_for(document.organization).settings
    meta.document_title = (request.POST.get("document_title") or meta.document_title or ("Angebot" if kind == "quote" else "Rechnung"))[:240]
    meta.salutation = (request.POST.get("document_salutation") or meta.salutation or "Sehr geehrte Damen und Herren,")[:240]
    meta.web_view_enabled = request.POST.get("web_view_enabled") in {"1", "on", "true", "yes"}
    if "web_view_enabled" not in request.POST and kind == "quote" and not meta.pk:
        meta.web_view_enabled = bool(profile.get("web_view", {}).get("quote_default", True))
    meta.labour_cost_share_visible = request.POST.get("labour_cost_share_visible") in {"1", "on", "true", "yes"}
    if kind == "invoice":
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
    if kind == "quote": return str(cfg.get("quote_prefix") or "A-")[:30], int(cfg.get("quote_start") or 1)
    if kind == "credit": return str(cfg.get("credit_prefix") or "GS-")[:30], int(cfg.get("credit_start") or 1)
    return str(cfg.get("customer_prefix") or "K-")[:30], int(cfg.get("customer_start") or 1)


def allocate_number(org, kind):
    prefix, start = _number_settings(org, kind)
    with transaction.atomic():
        seq, created = m.ToolTimeNumberSequence.objects.select_for_update().get_or_create(organization=org, kind=kind, defaults={"prefix": prefix, "next_value": max(1, start), "width": max(1, len(str(start)))})
        if created is False and seq.prefix != prefix:
            seq.prefix = prefix
        if seq.next_value < start:
            seq.next_value = start
        value = seq.next_value
        seq.next_value = value + 1
        seq.width = max(seq.width, len(str(start)))
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
''')


def install_views() -> None:
    write("erp/tooltime_parity_views.py", r'''from __future__ import annotations

import re
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.files.base import ContentFile
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from . import models as m
from . import rebuild_views as base
from .services.business_pdf_identity import inject_business_pdf_identity
from .services.field_authorization import html_to_pdf_bytes
from .services.tooltime_parity_finance import allocate_number, finalize_quote, invoice_type_allowed, meta_for, money, profile_for, save_document_meta, sync_position_extras


def _org(request): return base._org(request)


def _redirect_pk(response):
    location = response.get("Location", "") if hasattr(response, "get") else ""
    match = re.search(r"/(?:quotes|invoices)/(\d+)/?", location)
    return int(match.group(1)) if match else None


@login_required
@require_http_methods(["GET", "POST"])
def quote_editor(request, pk=None):
    org = _org(request)
    existing = get_object_or_404(m.Quote, pk=pk, organization=org) if pk else None
    if request.method == "POST" and existing is not None:
        meta = meta_for(existing, "quote", create=False)
        if existing.status == "accepted" and meta and meta.finalized_at:
            messages.error(request, "Ein angenommenes Angebot ist aufbewahrungspflichtig und kann inhaltlich nicht mehr bearbeitet werden.")
            return redirect("next-quote-edit", pk=existing.pk)
    response = base.quote_editor(request, pk)
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
@require_http_methods(["GET", "POST"])
def invoice_editor(request, pk=None):
    org = _org(request)
    existing = get_object_or_404(m.Invoice, pk=pk, organization=org) if pk else None
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


@login_required
@require_http_methods(["GET", "POST"])
def settings_page(request):
    org = _org(request)
    profile = profile_for(org)
    cfg = profile.settings
    integrations = m.IntegrationConfig.objects.filter(organization=org).order_by("provider")
    if request.method == "POST":
        section = request.POST.get("section") or "all"
        if section == "layout":
            cfg["logo"].update({"show": request.POST.get("logo_show") == "on", "position": request.POST.get("logo_position") or "right", "size": request.POST.get("logo_size") or "large"})
            cfg["sender_line"]["show"] = request.POST.get("sender_line_show") == "on"
            cfg["footer"].update({"show": request.POST.get("footer_show") == "on", "mode": request.POST.get("footer_mode") or "standard"})
        elif section == "numbering":
            num = cfg["numbering"]
            for key in ("quote_prefix", "invoice_prefix", "credit_prefix", "customer_prefix"):
                num[key] = (request.POST.get(key) or num.get(key) or "")[:30]
            for key in ("quote_start", "invoice_start", "credit_start", "customer_start"):
                try: num[key] = max(1, int(request.POST.get(key) or num.get(key) or 1))
                except ValueError: pass
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
        elif section == "dunning":
            d = cfg["dunning"]
            for key in ("reminder_days", "first_days", "second_days", "grace_days"):
                try: d[key] = max(0, int(request.POST.get(key) or d.get(key) or 0))
                except ValueError: pass
            d["first_fee"] = str(money(request.POST.get("first_fee")))
            d["second_fee"] = str(money(request.POST.get("second_fee")))
            d["automatic"] = request.POST.get("automatic_dunning") == "on"
        elif section == "communication":
            c = cfg["communication"]
            for key in ("reply_email", "invoice_subject", "invoice_body", "quote_subject", "quote_body", "sms"):
                c[key] = request.POST.get(key) or ""
            c["show_logo"] = request.POST.get("email_show_logo") == "on"
            c["sms"] = c["sms"][:160]
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
    return render(request, "rebuild/tooltime_settings.html", {"organization": org, "integrations": integrations, "profile": profile, "cfg": cfg, "text_templates": templates})


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
    org = _org(request); invoice = get_object_or_404(m.Invoice, organization=org, pk=pk)
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
    due = timezone.localdate() + timezone.timedelta(days=due_days)
    html = f'''<html><body style="font-family:Arial,sans-serif;font-size:12px"><h1>{heading}</h1><p>Rechnung: <strong>{invoice.number}</strong></p><p>Sehr geehrte Damen und Herren,</p><p>für die oben genannte Rechnung ist aktuell ein offener Betrag von <strong>{open_amount:.2f} €</strong> vorhanden.</p><p>Bitte überweisen Sie den offenen Betrag bis spätestens <strong>{due:%d.%m.%Y}</strong>.</p>{f'<p>Mahngebühr: <strong>{fee:.2f} €</strong></p>' if fee else ''}<p>Mit freundlichen Grüßen<br>{org.name}</p></body></html>'''
    pdf = html_to_pdf_bytes(inject_business_pdf_identity(html, org, document=invoice, kind="invoice"))
    doc = m.Document(organization=org, customer=customer, project=invoice.project, title=f"{heading} · {invoice.number}", category="other", mime_type="application/pdf", size=len(pdf), metadata={"kind":"dunning","level":level,"invoice_id":invoice.pk}, uploaded_by=request.user)
    doc.file.save(f"{heading.lower().replace(' ', '-')}-{invoice.pk}.pdf", ContentFile(pdf), save=False); doc.save()
    email = getattr(customer, "email", "") or ""
    m.ToolTimeDunningRecord.objects.create(organization=org, invoice=invoice, level=level, due_days=due_days, fee=fee, internal_note=request.POST.get("internal_note") or "", recipient_email=email, document=doc, created_by=request.user)
    messages.success(request, f"{heading} wurde erstellt und bei der Rechnung gespeichert.")
    return redirect("next-invoice-edit", pk=pk)


@require_http_methods(["GET", "POST"])
def public_quote(request, token):
    meta = get_object_or_404(m.ToolTimeDocumentMeta.objects.select_related("quote__project__customer"), web_token=token, quote__isnull=False)
    quote = meta.quote
    if not meta.web_view_enabled or not meta.finalized_at:
        return render(request, "rebuild/public_quote.html", {"unavailable": True}, status=404)
    customer = quote.project.customer
    verified = request.session.get(f"quote_verified_{meta.pk}") is True
    if request.method == "POST" and not verified:
        postal = (request.POST.get("postal_code") or "").strip().replace(" ", "")
        expected = (getattr(customer, "postal_code", "") or "").strip().replace(" ", "")
        if expected and postal == expected:
            request.session[f"quote_verified_{meta.pk}"] = True; verified = True
        else:
            messages.error(request, "Die Postleitzahl ist nicht korrekt.")
    if request.method == "POST" and verified and request.POST.get("decision") in {"accept", "reject"}:
        if request.POST["decision"] == "accept":
            quote.status = "accepted"; meta.accepted_at = timezone.now(); meta.rejected_at = None; messages.success(request, "Vielen Dank. Das Angebot wurde angenommen.")
        else:
            quote.status = "rejected"; meta.rejected_at = timezone.now(); meta.accepted_at = None; messages.success(request, "Das Angebot wurde abgelehnt.")
        quote.save(update_fields=["status", "updated_at"]); meta.save(update_fields=["accepted_at", "rejected_at", "updated_at"])
    return render(request, "rebuild/public_quote.html", {"quote": quote, "meta": meta, "verified": verified, "totals": base._quote_total(quote) if verified else None})
''')


def install_tags() -> None:
    write("erp/templatetags/__init__.py", "")
    write("erp/templatetags/tooltime_parity.py", r'''from django import template
from erp import models as m
from erp.services.tooltime_parity_finance import default_settings, meta_for, profile_for

register = template.Library()


@register.simple_tag
def tooltime_context(request, document, kind):
    profile = getattr(getattr(request.user, "profile", None), "organization", None)
    org = profile or getattr(document, "organization", None) or m.Organization.objects.first()
    if org is None:
        return {"cfg": default_settings(), "meta": None, "templates": [], "customers": []}
    commercial = profile_for(org)
    meta = meta_for(document, kind) if document is not None else None
    templates = list(m.ToolTimeTextTemplate.objects.filter(organization=org, document_kind=kind))
    customers = list(m.Customer.objects.filter(organization=org, active=True).order_by("company", "last_name", "first_name")[:300])
    dunning = list(document.tooltime_dunning_records.select_related("document").all()) if kind == "invoice" and document is not None else []
    return {"cfg": commercial.settings, "meta": meta, "templates": templates, "customers": customers, "dunning": dunning}
''')


def install_templates() -> None:
    write("templates/rebuild/document_editor.html", r'''{% extends 'rebuild/base.html' %}{% load static tooltime_parity %}
{% block title %}{% if kind == 'quote' %}Angebot{% else %}Rechnung{% endif %} · A+Bau{% endblock %}
{% block content %}
{% tooltime_context request document kind as tt %}
<link rel="stylesheet" href="{% static 'css/tooltime-parity-finance.css' %}?v=20260820-1">
<script src="{% static 'js/tooltime-parity-finance.js' %}?v=20260820-1" defer></script>
<div class="tt-pagehead"><div><span class="tt-eyebrow">{% if kind == 'quote' %}Angebot{% else %}Rechnung{% endif %}</span><h1>{% if document %}{% if document.number %}{{ document.number }}{% else %}Entwurf{% endif %}{% else %}{% if kind == 'quote' %}Neues Angebot{% else %}Neue Rechnung{% endif %}{% endif %}</h1></div><div class="tt-head-actions">{% if kind == 'quote' and document and tt.meta.finalized_at and tt.meta.web_view_enabled %}<button type="button" class="nx-btn" data-copy-link data-link="{{ request.scheme }}://{{ request.get_host }}{% url 'next-public-quote' tt.meta.web_token %}">Webansicht kopieren</button>{% endif %}{% if document %}<span class="nx-badge">{{ document.get_status_display }}</span>{% endif %}</div></div>
<form class="tt-document-form" method="post" enctype="multipart/form-data" data-article-search-url="{% url 'next-article-search' %}">{% csrf_token %}
<section class="tt-card tt-document-top"><h2>Kunde und Projekt</h2><div class="tt-two"><label>Kunde auswählen<select class="nx-control" data-customer-preview><option value="">Kunde auswählen</option>{% for c in tt.customers %}<option value="{{ c.pk }}" data-address="{{ c.street|default:'' }}, {{ c.postal_code|default:'' }} {{ c.city|default:'' }}">{{ c.display_name }}</option>{% endfor %}</select></label><label>Projekt auswählen {{ form.project }}</label></div><div class="tt-address-preview" data-address-preview>{% if document and document.project %}<strong>Adresse</strong><span>{{ document.project.customer.street }} · {{ document.project.customer.postal_code }} {{ document.project.customer.city }}</span>{% else %}<span>Bitte zuerst einen Kunden oder ein Projekt auswählen.</span>{% endif %}</div></section>
<section class="tt-card"><h2>{% if kind == 'quote' %}Angebotsdetails{% else %}Rechnungsdetails{% endif %}</h2><div class="tt-two"><label>{% if kind == 'quote' %}Angebotstitel{% else %}Rechnungstitel{% endif %}<input class="nx-control" name="document_title" value="{% if tt.meta %}{{ tt.meta.document_title }}{% elif kind == 'quote' %}Angebot{% else %}Rechnung{% endif %}"></label><label>{% if kind == 'quote' %}Angebotsdatum{% else %}Rechnungsdatum{% endif %}{{ form.issue_date }}</label></div>{% if kind == 'invoice' %}<div class="tt-two"><label>Rechnungsart<select class="nx-control" name="invoice_type"><option value="standard" {% if tt.meta.invoice_type == 'standard' %}selected{% endif %}>Standardrechnung</option><option value="advance" {% if tt.meta.invoice_type == 'advance' %}selected{% endif %}>Abschlagsrechnung</option><option value="partial" {% if tt.meta.invoice_type == 'partial' %}selected{% endif %}>Teilrechnung</option><option value="final" {% if tt.meta.invoice_type == 'final' %}selected{% endif %}>Schlussrechnung</option></select></label><label>Titelsuffix<input class="nx-control" name="invoice_title_suffix" value="{{ tt.meta.title_suffix|default:'' }}" placeholder="z. B. Badrenovierung"></label></div>{% endif %}</section>
<section class="tt-card"><div class="tt-section-title"><h2>Einleitungstext</h2><button type="button" class="tt-link" data-template-open="intro">Vorlagen</button></div><input class="nx-control" name="document_salutation" value="{% if tt.meta %}{{ tt.meta.salutation }}{% else %}Sehr geehrte Damen und Herren,{% endif %}"><textarea class="nx-control" name="intro_text" rows="5">{{ form.intro_text.value|default:'' }}</textarea></section>
<section class="tt-services"><div class="tt-section-title"><div><h2>Leistungen</h2><p>Leistungsgruppen und Positionen lassen sich per Drag & Drop sortieren.</p></div><button type="button" class="nx-btn" data-add-group>＋ Leistungsgruppe hinzufügen</button></div><div data-service-groups>
{% if items %}{% regroup items by ui_group as groups %}{% for group in groups %}<section class="tt-service-group" data-service-group><header><button type="button" class="tt-collapse" data-collapse>▾</button><span class="tt-grip" draggable="true">⠿</span><input class="tt-group-title" value="{{ group.grouper|default:'Leistungsgruppe' }}" aria-label="Titel der Leistungsgruppe"><strong data-group-total>0,00 €</strong><button type="button" class="tt-menu" data-group-menu>•••</button></header><div class="tt-group-body" data-group-body>{% for item in group.list %}{% include 'rebuild/_tooltime_position.html' with item=item index=forloop.counter %}{% endfor %}</div><button type="button" class="tt-add-position" data-add-position>＋ Position hinzufügen</button></section>{% endfor %}{% else %}<section class="tt-service-group" data-service-group><header><button type="button" class="tt-collapse" data-collapse>▾</button><span class="tt-grip" draggable="true">⠿</span><input class="tt-group-title" value="Leistungsgruppe" aria-label="Titel der Leistungsgruppe"><strong data-group-total>0,00 €</strong><button type="button" class="tt-menu" data-group-menu>•••</button></header><div class="tt-group-body" data-group-body>{% include 'rebuild/_tooltime_position.html' %}</div><button type="button" class="tt-add-position" data-add-position>＋ Position hinzufügen</button></section>{% endif %}
</div></section>
<div class="tt-bottom-grid"><section class="tt-card"><h2>Zahlungsbedingungen</h2><div class="tt-two"><label>Zahlungsziel<input class="nx-control" type="number" min="0" name="payment_due_days" value="{{ commercial.payment_due_days|default:tt.cfg.payment_terms.days|default:0 }}"></label><label>Skonto<div class="tt-inline"><input class="nx-control" type="number" step="0.01" min="0" max="100" name="early_discount_percent" value="{{ commercial.early_payment_discount_percent|default:0 }}"><span>% innerhalb</span><input class="nx-control" type="number" min="0" name="early_discount_days" value="{{ commercial.early_payment_discount_days|default:0 }}"><span>Tagen</span></div></label></div><h2>Schlusstext</h2><div class="tt-section-title"><span></span><button type="button" class="tt-link" data-template-open="closing">Vorlagen</button></div><textarea class="nx-control" name="closing_text" rows="9">{{ commercial.closing_text|default:document.outro_text|default:'' }}</textarea></section>
<aside class="tt-summary"><div class="tt-card tt-summary-card"><h3>Kalkulationsübersicht</h3><div class="tt-summary-line"><span>Nettobetrag</span><strong data-summary-net>0,00 €</strong></div><div class="tt-summary-line"><span>Gesamtkosten</span><strong data-summary-cost>0,00 €</strong></div><div class="tt-summary-line"><span>Gesamtmarge</span><strong data-summary-margin>0,00 €</strong></div><button type="button" class="tt-link" data-adjust-markups>Margen anpassen</button><label>Rabatt<div class="tt-inline"><select class="nx-control" name="discount_type"><option value="percent" {% if commercial.discount_type != 'fixed' %}selected{% endif %}>%</option><option value="fixed" {% if commercial.discount_type == 'fixed' %}selected{% endif %}>€</option></select><input class="nx-control" name="discount_value" type="number" step="0.01" min="0" value="{{ commercial.discount_value|default:0 }}"></div></label><label>Steuersatz<select class="nx-control" name="document_tax_code">{% for rate in tt.cfg.tax_rates %}{% if rate.active %}<option value="{% if rate.rate == '19' %}19{% elif rate.rate == '7' %}7{% elif '13b' in rate.title %}0_13b{% elif '19 UStG' in rate.title %}0_19{% else %}0{% endif %}" {% if commercial.tax_rate|stringformat:'s' == rate.rate|stringformat:'s' %}selected{% endif %}>{{ rate.title }}</option>{% endif %}{% endfor %}</select></label><div class="tt-summary-line tt-total"><span>Gesamtbetrag</span><strong data-summary-gross>0,00 €</strong></div><label class="tt-check"><input type="checkbox" name="labour_cost_share_visible" {% if tt.meta.labour_cost_share_visible or not tt.meta %}checked{% endif %}> Lohnkostenanteil ausweisen</label>{% if kind == 'quote' %}<label class="tt-check"><input type="checkbox" name="web_view_enabled" {% if tt.meta.web_view_enabled or not tt.meta %}checked{% endif %}> Webansicht für dieses Angebot aktivieren</label>{% endif %}</div>{% if kind == 'invoice' and document %}<div class="tt-card"><h3>Mahnwesen</h3><p>Offener Betrag: <strong>{{ totals.open|default:0|floatformat:2 }} €</strong></p><button type="button" class="nx-btn" data-open-dunning>Mahnung erstellen</button>{% for row in tt.dunning %}<a class="tt-history" href="{{ row.document.file.url }}" target="_blank">{{ row.get_level_display }} · {{ row.created_at|date:'d.m.Y' }}</a>{% endfor %}</div>{% endif %}</aside></div>
<div class="tt-actions"><a class="nx-btn" href="{% if kind == 'quote' %}{% url 'next-quotes' %}{% else %}{% url 'next-invoices' %}{% endif %}">Zurück</a><button class="nx-btn" type="submit" name="action" value="save">Entwurf speichern</button><button class="nx-btn nx-btn-accent" type="submit" name="action" value="finalize">Fertigstellen</button></div>
</form>
<div class="tt-modal" data-article-modal hidden><div class="tt-modal-card"><header><h2>Artikel durchsuchen</h2><button type="button" data-close-modal>×</button></header><div class="tt-search-filters"><input class="nx-control" type="search" data-advanced-query placeholder="Artikel suchen …"><select class="nx-control" data-advanced-source><option value="all">Alle Quellen</option><option value="catalog">Katalog</option><option value="own">Eigene Preislisten</option><option value="reference">B&O / Referenz</option><option value="used">Zuletzt verwendet</option></select><select class="nx-control" data-advanced-type><option value="all">Alle Positionsarten</option><option value="material">Material</option><option value="service">Lohn / Leistung</option></select></div><div data-advanced-results class="tt-search-results"></div></div></div>
<div class="tt-modal" data-template-modal hidden><div class="tt-modal-card"><header><h2>Textvorlage auswählen</h2><button type="button" data-close-modal>×</button></header><div class="tt-template-list">{% for tpl in tt.templates %}<button type="button" data-template-choice data-kind="{{ tpl.text_kind }}" data-salutation="{{ tpl.salutation|escape }}" data-body="{{ tpl.body|escape }}"><strong>{{ tpl.title }}</strong><span>{{ tpl.get_text_kind_display }}</span></button>{% empty %}<p>Noch keine eigene Textvorlage vorhanden. Lege sie in den Einstellungen unter „Texte & Layout“ an.</p>{% endfor %}</div></div></div>
{% if kind == 'invoice' and document %}<div class="tt-modal" data-dunning-modal hidden><form class="tt-modal-card" method="post" action="{% url 'next-invoice-dunning' document.pk %}">{% csrf_token %}<header><h2>Mahnung erstellen</h2><button type="button" data-close-modal>×</button></header><label>Stufe<select class="nx-control" name="level"><option value="reminder">Zahlungserinnerung</option><option value="first">1. Mahnung</option><option value="second">2. Mahnung</option></select></label><label>Zahlungsfrist in Tagen<input class="nx-control" name="due_days" type="number" min="0" value="7"></label><label>Mahngebühr<input class="nx-control" name="fee" type="number" min="0" step="0.01" value="3.00"></label><label>Interne Notiz<textarea class="nx-control" name="internal_note" rows="3"></textarea></label><button class="nx-btn nx-btn-accent" type="submit">Mahnung erstellen</button></form></div>{% endif %}
<template id="tt-position-template">{% include 'rebuild/_tooltime_position.html' %}</template>
{% endblock %}''')

    write("templates/rebuild/_tooltime_position.html", r'''<div class="tt-position" data-position draggable="true"><span class="tt-position-grip">⠿</span><span class="tt-position-number" data-position-number>1.1</span><select class="nx-control" name="item_type"><option value="material" {% if item.ui_type == 'material' %}selected{% endif %}>Material</option><option value="labour" {% if item.ui_type == 'labour' %}selected{% endif %}>Lohn</option><option value="mixed" {% if item.ui_type == 'mixed' %}selected{% endif %}>Mischposition</option><option value="other" {% if item.ui_type == 'other' %}selected{% endif %}>Sonstiges</option></select><input class="nx-control tt-qty" name="item_quantity" type="number" min="0" step="0.001" value="{{ item.quantity|default:1 }}"><input class="nx-control tt-unit" name="item_unit" value="{{ item.unit|default:'Stk.' }}"><div class="tt-description"><input type="hidden" name="item_catalog_id" value="{{ item.ui_catalog_id|default:'' }}"><input type="hidden" name="item_group" value="{{ item.ui_group|default:'' }}" data-group-hidden><input type="hidden" name="item_price" value="{{ item.unit_price|default:0 }}"><input class="nx-control" name="item_description" value="{{ item.description|default:'' }}" placeholder="Bezeichnung" autocomplete="off" data-position-search><button type="button" class="tt-browse" data-browse-articles>Artikel durchsuchen</button><textarea class="nx-control" name="item_detail" rows="2" placeholder="Beschreibung">{{ item.ui_detail|default:'' }}</textarea><div class="tt-position-extra"><label class="tt-check"><input type="checkbox" name="item_add_catalog" value="1"> Zum Katalog hinzufügen</label><label class="tt-upload">Bild hinzufügen<input type="file" name="item_image" accept="image/png,image/jpeg,image/webp"></label></div></div><input class="nx-control tt-money" name="item_purchase_price" type="number" min="0" step="0.01" value="{{ item.ui_purchase_price|default:0 }}"><div class="tt-percent"><input class="nx-control" name="item_markup_percent" type="number" step="0.01" value="{{ item.ui_markup_percent|default:0 }}"><span>%</span></div><output data-markup-value>0,00 €</output><output data-unit-price>0,00 €</output><output data-line-total>0,00 €</output><select class="nx-control tt-service-model" name="item_service_model"><option value="normal" {% if item.ui_service_model == 'normal' %}selected{% endif %}>Normalleistung</option><option value="alternative" {% if item.ui_service_model == 'alternative' %}selected{% endif %}>Alternativposition</option><option value="contingent" {% if item.ui_service_model == 'contingent' %}selected{% endif %}>Eventualposition</option></select><button type="button" class="tt-delete-position" data-delete-position title="Position löschen">🗑</button></div>''')

    write("templates/rebuild/tooltime_settings.html", r'''{% extends 'rebuild/base.html' %}{% load static %}{% block title %}Einstellungen · A+Bau{% endblock %}{% block content %}<link rel="stylesheet" href="{% static 'css/tooltime-parity-finance.css' %}?v=20260820-1"><div class="tt-settings"><div class="nx-pagehead"><div><div class="nx-kicker">Einstellungen</div><h1>Angebote, Rechnungen & Kommunikation</h1><p>Alle dokumentbezogenen Standards zentral konfigurieren.</p></div></div>
<section class="tt-card"><h2>Texte & Layout</h2><form method="post">{% csrf_token %}<input type="hidden" name="section" value="layout"><div class="tt-three"><label>Logo anzeigen<input type="checkbox" name="logo_show" {% if cfg.logo.show %}checked{% endif %}></label><label>Position<select class="nx-control" name="logo_position"><option value="left" {% if cfg.logo.position == 'left' %}selected{% endif %}>Links</option><option value="center" {% if cfg.logo.position == 'center' %}selected{% endif %}>Mittig</option><option value="right" {% if cfg.logo.position == 'right' %}selected{% endif %}>Rechts</option></select></label><label>Größe<select class="nx-control" name="logo_size"><option value="small">Klein</option><option value="medium">Mittel</option><option value="large" {% if cfg.logo.size == 'large' %}selected{% endif %}>Groß</option></select></label></div><label class="tt-check"><input type="checkbox" name="sender_line_show" {% if cfg.sender_line.show %}checked{% endif %}> Absenderzeile anzeigen</label><div class="tt-two"><label>Fußzeile<select class="nx-control" name="footer_mode"><option value="standard" {% if cfg.footer.mode == 'standard' %}selected{% endif %}>Standard</option><option value="custom" {% if cfg.footer.mode == 'custom' %}selected{% endif %}>Benutzerdefiniert</option></select></label><label class="tt-check"><input type="checkbox" name="footer_show" {% if cfg.footer.show %}checked{% endif %}> Fußzeile anzeigen</label></div><button class="nx-btn nx-btn-accent" type="submit">Layout speichern</button></form></section>
<section class="tt-card"><h2>Textvorlagen</h2><div class="tt-template-settings">{% for tpl in text_templates %}<form method="post" class="tt-template-editor">{% csrf_token %}<input type="hidden" name="section" value="template"><input type="hidden" name="template_id" value="{{ tpl.pk }}"><input type="hidden" name="document_kind" value="{{ tpl.document_kind }}"><input type="hidden" name="text_kind" value="{{ tpl.text_kind }}"><strong>{{ tpl.get_document_kind_display }} · {{ tpl.get_text_kind_display }}</strong><input class="nx-control" name="template_title" value="{{ tpl.title }}"><input class="nx-control" name="template_salutation" value="{{ tpl.salutation }}"><textarea class="nx-control" name="template_body" rows="5">{{ tpl.body }}</textarea><button class="nx-btn" type="submit">Vorlage speichern</button></form>{% endfor %}<form method="post" class="tt-template-editor">{% csrf_token %}<input type="hidden" name="section" value="template"><strong>Neue Vorlage</strong><div class="tt-two"><select class="nx-control" name="document_kind"><option value="quote">Angebote</option><option value="invoice">Rechnungen</option></select><select class="nx-control" name="text_kind"><option value="intro">Einleitungstext</option><option value="closing">Schlusstext</option></select></div><input class="nx-control" name="template_title" placeholder="Vorlagentitel"><input class="nx-control" name="template_salutation" placeholder="Anrede"><textarea class="nx-control" name="template_body" rows="4" placeholder="Text"></textarea><button class="nx-btn" type="submit">Vorlage hinzufügen</button></form></div></section>
<section class="tt-card"><h2>Nummernkreise für Dokumente</h2><form method="post">{% csrf_token %}<input type="hidden" name="section" value="numbering"><div class="tt-number-grid"><label>Angebote · Präfix<input class="nx-control" name="quote_prefix" value="{{ cfg.numbering.quote_prefix }}"></label><label>Beginnt bei<input class="nx-control" type="number" name="quote_start" value="{{ cfg.numbering.quote_start }}"></label><label>Rechnungen · Präfix<input class="nx-control" name="invoice_prefix" value="{{ cfg.numbering.invoice_prefix }}"></label><label>Beginnt bei<input class="nx-control" type="number" name="invoice_start" value="{{ cfg.numbering.invoice_start }}"></label><label>Gutschriften · Präfix<input class="nx-control" name="credit_prefix" value="{{ cfg.numbering.credit_prefix }}"></label><label>Beginnt bei<input class="nx-control" type="number" name="credit_start" value="{{ cfg.numbering.credit_start }}"></label></div><label class="tt-check"><input type="checkbox" name="customer_auto" {% if cfg.numbering.customer_auto %}checked{% endif %}> Kundennummern automatisch vergeben</label><div class="tt-two"><label>Kundenpräfix<input class="nx-control" name="customer_prefix" value="{{ cfg.numbering.customer_prefix }}"></label><label>Beginnt bei<input class="nx-control" type="number" name="customer_start" value="{{ cfg.numbering.customer_start }}"></label></div><label class="tt-check"><input type="checkbox" name="debtor_creditor_enabled" {% if cfg.numbering.debtor_creditor_enabled %}checked{% endif %}> Debitoren- und Kreditorennummer aktivieren</label><button class="nx-btn nx-btn-accent" type="submit">Nummernkreise speichern</button></form></section>
<section class="tt-card"><h2>Dokumente & Zahlungsbedingungen</h2><form method="post">{% csrf_token %}<input type="hidden" name="section" value="documents"><label class="tt-check"><input type="checkbox" name="quote_web_default" {% if cfg.web_view.quote_default %}checked{% endif %}> Webansicht für zukünftige Angebote aktivieren</label><label class="tt-check"><input type="checkbox" name="acceptance_email" {% if cfg.web_view.acceptance_email %}checked{% endif %}> E-Mail-Benachrichtigung bei digitaler Angebotsannahme</label><div class="tt-two"><label>Zahlungsziel<select class="nx-control" name="payment_mode"><option value="none">Kein Zahlungsziel</option><option value="immediately" {% if cfg.payment_terms.mode == 'immediately' %}selected{% endif %}>Sofort</option><option value="7">7 Tage</option><option value="14">14 Tage</option><option value="custom">Benutzerdefiniert</option></select></label><label>Tage<input class="nx-control" type="number" min="0" name="payment_days" value="{{ cfg.payment_terms.days }}"></label></div><label>Bereiche<select class="nx-control" name="payment_areas"><option value="invoice" {% if cfg.payment_terms.areas == 'invoice' %}selected{% endif %}>Rechnungen</option><option value="both" {% if cfg.payment_terms.areas == 'both' %}selected{% endif %}>Rechnungen und Angebote</option></select></label><h3>Ausweisung des Lohnkostenanteils</h3><div class="tt-two"><label class="tt-check"><input type="checkbox" name="quote_private" {% if cfg.labour_share.quote_private %}checked{% endif %}> Angebote für Privatkunden</label><label class="tt-check"><input type="checkbox" name="quote_company" {% if cfg.labour_share.quote_company %}checked{% endif %}> Angebote für Firmenkunden</label><label class="tt-check"><input type="checkbox" name="invoice_private" {% if cfg.labour_share.invoice_private %}checked{% endif %}> Rechnungen für Privatkunden</label><label class="tt-check"><input type="checkbox" name="invoice_company" {% if cfg.labour_share.invoice_company %}checked{% endif %}> Rechnungen für Firmenkunden</label></div><button class="nx-btn nx-btn-accent" type="submit">Dokumenteinstellungen speichern</button></form></section>
<section class="tt-card"><h2>Steuersätze</h2><div class="tt-tax-list">{% for rate in cfg.tax_rates %}<div><strong>{{ rate.title }}</strong><span>{{ rate.rate }} %</span><small>{{ rate.note }}</small></div>{% endfor %}</div><form method="post"><input type="hidden" name="section" value="tax">{% csrf_token %}<div class="tt-three"><input class="nx-control" name="tax_title" placeholder="Titel"><input class="nx-control" name="tax_rate" placeholder="Prozent"><input class="nx-control" name="tax_note" placeholder="Rechtlicher Hinweis"></div><button class="nx-btn" type="submit">Steuersatz hinzufügen</button></form></section>
<section class="tt-card"><h2>Zahlungen & Mahnwesen</h2><form method="post">{% csrf_token %}<input type="hidden" name="section" value="dunning"><div class="tt-three"><label>Zahlungserinnerung nach<input class="nx-control" type="number" name="reminder_days" value="{{ cfg.dunning.reminder_days }}"></label><label>1. Mahnung nach<input class="nx-control" type="number" name="first_days" value="{{ cfg.dunning.first_days }}"></label><label>Mahngebühr<input class="nx-control" type="number" step="0.01" name="first_fee" value="{{ cfg.dunning.first_fee }}"></label><label>2. Mahnung nach<input class="nx-control" type="number" name="second_days" value="{{ cfg.dunning.second_days }}"></label><label>Mahngebühr<input class="nx-control" type="number" step="0.01" name="second_fee" value="{{ cfg.dunning.second_fee }}"></label><label>Kulanzzeitraum<input class="nx-control" type="number" name="grace_days" value="{{ cfg.dunning.grace_days }}"></label></div><label class="tt-check"><input type="checkbox" name="automatic_dunning" {% if cfg.dunning.automatic %}checked{% endif %}> Automatisches Mahnwesen aktivieren</label><button class="nx-btn nx-btn-accent" type="submit">Mahnwesen speichern</button></form></section>
<section class="tt-card"><h2>Kommunikation</h2><form method="post">{% csrf_token %}<input type="hidden" name="section" value="communication"><label>Standard-Antwortadresse<input class="nx-control" type="email" name="reply_email" value="{{ cfg.communication.reply_email }}"></label><label class="tt-check"><input type="checkbox" name="email_show_logo" {% if cfg.communication.show_logo %}checked{% endif %}> Logo im E-Mail-Kopf anzeigen</label><div class="tt-two"><label>Betreff Rechnungen<input class="nx-control" name="invoice_subject" value="{{ cfg.communication.invoice_subject }}"></label><label>Betreff Angebote<input class="nx-control" name="quote_subject" value="{{ cfg.communication.quote_subject }}"></label></div><div class="tt-two"><label>Rechnungs-E-Mail<textarea class="nx-control" name="invoice_body" rows="7">{{ cfg.communication.invoice_body }}</textarea></label><label>Angebots-E-Mail<textarea class="nx-control" name="quote_body" rows="7">{{ cfg.communication.quote_body }}</textarea></label></div><label>SMS-Benachrichtigung (max. 160 Zeichen)<textarea class="nx-control" maxlength="160" name="sms" rows="4">{{ cfg.communication.sms }}</textarea></label><button class="nx-btn nx-btn-accent" type="submit">Kommunikation speichern</button></form></section></div>{% endblock %}''')

    write("templates/rebuild/public_quote.html", r'''<!doctype html><html lang="de"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Angebot · A+Bau</title><style>body{font-family:Arial,sans-serif;background:#f5f7fa;color:#1c2734;margin:0}.wrap{max-width:900px;margin:40px auto;padding:20px}.card{background:#fff;border:1px solid #e5e9ef;border-radius:14px;padding:28px;margin-bottom:16px}.row{display:flex;justify-content:space-between;gap:20px;padding:10px 0;border-bottom:1px solid #eef1f4}.btn{border:0;border-radius:8px;padding:12px 18px;cursor:pointer}.primary{background:#1268e8;color:white}.danger{background:#f2f4f7}input{padding:12px;border:1px solid #ccd3dc;border-radius:8px;width:100%;box-sizing:border-box}</style></head><body><div class="wrap">{% if unavailable %}<div class="card"><h1>Diese Webansicht ist nicht verfügbar.</h1></div>{% elif not verified %}<div class="card"><h1>Angebot geschützt</h1><p>Bitte geben Sie zur Identitätsprüfung Ihre Postleitzahl ein.</p><form method="post">{% csrf_token %}<input name="postal_code" inputmode="numeric" autocomplete="postal-code"><button class="btn primary" type="submit" style="margin-top:12px">Angebot öffnen</button></form></div>{% else %}<div class="card"><h1>{{ meta.document_title|default:'Angebot' }} {{ quote.number }}</h1><p>{{ meta.salutation }}</p><p>{{ quote.intro_text }}</p></div><div class="card">{% for item in quote.items.all %}<div class="row"><span>{{ item.position }} · {{ item.description }}<br><small>{{ item.quantity }} {{ item.unit }}</small></span><strong>{{ item.unit_price|floatformat:2 }} €</strong></div>{% endfor %}<div class="row"><strong>Gesamtbetrag</strong><strong>{{ totals.gross|floatformat:2 }} €</strong></div></div><div class="card"><form method="post">{% csrf_token %}<button class="btn primary" name="decision" value="accept">Angebot annehmen</button><button class="btn danger" name="decision" value="reject">Angebot ablehnen</button></form></div>{% endif %}</div></body></html>''')


def install_assets() -> None:
    write("static/css/tooltime-parity-finance.css", r'''/* A+BAU TOOLTIME FINANCE PARITY 2026-08-20 */
.tt-pagehead{display:flex;justify-content:space-between;gap:24px;align-items:flex-start;margin-bottom:20px}.tt-eyebrow{font-size:12px;font-weight:800;text-transform:uppercase;color:var(--nx-muted)}.tt-pagehead h1{margin:4px 0}.tt-head-actions{display:flex;gap:10px;align-items:center}.tt-document-form,.tt-settings{display:grid;gap:18px}.tt-card{background:var(--nx-card,#fff);border:1px solid var(--nx-line,#e5e9ef);border-radius:14px;padding:20px}.tt-card h2,.tt-card h3{margin-top:0}.tt-two,.tt-three{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px}.tt-three{grid-template-columns:repeat(3,minmax(0,1fr))}.tt-card label{display:grid;gap:6px;font-size:13px;font-weight:700}.tt-address-preview{margin-top:14px;padding:12px 14px;background:#f7f9fb;border-radius:10px;display:flex;gap:10px;flex-wrap:wrap}.tt-section-title{display:flex;align-items:center;justify-content:space-between;gap:12px}.tt-section-title h2{margin:0}.tt-section-title p{margin:4px 0 0;color:var(--nx-muted)}.tt-link,.tt-browse{border:0;background:transparent;color:#096fe8;font-weight:700;cursor:pointer;padding:5px}.tt-service-group{border:1px solid var(--nx-line,#e5e9ef);border-radius:12px;margin-top:12px;background:#fff;overflow:hidden}.tt-service-group>header{display:grid;grid-template-columns:30px 30px minmax(0,1fr) auto 42px;align-items:center;gap:8px;padding:12px;background:#f7f9fc}.tt-collapse,.tt-menu{border:0;background:transparent;cursor:pointer;font-size:17px}.tt-grip,.tt-position-grip{cursor:grab;color:#8190a2}.tt-group-title{border:0;background:transparent;font-size:15px;font-weight:800;min-width:0}.tt-group-body{padding:8px}.tt-position{display:grid;grid-template-columns:28px 42px 125px 75px 75px minmax(250px,1.7fr) 95px 90px 90px 100px 100px 120px 36px;gap:7px;align-items:start;padding:9px 2px;border-bottom:1px solid #eef1f4}.tt-position-number{padding-top:10px;font-size:12px;font-weight:700}.tt-description{display:grid;gap:6px;position:relative}.tt-position-extra{display:flex;justify-content:space-between;gap:8px;flex-wrap:wrap}.tt-check{display:flex!important;grid-template-columns:auto 1fr!important;align-items:center;gap:8px!important;font-weight:500!important}.tt-upload{font-size:12px!important;color:#096fe8;cursor:pointer}.tt-upload input{display:none}.tt-percent,.tt-inline{display:flex;align-items:center;gap:7px}.tt-percent span{margin-left:-30px}.tt-delete-position{border:0;background:transparent;cursor:pointer;padding:8px}.tt-add-position{border:0;background:transparent;color:#096fe8;font-weight:800;padding:12px 18px;cursor:pointer}.tt-bottom-grid{display:grid;grid-template-columns:minmax(0,1fr) 340px;gap:18px}.tt-summary{display:grid;gap:14px;align-content:start}.tt-summary-line{display:flex;justify-content:space-between;padding:7px 0}.tt-total{border-top:1px solid var(--nx-line);margin-top:8px;padding-top:14px;font-size:18px}.tt-actions{position:sticky;bottom:0;background:rgba(255,255,255,.96);backdrop-filter:blur(8px);border-top:1px solid var(--nx-line);padding:12px;display:flex;justify-content:flex-end;gap:10px;z-index:20}.tt-modal{position:fixed;inset:0;background:rgba(12,22,35,.45);display:grid;place-items:center;padding:20px;z-index:1000}.tt-modal[hidden]{display:none}.tt-modal-card{width:min(820px,96vw);max-height:86vh;overflow:auto;background:#fff;border-radius:14px;padding:20px;display:grid;gap:14px}.tt-modal-card header{display:flex;justify-content:space-between;align-items:center}.tt-modal-card header button{border:0;background:transparent;font-size:24px;cursor:pointer}.tt-search-filters{display:grid;grid-template-columns:1fr 180px 180px;gap:10px}.tt-search-results{display:grid;gap:8px}.tt-search-result{display:grid;grid-template-columns:1fr auto;gap:12px;text-align:left;padding:12px;border:1px solid #e4e9ef;border-radius:10px;background:#fff;cursor:pointer}.tt-search-result small{display:block;color:#6f7b8a;margin-top:4px}.tt-search-result strong:last-child{white-space:nowrap}.tt-template-list{display:grid;gap:8px}.tt-template-list button{display:grid;gap:4px;text-align:left;border:1px solid #e4e9ef;background:#fff;border-radius:10px;padding:12px;cursor:pointer}.tt-typeahead{position:absolute;top:42px;left:0;right:0;background:#fff;border:1px solid #dbe1e8;box-shadow:0 12px 30px rgba(25,40,60,.15);border-radius:10px;z-index:30;max-height:320px;overflow:auto}.tt-history{display:block;padding:8px 0}.tt-number-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px}.tt-template-settings{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}.tt-template-editor{border:1px solid #e4e9ef;border-radius:10px;padding:14px;display:grid;gap:8px}.tt-tax-list{display:grid;gap:8px;margin-bottom:14px}.tt-tax-list>div{display:grid;grid-template-columns:1fr 100px 2fr;gap:12px;padding:10px;border-bottom:1px solid #eef1f4}@media(max-width:1100px){.tt-position{grid-template-columns:28px 38px 110px 70px 70px minmax(220px,1fr) 90px 85px}.tt-position output,.tt-service-model{display:none}.tt-bottom-grid{grid-template-columns:1fr}.tt-three,.tt-number-grid{grid-template-columns:repeat(2,minmax(0,1fr))}}@media(max-width:720px){.tt-two,.tt-three,.tt-number-grid,.tt-template-settings,.tt-search-filters{grid-template-columns:1fr}.tt-pagehead{flex-direction:column}.tt-position{grid-template-columns:28px 38px 1fr;align-items:center}.tt-position>*:not(.tt-position-grip):not(.tt-position-number):not(.tt-description):not(.tt-delete-position){grid-column:3}.tt-description{grid-column:3}.tt-delete-position{grid-column:1}.tt-actions{justify-content:stretch;flex-wrap:wrap}.tt-actions .nx-btn{flex:1}}''')

    write("static/js/tooltime-parity-finance.js", r'''// A+BAU TOOLTIME FINANCE PARITY 2026-08-20
(() => {
  const form=document.querySelector('.tt-document-form'); if(!form)return;
  const money=new Intl.NumberFormat('de-DE',{style:'currency',currency:'EUR'}); const num=v=>{const n=Number(String(v??0).replace(',','.'));return Number.isFinite(n)?n:0};
  const modal=(sel,on=true)=>{const el=document.querySelector(sel);if(el)el.hidden=!on};
  const groupOf=el=>el.closest('[data-service-group]');
  function syncGroups(){document.querySelectorAll('[data-service-group]').forEach((g,gi)=>{const title=g.querySelector('.tt-group-title')?.value||`Leistungsgruppe ${gi+1}`;let sum=0;g.querySelectorAll('[data-position]').forEach((row,ri)=>{row.querySelector('[data-group-hidden]').value=title;row.querySelector('[data-position-number]').textContent=`${gi+1}.${ri+1}`;sum+=num(row.querySelector('[data-line-total]')?.dataset.raw)});const out=g.querySelector('[data-group-total]');if(out)out.textContent=money.format(sum)});}
  function calc(){let net=0,cost=0;document.querySelectorAll('[data-position]').forEach(row=>{const qty=num(row.querySelector('[name=item_quantity]')?.value),purchase=num(row.querySelector('[name=item_purchase_price]')?.value),markup=num(row.querySelector('[name=item_markup_percent]')?.value);const unit=purchase*(1+markup/100),markupValue=unit-purchase,total=qty*unit;row.querySelector('[name=item_price]').value=unit.toFixed(2);const map=[["[data-markup-value]",markupValue],["[data-unit-price]",unit],["[data-line-total]",total]];map.forEach(([s,v])=>{const o=row.querySelector(s);if(o){o.textContent=money.format(v);o.dataset.raw=String(v)}});if(row.querySelector('[name=item_service_model]').value==='normal'){net+=total;cost+=qty*purchase}});const dtype=form.querySelector('[name=discount_type]')?.value||'percent',dv=num(form.querySelector('[name=discount_value]')?.value);const discount=dtype==='fixed'?Math.min(net,dv):net*dv/100;const taxable=Math.max(0,net-discount);const taxText=form.querySelector('[name=document_tax_code] option:checked')?.textContent||'19';const rate=taxText.includes('19 %')?19:(taxText.includes('7 %')?7:0);const gross=taxable*(1+rate/100);document.querySelector('[data-summary-net]').textContent=money.format(taxable);document.querySelector('[data-summary-cost]').textContent=money.format(cost);document.querySelector('[data-summary-margin]').textContent=money.format(taxable-cost);document.querySelector('[data-summary-gross]').textContent=money.format(gross);syncGroups()}
  form.addEventListener('input',calc);form.addEventListener('change',calc);calc();
  function newPosition(group){const tpl=document.querySelector('#tt-position-template');const node=tpl.content.firstElementChild.cloneNode(true);group.querySelector('[data-group-body]').appendChild(node);syncGroups();calc();return node}
  document.addEventListener('click',e=>{const b=e.target.closest('[data-add-position]');if(b){newPosition(groupOf(b));return}if(e.target.closest('[data-delete-position]')){e.target.closest('[data-position]').remove();syncGroups();calc();return}if(e.target.closest('[data-add-group]')){const shell=document.createElement('section');shell.className='tt-service-group';shell.dataset.serviceGroup='';shell.innerHTML='<header><button type="button" class="tt-collapse" data-collapse>▾</button><span class="tt-grip" draggable="true">⠿</span><input class="tt-group-title" value="Neue Leistungsgruppe"><strong data-group-total>0,00 €</strong><button type="button" class="tt-menu" data-group-menu>•••</button></header><div class="tt-group-body" data-group-body></div><button type="button" class="tt-add-position" data-add-position>＋ Position hinzufügen</button>';document.querySelector('[data-service-groups]').appendChild(shell);newPosition(shell);return}if(e.target.closest('[data-collapse]')){const g=groupOf(e.target);const body=g.querySelector('[data-group-body]');body.hidden=!body.hidden;return}if(e.target.closest('[data-group-menu]')){const g=groupOf(e.target);const action=prompt('Aktion: umbenennen, kopieren, marge, hoch, runter, löschen');if(!action)return;const a=action.toLowerCase();if(a.startsWith('umb')){const title=prompt('Neuer Titel',g.querySelector('.tt-group-title').value);if(title)g.querySelector('.tt-group-title').value=title}else if(a.startsWith('kop')){g.after(g.cloneNode(true))}else if(a.startsWith('marg')){const value=prompt('Neuer Aufschlag in % für diese Leistungsgruppe','20');if(value!==null)g.querySelectorAll('[name=item_markup_percent]').forEach(i=>i.value=value)}else if(a==='hoch'&&g.previousElementSibling){g.parentNode.insertBefore(g,g.previousElementSibling)}else if(a==='runter'&&g.nextElementSibling){g.parentNode.insertBefore(g.nextElementSibling,g)}else if(a.startsWith('lö')||a.startsWith('lo')){if(confirm('Leistungsgruppe wirklich löschen?'))g.remove()}syncGroups();calc();return}if(e.target.closest('[data-browse-articles]')){window.ttTargetRow=e.target.closest('[data-position]');modal('[data-article-modal]',true);document.querySelector('[data-advanced-query]')?.focus();searchAdvanced();return}if(e.target.closest('[data-close-modal]')){e.target.closest('.tt-modal').hidden=true;return}if(e.target.closest('[data-template-open]')){window.ttTemplateKind=e.target.closest('[data-template-open]').dataset.templateOpen;modal('[data-template-modal]',true);return}const choice=e.target.closest('[data-template-choice]');if(choice&&choice.dataset.kind===window.ttTemplateKind){if(choice.dataset.kind==='intro'){form.querySelector('[name=document_salutation]').value=choice.dataset.salutation||form.querySelector('[name=document_salutation]').value;form.querySelector('[name=intro_text]').value=choice.dataset.body||''}else form.querySelector('[name=closing_text]').value=choice.dataset.body||'';modal('[data-template-modal]',false);return}if(e.target.closest('[data-adjust-markups]')){const val=prompt('Neuer Aufschlag in % für alle Positionen','20');if(val!==null){form.querySelectorAll('[name=item_markup_percent]').forEach(i=>i.value=val);calc()}return}if(e.target.closest('[data-open-dunning]')){modal('[data-dunning-modal]',true);return}const copy=e.target.closest('[data-copy-link]');if(copy){navigator.clipboard?.writeText(copy.dataset.link);copy.textContent='Link kopiert';setTimeout(()=>copy.textContent='Webansicht kopieren',1400);return}});
  document.querySelector('[data-customer-preview]')?.addEventListener('change',e=>{const opt=e.target.selectedOptions[0];const p=document.querySelector('[data-address-preview]');if(p)p.textContent=opt?.dataset.address||'Bitte ein Projekt auswählen.'});
  const endpoint=form.dataset.articleSearchUrl;let searchTimer=null;async function query(q,source='all',type='all'){const url=new URL(endpoint,location.origin);url.searchParams.set('q',q);url.searchParams.set('source',source);url.searchParams.set('type',type);try{const r=await fetch(url,{headers:{'X-Requested-With':'XMLHttpRequest'}});const d=await r.json();return d.ok?d.results:[]}catch(_){return[]}}
  function apply(row,item){row.querySelector('[name=item_description]').value=item.name||'';row.querySelector('[name=item_unit]').value=item.unit||'Stk.';row.querySelector('[name=item_purchase_price]').value=Number(item.purchase||item.sales||0).toFixed(2);row.querySelector('[name=item_markup_percent]').value='0';row.querySelector('[name=item_price]').value=Number(item.sales||item.purchase||0).toFixed(2);row.querySelector('[name=item_catalog_id]').value=item.kind==='catalog'?(item.id||''):'';row.querySelector('.tt-typeahead')?.remove();calc()}
  async function inlineSearch(input){const q=input.value.trim(),row=input.closest('[data-position]');row.querySelector('.tt-typeahead')?.remove();if(q.length<2)return;const rows=await query(q);if(input.value.trim()!==q)return;const pop=document.createElement('div');pop.className='tt-typeahead';rows.slice(0,8).forEach(item=>{const b=document.createElement('button');b.type='button';b.className='tt-search-result';b.innerHTML=`<span><strong>${item.name}</strong><small>${[item.code,item.unit,item.source].filter(Boolean).join(' · ')}</small></span><strong>${money.format(num(item.sales))}</strong>`;b.addEventListener('mousedown',ev=>ev.preventDefault());b.addEventListener('click',()=>apply(row,item));pop.appendChild(b)});const all=document.createElement('button');all.type='button';all.className='tt-browse';all.textContent='Artikel durchsuchen';all.addEventListener('click',()=>{window.ttTargetRow=row;modal('[data-article-modal]',true);document.querySelector('[data-advanced-query]').value=q;searchAdvanced()});pop.appendChild(all);input.parentElement.appendChild(pop)}
  form.addEventListener('input',e=>{if(e.target.matches('[data-position-search]')){clearTimeout(searchTimer);searchTimer=setTimeout(()=>inlineSearch(e.target),180)}});
  async function searchAdvanced(){const q=document.querySelector('[data-advanced-query]')?.value||'',source=document.querySelector('[data-advanced-source]')?.value||'all',type=document.querySelector('[data-advanced-type]')?.value||'all',out=document.querySelector('[data-advanced-results]');if(!out)return;out.innerHTML='<p>Artikel werden gesucht …</p>';const rows=await query(q,source,type);out.innerHTML='';rows.forEach(item=>{const b=document.createElement('button');b.type='button';b.className='tt-search-result';b.innerHTML=`<span><strong>${item.name}</strong><small>${[item.code,item.unit,item.source].filter(Boolean).join(' · ')}</small></span><strong>${money.format(num(item.sales))}</strong>`;b.addEventListener('click',()=>{apply(window.ttTargetRow,item);modal('[data-article-modal]',false)});out.appendChild(b)});if(!rows.length)out.innerHTML='<p>Keine passenden Artikel gefunden.</p>'}
  ['[data-advanced-query]','[data-advanced-source]','[data-advanced-type]'].forEach(s=>document.querySelector(s)?.addEventListener('input',()=>{clearTimeout(searchTimer);searchTimer=setTimeout(searchAdvanced,180)}));
  let dragged=null;document.addEventListener('dragstart',e=>{const row=e.target.closest('[data-position]');if(row){dragged=row;e.dataTransfer.effectAllowed='move'}});document.addEventListener('dragover',e=>{if(dragged&&e.target.closest('[data-group-body]'))e.preventDefault()});document.addEventListener('drop',e=>{if(!dragged)return;const target=e.target.closest('[data-position]'),body=e.target.closest('[data-group-body]');if(!body)return;e.preventDefault();if(target&&target!==dragged)body.insertBefore(dragged,target);else body.appendChild(dragged);dragged=null;syncGroups();calc()});
})();''')


def patch_urls() -> None:
    rel = "erp/rebuild_urls.py"; text = read(rel)
    imp = "from . import tooltime_parity_views as tooltime_parity\n"
    if imp not in text:
        anchor = "from . import rebuild_views as views\n"; text = text.replace(anchor, anchor + imp, 1)
    text = text.replace('path("quotes/new/", views.quote_editor, name="next-quote-create")', 'path("quotes/new/", tooltime_parity.quote_editor, name="next-quote-create")')
    text = text.replace('path("quotes/<int:pk>/", views.quote_editor, name="next-quote-edit")', 'path("quotes/<int:pk>/", tooltime_parity.quote_editor, name="next-quote-edit")')
    text = text.replace('path("invoices/new/", views.invoice_editor, name="next-invoice-create")', 'path("invoices/new/", tooltime_parity.invoice_editor, name="next-invoice-create")')
    text = text.replace('path("invoices/<int:pk>/", views.invoice_editor, name="next-invoice-edit")', 'path("invoices/<int:pk>/", tooltime_parity.invoice_editor, name="next-invoice-edit")')
    text = text.replace('path("settings/next/", views.settings_page, name="next-settings")', 'path("settings/next/", tooltime_parity.settings_page, name="next-settings")')
    routes = '''    path("pricing/artikel-suche/", tooltime_parity.article_search, name="next-article-search"),\n    path("invoices/<int:pk>/mahnung/", tooltime_parity.invoice_dunning, name="next-invoice-dunning"),\n    path("angebot/<str:token>/", tooltime_parity.public_quote, name="next-public-quote"),\n'''
    if 'name="next-article-search"' not in text:
        text = text.replace("urlpatterns = [\n", "urlpatterns = [\n" + routes, 1)
    write(rel, text)


def install_tests() -> None:
    write("tests/test_tooltime_finance_parity_batch.py", r'''from pathlib import Path
from django.test import TestCase

ROOT = Path(__file__).resolve().parents[1]


class ToolTimeFinanceParityContractTests(TestCase):
    def test_runtime_files_are_installed(self):
        self.assertIn("A+BAU TOOLTIME FINANCE PARITY", (ROOT / "static/css/tooltime-parity-finance.css").read_text())
        self.assertIn("Leistungsgruppe hinzufügen", (ROOT / "templates/rebuild/document_editor.html").read_text())
        self.assertIn("Artikel durchsuchen", (ROOT / "templates/rebuild/document_editor.html").read_text())
        self.assertIn("Mahnwesen", (ROOT / "templates/rebuild/tooltime_settings.html").read_text())

    def test_german_visible_copy(self):
        template = (ROOT / "templates/rebuild/document_editor.html").read_text()
        for phrase in ("Kunde und Projekt", "Angebotsdetails", "Einleitungstext", "Leistungen", "Zahlungsbedingungen", "Schlusstext", "Fertigstellen"):
            self.assertIn(phrase, template)

    def test_routes_use_parity_views(self):
        urls = (ROOT / "erp/rebuild_urls.py").read_text()
        self.assertIn("tooltime_parity.quote_editor", urls)
        self.assertIn("tooltime_parity.invoice_editor", urls)
        self.assertIn('name="next-article-search"', urls)
        self.assertIn('name="next-invoice-dunning"', urls)
        self.assertIn('name="next-public-quote"', urls)

    def test_quote_draft_numbering_is_not_persisted(self):
        views = (ROOT / "erp/tooltime_parity_views.py").read_text()
        self.assertIn('elif meta.finalized_at is None and quote.number:', views)
        self.assertIn('quote.number = ""', views)
        self.assertIn('if action == "finalize":', views)

    def test_invoice_type_mixing_guard_exists(self):
        service = (ROOT / "erp/services/tooltime_parity_finance.py").read_text()
        self.assertIn("Abschlags- und Teilrechnungen können innerhalb desselben Projekts nicht kombiniert werden.", service)
''')


def run() -> None:
    install_models(); install_service(); install_views(); install_tags(); install_templates(); install_assets(); patch_urls(); install_tests()
    print("ToolTime-Finanzparität installiert: Angebote, Rechnungen, Nummern, Texte/Layout, Artikelsuche, Webansicht und Mahnwesen.")


if __name__ == "__main__":
    run()
