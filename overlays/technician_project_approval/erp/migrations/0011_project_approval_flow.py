from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("erp", "0010_ab_bau_commercial"),
    ]

    operations = [
        migrations.CreateModel(
            name="ProjectApprovalFlow",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("mode", models.CharField(choices=[("owner", "Inhaber vor Ort"), ("technician", "Mitarbeiter vor Ort")], default="technician", max_length=16)),
                ("status", models.CharField(choices=[("draft", "Entwurf"), ("submitted", "Zur Freigabe eingereicht"), ("confirmed", "Vom Büro freigegeben"), ("signed", "Vom Kunden unterschrieben"), ("changes_requested", "Änderung angefordert"), ("cancelled", "Abgebrochen")], default="draft", max_length=24)),
                ("intake_text", models.TextField(blank=True)),
                ("voice_transcript", models.TextField(blank=True)),
                ("review_note", models.TextField(blank=True)),
                ("signer_name", models.CharField(blank=True, max_length=220)),
                ("signature_data", models.TextField(blank=True)),
                ("submitted_at", models.DateTimeField(blank=True, null=True)),
                ("confirmed_at", models.DateTimeField(blank=True, null=True)),
                ("signed_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("confirmed_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="confirmed_project_approvals", to=settings.AUTH_USER_MODEL)),
                ("organization", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="project_approval_flows", to="erp.organization")),
                ("project", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="approval_flow", to="erp.project")),
                ("quote", models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="project_approval_flow", to="erp.quote")),
                ("requested_by", models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="requested_project_approvals", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["-updated_at"]},
        ),
        migrations.AddIndex(
            model_name="projectapprovalflow",
            index=models.Index(fields=["organization", "status"], name="erp_projapproval_org_status_idx"),
        ),
    ]
