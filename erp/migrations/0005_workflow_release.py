# Generated for A+Bau workflow release
from decimal import Decimal
import uuid

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import migrations, models
import django.db.models.deletion


def populate_price_source_share_tokens(apps, schema_editor):
    PriceSource = apps.get_model("erp", "PriceSource")
    for source in PriceSource.objects.filter(share_token__isnull=True).only("pk").iterator():
        source.share_token = uuid.uuid4()
        source.save(update_fields=["share_token"])


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("erp", "0004_rename_erp_room_org_status_idx_erp_roommea_organiz_dd42ac_idx_and_more"),
    ]

    operations = [
        migrations.AddField(model_name="employee", name="can_view_prices", field=models.BooleanField(default=False)),
        migrations.AddField(model_name="project", name="job_type", field=models.CharField(choices=[("private", "Privatauftrag"), ("insurance", "Versicherung / B&O")], default="private", max_length=20)),
        migrations.AddField(model_name="project", name="price_source", field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="projects", to="erp.pricesource")),
        migrations.AddField(model_name="calendarevent", name="reminder_minutes", field=models.JSONField(blank=True, default=list)),
        migrations.AddField(model_name="measurementcapture", name="annotations", field=models.JSONField(blank=True, default=list)),
        migrations.AddField(model_name="notification", name="scheduled_for", field=models.DateTimeField(blank=True, null=True)),
        migrations.AddField(model_name="notification", name="delivered_at", field=models.DateTimeField(blank=True, null=True)),
        migrations.AddField(model_name="pricesource", name="share_enabled", field=models.BooleanField(default=False)),
        migrations.AddField(model_name="pricesource", name="share_token", field=models.UUIDField(editable=False, null=True)),
        migrations.RunPython(populate_price_source_share_tokens, migrations.RunPython.noop),
        migrations.AlterField(model_name="pricesource", name="share_token", field=models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
        migrations.AlterField(model_name="integrationconfig", name="provider", field=models.CharField(choices=[("gmx", "GMX"), ("tooltime", "ToolTime"), ("bundo", "B&O Portal"), ("openai", "OpenAI"), ("datev", "DATEV"), ("marketplace", "Material-Marktplatz"), ("webpush", "PWA Push")], max_length=30)),
        migrations.CreateModel(
            name="BugReport",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)), ("updated_at", models.DateTimeField(auto_now=True)),
                ("title", models.CharField(max_length=220)), ("description", models.TextField()), ("page_url", models.CharField(blank=True, max_length=500)),
                ("screenshot", models.ImageField(blank=True, upload_to="bug_reports/%Y/%m/")),
                ("status", models.CharField(choices=[("open", "Offen"), ("review", "Prüfung"), ("resolved", "Gelöst")], default="open", max_length=20)),
                ("organization", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="bug_reports", to="erp.organization")),
                ("project", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="bug_reports", to="erp.project")),
                ("reported_by", models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="bug_reports", to=settings.AUTH_USER_MODEL)),
            ], options={"ordering": ["-created_at"]},
        ),
        migrations.CreateModel(
            name="ChangeOrder",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)), ("updated_at", models.DateTimeField(auto_now=True)),
                ("number", models.CharField(max_length=40)), ("title", models.CharField(max_length=240)), ("description", models.TextField()),
                ("amount_net", models.DecimalField(decimal_places=2, default=0, max_digits=14)), ("tax_rate", models.DecimalField(decimal_places=2, default=19, max_digits=5)),
                ("status", models.CharField(choices=[("draft", "Entwurf"), ("sent", "Zur Unterschrift"), ("accepted", "Bestätigt"), ("rejected", "Abgelehnt"), ("invoiced", "Abgerechnet")], default="draft", max_length=20)),
                ("public_token", models.UUIDField(default=uuid.uuid4, editable=False, unique=True)), ("signed_name", models.CharField(blank=True, max_length=180)),
                ("signature_data", models.TextField(blank=True)), ("signed_at", models.DateTimeField(blank=True, null=True)), ("customer_comment", models.TextField(blank=True)),
                ("organization", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="change_orders", to="erp.organization")),
                ("project", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="change_orders", to="erp.project")),
                ("requested_by", models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="requested_change_orders", to=settings.AUTH_USER_MODEL)),
            ], options={"ordering": ["-created_at"]},
        ),
        migrations.AddConstraint(model_name="changeorder", constraint=models.UniqueConstraint(fields=("organization", "number"), name="unique_change_order_number")),
        migrations.CreateModel(
            name="ChangeOrderAttachment",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")), ("created_at", models.DateTimeField(auto_now_add=True)), ("updated_at", models.DateTimeField(auto_now=True)),
                ("file", models.FileField(upload_to="change_orders/%Y/%m/")), ("title", models.CharField(blank=True, max_length=220)),
                ("change_order", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="attachments", to="erp.changeorder")),
                ("uploaded_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name="SiteReport",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")), ("created_at", models.DateTimeField(auto_now_add=True)), ("updated_at", models.DateTimeField(auto_now=True)),
                ("title", models.CharField(default="Vor-Ort-Bericht", max_length=220)), ("report_text", models.TextField(blank=True)), ("voice_file", models.FileField(blank=True, upload_to="site_reports/audio/%Y/%m/")),
                ("customer_signature", models.TextField(blank=True)), ("signed_name", models.CharField(blank=True, max_length=180)), ("signed_at", models.DateTimeField(blank=True, null=True)),
                ("created_by", models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="created_site_reports", to=settings.AUTH_USER_MODEL)),
                ("employee", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="site_reports", to="erp.employee")),
                ("organization", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="site_reports", to="erp.organization")),
                ("project", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="site_reports", to="erp.project")),
            ], options={"ordering": ["-created_at"]},
        ),
        migrations.CreateModel(
            name="WorkMedia",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")), ("created_at", models.DateTimeField(auto_now_add=True)), ("updated_at", models.DateTimeField(auto_now=True)),
                ("kind", models.CharField(choices=[("photo", "Foto"), ("video", "Video"), ("audio", "Audio")], default="photo", max_length=20)),
                ("stage", models.CharField(choices=[("before", "Vorher"), ("during", "Während"), ("after", "Nachher"), ("damage", "Schaden"), ("other", "Sonstiges")], default="during", max_length=20)),
                ("title", models.CharField(blank=True, max_length=220)), ("caption", models.TextField(blank=True)), ("file", models.FileField(upload_to="work_media/%Y/%m/")),
                ("mime_type", models.CharField(blank=True, max_length=120)), ("size", models.PositiveBigIntegerField(default=0)), ("annotations", models.JSONField(blank=True, default=list)), ("visible_to_customer", models.BooleanField(default=False)),
                ("employee", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="work_media", to="erp.employee")),
                ("organization", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="work_media", to="erp.organization")),
                ("project", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="work_media", to="erp.project")),
                ("uploaded_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="uploaded_work_media", to=settings.AUTH_USER_MODEL)),
            ], options={"ordering": ["stage", "created_at"]},
        ),
        migrations.CreateModel(
            name="CustomerSurvey",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")), ("created_at", models.DateTimeField(auto_now_add=True)), ("updated_at", models.DateTimeField(auto_now=True)),
                ("token", models.UUIDField(default=uuid.uuid4, editable=False, unique=True)), ("sent_at", models.DateTimeField(blank=True, null=True)), ("completed_at", models.DateTimeField(blank=True, null=True)),
                ("rating_quality", models.PositiveSmallIntegerField(blank=True, null=True, validators=[MinValueValidator(1), MaxValueValidator(5)])),
                ("rating_punctuality", models.PositiveSmallIntegerField(blank=True, null=True, validators=[MinValueValidator(1), MaxValueValidator(5)])),
                ("rating_team", models.PositiveSmallIntegerField(blank=True, null=True, validators=[MinValueValidator(1), MaxValueValidator(5)])),
                ("rating_cleanliness", models.PositiveSmallIntegerField(blank=True, null=True, validators=[MinValueValidator(1), MaxValueValidator(5)])),
                ("comment", models.TextField(blank=True)), ("allow_public_review", models.BooleanField(default=False)),
                ("organization", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="surveys", to="erp.organization")),
                ("project", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="survey", to="erp.project")),
            ],
        ),
        migrations.CreateModel(
            name="CustomerPortalAccess",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")), ("created_at", models.DateTimeField(auto_now_add=True)), ("updated_at", models.DateTimeField(auto_now=True)),
                ("token", models.UUIDField(default=uuid.uuid4, editable=False, unique=True)), ("active", models.BooleanField(default=True)), ("last_viewed_at", models.DateTimeField(blank=True, null=True)),
                ("organization", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="customer_portals", to="erp.organization")),
                ("project", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="customer_portal", to="erp.project")),
            ],
        ),
        migrations.CreateModel(
            name="PurchaseOrder",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")), ("created_at", models.DateTimeField(auto_now_add=True)), ("updated_at", models.DateTimeField(auto_now=True)),
                ("number", models.CharField(max_length=40)), ("status", models.CharField(choices=[("draft", "Entwurf"), ("ordered", "Bestellt"), ("received", "Geliefert"), ("invoiced", "Lieferantenrechnung"), ("cancelled", "Storniert")], default="draft", max_length=20)),
                ("ordered_at", models.DateField(blank=True, null=True)), ("expected_at", models.DateField(blank=True, null=True)), ("total_net", models.DecimalField(decimal_places=2, default=0, max_digits=14)),
                ("external_reference", models.CharField(blank=True, max_length=180)), ("notes", models.TextField(blank=True)),
                ("created_by", models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="created_purchase_orders", to=settings.AUTH_USER_MODEL)),
                ("organization", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="purchase_orders", to="erp.organization")),
                ("project", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="purchase_orders", to="erp.project")),
                ("supplier", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="purchase_orders", to="erp.supplier")),
            ], options={"ordering": ["-created_at"]},
        ),
        migrations.AddConstraint(model_name="purchaseorder", constraint=models.UniqueConstraint(fields=("organization", "number"), name="unique_purchase_order_number")),
        migrations.CreateModel(
            name="PurchaseDocument",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")), ("created_at", models.DateTimeField(auto_now_add=True)), ("updated_at", models.DateTimeField(auto_now=True)),
                ("kind", models.CharField(choices=[("order", "Bestellung"), ("receipt", "Bestellbestätigung"), ("delivery", "Lieferschein"), ("invoice", "Lieferantenrechnung")], max_length=20)),
                ("file", models.FileField(upload_to="purchase_documents/%Y/%m/")), ("title", models.CharField(blank=True, max_length=220)),
                ("purchase_order", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="documents", to="erp.purchaseorder")),
                ("uploaded_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
            ],
        ),
    ]
