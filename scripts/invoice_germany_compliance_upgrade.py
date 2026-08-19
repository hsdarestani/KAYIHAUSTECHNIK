from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MARKER = "A+BAU GERMAN INVOICE COMPLIANCE 2026-08-20"


def read(rel: str) -> str:
    path = ROOT / rel
    if not path.exists():
        raise RuntimeError(f"Invoice compliance target missing: {rel}")
    return path.read_text(encoding="utf-8")


def write(rel: str, text: str) -> None:
    path = ROOT / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def install_models() -> None:
    write("erp/invoice_compliance.py", r'''from __future__ import annotations

from django.conf import settings
from django.db import models


class InvoiceNumberSequence(models.Model):
    organization = models.ForeignKey("erp.Organization", on_delete=models.PROTECT, related_name="invoice_number_sequences")
    year = models.PositiveIntegerField()
    prefix = models.CharField(max_length=20, default="RE")
    digits = models.PositiveSmallIntegerField(default=5)
    next_value = models.PositiveBigIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["organization", "year", "prefix"], name="uniq_invoice_sequence_org_year_prefix")]


class CustomerInvoiceProfile(models.Model):
    CUSTOMER_TYPES = [("b2c", "B2C"), ("b2b", "B2B"), ("authority", "Behörde")]
    FORMATS = [("pdf", "PDF"), ("xrechnung", "XRechnung"), ("zugferd", "ZUGFeRD")]

    organization = models.ForeignKey("erp.Organization", on_delete=models.CASCADE, related_name="customer_invoice_profiles")
    customer = models.OneToOneField("erp.Customer", on_delete=models.CASCADE, related_name="invoice_profile")
    customer_type = models.CharField(max_length=20, choices=CUSTOMER_TYPES, default="b2c")
    preferred_format = models.CharField(max_length=20, choices=FORMATS, default="pdf")
    invoice_email = models.EmailField(blank=True)
    tax_number = models.CharField(max_length=80, blank=True)
    leitweg_id = models.CharField(max_length=120, blank=True)
    peppol_id = models.CharField(max_length=180, blank=True)
    buyer_reference = models.CharField(max_length=180, blank=True)
    order_reference = models.CharField(max_length=180, blank=True)
    contract_reference = models.CharField(max_length=180, blank=True)
    project_reference = models.CharField(max_length=180, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["organization", "customer"], name="uniq_invoice_profile_org_customer")]


class InvoiceComplianceRecord(models.Model):
    STATES = [("draft", "Entwurf"), ("finalized", "Finalisiert"), ("cancelled", "Storniert"), ("credited", "Gutgeschrieben")]
    TYPES = [("invoice", "Rechnung"), ("credit_note", "Gutschrift"), ("cancellation", "Storno")]
    E_STATUS = [("not_required", "Nicht erforderlich"), ("not_validated", "Nicht validiert"), ("valid", "Valide"), ("invalid", "Ungültig"), ("error", "Validierungsfehler")]

    organization = models.ForeignKey("erp.Organization", on_delete=models.PROTECT, related_name="invoice_compliance_records")
    invoice = models.OneToOneField("erp.Invoice", on_delete=models.PROTECT, related_name="compliance")
    state = models.CharField(max_length=20, choices=STATES, default="draft")
    document_type = models.CharField(max_length=20, choices=TYPES, default="invoice")
    final_number = models.CharField(max_length=60, blank=True)
    finalized_at = models.DateTimeField(blank=True, null=True)
    snapshot = models.JSONField(default=dict, blank=True)
    snapshot_sha256 = models.CharField(max_length=64, blank=True)
    retention_until = models.DateField(blank=True, null=True)
    e_invoice_format = models.CharField(max_length=30, blank=True)
    e_invoice_status = models.CharField(max_length=30, choices=E_STATUS, default="not_required")
    schema_version = models.CharField(max_length=80, blank=True)
    generator_version = models.CharField(max_length=80, blank=True)
    validator_version = models.CharField(max_length=80, blank=True)
    validation_date = models.DateTimeField(blank=True, null=True)
    validation_errors = models.JSONField(default=list, blank=True)
    original_pdf_document = models.ForeignKey("erp.Document", on_delete=models.PROTECT, related_name="frozen_invoice_pdf_records", blank=True, null=True)
    original_xml_document = models.ForeignKey("erp.Document", on_delete=models.PROTECT, related_name="frozen_invoice_xml_records", blank=True, null=True)
    correction_of = models.ForeignKey("erp.Invoice", on_delete=models.PROTECT, related_name="corrections", blank=True, null=True)
    cancellation_of = models.ForeignKey("erp.Invoice", on_delete=models.PROTECT, related_name="cancellations", blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["organization", "final_number"], condition=~models.Q(final_number=""), name="uniq_final_invoice_number_per_org")]


class InvoiceAuditEvent(models.Model):
    organization = models.ForeignKey("erp.Organization", on_delete=models.PROTECT, related_name="invoice_audit_events")
    invoice = models.ForeignKey("erp.Invoice", on_delete=models.PROTECT, related_name="compliance_audit_events")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="invoice_compliance_events")
    timestamp = models.DateTimeField(auto_now_add=True)
    event_type = models.CharField(max_length=80)
    old_value = models.JSONField(default=dict, blank=True)
    new_value = models.JSONField(default=dict, blank=True)
    ip_address = models.GenericIPAddressField(blank=True, null=True)
    session_key = models.CharField(max_length=80, blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["timestamp", "pk"]
''')

    models_rel = "erp/models.py"
    models_text = read(models_rel)
    import_line = "from .invoice_compliance import CustomerInvoiceProfile, InvoiceAuditEvent, InvoiceComplianceRecord, InvoiceNumberSequence"
    if import_line not in models_text:
        models_text = models_text.rstrip() + "\n\n# German invoice compliance sidecar models.\n" + import_line + "\n"
        write(models_rel, models_text)

    migration = r'''from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("erp", "0010_ab_bau_commercial"),
    ]
    operations = [
        migrations.CreateModel(
            name="InvoiceNumberSequence",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("year", models.PositiveIntegerField()),
                ("prefix", models.CharField(default="RE", max_length=20)),
                ("digits", models.PositiveSmallIntegerField(default=5)),
                ("next_value", models.PositiveBigIntegerField(default=1)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("organization", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="invoice_number_sequences", to="erp.organization")),
            ],
        ),
        migrations.CreateModel(
            name="CustomerInvoiceProfile",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("customer_type", models.CharField(choices=[("b2c", "B2C"), ("b2b", "B2B"), ("authority", "Behörde")], default="b2c", max_length=20)),
                ("preferred_format", models.CharField(choices=[("pdf", "PDF"), ("xrechnung", "XRechnung"), ("zugferd", "ZUGFeRD")], default="pdf", max_length=20)),
                ("invoice_email", models.EmailField(blank=True, max_length=254)),
                ("tax_number", models.CharField(blank=True, max_length=80)),
                ("leitweg_id", models.CharField(blank=True, max_length=120)),
                ("peppol_id", models.CharField(blank=True, max_length=180)),
                ("buyer_reference", models.CharField(blank=True, max_length=180)),
                ("order_reference", models.CharField(blank=True, max_length=180)),
                ("contract_reference", models.CharField(blank=True, max_length=180)),
                ("project_reference", models.CharField(blank=True, max_length=180)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("customer", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="invoice_profile", to="erp.customer")),
                ("organization", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="customer_invoice_profiles", to="erp.organization")),
            ],
        ),
        migrations.CreateModel(
            name="InvoiceComplianceRecord",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("state", models.CharField(choices=[("draft", "Entwurf"), ("finalized", "Finalisiert"), ("cancelled", "Storniert"), ("credited", "Gutgeschrieben")], default="draft", max_length=20)),
                ("document_type", models.CharField(choices=[("invoice", "Rechnung"), ("credit_note", "Gutschrift"), ("cancellation", "Storno")], default="invoice", max_length=20)),
                ("final_number", models.CharField(blank=True, max_length=60)),
                ("finalized_at", models.DateTimeField(blank=True, null=True)),
                ("snapshot", models.JSONField(blank=True, default=dict)),
                ("snapshot_sha256", models.CharField(blank=True, max_length=64)),
                ("retention_until", models.DateField(blank=True, null=True)),
                ("e_invoice_format", models.CharField(blank=True, max_length=30)),
                ("e_invoice_status", models.CharField(choices=[("not_required", "Nicht erforderlich"), ("not_validated", "Nicht validiert"), ("valid", "Valide"), ("invalid", "Ungültig"), ("error", "Validierungsfehler")], default="not_required", max_length=30)),
                ("schema_version", models.CharField(blank=True, max_length=80)),
                ("generator_version", models.CharField(blank=True, max_length=80)),
                ("validator_version", models.CharField(blank=True, max_length=80)),
                ("validation_date", models.DateTimeField(blank=True, null=True)),
                ("validation_errors", models.JSONField(blank=True, default=list)),
                ("cancellation_of", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="cancellations", to="erp.invoice")),
                ("correction_of", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="corrections", to="erp.invoice")),
                ("invoice", models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, related_name="compliance", to="erp.invoice")),
                ("organization", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="invoice_compliance_records", to="erp.organization")),
                ("original_pdf_document", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="frozen_invoice_pdf_records", to="erp.document")),
                ("original_xml_document", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="frozen_invoice_xml_records", to="erp.document")),
            ],
        ),
        migrations.CreateModel(
            name="InvoiceAuditEvent",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("timestamp", models.DateTimeField(auto_now_add=True)),
                ("event_type", models.CharField(max_length=80)),
                ("old_value", models.JSONField(blank=True, default=dict)),
                ("new_value", models.JSONField(blank=True, default=dict)),
                ("ip_address", models.GenericIPAddressField(blank=True, null=True)),
                ("session_key", models.CharField(blank=True, max_length=80)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("invoice", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="compliance_audit_events", to="erp.invoice")),
                ("organization", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="invoice_audit_events", to="erp.organization")),
                ("user", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="invoice_compliance_events", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["timestamp", "pk"]},
        ),
        migrations.AddConstraint(model_name="invoicenumbersequence", constraint=models.UniqueConstraint(fields=("organization", "year", "prefix"), name="uniq_invoice_sequence_org_year_prefix")),
        migrations.AddConstraint(model_name="customerinvoiceprofile", constraint=models.UniqueConstraint(fields=("organization", "customer"), name="uniq_invoice_profile_org_customer")),
        migrations.AddConstraint(model_name="invoicecompliancerecord", constraint=models.UniqueConstraint(condition=models.Q(("final_number", ""), _negated=True), fields=("organization", "final_number"), name="uniq_final_invoice_number_per_org")),
    ]
'''
    write("erp/migrations/0011_invoice_germany_compliance.py", migration)


def install_service() -> None:
    write("erp/services/invoice_compliance_service.py", r'''from __future__ import annotations

import hashlib
import html
import json
import os
import re
import urllib.error
import urllib.request
from collections import defaultdict
from datetime import date, datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from xml.etree import ElementTree as ET

from django.core.files.base import ContentFile
from django.db import transaction
from django.utils import timezone

from erp import models as m
from erp.services.business_pdf_identity import business_identity, inject_business_pdf_identity
from erp.services.field_authorization import html_to_pdf_bytes

MONEY = Decimal("0.01")
GENERATOR_VERSION = "ab-bau-invoice-core-2026.08.20"
XRECHNUNG_CUSTOMIZATION_ID = "urn:cen.eu:en16931:2017#compliant#urn:xeinkauf.de:kosit:xrechnung_3.0"
XRECHNUNG_PROFILE_ID = "urn:fdc:peppol.eu:2017:poacc:billing:01:1.0"
XRECHNUNG_SCHEMA_VERSION = "XRechnung 3.0.x / KoSIT configuration 2026-01-31"


class ComplianceError(ValueError):
    pass


def money(value) -> Decimal:
    try:
        return Decimal(str(value if value not in (None, "") else "0").replace(",", ".")).quantize(MONEY, rounding=ROUND_HALF_UP)
    except (InvalidOperation, TypeError, ValueError):
        return Decimal("0.00")


def _json(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _sha(value) -> str:
    return hashlib.sha256(_json(value).encode("utf-8")).hexdigest()


def _settings(org) -> dict:
    raw = getattr(org, "settings", None)
    return raw if isinstance(raw, dict) else {}


def get_compliance(invoice):
    if invoice is None:
        return None
    try:
        return invoice.compliance
    except (m.InvoiceComplianceRecord.DoesNotExist, AttributeError):
        return None


def is_finalized(invoice) -> bool:
    record = get_compliance(invoice)
    return bool(record and record.state in {"finalized", "cancelled", "credited"})


def _profile(customer, org):
    try:
        return customer.invoice_profile
    except (m.CustomerInvoiceProfile.DoesNotExist, AttributeError):
        inferred = "b2b" if getattr(customer, "type", "") in {"business", "insurance", "property_manager"} else "b2c"
        return m.CustomerInvoiceProfile(organization=org, customer=customer, customer_type=inferred, invoice_email=getattr(customer, "email", "") or "")


def save_customer_profile(invoice, post):
    if not invoice or not invoice.project_id or not invoice.project.customer_id:
        return None
    customer = invoice.project.customer
    profile, _ = m.CustomerInvoiceProfile.objects.get_or_create(
        organization=invoice.organization,
        customer=customer,
        defaults={"customer_type": "b2b" if customer.type in {"business", "insurance", "property_manager"} else "b2c"},
    )
    profile.customer_type = (post.get("invoice_customer_type") or profile.customer_type or "b2c")[:20]
    if profile.customer_type not in {"b2c", "b2b", "authority"}:
        profile.customer_type = "b2c"
    profile.preferred_format = (post.get("invoice_preferred_format") or profile.preferred_format or "pdf")[:20]
    if profile.preferred_format not in {"pdf", "xrechnung", "zugferd"}:
        profile.preferred_format = "pdf"
    for field in ("invoice_email", "tax_number", "leitweg_id", "peppol_id", "buyer_reference", "order_reference", "contract_reference", "project_reference"):
        if field in post:
            setattr(profile, field, (post.get(field) or "").strip())
    profile.save()
    return profile


def _seller(org):
    identity = business_identity(org)
    settings = _settings(org)
    legal = settings.get("invoice_legal") if isinstance(settings.get("invoice_legal"), dict) else {}
    full_address = (getattr(org, "address", "") or "").strip()
    if not full_address:
        full_address = ", ".join(part for part in (identity.get("street"), identity.get("city_line"), identity.get("country")) if part)
    tax_number = identity.get("tax_number") or getattr(org, "tax_id", "") or legal.get("tax_number", "")
    vat_id = identity.get("vat_id") or legal.get("vat_id", "")
    return {
        "name": identity.get("name") or getattr(org, "legal_name", "") or getattr(org, "name", ""),
        "address": full_address,
        "street": legal.get("street", identity.get("street", "")),
        "postal_code": legal.get("postal_code", ""),
        "city": legal.get("city", ""),
        "country": legal.get("country", "DE") or "DE",
        "email": identity.get("email") or getattr(org, "email", ""),
        "phone": identity.get("phone") or getattr(org, "phone", ""),
        "website": identity.get("website", ""),
        "tax_number": str(tax_number or ""),
        "vat_id": str(vat_id or ""),
        "register": identity.get("register", "") or legal.get("register_number", ""),
        "register_court": identity.get("register_court", "") or legal.get("register_court", ""),
        "managing_director": identity.get("managing_director", "") or legal.get("managing_director", ""),
        "iban": identity.get("iban") or getattr(org, "iban", "") or legal.get("iban", ""),
        "bic": identity.get("bic", "") or legal.get("bic", ""),
        "bank": identity.get("bank", "") or legal.get("bank_name", ""),
    }


def _buyer(invoice):
    customer = invoice.project.customer
    profile = _profile(customer, invoice.organization)
    name = (getattr(customer, "company", "") or "").strip()
    if not name:
        name = " ".join(part for part in (getattr(customer, "first_name", ""), getattr(customer, "last_name", "")) if part).strip()
    address = ", ".join(part for part in (getattr(customer, "street", ""), f"{getattr(customer, 'postal_code', '')} {getattr(customer, 'city', '')}".strip(), getattr(customer, "country", "")) if part)
    return {
        "id": customer.pk,
        "number": getattr(customer, "number", "") or "",
        "name": name,
        "address": address,
        "street": getattr(customer, "street", "") or "",
        "postal_code": getattr(customer, "postal_code", "") or "",
        "city": getattr(customer, "city", "") or "",
        "country": getattr(customer, "country", "") or "DE",
        "email": profile.invoice_email or getattr(customer, "email", "") or "",
        "vat_id": getattr(customer, "vat_id", "") or "",
        "tax_number": profile.tax_number or "",
        "type": profile.customer_type,
        "preferred_format": profile.preferred_format,
        "leitweg_id": profile.leitweg_id or "",
        "peppol_id": profile.peppol_id or "",
        "buyer_reference": profile.buyer_reference or profile.leitweg_id or getattr(customer, "number", "") or "KUNDE",
        "order_reference": profile.order_reference or "",
        "contract_reference": profile.contract_reference or "",
        "project_reference": profile.project_reference or getattr(invoice.project, "number", "") or "",
    }


def _commercial(invoice):
    try:
        return invoice.commercial_settings
    except Exception:
        return None


def _tax_code(invoice):
    settings = _commercial(invoice)
    return getattr(settings, "tax_code", "19") if settings else "19"


def _tax_reason(code: str, org) -> str:
    custom = _settings(org).get("invoice_tax_reason") or ""
    return {
        "0_19": "Gemäß § 19 UStG wird keine Umsatzsteuer berechnet.",
        "0_13b": "Steuerschuldnerschaft des Leistungsempfängers (§ 13b UStG).",
        "0_4": "Umsatzsteuerfrei gemäß § 4 UStG.",
        "0": str(custom),
    }.get(code, "")


def _discount(invoice, raw_net: Decimal) -> Decimal:
    settings = _commercial(invoice)
    if settings is None:
        return Decimal("0.00")
    value = max(Decimal("0"), money(getattr(settings, "discount_value", 0)))
    if getattr(settings, "discount_type", "percent") == "fixed":
        return min(raw_net, value)
    return min(raw_net, (raw_net * value / Decimal("100")).quantize(MONEY, rounding=ROUND_HALF_UP))


def build_core(invoice, *, number: str | None = None, document_type: str | None = None) -> dict:
    org = invoice.organization
    seller = _seller(org)
    buyer = _buyer(invoice)
    compliance = get_compliance(invoice)
    document_type = document_type or getattr(compliance, "document_type", "invoice") or "invoice"
    lines = []
    raw_by_rate: dict[str, Decimal] = defaultdict(lambda: Decimal("0.00"))
    raw_net = Decimal("0.00")
    for item in invoice.items.all().order_by("position", "pk"):
        qty = Decimal(str(item.quantity)).quantize(Decimal("0.001"))
        unit_price = money(item.unit_price)
        line_net = (qty * unit_price).quantize(MONEY, rounding=ROUND_HALF_UP)
        rate = money(item.tax_rate)
        raw_net += line_net
        raw_by_rate[str(rate)] += line_net
        lines.append({
            "position": item.position,
            "code": item.code or "",
            "description": (item.description or "").strip(),
            "quantity": str(qty),
            "unit": item.unit or "Stk.",
            "unit_price": str(unit_price),
            "tax_rate": str(rate),
            "net": str(line_net),
        })
    discount = _discount(invoice, raw_net)
    tax_groups = []
    tax_total = Decimal("0.00")
    net_total = Decimal("0.00")
    for rate_key, taxable_raw in sorted(raw_by_rate.items(), key=lambda row: Decimal(row[0])):
        share = (taxable_raw / raw_net) if raw_net else Decimal("0")
        group_discount = (discount * share).quantize(MONEY, rounding=ROUND_HALF_UP) if discount else Decimal("0.00")
        taxable = max(Decimal("0.00"), taxable_raw - group_discount)
        rate = Decimal(rate_key)
        tax = (taxable * rate / Decimal("100")).quantize(MONEY, rounding=ROUND_HALF_UP)
        net_total += taxable
        tax_total += tax
        tax_groups.append({"rate": str(rate), "taxable": str(taxable), "tax": str(tax)})
    gross_total = (net_total + tax_total).quantize(MONEY)
    sign = Decimal("-1") if document_type in {"credit_note", "cancellation"} else Decimal("1")
    settings = _settings(org)
    return {
        "schema": "ab-bau.invoice-core.v1",
        "invoice_id": invoice.pk,
        "invoice_number": number if number is not None else (invoice.number or ""),
        "document_type": document_type,
        "seller": seller,
        "buyer": buyer,
        "issue_date": invoice.issue_date.isoformat() if invoice.issue_date else "",
        "service_date": invoice.service_date.isoformat() if invoice.service_date else "",
        "due_date": invoice.due_date.isoformat() if invoice.due_date else "",
        "currency": settings.get("invoice_currency", "EUR") or "EUR",
        "items": lines,
        "discount": str(discount),
        "net_total": str((net_total * sign).quantize(MONEY)),
        "tax_total": str((tax_total * sign).quantize(MONEY)),
        "gross_total": str((gross_total * sign).quantize(MONEY)),
        "absolute_net_total": str(net_total.quantize(MONEY)),
        "absolute_tax_total": str(tax_total.quantize(MONEY)),
        "absolute_gross_total": str(gross_total.quantize(MONEY)),
        "tax_groups": tax_groups,
        "tax_code": _tax_code(invoice),
        "tax_reason": _tax_reason(_tax_code(invoice), org),
        "payment": {"iban": seller.get("iban", ""), "bic": seller.get("bic", ""), "bank": seller.get("bank", ""), "terms": f"Zahlbar bis {invoice.due_date:%d.%m.%Y}" if invoice.due_date else ""},
        "references": {
            "project": buyer.get("project_reference", ""),
            "buyer": buyer.get("buyer_reference", ""),
            "order": buyer.get("order_reference", ""),
            "contract": buyer.get("contract_reference", ""),
            "correction_of": getattr(getattr(compliance, "correction_of", None), "number", "") if compliance else "",
            "cancellation_of": getattr(getattr(compliance, "cancellation_of", None), "number", "") if compliance else "",
        },
    }


def validate_core(core: dict, *, require_number: bool) -> list[str]:
    errors = []
    seller, buyer = core["seller"], core["buyer"]
    if not seller.get("name"): errors.append("Vollständiger Name des Leistungserbringers fehlt.")
    if not seller.get("address"): errors.append("Vollständige Anschrift des Leistungserbringers fehlt.")
    if not (seller.get("tax_number") or seller.get("vat_id")): errors.append("Steuernummer oder USt-IdNr. des Leistungserbringers fehlt.")
    if not buyer.get("name"): errors.append("Vollständiger Name des Leistungsempfängers fehlt.")
    if not buyer.get("address"): errors.append("Vollständige Anschrift des Leistungsempfängers fehlt.")
    if not core.get("issue_date"): errors.append("Ausstellungsdatum fehlt.")
    if require_number and not core.get("invoice_number"): errors.append("Eindeutige Rechnungsnummer fehlt.")
    if not core.get("service_date"): errors.append("Leistungsdatum / Leistungszeitpunkt fehlt.")
    if not core.get("items"): errors.append("Mindestens eine Rechnungsposition ist erforderlich.")
    for index, item in enumerate(core.get("items") or [], 1):
        if not item.get("description"): errors.append(f"Position {index}: Art/Umfang der Leistung fehlt.")
        if Decimal(item.get("quantity") or "0") <= 0: errors.append(f"Position {index}: Menge muss größer als 0 sein.")
        if item.get("tax_rate") in (None, ""): errors.append(f"Position {index}: Steuersatz fehlt.")
    if core.get("tax_code") in {"0", "0_19", "0_13b", "0_4"} and not core.get("tax_reason"):
        errors.append("Bei 0 % Umsatzsteuer muss der Steuerbefreiungs-/Steuerschuldnerschaftsgrund angegeben werden.")
    if buyer.get("type") == "authority" and not (buyer.get("leitweg_id") or buyer.get("buyer_reference")):
        errors.append("Für Behördenkunden fehlt Leitweg-ID / Buyer Reference.")
    if buyer.get("type") in {"b2b", "authority"} and not buyer.get("email") and not buyer.get("peppol_id"):
        errors.append("Für die elektronische Rechnungszustellung fehlt Rechnungs-E-Mail oder Peppol-ID.")
    if not core.get("due_date"): errors.append("Zahlungsziel / Fälligkeitsdatum fehlt.")
    return errors


def _number_settings(org):
    settings = _settings(org)
    prefix = str(settings.get("invoice_number_prefix") or "RE").strip()[:20] or "RE"
    digits = max(3, min(int(settings.get("invoice_number_digits") or 5), 12))
    start = max(1, int(settings.get("invoice_number_start") or 1))
    return prefix, digits, start


def allocate_number(invoice) -> str:
    prefix, digits, start = _number_settings(invoice.organization)
    year = invoice.issue_date.year
    seq, created = m.InvoiceNumberSequence.objects.select_for_update().get_or_create(
        organization=invoice.organization,
        year=year,
        prefix=prefix,
        defaults={"digits": digits, "next_value": start},
    )
    if not created and seq.digits != digits:
        seq.digits = digits
    value = seq.next_value
    seq.next_value = value + 1
    seq.save(update_fields=["digits", "next_value", "updated_at"])
    return f"{prefix}-{year}-{value:0{seq.digits}d}"


def _retention_until(issue_date: date) -> date:
    return date(issue_date.year + 8, 12, 31)


def _client_ip(request) -> str | None:
    if request is None:
        return None
    forwarded = (request.META.get("HTTP_X_FORWARDED_FOR") or "").split(",")[0].strip()
    return forwarded or request.META.get("REMOTE_ADDR") or None


def audit(invoice, event_type: str, *, user=None, request=None, old=None, new=None, metadata=None):
    return m.InvoiceAuditEvent.objects.create(
        organization=invoice.organization,
        invoice=invoice,
        user=user if getattr(user, "is_authenticated", False) else None,
        event_type=event_type,
        old_value=old or {},
        new_value=new or {},
        ip_address=_client_ip(request),
        session_key=getattr(getattr(request, "session", None), "session_key", "") or "",
        metadata=metadata or {},
    )


def _unit_code(unit: str) -> str:
    value = (unit or "").strip().casefold()
    return {"stk.": "C62", "stk": "C62", "stück": "C62", "st": "C62", "h": "HUR", "std.": "HUR", "stunde": "HUR", "tag": "DAY", "woche": "WEE", "monat": "MON", "m": "MTR", "m²": "MTK", "m2": "MTK", "m³": "MTQ", "m3": "MTQ", "kg": "KGM", "l": "LTR", "pauschal": "LS", "psch": "LS"}.get(value, "C62")


def _vat_category(core: dict, rate: Decimal) -> tuple[str, str]:
    code = core.get("tax_code")
    if code == "0_13b": return "AE", core.get("tax_reason") or "Reverse charge"
    if rate == 0: return "E", core.get("tax_reason") or "Steuerbefreit"
    return "S", ""


def xrechnung_xml(core: dict) -> bytes:
    ns = {
        "ubl": "urn:oasis:names:specification:ubl:schema:xsd:Invoice-2",
        "credit": "urn:oasis:names:specification:ubl:schema:xsd:CreditNote-2",
        "cac": "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2",
        "cbc": "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2",
    }
    for key, value in ns.items(): ET.register_namespace(key, value)
    credit = core.get("document_type") in {"credit_note", "cancellation"}
    root = ET.Element(f"{{{ns['credit'] if credit else ns['ubl']}}}{'CreditNote' if credit else 'Invoice'}")
    cbc, cac = ns["cbc"], ns["cac"]
    def b(parent, name, value, **attrs):
        if value in (None, ""): return None
        node = ET.SubElement(parent, f"{{{cbc}}}{name}", attrs); node.text = str(value); return node
    def a(parent, name): return ET.SubElement(parent, f"{{{cac}}}{name}")

    b(root, "CustomizationID", XRECHNUNG_CUSTOMIZATION_ID)
    b(root, "ProfileID", XRECHNUNG_PROFILE_ID)
    b(root, "ID", core["invoice_number"])
    b(root, "IssueDate", core["issue_date"])
    b(root, "InvoiceTypeCode" if not credit else "CreditNoteTypeCode", "380" if not credit else "381")
    b(root, "DocumentCurrencyCode", core["currency"])
    b(root, "BuyerReference", core["buyer"].get("buyer_reference") or core["buyer"].get("number") or "KUNDE")
    if core.get("tax_reason"): b(root, "Note", core["tax_reason"])
    if core["references"].get("correction_of") or core["references"].get("cancellation_of"):
        ref = a(root, "BillingReference"); doc = a(ref, "InvoiceDocumentReference"); b(doc, "ID", core["references"].get("correction_of") or core["references"].get("cancellation_of"))
    if core["references"].get("order"):
        order = a(root, "OrderReference"); b(order, "ID", core["references"]["order"])
    if core["references"].get("contract"):
        contract = a(root, "ContractDocumentReference"); b(contract, "ID", core["references"]["contract"])

    def party(parent, data, supplier: bool):
        block = a(parent, "AccountingSupplierParty" if supplier else "AccountingCustomerParty")
        p = a(block, "Party")
        endpoint = data.get("peppol_id") or data.get("email")
        if endpoint:
            b(p, "EndpointID", endpoint, schemeID="0088" if data.get("peppol_id") else "EM")
        pname = a(p, "PartyName"); b(pname, "Name", data.get("name"))
        addr = a(p, "PostalAddress")
        b(addr, "StreetName", data.get("street") or data.get("address"))
        b(addr, "CityName", data.get("city"))
        b(addr, "PostalZone", data.get("postal_code"))
        country = a(addr, "Country"); b(country, "IdentificationCode", (data.get("country") or "DE")[:2].upper())
        tax_id = data.get("vat_id") or data.get("tax_number")
        if tax_id:
            pts = a(p, "PartyTaxScheme"); b(pts, "CompanyID", tax_id); scheme = a(pts, "TaxScheme"); b(scheme, "ID", "VAT")
        legal = a(p, "PartyLegalEntity"); b(legal, "RegistrationName", data.get("name")); b(legal, "CompanyID", data.get("register"))
        if supplier:
            contact = a(p, "Contact"); b(contact, "Telephone", data.get("phone")); b(contact, "ElectronicMail", data.get("email"))
    party(root, core["seller"], True); party(root, core["buyer"], False)

    if core.get("service_date"):
        period = a(root, "InvoicePeriod"); b(period, "StartDate", core["service_date"]); b(period, "EndDate", core["service_date"])
    pay = a(root, "PaymentMeans"); b(pay, "PaymentMeansCode", "58")
    if core["payment"].get("iban"):
        acct = a(pay, "PayeeFinancialAccount"); b(acct, "ID", re.sub(r"\s+", "", core["payment"]["iban"]))
    terms = a(root, "PaymentTerms"); b(terms, "Note", core["payment"].get("terms") or "Zahlbar gemäß Zahlungsziel.")

    tax_total = a(root, "TaxTotal"); b(tax_total, "TaxAmount", core["absolute_tax_total"], currencyID=core["currency"])
    for group in core.get("tax_groups") or []:
        sub = a(tax_total, "TaxSubtotal"); b(sub, "TaxableAmount", group["taxable"], currencyID=core["currency"]); b(sub, "TaxAmount", group["tax"], currencyID=core["currency"])
        cat = a(sub, "TaxCategory"); cat_code, reason = _vat_category(core, Decimal(group["rate"])); b(cat, "ID", cat_code); b(cat, "Percent", group["rate"])
        if reason: b(cat, "TaxExemptionReason", reason)
        scheme = a(cat, "TaxScheme"); b(scheme, "ID", "VAT")
    total = a(root, "LegalMonetaryTotal")
    b(total, "LineExtensionAmount", str(sum((Decimal(i["net"]) for i in core["items"]), Decimal("0.00"))), currencyID=core["currency"])
    if Decimal(core.get("discount") or "0") > 0:
        b(total, "AllowanceTotalAmount", core["discount"], currencyID=core["currency"])
    b(total, "TaxExclusiveAmount", core["absolute_net_total"], currencyID=core["currency"])
    b(total, "TaxInclusiveAmount", core["absolute_gross_total"], currencyID=core["currency"])
    b(total, "PayableAmount", core["absolute_gross_total"], currencyID=core["currency"])

    for item in core["items"]:
        line = a(root, "CreditNoteLine" if credit else "InvoiceLine")
        b(line, "ID", item.get("position"))
        b(line, "CreditedQuantity" if credit else "InvoicedQuantity", item["quantity"], unitCode=_unit_code(item["unit"]))
        b(line, "LineExtensionAmount", item["net"], currencyID=core["currency"])
        ip = a(line, "InvoicePeriod"); b(ip, "StartDate", core.get("service_date")); b(ip, "EndDate", core.get("service_date"))
        it = a(line, "Item"); b(it, "Description", item["description"]); b(it, "Name", item["description"][:100])
        cat = a(it, "ClassifiedTaxCategory"); cat_code, reason = _vat_category(core, Decimal(item["tax_rate"])); b(cat, "ID", cat_code); b(cat, "Percent", item["tax_rate"])
        if reason: b(cat, "TaxExemptionReason", reason)
        scheme = a(cat, "TaxScheme"); b(scheme, "ID", "VAT")
        price = a(line, "Price"); b(price, "PriceAmount", item["unit_price"], currencyID=core["currency"])
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def validate_xrechnung(xml_bytes: bytes) -> dict:
    url = (os.environ.get("XRECHNUNG_VALIDATOR_URL") or "").strip()
    version = (os.environ.get("XRECHNUNG_VALIDATOR_VERSION") or "KoSIT external validator").strip()
    if not url:
        return {"status": "not_validated", "version": "", "errors": ["Kein echter XRechnung-Validator konfiguriert (XRECHNUNG_VALIDATOR_URL)."]}
    req = urllib.request.Request(url.rstrip("/") + "/invoice.xml", data=xml_bytes, headers={"Content-Type": "application/xml"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=25) as response:
            body = response.read().decode("utf-8", errors="replace")
            if response.status == 200:
                return {"status": "valid", "version": version, "errors": [], "report": body[:20000]}
            return {"status": "error", "version": version, "errors": [f"Validator HTTP {response.status}"], "report": body[:20000]}
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        if exc.code == 406:
            return {"status": "invalid", "version": version, "errors": ["XRechnung ist nach Validator-Regeln nicht akzeptabel."], "report": body[:20000]}
        return {"status": "error", "version": version, "errors": [f"Validator-Verarbeitung fehlgeschlagen (HTTP {exc.code})."], "report": body[:20000]}
    except Exception as exc:
        return {"status": "error", "version": version, "errors": [f"Validator nicht erreichbar: {exc}" ]}


def _transition_end(org) -> date:
    raw = str(_settings(org).get("einvoice_transition_end") or "2026-12-31")
    try: return date.fromisoformat(raw)
    except ValueError: return date(2026, 12, 31)


def e_invoice_required(core: dict, org) -> bool:
    buyer_type = core["buyer"].get("type")
    if buyer_type == "authority": return True
    if buyer_type != "b2b": return False
    issue = date.fromisoformat(core["issue_date"])
    return issue > _transition_end(org)


def _fmt(value) -> str:
    return f"{money(value):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def invoice_pdf_html(core: dict, org) -> str:
    e = lambda v: html.escape(str(v or ""))
    title = {"invoice": "Rechnung", "credit_note": "Gutschrift", "cancellation": "Stornorechnung"}.get(core.get("document_type"), "Rechnung")
    sign = "−" if core.get("document_type") in {"credit_note", "cancellation"} else ""
    rows = "".join(
        f'<tr><td>{e(i["position"])}</td><td><b>{e(i["description"])}</b></td><td class="r">{e(i["quantity"])} {e(i["unit"])}</td><td class="r">{_fmt(i["unit_price"])} €</td><td class="r">{e(i["tax_rate"])} %</td><td class="r">{sign}{_fmt(i["net"])} €</td></tr>'
        for i in core["items"]
    )
    tax_rows = "".join(f'<div><span>USt. {e(g["rate"])} % auf {_fmt(g["taxable"])} €</span><b>{sign}{_fmt(g["tax"])} €</b></div>' for g in core["tax_groups"])
    refs = []
    for label, key in (("Bestellreferenz", "order"), ("Vertragsreferenz", "contract"), ("Projektreferenz", "project"), ("Korrektur zu", "correction_of"), ("Storno zu", "cancellation_of")):
        if core["references"].get(key): refs.append(f"<span><small>{label}</small><b>{e(core['references'][key])}</b></span>")
    tax_note = f'<div class="notice">{e(core["tax_reason"])}</div>' if core.get("tax_reason") else ""
    body = f"""<!doctype html><html lang="de"><head><meta charset="utf-8"><title>{e(title)} {e(core['invoice_number'])}</title><style>
    @page{{size:A4;margin:16mm 14mm 18mm}}*{{box-sizing:border-box}}body{{font-family:Arial,Helvetica,sans-serif;color:#182126;font-size:10px;line-height:1.45;margin:0}}.dochead{{display:flex;justify-content:space-between;align-items:flex-start;margin:24px 0 18px}}h1{{font-size:30px;margin:0}}.number{{text-align:right;font-size:11px}}.number b{{display:block;font-size:17px}}.addresses{{display:grid;grid-template-columns:1fr 1fr;gap:18px;margin:10px 0 18px}}.box{{border:1px solid #e1e6e8;border-radius:10px;padding:11px}}small{{color:#6e777d;font-size:8px;display:block}}.meta{{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin-bottom:14px}}.meta>div{{border:1px solid #e4e8ea;border-radius:9px;padding:8px}}table{{width:100%;border-collapse:collapse}}th,td{{padding:7px 5px;border-bottom:1px solid #e5e8e9;text-align:left}}th{{background:#f6f8f8;color:#59656c}}.r{{text-align:right}}.totals{{margin:14px 0 0 auto;max-width:320px;display:grid;gap:6px}}.totals>div{{display:flex;justify-content:space-between}}.grand{{font-size:16px;border-top:2px solid #222;padding-top:8px}}.notice{{margin-top:14px;padding:9px 11px;background:#f7f8f8;border-radius:8px}}.refs{{display:flex;gap:12px;flex-wrap:wrap;margin:10px 0}}.payment{{margin-top:18px;border-top:1px solid #ddd;padding-top:10px}}</style></head><body>
    <div class="dochead"><div><h1>{e(title)}</h1><div>{e(core['seller']['name'])}</div></div><div class="number"><small>Rechnungsnummer</small><b>{e(core['invoice_number'])}</b><span>{e(core['issue_date'])}</span></div></div>
    <div class="addresses"><div class="box"><small>Leistungsempfänger</small><b>{e(core['buyer']['name'])}</b><br>{e(core['buyer']['address'])}</div><div class="box"><small>Leistungserbringer</small><b>{e(core['seller']['name'])}</b><br>{e(core['seller']['address'])}<br>{'USt-IdNr. ' + e(core['seller']['vat_id']) if core['seller']['vat_id'] else 'Steuernr. ' + e(core['seller']['tax_number'])}</div></div>
    <div class="meta"><div><small>Ausstellungsdatum</small><b>{e(core['issue_date'])}</b></div><div><small>Leistungsdatum</small><b>{e(core['service_date'])}</b></div><div><small>Fällig am</small><b>{e(core['due_date'])}</b></div></div>
    <div class="refs">{''.join(refs)}</div>
    <table><thead><tr><th>Pos.</th><th>Leistung / Gegenstand</th><th class="r">Menge</th><th class="r">Einzelpreis netto</th><th class="r">USt.</th><th class="r">Netto</th></tr></thead><tbody>{rows}</tbody></table>
    <div class="totals"><div><span>Netto</span><b>{_fmt(core['net_total'])} €</b></div>{tax_rows}<div class="grand"><span>Gesamt</span><b>{_fmt(core['gross_total'])} €</b></div></div>
    {tax_note}
    <div class="payment"><b>Zahlungsinformationen</b><p>{e(core['payment']['terms'])}<br>{e(core['payment']['bank'])} · IBAN {e(core['payment']['iban'])}{' · BIC ' + e(core['payment']['bic']) if core['payment']['bic'] else ''}</p></div>
    </body></html>"""
    return inject_business_pdf_identity(body, org=org, document_kind=title)


def _save_document(invoice, *, filename: str, payload: bytes, mime: str, kind: str, retention_until: date, user=None):
    customer = invoice.project.customer if invoice.project_id else None
    doc = m.Document(
        organization=invoice.organization,
        project=invoice.project,
        customer=customer,
        uploaded_by=user if getattr(user, "is_authenticated", False) else None,
        title=filename,
        category="invoice",
        mime_type=mime,
        size=len(payload),
        sha256=hashlib.sha256(payload).hexdigest(),
        metadata={"kind": kind, "invoice_id": invoice.pk, "invoice_number": invoice.number, "retention_until": retention_until.isoformat(), "immutable_original": True},
    )
    doc.file.save(filename, ContentFile(payload), save=False)
    doc.save()
    return doc


def finalize_invoice(invoice, *, user=None, request=None):
    with transaction.atomic():
        invoice = m.Invoice.objects.select_for_update().select_related("organization", "project", "project__customer").get(pk=invoice.pk, organization=invoice.organization)
        record, _ = m.InvoiceComplianceRecord.objects.select_for_update().get_or_create(organization=invoice.organization, invoice=invoice)
        if record.state != "draft":
            raise ComplianceError("Diese Rechnung wurde bereits finalisiert und darf nicht still überschrieben werden.")
        pre_core = build_core(invoice, number="", document_type=record.document_type)
        errors = validate_core(pre_core, require_number=False)
        if errors:
            raise ComplianceError(" | ".join(errors))
        number = allocate_number(invoice)
        if m.Invoice.objects.filter(organization=invoice.organization, number=number).exclude(pk=invoice.pk).exists():
            raise ComplianceError("Rechnungsnummer ist nicht eindeutig. Bitte Nummernkreis prüfen.")
        invoice.number = number
        invoice.status = "review"
        invoice.save(update_fields=["number", "status", "updated_at"])
        core = build_core(invoice, number=number, document_type=record.document_type)
        errors = validate_core(core, require_number=True)
        if errors:
            raise ComplianceError(" | ".join(errors))

        xml_doc = None
        validation = {"status": "not_required", "version": "", "errors": []}
        e_format = ""
        if core["buyer"].get("type") in {"b2b", "authority"}:
            e_format = "XRECHNUNG"
            xml = xrechnung_xml(core)
            validation = validate_xrechnung(xml)
            if e_invoice_required(core, invoice.organization) and validation["status"] != "valid":
                raise ComplianceError("E-Rechnung ist für diesen Vorgang erforderlich, aber nicht valide: " + " ".join(validation.get("errors") or []))
        retention = _retention_until(invoice.issue_date)
        pdf = html_to_pdf_bytes(invoice_pdf_html(core, invoice.organization))
        pdf_doc = _save_document(invoice, filename=f"rechnung-{number}.pdf", payload=pdf, mime="application/pdf", kind="invoice_original_pdf", retention_until=retention, user=user)
        if core["buyer"].get("type") in {"b2b", "authority"}:
            xml_doc = _save_document(invoice, filename=f"xrechnung-{number}.xml", payload=xrechnung_xml(core), mime="application/xml", kind="invoice_original_xrechnung", retention_until=retention, user=user)
        record.state = "finalized" if record.document_type == "invoice" else ("cancelled" if record.document_type == "cancellation" else "credited")
        record.final_number = number
        record.finalized_at = timezone.now()
        record.snapshot = core
        record.snapshot_sha256 = _sha(core)
        record.retention_until = retention
        record.e_invoice_format = e_format
        record.e_invoice_status = validation["status"]
        record.schema_version = XRECHNUNG_SCHEMA_VERSION if e_format else ""
        record.generator_version = GENERATOR_VERSION
        record.validator_version = validation.get("version", "")
        record.validation_date = timezone.now() if e_format else None
        record.validation_errors = validation.get("errors") or []
        record.original_pdf_document = pdf_doc
        record.original_xml_document = xml_doc
        record.save()
        audit(invoice, "invoice.finalized", user=user, request=request, new={"number": number, "sha256": record.snapshot_sha256, "e_invoice_status": record.e_invoice_status}, metadata={"retention_until": retention.isoformat(), "generator_version": GENERATOR_VERSION})
        if xml_doc:
            audit(invoice, "xrechnung.generated", user=user, request=request, new={"document_id": xml_doc.pk, "sha256": xml_doc.sha256})
            audit(invoice, "xrechnung.validation", user=user, request=request, new={"status": record.e_invoice_status, "validator_version": record.validator_version}, metadata={"errors": record.validation_errors})
        return record


def create_correction(original, *, user=None):
    if not is_finalized(original): raise ComplianceError("Nur finalisierte Rechnungen können korrigiert werden.")
    with transaction.atomic():
        new = m.Invoice.objects.create(
            organization=original.organization, project=original.project, quote=getattr(original, "quote", None), number="", status="draft",
            issue_date=timezone.localdate(), due_date=timezone.localdate(), service_date=original.service_date, intro_text=original.intro_text,
            outro_text=original.outro_text, notes=f"Korrektur zu {original.number}", created_by=user if getattr(user, "is_authenticated", False) else original.created_by,
        )
        for item in original.items.all().order_by("position", "pk"):
            copied = m.InvoiceItem.objects.create(invoice=new, position=item.position, code=item.code, description=item.description, quantity=item.quantity, unit=item.unit, unit_price=item.unit_price, tax_rate=item.tax_rate, catalog_item=item.catalog_item, ai_generated=False, approved=True)
            try:
                meta = item.commercial_meta
                m.CommercialItemMeta.objects.create(organization=new.organization, invoice_item=copied, position_type=meta.position_type, purchase_price=meta.purchase_price, markup_percent=meta.markup_percent, service_model=meta.service_model, detail_text=meta.detail_text, group_title=meta.group_title)
            except Exception: pass
        try:
            s = original.commercial_settings
            m.CommercialDocumentSettings.objects.create(organization=new.organization, invoice=new, tax_code=s.tax_code, tax_rate=s.tax_rate, discount_type=s.discount_type, discount_value=s.discount_value, payment_due_days=s.payment_due_days, early_payment_discount_percent=s.early_payment_discount_percent, early_payment_discount_days=s.early_payment_discount_days, closing_text=s.closing_text)
        except Exception: pass
        m.InvoiceComplianceRecord.objects.create(organization=new.organization, invoice=new, correction_of=original, document_type="invoice")
        audit(original, "invoice.correction_draft_created", user=user, new={"correction_invoice_id": new.pk})
        return new


def create_cancellation(original, *, user=None, request=None):
    if not is_finalized(original): raise ComplianceError("Nur finalisierte Rechnungen können storniert werden.")
    if getattr(original, "cancellations", None) and original.cancellations.exists(): raise ComplianceError("Für diese Rechnung existiert bereits ein Storno.")
    with transaction.atomic():
        new = m.Invoice.objects.create(
            organization=original.organization, project=original.project, quote=getattr(original, "quote", None), number="", status="draft",
            issue_date=timezone.localdate(), due_date=timezone.localdate(), service_date=original.service_date, intro_text="Stornorechnung",
            outro_text=f"Storno zu Rechnung {original.number}", notes=f"Vollständiges Storno zu {original.number}", created_by=user if getattr(user, "is_authenticated", False) else original.created_by,
        )
        for item in original.items.all().order_by("position", "pk"):
            m.InvoiceItem.objects.create(invoice=new, position=item.position, code=item.code, description=item.description, quantity=item.quantity, unit=item.unit, unit_price=item.unit_price, tax_rate=item.tax_rate, catalog_item=item.catalog_item, ai_generated=False, approved=True)
        try:
            s = original.commercial_settings
            m.CommercialDocumentSettings.objects.create(organization=new.organization, invoice=new, tax_code=s.tax_code, tax_rate=s.tax_rate, discount_type=s.discount_type, discount_value=s.discount_value, payment_due_days=0, early_payment_discount_percent=0, early_payment_discount_days=0, closing_text=f"Storno zu Rechnung {original.number}")
        except Exception: pass
        m.InvoiceComplianceRecord.objects.create(organization=new.organization, invoice=new, cancellation_of=original, document_type="cancellation")
    record = finalize_invoice(new, user=user, request=request)
    original.status = "cancelled"; original.save(update_fields=["status", "updated_at"])
    audit(original, "invoice.cancelled", user=user, request=request, new={"cancellation_invoice_id": new.pk, "cancellation_number": record.final_number})
    return new, record
''')


def install_views() -> None:
    write("erp/invoice_compliance_views.py", r'''from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods, require_POST

from . import models as m
from .rebuild_views import _is_field_user, _org
from .services.invoice_compliance_service import ComplianceError, create_cancellation, create_correction, get_compliance


def _office(request):
    if _is_field_user(request):
        messages.error(request, "Rechnungs-Compliance ist nur für Büro/Buchhaltung verfügbar.")
        return False
    return True


@login_required
@require_http_methods(["GET", "POST"])
def compliance_settings(request):
    if not _office(request): return redirect("next-dashboard")
    org = _org(request)
    settings = dict(org.settings or {})
    legal = dict(settings.get("invoice_legal") or {})
    if request.method == "POST":
        fields = ("legal_form", "street", "house_number", "postal_code", "city", "country", "website", "tax_number", "vat_id", "register", "register_number", "register_court", "managing_director", "bic", "bank_name")
        for field in fields: legal[field] = (request.POST.get(field) or "").strip()
        settings["invoice_legal"] = legal
        settings["invoice_currency"] = (request.POST.get("invoice_currency") or "EUR").strip().upper()[:3]
        settings["invoice_number_prefix"] = (request.POST.get("invoice_number_prefix") or "RE").strip()[:20]
        settings["invoice_number_digits"] = max(3, min(int(request.POST.get("invoice_number_digits") or 5), 12))
        settings["invoice_number_start"] = max(1, int(request.POST.get("invoice_number_start") or 1))
        settings["einvoice_transition_end"] = (request.POST.get("einvoice_transition_end") or "2026-12-31").strip()
        settings["invoice_tax_reason"] = (request.POST.get("invoice_tax_reason") or "").strip()
        org.settings = settings
        org.legal_name = (request.POST.get("legal_name") or org.legal_name or org.name).strip()
        org.email = (request.POST.get("email") or org.email or "").strip()
        org.phone = (request.POST.get("phone") or org.phone or "").strip()
        org.address = (request.POST.get("address") or org.address or "").strip()
        org.tax_id = legal.get("tax_number") or legal.get("vat_id") or org.tax_id
        org.iban = (request.POST.get("iban") or org.iban or "").strip()
        org.save()
        messages.success(request, "Rechnungs- und Unternehmensdaten gespeichert.")
        return redirect("invoice-compliance-settings")
    return render(request, "rebuild/invoice_compliance_settings.html", {"org": org, "legal": legal, "settings": settings, "validator_configured": bool(__import__('os').environ.get('XRECHNUNG_VALIDATOR_URL'))})


@login_required
@require_POST
def correction_create(request, pk):
    if not _office(request): return redirect("next-dashboard")
    org = _org(request); original = get_object_or_404(m.Invoice, organization=org, pk=pk)
    try: draft = create_correction(original, user=request.user)
    except ComplianceError as exc:
        messages.error(request, str(exc)); return redirect("next-invoice-edit", pk=pk)
    messages.success(request, f"Korrekturentwurf zu {original.number} erstellt.")
    return redirect("next-invoice-edit", pk=draft.pk)


@login_required
@require_POST
def cancellation_create(request, pk):
    if not _office(request): return redirect("next-dashboard")
    org = _org(request); original = get_object_or_404(m.Invoice, organization=org, pk=pk)
    try: cancellation, record = create_cancellation(original, user=request.user, request=request)
    except ComplianceError as exc:
        messages.error(request, str(exc)); return redirect("next-invoice-edit", pk=pk)
    messages.success(request, f"Storno {record.final_number} wurde revisionsorientiert erstellt.")
    return redirect("next-invoice-edit", pk=cancellation.pk)


@login_required
def frozen_pdf(request, pk):
    if not _office(request): return redirect("next-dashboard")
    org = _org(request); invoice = get_object_or_404(m.Invoice, organization=org, pk=pk); record = get_compliance(invoice)
    if not record or not record.original_pdf_document_id: raise Http404
    return FileResponse(record.original_pdf_document.file.open("rb"), content_type="application/pdf", filename=f"rechnung-{record.final_number}.pdf")


@login_required
def frozen_xml(request, pk):
    if not _office(request): return redirect("next-dashboard")
    org = _org(request); invoice = get_object_or_404(m.Invoice, organization=org, pk=pk); record = get_compliance(invoice)
    if not record or not record.original_xml_document_id: raise Http404
    return FileResponse(record.original_xml_document.file.open("rb"), content_type="application/xml", filename=f"xrechnung-{record.final_number}.xml")
''')

    urls_rel = "erp/rebuild_urls.py"
    urls = read(urls_rel)
    import_line = "from . import invoice_compliance_views as invoice_compliance\n"
    if import_line not in urls:
        anchor = "from . import rebuild_views as views\n"
        if anchor not in urls: raise RuntimeError("Invoice compliance URL import anchor changed")
        urls = urls.replace(anchor, anchor + import_line, 1)
    routes = '''    path("settings/next/rechnung-compliance/", invoice_compliance.compliance_settings, name="invoice-compliance-settings"),
    path("invoices/<int:pk>/correction/", invoice_compliance.correction_create, name="invoice-compliance-correction"),
    path("invoices/<int:pk>/cancel/", invoice_compliance.cancellation_create, name="invoice-compliance-cancel"),
    path("invoices/<int:pk>/frozen.pdf", invoice_compliance.frozen_pdf, name="invoice-compliance-pdf"),
    path("invoices/<int:pk>/xrechnung.xml", invoice_compliance.frozen_xml, name="invoice-compliance-xml"),
'''
    if "invoice-compliance-settings" not in urls:
        anchor = "urlpatterns = [\n"
        if anchor not in urls: raise RuntimeError("Invoice compliance urlpatterns anchor changed")
        urls = urls.replace(anchor, anchor + routes, 1)
    write(urls_rel, urls)


def patch_invoice_editor() -> None:
    rel = "erp/rebuild_views.py"
    text = read(rel)
    imports = "from .services.invoice_compliance_service import ComplianceError, finalize_invoice, get_compliance, is_finalized, save_customer_profile\n"
    if imports not in text:
        anchor = "from . import models as m\n"
        if anchor not in text: raise RuntimeError("Invoice compliance view import anchor changed")
        text = text.replace(anchor, anchor + imports, 1)

    pattern = re.compile(r'@login_required\n@require_http_methods\(\["GET", "POST"\]\)\ndef invoice_editor\(request, pk=None\):.*?\n\n@login_required\n@require_POST\ndef invoice_payment', re.S)
    match = pattern.search(text)
    if not match: raise RuntimeError("Invoice editor function anchor changed")
    old = match.group(0)
    new = r'''@login_required
@require_http_methods(["GET", "POST"])
def invoice_editor(request, pk=None):
    org = _org(request)
    invoice = get_object_or_404(m.Invoice, pk=pk, organization=org) if pk else None
    if invoice is not None and is_finalized(invoice) and request.method == "POST":
        messages.error(request, "Finalisierte Rechnungen sind unveränderbar. Bitte Storno oder Korrektur verwenden.")
        return redirect("next-invoice-edit", pk=invoice.pk)
    initial = {}
    if request.GET.get("project"):
        initial["project"] = request.GET.get("project")
    if request.GET.get("quote"):
        initial["quote"] = request.GET.get("quote")
    form = InvoiceForm(request.POST or None, instance=invoice, organization=org, initial=initial)
    if request.method == "POST" and form.is_valid():
        action = request.POST.get("action") or "save"
        try:
            with transaction.atomic():
                obj = form.save(commit=False)
                obj.organization = org
                obj.created_by = obj.created_by or request.user
                # A draft deliberately has no fiscal invoice number. The number is
                # allocated transactionally only during finalization.
                if not obj.pk:
                    obj.number = ""
                    obj.status = "draft"
                due_days = max(0, min(365, int(_money(request.POST.get("payment_due_days") or 14))))
                obj.due_date = obj.issue_date + timedelta(days=due_days)
                obj.outro_text = (request.POST.get("closing_text") or "").strip()
                obj.save()
                settings = _save_document_settings(obj, request, "invoice")
                _save_commercial_items(obj, request, "invoice", settings)
                save_customer_profile(obj, request.POST)
                if action == "finalize":
                    finalize_invoice(obj, user=request.user, request=request)
        except ComplianceError as exc:
            messages.error(request, "Rechnung kann nicht finalisiert werden: " + str(exc))
            return render(request, "rebuild/document_editor.html", {
                "form": form, "document": invoice, "items": _items_for_editor(invoice),
                "catalog": m.CatalogItem.objects.filter(organization=org, active=True).order_by("name")[:500],
                "kind": "invoice", "totals": _invoice_total(invoice) if invoice else None, "commercial": _commercial_settings(invoice),
                "invoice_compliance": get_compliance(invoice),
            })
        if action == "finalize":
            messages.success(request, "Rechnung finalisiert, nummeriert, gehasht und archiviert.")
        else:
            messages.success(request, "Rechnungsentwurf gespeichert.")
        return redirect("next-invoice-edit", pk=obj.pk)
    settings = _commercial_settings(invoice)
    return render(request, "rebuild/document_editor.html", {
        "form": form, "document": invoice, "items": _items_for_editor(invoice),
        "catalog": m.CatalogItem.objects.filter(organization=org, active=True).order_by("name")[:500],
        "kind": "invoice", "totals": _invoice_total(invoice) if invoice else None, "commercial": settings,
        "invoice_compliance": get_compliance(invoice),
    })


@login_required
@require_POST
def invoice_payment'''
    text = text[:match.start()] + new + text[match.end():]
    write(rel, text)

    template_rel = "templates/rebuild/document_editor.html"
    template = read(template_rel)
    if "INVOICE_COMPLIANCE_FINALIZE_20260820" not in template:
        head = '<div class="nx-pagehead ab-doc-head">'
        banner = '''<!-- INVOICE_COMPLIANCE_FINALIZE_20260820 -->
{% if kind == 'invoice' and invoice_compliance and invoice_compliance.state != 'draft' %}
<div class="nx-card nx-card-pad" style="margin-bottom:16px;border-color:#9fc6ad;background:#f3faf5"><b>Finalisierte Originalrechnung · {{ invoice_compliance.final_number }}</b><p style="margin:5px 0 0">Dieses Dokument ist gesperrt. Änderungen erfolgen ausschließlich über Korrektur oder Storno. SHA-256: <code>{{ invoice_compliance.snapshot_sha256 }}</code></p><div class="nx-actions" style="margin-top:10px"><a class="nx-btn" href="{% url 'invoice-compliance-pdf' document.pk %}" target="_blank">Original-PDF</a>{% if invoice_compliance.original_xml_document_id %}<a class="nx-btn" href="{% url 'invoice-compliance-xml' document.pk %}" target="_blank">XRechnung XML</a>{% endif %}<form method="post" action="{% url 'invoice-compliance-correction' document.pk %}" style="display:inline">{% csrf_token %}<button class="nx-btn" type="submit">Korrektur erstellen</button></form><form method="post" action="{% url 'invoice-compliance-cancel' document.pk %}" style="display:inline">{% csrf_token %}<button class="nx-btn" type="submit">Storno erstellen</button></form></div></div>
{% endif %}
'''
        if head in template: template = template.replace(head, banner + head, 1)
        profile_block = '''{% if kind == 'invoice' %}
  <section class="nx-card nx-card-pad">
    <div class="nx-card-head" style="padding:0 0 12px"><div><div class="nx-kicker">E-Rechnung</div><h2>Empfänger- & Referenzdaten</h2><p>B2B/B2G-Felder für strukturierte Rechnungen. Behörden benötigen insbesondere Buyer Reference / Leitweg-ID.</p></div></div>
    <div class="nx-form-grid">
      <div class="nx-field"><label>Kundentyp</label><select class="nx-control" name="invoice_customer_type"><option value="b2c">B2C</option><option value="b2b">B2B</option><option value="authority">Behörde</option></select></div>
      <div class="nx-field"><label>Bevorzugtes Format</label><select class="nx-control" name="invoice_preferred_format"><option value="pdf">PDF</option><option value="xrechnung">XRechnung</option><option value="zugferd">ZUGFeRD</option></select></div>
      <div class="nx-field"><label>Rechnungs-E-Mail</label><input class="nx-control" type="email" name="invoice_email"></div>
      <div class="nx-field"><label>Leitweg-ID</label><input class="nx-control" name="leitweg_id"></div>
      <div class="nx-field"><label>Buyer Reference</label><input class="nx-control" name="buyer_reference"></div>
      <div class="nx-field"><label>Peppol-ID</label><input class="nx-control" name="peppol_id"></div>
      <div class="nx-field"><label>Bestellreferenz</label><input class="nx-control" name="order_reference"></div>
      <div class="nx-field"><label>Vertragsreferenz</label><input class="nx-control" name="contract_reference"></div>
      <div class="nx-field"><label>Projektreferenz</label><input class="nx-control" name="project_reference"></div>
      <div class="nx-field"><label>Steuernummer Empfänger (optional)</label><input class="nx-control" name="tax_number"></div>
    </div>
  </section>
{% endif %}
'''
        closing_anchor = '<section class="nx-card nx-card-pad ab-closing-card">'
        if closing_anchor in template: template = template.replace(closing_anchor, profile_block + "\n  " + closing_anchor, 1)
        old_actions = '<div class="nx-form-actions"><a class="nx-btn" href="{% if kind == \'quote\' %}{% url \'next-quotes\' %}{% else %}{% url \'next-invoices\' %}{% endif %}">Zurück</a><button class="nx-btn" type="submit" name="action" value="save">Entwurf speichern</button><button class="nx-btn nx-btn-primary" type="submit" name="action" value="send">Speichern & als gesendet markieren</button></div>'
        new_actions = '''<div class="nx-form-actions"><a class="nx-btn" href="{% if kind == 'quote' %}{% url 'next-quotes' %}{% else %}{% url 'next-invoices' %}{% endif %}">Zurück</a>{% if kind == 'invoice' %}{% if not invoice_compliance or invoice_compliance.state == 'draft' %}<button class="nx-btn" type="submit" name="action" value="save">Entwurf speichern</button><button class="nx-btn nx-btn-primary" type="submit" name="action" value="finalize">Rechnung finalisieren</button>{% else %}<span class="nx-badge">Finalisiert · unveränderbar</span>{% endif %}{% else %}<button class="nx-btn" type="submit" name="action" value="save">Entwurf speichern</button><button class="nx-btn nx-btn-primary" type="submit" name="action" value="send">Speichern & als gesendet markieren</button>{% endif %}</div>'''
        if old_actions not in template: raise RuntimeError("Document editor action anchor changed")
        template = template.replace(old_actions, new_actions, 1)
        write(template_rel, template)


def install_settings_template() -> None:
    write("templates/rebuild/invoice_compliance_settings.html", r'''{% extends 'rebuild/base.html' %}
{% block title %}Rechnungs-Compliance · A+Bau{% endblock %}
{% block content %}
<div class="nx-pagehead"><div><div class="nx-kicker">Rechnung & E-Rechnung</div><h1>Unternehmens- und Compliance-Daten</h1><p>Diese Angaben werden als zentrale Quelle für Rechnungen, PDF und strukturierte E-Rechnungen verwendet.</p></div></div>
<form method="post" class="nx-form">{% csrf_token %}
<section class="nx-card nx-card-pad"><h2>Rechtliche Unternehmensdaten</h2><div class="nx-form-grid">
<div class="nx-field"><label>Vollständiger Firmenname</label><input class="nx-control" name="legal_name" value="{{ org.legal_name }}" required></div>
<div class="nx-field"><label>Rechtsform</label><input class="nx-control" name="legal_form" value="{{ legal.legal_form|default:'' }}"></div>
<div class="nx-field nx-field-full"><label>Vollständige Anschrift</label><input class="nx-control" name="address" value="{{ org.address }}" required></div>
<div class="nx-field"><label>Straße</label><input class="nx-control" name="street" value="{{ legal.street|default:'' }}"></div><div class="nx-field"><label>Hausnummer</label><input class="nx-control" name="house_number" value="{{ legal.house_number|default:'' }}"></div>
<div class="nx-field"><label>PLZ</label><input class="nx-control" name="postal_code" value="{{ legal.postal_code|default:'' }}"></div><div class="nx-field"><label>Ort</label><input class="nx-control" name="city" value="{{ legal.city|default:'' }}"></div>
<div class="nx-field"><label>Land</label><input class="nx-control" name="country" value="{{ legal.country|default:'DE' }}"></div><div class="nx-field"><label>E-Mail</label><input class="nx-control" type="email" name="email" value="{{ org.email }}"></div>
<div class="nx-field"><label>Telefon</label><input class="nx-control" name="phone" value="{{ org.phone }}"></div><div class="nx-field"><label>Website</label><input class="nx-control" name="website" value="{{ legal.website|default:'' }}"></div>
<div class="nx-field"><label>Steuernummer</label><input class="nx-control" name="tax_number" value="{{ legal.tax_number|default:org.tax_id }}"></div><div class="nx-field"><label>USt-IdNr.</label><input class="nx-control" name="vat_id" value="{{ legal.vat_id|default:'' }}"></div>
<div class="nx-field"><label>Handelsregister</label><input class="nx-control" name="register" value="{{ legal.register|default:'' }}"></div><div class="nx-field"><label>Registernummer</label><input class="nx-control" name="register_number" value="{{ legal.register_number|default:'' }}"></div>
<div class="nx-field"><label>Registergericht</label><input class="nx-control" name="register_court" value="{{ legal.register_court|default:'' }}"></div><div class="nx-field"><label>Geschäftsführer / Inhaber</label><input class="nx-control" name="managing_director" value="{{ legal.managing_director|default:'' }}"></div>
</div></section>
<section class="nx-card nx-card-pad"><h2>Bank & Rechnungsstandard</h2><div class="nx-form-grid">
<div class="nx-field"><label>IBAN</label><input class="nx-control" name="iban" value="{{ org.iban }}"></div><div class="nx-field"><label>BIC</label><input class="nx-control" name="bic" value="{{ legal.bic|default:'' }}"></div><div class="nx-field"><label>Bank</label><input class="nx-control" name="bank_name" value="{{ legal.bank_name|default:'' }}"></div>
<div class="nx-field"><label>Währung</label><input class="nx-control" name="invoice_currency" value="{{ settings.invoice_currency|default:'EUR' }}"></div><div class="nx-field"><label>Rechnungsnummer Prefix</label><input class="nx-control" name="invoice_number_prefix" value="{{ settings.invoice_number_prefix|default:'RE' }}"></div><div class="nx-field"><label>Stellen</label><input class="nx-control" type="number" min="3" max="12" name="invoice_number_digits" value="{{ settings.invoice_number_digits|default:5 }}"></div><div class="nx-field"><label>Startnummer</label><input class="nx-control" type="number" min="1" name="invoice_number_start" value="{{ settings.invoice_number_start|default:1 }}"></div>
<div class="nx-field"><label>E-Rechnung Übergang bis</label><input class="nx-control" type="date" name="einvoice_transition_end" value="{{ settings.einvoice_transition_end|default:'2026-12-31' }}"></div><div class="nx-field nx-field-full"><label>Individueller Hinweis bei 0 % Steuer</label><input class="nx-control" name="invoice_tax_reason" value="{{ settings.invoice_tax_reason|default:'' }}"></div>
</div><p class="nx-muted">XRechnung-Validator: {% if validator_configured %}<b>konfiguriert</b>{% else %}<b>nicht konfiguriert</b> – XML wird niemals fälschlich als VALID markiert.{% endif %}</p></section>
<div class="nx-form-actions"><button class="nx-btn nx-btn-primary" type="submit">Speichern</button></div></form>
{% endblock %}''')

    settings_rel = "templates/rebuild/settings.html"
    settings = read(settings_rel)
    marker = "INVOICE_COMPLIANCE_SETTINGS_CARD_20260820"
    if marker not in settings:
        card = f'''\n<!-- {marker} -->\n<section class="nx-card nx-card-pad" style="margin-top:16px"><div class="nx-card-head" style="padding:0"><div><div class="nx-kicker">Rechnung & E-Rechnung</div><h2>Rechnungs-Compliance</h2><p>Pflichtangaben, Nummernkreis, E-Rechnung, Archivierung und Unternehmensdaten.</p></div><a class="nx-btn nx-btn-primary" href="{{% url 'invoice-compliance-settings' %}}">Konfigurieren →</a></div></section>\n'''
        before, end, after = settings.rpartition("{% endblock %}")
        if not end: raise RuntimeError("Settings content endblock missing")
        settings = before + card + end + after
        write(settings_rel, settings)


def install_tests() -> None:
    write("tests/test_invoice_germany_compliance.py", r'''from pathlib import Path
from django.test import SimpleTestCase

R = Path(__file__).resolve().parents[1]


class GermanInvoiceComplianceAssemblyTests(SimpleTestCase):
    def test_sidecar_models_cover_numbering_freeze_audit_retention(self):
        text = (R / "erp/invoice_compliance.py").read_text(encoding="utf-8")
        for marker in ("InvoiceNumberSequence", "InvoiceComplianceRecord", "InvoiceAuditEvent", "snapshot_sha256", "retention_until", "original_pdf_document", "original_xml_document"):
            self.assertIn(marker, text)

    def test_invoice_number_is_only_allocated_by_finalize_service(self):
        views = (R / "erp/rebuild_views.py").read_text(encoding="utf-8")
        service = (R / "erp/services/invoice_compliance_service.py").read_text(encoding="utf-8")
        invoice_block = views[views.index("def invoice_editor"):views.index("def invoice_payment")]
        self.assertNotIn('_unique_number(m.Invoice', invoice_block)
        self.assertIn("allocate_number(invoice)", service)
        self.assertIn("select_for_update", service)

    def test_finalized_invoice_is_immutable_in_editor(self):
        views = (R / "erp/rebuild_views.py").read_text(encoding="utf-8")
        self.assertIn("Finalisierte Rechnungen sind unveränderbar", views)
        self.assertIn("is_finalized(invoice)", views)

    def test_mandatory_invoice_fields_are_backend_validated(self):
        service = (R / "erp/services/invoice_compliance_service.py").read_text(encoding="utf-8")
        for marker in ("Leistungserbringers", "Leistungsempfängers", "Steuernummer oder USt-IdNr.", "Ausstellungsdatum", "Leistungsdatum", "Steuersatz", "Fälligkeitsdatum"):
            self.assertIn(marker, service)

    def test_xrechnung_is_structured_and_never_self_declared_valid(self):
        service = (R / "erp/services/invoice_compliance_service.py").read_text(encoding="utf-8")
        self.assertIn("XRECHNUNG_CUSTOMIZATION_ID", service)
        self.assertIn("XRECHNUNG_VALIDATOR_URL", service)
        self.assertIn('"not_validated"', service)
        self.assertIn("HTTPError", service)
        self.assertNotIn('return {"status": "valid"', service.split("def validate_xrechnung",1)[1].split("def _transition_end",1)[0].split("if not url:",1)[0])

    def test_invoice_ui_has_real_finalize_not_send_bypass(self):
        template = (R / "templates/rebuild/document_editor.html").read_text(encoding="utf-8")
        self.assertIn('value="finalize"', template)
        self.assertIn("Korrektur erstellen", template)
        self.assertIn("Storno erstellen", template)
        self.assertIn("Original-PDF", template)

    def test_compliance_settings_expose_legal_company_data(self):
        template = (R / "templates/rebuild/invoice_compliance_settings.html").read_text(encoding="utf-8")
        for marker in ("Steuernummer", "USt-IdNr.", "Registergericht", "Geschäftsführer", "IBAN", "Rechnungsnummer Prefix"):
            self.assertIn(marker, template)
''')


def main() -> None:
    install_models()
    install_service()
    install_views()
    patch_invoice_editor()
    install_settings_template()
    install_tests()
    print(MARKER + " installed")


if __name__ == "__main__":
    main()
