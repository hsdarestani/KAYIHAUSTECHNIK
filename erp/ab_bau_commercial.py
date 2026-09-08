from __future__ import annotations

from django.db import models


class CommercialDocumentSettings(models.Model):
    TAX_CHOICES = [
        ("19", "19 % Umsatzsteuer"),
        ("7", "7 % Umsatzsteuer"),
        ("0_19", "0 % gemäß § 19 UStG"),
        ("0_13b", "0 % gemäß § 13b UStG"),
        ("0_4", "0 % gemäß § 4 UStG"),
        ("0", "0 % Umsatzsteuer"),
    ]
    DISCOUNT_CHOICES = [("percent", "Prozent"), ("fixed", "Fester Betrag")]

    organization = models.ForeignKey("erp.Organization", on_delete=models.CASCADE, related_name="commercial_document_settings")
    quote = models.OneToOneField("erp.Quote", null=True, blank=True, on_delete=models.CASCADE, related_name="commercial_settings")
    invoice = models.OneToOneField("erp.Invoice", null=True, blank=True, on_delete=models.CASCADE, related_name="commercial_settings")
    tax_code = models.CharField(max_length=20, choices=TAX_CHOICES, default="19")
    tax_rate = models.DecimalField(max_digits=5, decimal_places=2, default=19)
    discount_type = models.CharField(max_length=16, choices=DISCOUNT_CHOICES, default="percent")
    discount_value = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    payment_due_days = models.PositiveIntegerField(default=14)
    early_payment_discount_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    early_payment_discount_days = models.PositiveIntegerField(default=0)
    closing_text = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]


class CommercialItemMeta(models.Model):
    TYPE_CHOICES = [
        ("material", "Material"),
        ("labour", "Arbeitsleistung"),
        ("mixed", "Gemischte Leistung"),
        ("other", "Sonstiges"),
    ]
    SERVICE_CHOICES = [
        ("normal", "Normalleistung"),
        ("alternative", "Alternativposition"),
        ("contingent", "Eventualposition"),
    ]

    organization = models.ForeignKey("erp.Organization", on_delete=models.CASCADE, related_name="commercial_item_meta")
    quote_item = models.OneToOneField("erp.QuoteItem", null=True, blank=True, on_delete=models.CASCADE, related_name="commercial_meta")
    invoice_item = models.OneToOneField("erp.InvoiceItem", null=True, blank=True, on_delete=models.CASCADE, related_name="commercial_meta")
    position_type = models.CharField(max_length=16, choices=TYPE_CHOICES, default="material")
    purchase_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    markup_percent = models.DecimalField(max_digits=7, decimal_places=2, default=0)
    service_model = models.CharField(max_length=16, choices=SERVICE_CHOICES, default="normal")
    detail_text = models.TextField(blank=True)
    group_title = models.CharField(max_length=220, blank=True)
    show_subitems_in_pdf = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["id"]
