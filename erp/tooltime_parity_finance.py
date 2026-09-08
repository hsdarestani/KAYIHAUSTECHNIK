from __future__ import annotations

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
    customer = models.ForeignKey("erp.Customer", null=True, blank=True, on_delete=models.PROTECT, related_name="tooltime_document_meta")
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
    automatic_dunning_disabled = models.BooleanField(default=False)
    default_attachment_ids = models.JSONField(default=list, blank=True)
    acceptance_details = models.JSONField(default=dict, blank=True)
    withdrawn_at = models.DateTimeField(null=True, blank=True)
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


class ToolTimeDatevAccount(models.Model):
    PARTY_TYPES = [("customer", "Debitor"), ("supplier", "Kreditor")]
    SOURCES = [("automatic", "Automatisch"), ("customer_number", "Kundennummer"), ("import", "DATEV-Import"), ("manual", "Manuell")]
    organization = models.ForeignKey("erp.Organization", on_delete=models.CASCADE, related_name="tooltime_datev_accounts")
    party_type = models.CharField(max_length=20, choices=PARTY_TYPES)
    party_key = models.CharField(max_length=120)
    party_name = models.CharField(max_length=240, blank=True)
    account_number = models.CharField(max_length=5)
    source = models.CharField(max_length=30, choices=SOURCES, default="automatic")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["party_type", "account_number", "id"]
        constraints = [
            models.UniqueConstraint(fields=["organization", "party_type", "party_key"], name="uniq_tooltime_datev_party"),
            models.UniqueConstraint(fields=["organization", "account_number"], name="uniq_tooltime_datev_number"),
        ]


class ToolTimeMixedSubitem(models.Model):
    TYPES = [("material", "Material"), ("labour", "Lohn"), ("other", "Sonstiges")]
    organization = models.ForeignKey("erp.Organization", on_delete=models.CASCADE, related_name="tooltime_mixed_subitems")
    quote_item = models.ForeignKey("erp.QuoteItem", null=True, blank=True, on_delete=models.CASCADE, related_name="tooltime_mixed_subitems")
    invoice_item = models.ForeignKey("erp.InvoiceItem", null=True, blank=True, on_delete=models.CASCADE, related_name="tooltime_mixed_subitems")
    item_type = models.CharField(max_length=16, choices=TYPES, default="material")
    description = models.CharField(max_length=300)
    quantity = models.DecimalField(max_digits=12, decimal_places=3, default=1)
    unit = models.CharField(max_length=30, default="Stk.")
    purchase_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    sales_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    sort_order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["sort_order", "id"]



class ToolTimeDocumentDelivery(models.Model):
    CHANNELS = [("email", "E-Mail")]
    STATUSES = [("sent", "Gesendet"), ("failed", "Fehlgeschlagen")]
    organization = models.ForeignKey("erp.Organization", on_delete=models.CASCADE, related_name="tooltime_document_deliveries")
    quote = models.ForeignKey("erp.Quote", null=True, blank=True, on_delete=models.PROTECT, related_name="tooltime_deliveries")
    invoice = models.ForeignKey("erp.Invoice", null=True, blank=True, on_delete=models.PROTECT, related_name="tooltime_deliveries")
    document = models.ForeignKey("erp.Document", null=True, blank=True, on_delete=models.PROTECT, related_name="tooltime_document_deliveries")
    channel = models.CharField(max_length=20, choices=CHANNELS, default="email")
    status = models.CharField(max_length=20, choices=STATUSES)
    recipient_email = models.EmailField()
    subject = models.CharField(max_length=300)
    body_excerpt = models.TextField(blank=True)
    error_message = models.CharField(max_length=500, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="tooltime_document_deliveries")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]



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
