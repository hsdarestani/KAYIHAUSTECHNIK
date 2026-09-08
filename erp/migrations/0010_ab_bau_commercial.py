from django.db import migrations, models
import django.db.models.deletion


def rename_brand(apps, schema_editor):
    Organization = apps.get_model("erp", "Organization")
    Organization.objects.filter(name__iexact="A+Bau").update(name="A+Bau")


class Migration(migrations.Migration):
    dependencies = [("erp", "0009_site_report_bando_fields")]
    operations = [
        migrations.CreateModel(
            name="CommercialDocumentSettings",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("tax_code", models.CharField(choices=[("19", "19 % Umsatzsteuer"), ("7", "7 % Umsatzsteuer"), ("0_19", "0 % gemäß § 19 UStG"), ("0_13b", "0 % gemäß § 13b UStG"), ("0_4", "0 % gemäß § 4 UStG"), ("0", "0 % Umsatzsteuer")], default="19", max_length=20)),
                ("tax_rate", models.DecimalField(decimal_places=2, default=19, max_digits=5)),
                ("discount_type", models.CharField(choices=[("percent", "Prozent"), ("fixed", "Fester Betrag")], default="percent", max_length=16)),
                ("discount_value", models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ("payment_due_days", models.PositiveIntegerField(default=14)),
                ("early_payment_discount_percent", models.DecimalField(decimal_places=2, default=0, max_digits=5)),
                ("early_payment_discount_days", models.PositiveIntegerField(default=0)),
                ("closing_text", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("invoice", models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="commercial_settings", to="erp.invoice")),
                ("organization", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="commercial_document_settings", to="erp.organization")),
                ("quote", models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="commercial_settings", to="erp.quote")),
            ],
            options={"ordering": ["-updated_at"]},
        ),
        migrations.CreateModel(
            name="CommercialItemMeta",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("position_type", models.CharField(choices=[("material", "Material"), ("labour", "Arbeitsleistung"), ("mixed", "Gemischte Leistung"), ("other", "Sonstiges")], default="material", max_length=16)),
                ("purchase_price", models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ("markup_percent", models.DecimalField(decimal_places=2, default=0, max_digits=7)),
                ("service_model", models.CharField(choices=[("normal", "Normalleistung"), ("alternative", "Alternativposition"), ("contingent", "Eventualposition")], default="normal", max_length=16)),
                ("detail_text", models.TextField(blank=True)),
                ("group_title", models.CharField(blank=True, max_length=220)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("invoice_item", models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="commercial_meta", to="erp.invoiceitem")),
                ("organization", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="commercial_item_meta", to="erp.organization")),
                ("quote_item", models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="commercial_meta", to="erp.quoteitem")),
            ],
            options={"ordering": ["id"]},
        ),
        migrations.RunPython(rename_brand, migrations.RunPython.noop),
    ]
