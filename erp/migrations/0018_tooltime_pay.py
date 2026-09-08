from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [migrations.swappable_dependency(settings.AUTH_USER_MODEL), ("erp", "0017_tooltime_phase5_communication")]
    operations = [
        migrations.AddField(model_name="tooltimedocumentmeta", name="automatic_dunning_disabled", field=models.BooleanField(default=False)),
        migrations.CreateModel(
            name="ToolTimePaymentTransaction",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("local_reference", models.CharField(max_length=80, unique=True)),
                ("provider", models.CharField(default="webhook", max_length=40)),
                ("provider_reference", models.CharField(blank=True, max_length=180)),
                ("status", models.CharField(choices=[("pending", "Ausstehend"), ("succeeded", "Bezahlt"), ("failed", "Fehlgeschlagen"), ("refunded", "Erstattet")], default="pending", max_length=20)),
                ("invoice_amount", models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ("dunning_fee", models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ("amount", models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ("currency", models.CharField(default="EUR", max_length=3)),
                ("checkout_url", models.URLField(blank=True, max_length=1000)),
                ("provider_payload", models.JSONField(blank=True, default=dict)),
                ("failure_reason", models.CharField(blank=True, max_length=500)),
                ("paid_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="tooltime_payment_transactions", to=settings.AUTH_USER_MODEL)),
                ("invoice", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="tooltime_payment_transactions", to="erp.invoice")),
                ("organization", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="tooltime_payment_transactions", to="erp.organization")),
                ("payment", models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="tooltime_provider_transaction", to="erp.payment")),
            ], options={"ordering": ["-created_at", "-id"]},
        ),
        migrations.CreateModel(
            name="ToolTimePayout",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("provider", models.CharField(default="webhook", max_length=40)),
                ("provider_reference", models.CharField(max_length=180)),
                ("status", models.CharField(choices=[("pending", "Ausstehend"), ("paid", "Ausgezahlt"), ("failed", "Fehlgeschlagen")], default="pending", max_length=20)),
                ("mode", models.CharField(choices=[("individual", "Einzeln"), ("aggregated", "Gebündelt")], default="aggregated", max_length=20)),
                ("amount", models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ("currency", models.CharField(default="EUR", max_length=3)),
                ("period_start", models.DateField(blank=True, null=True)),
                ("period_end", models.DateField(blank=True, null=True)),
                ("paid_at", models.DateTimeField(blank=True, null=True)),
                ("provider_payload", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("organization", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="tooltime_payouts", to="erp.organization")),
            ], options={"ordering": ["-created_at", "-id"]},
        ),
        migrations.AddConstraint(model_name="tooltimepaymenttransaction", constraint=models.UniqueConstraint(fields=("organization", "provider", "provider_reference"), name="uniq_tooltime_provider_reference")),
        migrations.AddConstraint(model_name="tooltimepayout", constraint=models.UniqueConstraint(fields=("organization", "provider", "provider_reference"), name="uniq_tooltime_payout_reference")),
    ]
