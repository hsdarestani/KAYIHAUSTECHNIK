from __future__ import annotations

from django.conf import settings
from django.db import models


class ProjectApprovalFlow(models.Model):
    MODE_CHOICES = [
        ("owner", "Inhaber vor Ort"),
        ("technician", "Mitarbeiter vor Ort"),
    ]
    STATUS_CHOICES = [
        ("draft", "Entwurf"),
        ("submitted", "Zur Freigabe eingereicht"),
        ("confirmed", "Vom Büro freigegeben"),
        ("signed", "Vom Kunden unterschrieben"),
        ("changes_requested", "Änderung angefordert"),
        ("cancelled", "Abgebrochen"),
    ]

    organization = models.ForeignKey("erp.Organization", on_delete=models.CASCADE, related_name="project_approval_flows")
    project = models.OneToOneField("erp.Project", on_delete=models.CASCADE, related_name="approval_flow")
    quote = models.OneToOneField("erp.Quote", null=True, blank=True, on_delete=models.SET_NULL, related_name="project_approval_flow")
    requested_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="requested_project_approvals")
    confirmed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="confirmed_project_approvals")
    mode = models.CharField(max_length=16, choices=MODE_CHOICES, default="technician")
    status = models.CharField(max_length=24, choices=STATUS_CHOICES, default="draft")
    intake_text = models.TextField(blank=True)
    voice_transcript = models.TextField(blank=True)
    review_note = models.TextField(blank=True)
    signer_name = models.CharField(max_length=220, blank=True)
    signature_data = models.TextField(blank=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    signed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]
        indexes = [models.Index(fields=["organization", "status"], name="erp_appr_org_status_idx")]
