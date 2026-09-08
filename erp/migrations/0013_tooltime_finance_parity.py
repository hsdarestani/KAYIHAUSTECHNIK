from django.conf import settings
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
