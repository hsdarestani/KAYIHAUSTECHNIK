from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from . import models as m
from .rebuild_views import _is_field_user, _org
from .services.field_authorization import COMPLETION_KIND


PENDING = "pending_review"
APPROVED = "approved"
CHANGES = "changes_requested"


def _office_only(request):
    if _is_field_user(request):
        return HttpResponseForbidden("Die Einsatzprüfung ist nur für Büro/Leitung verfügbar.")
    return None


def _completion(org, pk):
    return get_object_or_404(
        m.Document.objects.select_related("project", "project__customer", "uploaded_by"),
        pk=pk,
        organization=org,
        metadata__kind=COMPLETION_KIND,
    )


def _audit(request, org, completion, verb, description, extra=None):
    payload = {
        "completion_document_id": completion.pk,
        "event_id": (completion.metadata or {}).get("event_id"),
        "project_id": completion.project_id,
    }
    payload.update(extra or {})
    m.ActivityLog.objects.create(
        organization=org,
        user=request.user,
        verb=verb,
        entity_type="field_completion",
        entity_id=str(completion.pk),
        description=description,
        metadata=payload,
    )


@login_required
def review_queue(request):
    denied = _office_only(request)
    if denied:
        return denied
    org = _org(request)
    qs = (
        m.Document.objects.filter(organization=org, metadata__kind=COMPLETION_KIND)
        .select_related("project", "project__customer", "uploaded_by")
        .order_by("-created_at")
    )
    pending = list(qs.filter(metadata__status=PENDING)[:100])
    changes = list(qs.filter(metadata__status=CHANGES)[:50])
    approved = list(qs.filter(metadata__status=APPROVED)[:50])
    # Old completions created before the approval workflow stay visible instead
    # of silently disappearing. Office can approve them explicitly if needed.
    legacy = list(qs.filter(metadata__status="completed")[:50])
    return render(request, "rebuild/review_queue.html", {
        "pending_reviews": pending,
        "changes_requested": changes,
        "approved_reviews": approved,
        "legacy_reviews": legacy,
        "pending_count": len(pending) + len(legacy),
    })


@login_required
@require_POST
def approve_completion(request, pk):
    denied = _office_only(request)
    if denied:
        return denied
    org = _org(request)
    completion = _completion(org, pk)
    metadata = dict(completion.metadata or {})
    metadata.update({
        "status": APPROVED,
        "reviewed_at": timezone.now().isoformat(),
        "reviewed_by_id": request.user.pk,
        "reviewed_by": request.user.get_full_name() or request.user.get_username(),
        "review_note": (request.POST.get("note") or "").strip()[:2000],
        "billing_ready": True,
    })
    completion.metadata = metadata
    completion.save(update_fields=["metadata", "updated_at"])
    _audit(request, org, completion, "field_completion_approved", "Einsatzabschluss durch Büro freigegeben.")
    messages.success(request, "Einsatz freigegeben. Er ist jetzt für die Rechnungsstellung bereit.")
    return redirect("field-review-queue")


@login_required
@require_POST
def request_changes(request, pk):
    denied = _office_only(request)
    if denied:
        return denied
    org = _org(request)
    completion = _completion(org, pk)
    note = (request.POST.get("note") or "").strip()
    if not note:
        messages.error(request, "Bitte kurz angeben, was der Monteur korrigieren oder ergänzen soll.")
        return redirect("field-review-queue")
    metadata = dict(completion.metadata or {})
    metadata.update({
        "status": CHANGES,
        "reviewed_at": timezone.now().isoformat(),
        "reviewed_by_id": request.user.pk,
        "reviewed_by": request.user.get_full_name() or request.user.get_username(),
        "review_note": note[:2000],
        "billing_ready": False,
    })
    completion.metadata = metadata
    completion.save(update_fields=["metadata", "updated_at"])
    _audit(request, org, completion, "field_completion_changes_requested", "Änderung am Einsatzabschluss angefordert.", {"note": note[:2000]})
    messages.success(request, "Änderung angefordert. Der Einsatz ist beim Monteur wieder zur Bearbeitung offen.")
    return redirect("field-review-queue")
