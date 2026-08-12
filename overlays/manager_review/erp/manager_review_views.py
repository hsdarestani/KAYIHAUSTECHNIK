from __future__ import annotations

import hashlib
import json
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods, require_POST

from . import models as m
from .rebuild_views import _is_field_user, _org
from .services.field_authorization import AUTH_KIND, COMPLETION_KIND, money


PENDING = "pending_review"
APPROVED = "approved"
CHANGES = "changes_requested"
MONEY = Decimal("0.01")


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


def _authorization(org, completion):
    event_id = (completion.metadata or {}).get("event_id")
    if not event_id:
        return None
    return (
        m.Document.objects.filter(
            organization=org,
            project=completion.project,
            metadata__kind=AUTH_KIND,
            metadata__event_id=event_id,
            metadata__status="signed",
        )
        .order_by("-created_at", "-pk")
        .first()
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


def _normalize_item(raw, position):
    quantity = max(Decimal("0"), money(raw.get("quantity") or "1"))
    unit_price = max(Decimal("0"), money(raw.get("unit_price") or raw.get("price") or "0"))
    tax_rate = max(Decimal("0"), money(raw.get("tax_rate") or "19"))
    purchase_price = max(Decimal("0"), money(raw.get("purchase_price") or "0"))
    markup_percent = money(raw.get("markup_percent") or "0")
    net = (quantity * unit_price).quantize(MONEY)
    tax = (net * tax_rate / Decimal("100")).quantize(MONEY)
    cost = (quantity * purchase_price).quantize(MONEY)
    return {
        "position": position,
        "description": str(raw.get("description") or "")[:500],
        "quantity": str(quantity),
        "unit": str(raw.get("unit") or "Stk.")[:30],
        "position_type": str(raw.get("position_type") or "other")[:20],
        "purchase_price": str(purchase_price),
        "markup_percent": str(markup_percent),
        "unit_price": str(unit_price),
        "tax_rate": str(tax_rate),
        "cost": str(cost),
        "net": str(net),
        "tax": str(tax),
        "gross": str((net + tax).quantize(MONEY)),
    }


def _totals(items):
    net = sum((money(item.get("net")) for item in items), Decimal("0"))
    tax = sum((money(item.get("tax")) for item in items), Decimal("0"))
    cost = sum((money(item.get("cost")) for item in items), Decimal("0"))
    gross = net + tax
    margin = net - cost
    margin_percent = (margin / net * Decimal("100")) if net else Decimal("0")
    return {
        "net": str(net.quantize(MONEY)),
        "tax": str(tax.quantize(MONEY)),
        "gross": str(gross.quantize(MONEY)),
        "cost": str(cost.quantize(MONEY)),
        "margin": str(margin.quantize(MONEY)),
        "margin_percent": str(margin_percent.quantize(MONEY)),
    }


def _default_review(completion, authorization):
    metadata = completion.metadata or {}
    completion_snapshot = metadata.get("snapshot") if isinstance(metadata.get("snapshot"), dict) else {}
    auth_snapshot = authorization.metadata.get("snapshot") if authorization and isinstance(authorization.metadata, dict) else {}
    source_items = auth_snapshot.get("items") if isinstance(auth_snapshot.get("items"), list) else []
    items = [_normalize_item(item, index + 1) for index, item in enumerate(source_items)]
    return {
        "schema": "ab-bau.office-billing-review.v1",
        "report": completion_snapshot.get("report") or "",
        "services": completion_snapshot.get("services") or "",
        "material": completion_snapshot.get("material") or "",
        "items": items,
        "totals": _totals(items),
        "note": metadata.get("review_note") or "",
        "source_authorization_document_id": authorization.pk if authorization else None,
        "source_authorization_snapshot_sha256": (authorization.metadata or {}).get("snapshot_sha256") if authorization else None,
        "source_completion_snapshot_sha256": metadata.get("snapshot_sha256"),
    }


def _review_state(completion, authorization):
    review = (completion.metadata or {}).get("billing_review")
    if isinstance(review, dict) and isinstance(review.get("items"), list):
        clean = dict(review)
        clean["items"] = [_normalize_item(item, index + 1) for index, item in enumerate(review.get("items") or [])]
        clean["totals"] = _totals(clean["items"])
        return clean
    return _default_review(completion, authorization)


def _parse_posted_review(request, completion, authorization):
    descriptions = request.POST.getlist("item_description")
    quantities = request.POST.getlist("item_quantity")
    units = request.POST.getlist("item_unit")
    position_types = request.POST.getlist("item_position_type")
    purchase_prices = request.POST.getlist("item_purchase_price")
    markups = request.POST.getlist("item_markup_percent")
    prices = request.POST.getlist("item_price")
    taxes = request.POST.getlist("item_tax")
    items = []
    for index, description in enumerate(descriptions):
        description = (description or "").strip()
        if not description:
            continue
        raw = {
            "description": description,
            "quantity": quantities[index] if index < len(quantities) else "1",
            "unit": units[index] if index < len(units) else "Stk.",
            "position_type": position_types[index] if index < len(position_types) else "other",
            "purchase_price": purchase_prices[index] if index < len(purchase_prices) else "0",
            "markup_percent": markups[index] if index < len(markups) else "0",
            "unit_price": prices[index] if index < len(prices) else "0",
            "tax_rate": taxes[index] if index < len(taxes) else "19",
        }
        items.append(_normalize_item(raw, len(items) + 1))
    review = _default_review(completion, authorization)
    review.update({
        "report": (request.POST.get("report") or "").strip()[:12000],
        "services": (request.POST.get("services") or "").strip()[:12000],
        "material": (request.POST.get("material") or "").strip()[:12000],
        "note": (request.POST.get("note") or "").strip()[:3000],
        "items": items,
        "totals": _totals(items),
        "edited_at": timezone.now().isoformat(),
        "edited_by_id": request.user.pk,
        "edited_by": request.user.get_full_name() or request.user.get_username(),
    })
    digest_source = json.dumps(review, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    review["review_sha256"] = hashlib.sha256(digest_source.encode("utf-8")).hexdigest()
    return review


def _save_review(request, org, completion, review):
    metadata = dict(completion.metadata or {})
    metadata["billing_review"] = review
    metadata["review_note"] = review.get("note") or ""
    if metadata.get("status") == APPROVED:
        metadata["status"] = PENDING
    metadata["billing_ready"] = False
    completion.metadata = metadata
    completion.save(update_fields=["metadata", "updated_at"])
    _audit(
        request,
        org,
        completion,
        "field_completion_office_edited",
        "Einsatzabschluss und Abrechnungspositionen durch Büro/Leitung bearbeitet.",
        {"review_sha256": review.get("review_sha256"), "item_count": len(review.get("items") or [])},
    )


def _approve(request, org, completion, review):
    metadata = dict(completion.metadata or {})
    metadata.update({
        "status": APPROVED,
        "reviewed_at": timezone.now().isoformat(),
        "reviewed_by_id": request.user.pk,
        "reviewed_by": request.user.get_full_name() or request.user.get_username(),
        "review_note": review.get("note") or "",
        "billing_review": review,
        "billing_ready": True,
    })
    completion.metadata = metadata
    completion.save(update_fields=["metadata", "updated_at"])
    _audit(
        request,
        org,
        completion,
        "field_completion_approved",
        "Einsatzabschluss nach Büro-Bearbeitung freigegeben.",
        {"review_sha256": review.get("review_sha256"), "item_count": len(review.get("items") or [])},
    )


def _request_changes(request, org, completion, note):
    metadata = dict(completion.metadata or {})
    metadata.update({
        "status": CHANGES,
        "reviewed_at": timezone.now().isoformat(),
        "reviewed_by_id": request.user.pk,
        "reviewed_by": request.user.get_full_name() or request.user.get_username(),
        "review_note": note[:3000],
        "billing_ready": False,
    })
    completion.metadata = metadata
    completion.save(update_fields=["metadata", "updated_at"])
    _audit(request, org, completion, "field_completion_changes_requested", "Einsatz zur Ergänzung an den Monteur zurückgegeben.", {"note": note[:3000]})


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
    legacy = list(qs.filter(metadata__status="completed")[:50])
    return render(request, "rebuild/review_queue.html", {
        "pending_reviews": pending,
        "changes_requested": changes,
        "approved_reviews": approved,
        "legacy_reviews": legacy,
        "pending_count": len(pending) + len(legacy),
    })


@login_required
@require_http_methods(["GET", "POST"])
def review_detail(request, pk):
    denied = _office_only(request)
    if denied:
        return denied
    org = _org(request)
    completion = _completion(org, pk)
    authorization = _authorization(org, completion)
    event_id = (completion.metadata or {}).get("event_id")
    event = None
    if event_id:
        event = m.CalendarEvent.objects.filter(organization=org, pk=event_id).select_related("project", "project__customer", "project__object_location").first()
    review = _review_state(completion, authorization)

    if request.method == "POST":
        action = (request.POST.get("action") or "save").strip()
        review = _parse_posted_review(request, completion, authorization)
        if action == "return":
            note = review.get("note") or ""
            if not note:
                messages.error(request, "Bitte angeben, was der Monteur ergänzen oder prüfen soll.")
            else:
                _save_review(request, org, completion, review)
                _request_changes(request, org, completion, note)
                messages.success(request, "Einsatz wurde mit deinen gespeicherten Büro-Änderungen an den Monteur zurückgegeben.")
                return redirect("field-review-queue")
        elif not review.get("items"):
            messages.error(request, "Mindestens eine Abrechnungsposition ist erforderlich.")
        elif action == "approve":
            _approve(request, org, completion, review)
            messages.success(request, "Änderungen gespeichert und Einsatz freigegeben. Die geprüften Positionen sind für die Abrechnung bereit.")
            return redirect("field-review-queue")
        else:
            _save_review(request, org, completion, review)
            messages.success(request, "Büro-Änderungen gespeichert. Der ursprüngliche unterschriebene Einsatz bleibt unverändert archiviert.")
            return redirect("field-review-detail", pk=completion.pk)

    before_docs = []
    after_docs = []
    other_docs = []
    if event_id:
        docs = m.Document.objects.filter(organization=org, project=completion.project, metadata__event_id=event_id).order_by("created_at", "pk")
        before_docs = list(docs.filter(category="photo", metadata__phase="before"))
        after_docs = list(docs.filter(category="photo", metadata__phase="after"))
        other_docs = list(docs.exclude(category="photo")[:50])
    auth_snapshot = authorization.metadata.get("snapshot") if authorization and isinstance(authorization.metadata, dict) else {}
    return render(request, "rebuild/review_detail.html", {
        "completion": completion,
        "authorization": authorization,
        "authorization_data": auth_snapshot,
        "event": event,
        "review": review,
        "before_docs": before_docs,
        "after_docs": after_docs,
        "other_docs": other_docs,
    })


@login_required
@require_POST
def approve_completion(request, pk):
    denied = _office_only(request)
    if denied:
        return denied
    org = _org(request)
    completion = _completion(org, pk)
    authorization = _authorization(org, completion)
    review = _review_state(completion, authorization)
    note = (request.POST.get("note") or "").strip()
    if note:
        review["note"] = note[:3000]
    review["edited_at"] = timezone.now().isoformat()
    review["edited_by_id"] = request.user.pk
    review["edited_by"] = request.user.get_full_name() or request.user.get_username()
    digest_source = json.dumps(review, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    review["review_sha256"] = hashlib.sha256(digest_source.encode("utf-8")).hexdigest()
    if not review.get("items"):
        messages.error(request, "Vor der Freigabe müssen Abrechnungspositionen vorhanden sein.")
        return redirect("field-review-detail", pk=completion.pk)
    _approve(request, org, completion, review)
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
        return redirect("field-review-detail", pk=completion.pk)
    _request_changes(request, org, completion, note)
    messages.success(request, "Einsatz wurde zur Ergänzung an den Monteur zurückgegeben.")
    return redirect("field-review-queue")
