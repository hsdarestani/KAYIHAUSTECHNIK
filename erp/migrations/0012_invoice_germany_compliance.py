from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("erp", "0011_project_approval_flow"),
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
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
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
