# Generated for A+Bau UI parity and camera-assisted room measurement.

import decimal
import django.core.validators
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("erp", "0002_supplier_pricesource_priceitem"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="RoomMeasurement",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("name", models.CharField(default="Raum", max_length=160)),
                ("method", models.CharField(choices=[("manual", "Manuell"), ("ai_photo", "KI-Fotoaufmaß"), ("ar_lidar", "AR / LiDAR")], default="manual", max_length=20)),
                ("status", models.CharField(choices=[("draft", "Entwurf"), ("analyzing", "Analyse läuft"), ("review", "Zu prüfen"), ("confirmed", "Bestätigt")], default="draft", max_length=20)),
                ("length_m", models.DecimalField(blank=True, decimal_places=3, max_digits=8, null=True, validators=[django.core.validators.MinValueValidator(decimal.Decimal("0.01"))])),
                ("width_m", models.DecimalField(blank=True, decimal_places=3, max_digits=8, null=True, validators=[django.core.validators.MinValueValidator(decimal.Decimal("0.01"))])),
                ("height_m", models.DecimalField(blank=True, decimal_places=3, max_digits=8, null=True, validators=[django.core.validators.MinValueValidator(decimal.Decimal("0.01"))])),
                ("deductions_area_m2", models.DecimalField(decimal_places=3, default=0, max_digits=10, validators=[django.core.validators.MinValueValidator(decimal.Decimal("0")), django.core.validators.MaxValueValidator(decimal.Decimal("1"))])),
                ("waste_percent", models.DecimalField(decimal_places=2, default=10, max_digits=5, validators=[django.core.validators.MinValueValidator(decimal.Decimal("0"))])),
                ("confidence", models.DecimalField(decimal_places=4, default=0, max_digits=5, validators=[django.core.validators.MinValueValidator(decimal.Decimal("0"))])),
                ("reference_type", models.CharField(blank=True, max_length=40)),
                ("reference_width_cm", models.DecimalField(blank=True, decimal_places=2, max_digits=8, null=True)),
                ("reference_height_cm", models.DecimalField(blank=True, decimal_places=2, max_digits=8, null=True)),
                ("ai_summary", models.TextField(blank=True)),
                ("ai_warnings", models.JSONField(blank=True, default=list)),
                ("ai_payload", models.JSONField(blank=True, default=dict)),
                ("confirmed_at", models.DateTimeField(blank=True, null=True)),
                ("confirmed_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="confirmed_room_measurements", to=settings.AUTH_USER_MODEL)),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="created_room_measurements", to=settings.AUTH_USER_MODEL)),
                ("organization", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="room_measurements", to="erp.organization")),
                ("project", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="room_measurements", to="erp.project")),
            ],
            options={
                "ordering": ["project", "created_at"],
                "indexes": [
                    models.Index(fields=["organization", "status"], name="erp_room_org_status_idx"),
                    models.Index(fields=["project", "created_at"], name="erp_room_proj_created_idx"),
                ],
            },
        ),
        migrations.CreateModel(
            name="MeasurementCapture",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("kind", models.CharField(choices=[("doorway", "Von der Tür"), ("wall_1", "Wand 1"), ("wall_2", "Wand 2"), ("wall_3", "Wand 3"), ("wall_4", "Wand 4"), ("floor", "Boden"), ("ceiling", "Decke"), ("connections", "Anschlüsse"), ("windows", "Fenster / Türen"), ("damage", "Schäden"), ("other", "Weitere Aufnahme")], default="other", max_length=24)),
                ("image", models.ImageField(upload_to="measurements/%Y/%m/")),
                ("mime_type", models.CharField(blank=True, max_length=120)),
                ("size", models.PositiveBigIntegerField(default=0)),
                ("sha256", models.CharField(blank=True, max_length=64)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="measurement_captures", to=settings.AUTH_USER_MODEL)),
                ("measurement", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="captures", to="erp.roommeasurement")),
            ],
            options={"ordering": ["created_at"]},
        ),
    ]
