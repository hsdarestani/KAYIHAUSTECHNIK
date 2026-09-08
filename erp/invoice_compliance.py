from __future__ import annotations

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
