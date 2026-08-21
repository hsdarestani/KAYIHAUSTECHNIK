from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MIGRATION_REL = "erp/migrations/0023_appointment_process_parity.py"


def _add_field(text: str, class_name: str, anchor: str, field: str, guard: str) -> str:
    start = text.find(f"class {class_name}(")
    if start < 0:
        raise RuntimeError(f"Appointment parity: model {class_name} fehlt")
    end = text.find("\n\nclass ", start + 1)
    if end < 0:
        end = len(text)
    block = text[start:end]
    if guard in block:
        return text
    pos = block.find(anchor)
    if pos < 0:
        raise RuntimeError(f"Appointment parity: anchor für {class_name} fehlt")
    block = block[:pos] + field + block[pos:]
    return text[:start] + block + text[end:]


def patch_models(module) -> None:
    rel = "erp/models.py"
    text = module.read(rel)
    text = _add_field(
        text,
        "CalendarEvent",
        "\n    project = models.ForeignKey(",
        '''\n    source_quote = models.ForeignKey(
        "erp.Quote", null=True, blank=True, on_delete=models.SET_NULL, related_name="generated_appointments"
    )
    work_report = models.TextField(blank=True, default="")
''',
        "source_quote = models.ForeignKey",
    )
    text = _add_field(
        text,
        "Quote",
        "\n    project = models.ForeignKey(",
        '''\n    source_event = models.ForeignKey(
        "erp.CalendarEvent", null=True, blank=True, on_delete=models.SET_NULL, related_name="generated_quotes"
    )
''',
        "source_event = models.ForeignKey",
    )
    text = _add_field(
        text,
        "Invoice",
        "\n    project = models.ForeignKey(",
        '''\n    source_event = models.ForeignKey(
        "erp.CalendarEvent", null=True, blank=True, on_delete=models.SET_NULL, related_name="generated_invoices"
    )
''',
        "source_event = models.ForeignKey",
    )
    if "class AppointmentServiceGroup(" not in text:
        text += r'''

class AppointmentServiceGroup(models.Model):
    organization = models.ForeignKey("erp.Organization", on_delete=models.CASCADE, related_name="appointment_service_groups")
    event = models.ForeignKey("erp.CalendarEvent", on_delete=models.CASCADE, related_name="service_groups")
    title = models.CharField(max_length=220, blank=True, default="")
    position = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["position", "id"]


class AppointmentServiceItem(models.Model):
    KINDS = [
        ("labour", "Arbeitszeit"),
        ("material", "Material"),
        ("mixed", "Mischposition"),
        ("other", "Sonstiges"),
    ]
    organization = models.ForeignKey("erp.Organization", on_delete=models.CASCADE, related_name="appointment_service_items")
    event = models.ForeignKey("erp.CalendarEvent", on_delete=models.CASCADE, related_name="service_items")
    group = models.ForeignKey("erp.AppointmentServiceGroup", null=True, blank=True, on_delete=models.CASCADE, related_name="items")
    catalog_item = models.ForeignKey("erp.CatalogItem", null=True, blank=True, on_delete=models.SET_NULL, related_name="appointment_uses")
    source_quote_item = models.ForeignKey("erp.QuoteItem", null=True, blank=True, on_delete=models.SET_NULL, related_name="appointment_copies")
    position = models.PositiveIntegerField(default=1)
    kind = models.CharField(max_length=16, choices=KINDS, default="other")
    code = models.CharField(max_length=80, blank=True)
    description = models.TextField()
    quantity = models.DecimalField(max_digits=12, decimal_places=3, default=1)
    unit = models.CharField(max_length=30, default="Stk.")
    purchase_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    tax_rate = models.DecimalField(max_digits=5, decimal_places=2, default=19)
    mixed_payload = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["position", "id"]
'''
    module.write(rel, text)
    compile(text, str(ROOT / rel), "exec")


def install_migration(module) -> None:
    migration = r'''from django.db import migrations, models
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
'''
    module.write(MIGRATION_REL, migration)
    compile(migration, str(ROOT / MIGRATION_REL), "exec")


def run(module) -> None:
    patch_models(module)
    install_migration(module)
