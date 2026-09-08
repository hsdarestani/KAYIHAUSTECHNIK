import uuid

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("erp", "0005_workflow_release"),
    ]

    operations = [
        migrations.CreateModel(
            name="NativeRoomScan",
            fields=[
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("client_scan_id", models.UUIDField()),
                ("provider", models.CharField(choices=[("apple_roomplan", "Apple RoomPlan / LiDAR"), ("android_arcore_depth", "Android ARCore Depth")], max_length=32)),
                ("status", models.CharField(choices=[("uploading", "Upload läuft"), ("review", "Zu prüfen"), ("confirmed", "Bestätigt"), ("rejected", "Verworfen"), ("failed", "Fehlgeschlagen")], default="review", max_length=20)),
                ("room_name", models.CharField(default="Raum", max_length=160)),
                ("app_version", models.CharField(blank=True, max_length=40)),
                ("device_model", models.CharField(blank=True, max_length=120)),
                ("operating_system", models.CharField(blank=True, max_length=80)),
                ("confidence", models.DecimalField(decimal_places=4, default=0, max_digits=5, validators=[MinValueValidator(0), MaxValueValidator(1)])),
                ("raw_payload", models.JSONField(blank=True, default=dict)),
                ("normalized_payload", models.JSONField(blank=True, default=dict)),
                ("model_file", models.FileField(blank=True, upload_to="native-scans/%Y/%m/")),
                ("model_mime_type", models.CharField(blank=True, max_length=120)),
                ("model_size", models.PositiveBigIntegerField(default=0)),
                ("model_sha256", models.CharField(blank=True, max_length=64)),
                ("preview_file", models.FileField(blank=True, upload_to="native-scans/previews/%Y/%m/")),
                ("warnings", models.JSONField(blank=True, default=list)),
                ("confirmed_at", models.DateTimeField(blank=True, null=True)),
                ("confirmed_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="confirmed_native_room_scans", to=settings.AUTH_USER_MODEL)),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="created_native_room_scans", to=settings.AUTH_USER_MODEL)),
                ("measurement", models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="native_scan", to="erp.roommeasurement")),
                ("organization", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="native_room_scans", to="erp.organization")),
                ("project", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="native_room_scans", to="erp.project")),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.AddConstraint(
            model_name="nativeroomscan",
            constraint=models.UniqueConstraint(fields=("organization", "client_scan_id"), name="erp_native_scan_org_client_uniq"),
        ),
        migrations.AddIndex(
            model_name="nativeroomscan",
            index=models.Index(fields=["organization", "status"], name="erp_nativ_organiz_1f223e_idx"),
        ),
        migrations.AddIndex(
            model_name="nativeroomscan",
            index=models.Index(fields=["project", "created_at"], name="erp_nativ_project_b9005d_idx"),
        ),
    ]
