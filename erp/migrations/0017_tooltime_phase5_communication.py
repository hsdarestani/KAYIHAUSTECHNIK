from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("erp", "0016_tooltime_phase3_editor"),
    ]
    operations = [
        migrations.CreateModel(
            name="ToolTimeDocumentDelivery",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("channel", models.CharField(choices=[("email", "E-Mail")], default="email", max_length=20)),
                ("status", models.CharField(choices=[("sent", "Gesendet"), ("failed", "Fehlgeschlagen")], max_length=20)),
                ("recipient_email", models.EmailField(max_length=254)),
                ("subject", models.CharField(max_length=300)),
                ("body_excerpt", models.TextField(blank=True)),
                ("error_message", models.CharField(blank=True, max_length=500)),
                ("sent_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="tooltime_document_deliveries", to=settings.AUTH_USER_MODEL)),
                ("document", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="tooltime_document_deliveries", to="erp.document")),
                ("invoice", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="tooltime_deliveries", to="erp.invoice")),
                ("organization", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="tooltime_document_deliveries", to="erp.organization")),
                ("quote", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="tooltime_deliveries", to="erp.quote")),
            ],
            options={"ordering": ["-created_at", "-id"]},
        ),
    ]
