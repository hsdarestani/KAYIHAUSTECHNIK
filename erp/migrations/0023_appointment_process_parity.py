from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("erp", "0022_calendar_event_custom_recurrence")]
    operations = [
        migrations.AddField(
            model_name="calendarevent",
            name="source_quote",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="generated_appointments", to="erp.quote"),
        ),
        migrations.AddField(
            model_name="calendarevent",
            name="work_report",
            field=models.TextField(blank=True, default=""),
        ),
        migrations.AddField(
            model_name="quote",
            name="source_event",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="generated_quotes", to="erp.calendarevent"),
        ),
        migrations.AddField(
            model_name="invoice",
            name="source_event",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="generated_invoices", to="erp.calendarevent"),
        ),
        migrations.CreateModel(
            name="AppointmentServiceGroup",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("title", models.CharField(blank=True, default="", max_length=220)),
                ("position", models.PositiveIntegerField(default=1)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("event", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="service_groups", to="erp.calendarevent")),
                ("organization", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="appointment_service_groups", to="erp.organization")),
            ],
            options={"ordering": ["position", "id"]},
        ),
        migrations.CreateModel(
            name="AppointmentServiceItem",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("position", models.PositiveIntegerField(default=1)),
                ("kind", models.CharField(choices=[("labour", "Arbeitszeit"), ("material", "Material"), ("mixed", "Mischposition"), ("other", "Sonstiges")], default="other", max_length=16)),
                ("code", models.CharField(blank=True, max_length=80)),
                ("description", models.TextField()),
                ("quantity", models.DecimalField(decimal_places=3, default=1, max_digits=12)),
                ("unit", models.CharField(default="Stk.", max_length=30)),
                ("purchase_price", models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ("unit_price", models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ("tax_rate", models.DecimalField(decimal_places=2, default=19, max_digits=5)),
                ("mixed_payload", models.JSONField(blank=True, default=list)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("catalog_item", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="appointment_uses", to="erp.catalogitem")),
                ("event", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="service_items", to="erp.calendarevent")),
                ("group", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="items", to="erp.appointmentservicegroup")),
                ("organization", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="appointment_service_items", to="erp.organization")),
                ("source_quote_item", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="appointment_copies", to="erp.quoteitem")),
            ],
            options={"ordering": ["position", "id"]},
        ),
    ]
