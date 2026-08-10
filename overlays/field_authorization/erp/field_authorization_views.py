from __future__ import annotations

import base64
import json
import os
import re
from datetime import timedelta
from decimal import Decimal
from pathlib import Path

from django.contrib.auth.decorators import login_required
from django.core.files.base import ContentFile
from django.db import transaction
from django.db.models import Q
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from . import models as m
from .rebuild_views import _employee, _is_field_user, _org, _unique_number
from .services.field_authorization import (
    AUTH_KIND,
    COMPLETION_KIND,
    authorization_html,
    authorization_snapshot,
    completion_html,
    decode_signature,
    document_response,
    event_documents,
    html_to_pdf_bytes,
    latest_authorization,
    latest_completion,
    latest_room_revision,
    money,
    parse_items,
    room_plan_svg,
    save_binary_document,
    sha256_bytes,
    sha256_json,
    totals_for_items,
    uploaded_images,
)


PRICING_MODES = {"fixed", "estimate", "hourly"}


def _event_for(request, pk):
    org = _org(request)
    qs = m.CalendarEvent.objects.filter(organization=org).select_related("project", "project__customer", "project__object_location").prefetch_related("attendees")
    if _is_field_user(request):
        employee = _employee(request, org)
        if employee is None:
            return org, get_object_or_404(qs.none(), pk=pk)
        qs = qs.filter(Q(attendees=employee) | Q(project__manager=employee) | Q(project__members=employee)).distinct()
    return org, get_object_or_404(qs, pk=pk)


def _doc_image_payload(document):
    if not document.file or not (document.mime_type or "").startswith("image/"):
        return None
    try:
        document.file.open("rb")
        raw = document.file.read()
        document.file.close()
    except Exception:
        return None
    if not raw:
        return None
    return {"name": Path(document.file.name).name, "mime": document.mime_type, "bytes": raw, "sha256": sha256_bytes(raw)}


def _phase_images(org, event, phase):
    docs = event_documents(org, event, phase=phase).filter(category="photo")
    return [payload for payload in (_doc_image_payload(doc) for doc in docs) if payload]


def _room_revision_for_post(project, revision_id):
    if not revision_id:
        return None
    return (
        m.RoomModelRevision.objects.filter(pk=revision_id, organization=project.organization, project=project)
        .select_related("measurement")
        .first()
    )


def _authorization_version(org, event):
    return m.Document.objects.filter(organization=org, project=event.project, metadata__kind=AUTH_KIND, metadata__event_id=event.pk).count() + 1


def _catalog_match(org, query):
    words = [word for word in re.split(r"[^\wäöüÄÖÜß]+", query or "") if len(word) >= 3][:5]
    if not words:
        return None
    condition = Q()
    for word in words:
        condition |= Q(name__icontains=word) | Q(description__icontains=word) | Q(code__icontains=word)
    return m.CatalogItem.objects.filter(organization=org, active=True).filter(condition).order_by("name").first()


@login_required
@require_http_methods(["GET", "POST"])
def quick_job(request):
    org = _org(request)
    employee = _employee(request, org)
    customers = m.Customer.objects.filter(organization=org, active=True).order_by("company", "last_name", "first_name")[:300]
    if request.method == "GET":
        return render(request, "rebuild/field_quick_job.html", {"customers": customers, "employee": employee})

    mode = request.POST.get("customer_mode") or "existing"
    title = (request.POST.get("title") or "Reparatur / Vor-Ort-Auftrag").strip()[:200]
    issue = (request.POST.get("issue") or "").strip()
    street = (request.POST.get("street") or "").strip()[:200]
    postal_code = (request.POST.get("postal_code") or "").strip()[:20]
    city = (request.POST.get("city") or "").strip()[:120]
    if mode == "existing":
        customer = get_object_or_404(m.Customer, organization=org, active=True, pk=request.POST.get("customer_id"))
    else:
        company = (request.POST.get("company") or "").strip()[:200]
        first_name = (request.POST.get("first_name") or "").strip()[:120]
        last_name = (request.POST.get("last_name") or "").strip()[:120]
        if not company and not (first_name or last_name):
            return render(request, "rebuild/field_quick_job.html", {"customers": customers, "employee": employee, "error": "Bitte Kundenname oder Firma angeben."}, status=400)
        customer = m.Customer.objects.create(
            organization=org,
            number=_unique_number(m.Customer, org, "K"),
            type="business" if company else "private",
            company=company,
            first_name=first_name,
            last_name=last_name,
            mobile=(request.POST.get("mobile") or "").strip()[:80],
            email=(request.POST.get("email") or "").strip()[:200],
            street=street,
            postal_code=postal_code,
            city=city,
            country="Deutschland",
        )

    with transaction.atomic():
        location = None
        if street or postal_code or city:
            location = m.ObjectLocation.objects.create(
                organization=org,
                customer=customer,
                name="Einsatzort",
                street=street or customer.street,
                postal_code=postal_code or customer.postal_code,
                city=city or customer.city,
            )
        project = m.Project.objects.create(
            organization=org,
            number=_unique_number(m.Project, org, "P"),
            title=title,
            description=issue,
            customer=customer,
            object_location=location,
            manager=employee,
            status="confirmed",
            priority="normal",
        )
        if employee:
            project.members.add(employee)
        now = timezone.now().replace(second=0, microsecond=0)
        address = ", ".join(part for part in [street or customer.street, f"{postal_code or customer.postal_code} {city or customer.city}".strip()] if part)
        event = m.CalendarEvent.objects.create(
            organization=org,
            project=project,
            title=title,
            type="site",
            starts_at=now,
            ends_at=now + timedelta(hours=2),
            location=address,
            notes=issue,
            created_by=request.user,
        )
        if employee:
            event.attendees.add(employee)
    return redirect("next-appointment-detail", pk=event.pk)


@login_required
@require_GET
def customer_search(request):
    org = _org(request)
    query = (request.GET.get("q") or "").strip()
    qs = m.Customer.objects.filter(organization=org, active=True)
    if query:
        qs = qs.filter(Q(company__icontains=query) | Q(first_name__icontains=query) | Q(last_name__icontains=query) | Q(phone__icontains=query) | Q(mobile__icontains=query) | Q(number__icontains=query))
    rows = []
    for customer in qs.order_by("company", "last_name", "first_name")[:30]:
        rows.append({"id": customer.pk, "number": customer.number, "name": customer.display_name, "phone": customer.mobile or customer.phone, "address": ", ".join(part for part in [customer.street, f"{customer.postal_code} {customer.city}".strip()] if part)})
    return JsonResponse({"results": rows})


@login_required
def field_job_detail(request, pk):
    org, event = _event_for(request, pk)
    if event.project_id is None:
        return render(request, "rebuild/appointment_detail.html", {"event": event, "project_missing": True})
    authorization = latest_authorization(org, event)
    completion = latest_completion(org, event)
    employee = _employee(request, org)
    running = None
    if employee:
        running = m.TimeEntry.objects.filter(organization=org, employee=employee, project=event.project, ended_at__isnull=True).order_by("-started_at").first()
    measurement, room_revision = latest_room_revision(event.project)
    before_docs = event_documents(org, event, phase="before")
    after_docs = event_documents(org, event, phase="after")
    other_docs = m.Document.objects.filter(organization=org, project=event.project, metadata__event_id=event.pk).exclude(metadata__phase__in=["before", "after"]).order_by("-created_at")[:40]
    authorization_data = authorization.metadata.get("snapshot") if authorization and isinstance(authorization.metadata, dict) else None
    return render(request, "rebuild/appointment_detail.html", {
        "event": event,
        "authorization": authorization,
        "authorization_data": authorization_data,
        "completion": completion,
        "employee": employee,
        "running": running,
        "measurement": measurement,
        "room_revision": room_revision,
        "before_docs": before_docs,
        "after_docs": after_docs,
        "documents": other_docs,
        "pricing_modes": [("fixed", "Festpreis"), ("estimate", "Kostenschätzung / Budgetfreigabe"), ("hourly", "Nach Aufwand")],
    })


@login_required
@require_POST
def gated_time_toggle(request, event_pk):
    org, event = _event_for(request, event_pk)
    employee = _employee(request, org)
    if employee is None or event.project_id is None:
        return JsonResponse({"ok": False, "error": "Mitarbeiter oder Projekt fehlt."}, status=400)
    running = m.TimeEntry.objects.filter(organization=org, employee=employee, project=event.project, ended_at__isnull=True).order_by("-started_at").first()
    if running:
        running.ended_at = timezone.now()
        running.save(update_fields=["ended_at", "updated_at"])
        return JsonResponse({"ok": True, "state": "stopped"})
    authorization = latest_authorization(org, event)
    if authorization is None:
        return JsonResponse({"ok": False, "error": "Vor Arbeitsbeginn muss der Kunde Leistungsumfang und Preis freigeben und unterschreiben.", "requires_authorization": True}, status=409)
    entry = m.TimeEntry.objects.create(
        organization=org,
        employee=employee,
        project=event.project,
        started_at=timezone.now(),
        description=f"Termin #{event.pk}: {event.title} · Freigabe #{authorization.pk}",
    )
    if event.project.status in {"inquiry", "planning", "quoted", "confirmed"}:
        event.project.status = "in_progress"
        event.project.actual_start = event.project.actual_start or timezone.localdate()
        event.project.save(update_fields=["status", "actual_start", "updated_at"])
    return JsonResponse({"ok": True, "state": "running", "id": entry.pk, "authorization_id": authorization.pk})


@login_required
@require_POST
def authorization_sign(request, pk):
    org, event = _event_for(request, pk)
    if event.project_id is None:
        return JsonResponse({"ok": False, "error": "Termin hat kein Projekt."}, status=400)
    issue = (request.POST.get("issue") or "").strip()
    scope = (request.POST.get("scope") or "").strip()
    pricing_mode = request.POST.get("pricing_mode") or "fixed"
    signer_name = (request.POST.get("signer_name") or "").strip()
    consent = request.POST.get("consent") == "on"
    signature = decode_signature(request.POST.get("signature_data") or "")
    if not issue or not scope:
        return JsonResponse({"ok": False, "error": "Zustand und Leistungsumfang müssen beschrieben sein."}, status=400)
    if pricing_mode not in PRICING_MODES:
        return JsonResponse({"ok": False, "error": "Ungültige Preisart."}, status=400)
    items = parse_items(request.POST)
    if not items:
        return JsonResponse({"ok": False, "error": "Mindestens eine Preisposition ist erforderlich."}, status=400)
    if not signer_name or not consent or not signature:
        return JsonResponse({"ok": False, "error": "Name, Zustimmung und Kundenunterschrift sind erforderlich."}, status=400)
    cap_value = (request.POST.get("price_cap_gross") or "").strip()
    price_cap = money(cap_value) if cap_value else None
    totals = totals_for_items(items)
    if price_cap is not None and price_cap < money(totals["gross"]):
        return JsonResponse({"ok": False, "error": "Das Kostenlimit darf nicht unter der aktuell angezeigten Bruttosumme liegen."}, status=400)
    try:
        before_photos = uploaded_images(request.FILES.getlist("before_photos"))
    except ValueError as exc:
        return JsonResponse({"ok": False, "error": str(exc)}, status=400)
    room_revision = _room_revision_for_post(event.project, request.POST.get("room_revision_id"))
    snapshot = authorization_snapshot(
        request=request,
        event=event,
        issue=issue,
        scope=scope,
        pricing_mode=pricing_mode,
        items=items,
        price_cap_gross=price_cap,
        room_revision=room_revision,
        before_photos=before_photos,
        signer_name=signer_name,
    )
    snapshot_hash = sha256_json(snapshot)
    room_svg = room_plan_svg(room_revision.state, title=f"Raumplan bei Freigabe · v{room_revision.revision}") if room_revision else None
    pdf = html_to_pdf_bytes(authorization_html(org=org, snapshot=snapshot, signature=signature, room_svg=room_svg, before_photos=before_photos))
    version = _authorization_version(org, event)
    with transaction.atomic():
        for photo in before_photos:
            save_binary_document(
                org=org, project=event.project, customer=event.project.customer, user=request.user,
                title=f"Vorher · {photo['name']}", category="photo", filename=f"before-{event.pk}-{photo['sha256'][:10]}-{photo['name']}", mime=photo["mime"], raw=photo["bytes"],
                metadata={"event_id": event.pk, "kind": "field_authorization_photo", "phase": "before", "authorization_snapshot_sha256": snapshot_hash, "file_sha256": photo["sha256"]},
            )
        signature_doc = save_binary_document(
            org=org, project=event.project, customer=event.project.customer, user=request.user,
            title=f"Kundenunterschrift Auftragsfreigabe · {signer_name}", category="other", filename=f"authorization-signature-{event.pk}-v{version}.png", mime="image/png", raw=signature,
            metadata={"event_id": event.pk, "kind": "field_authorization_signature", "phase": "authorization", "snapshot_sha256": snapshot_hash, "signer_name": signer_name},
        )
        authorization = save_binary_document(
            org=org, project=event.project, customer=event.project.customer, user=request.user,
            title=f"Auftragsfreigabe · {event.title} · v{version}", category="contract", filename=f"auftragsfreigabe-{event.pk}-v{version}.pdf", mime="application/pdf", raw=pdf,
            metadata={"event_id": event.pk, "kind": AUTH_KIND, "phase": "authorization", "status": "signed", "authorization_version": version, "snapshot": snapshot, "snapshot_sha256": snapshot_hash, "signature_document_id": signature_doc.pk, "room_revision_id": room_revision.pk if room_revision else None},
        )
    return JsonResponse({"ok": True, "authorization_id": authorization.pk, "snapshot_sha256": snapshot_hash, "pdf_url": f"/appointments/{event.pk}/authorization/pdf/", "reload": True})


@login_required
@require_GET
def authorization_pdf(request, pk):
    org, event = _event_for(request, pk)
    document = latest_authorization(org, event)
    if document is None:
        return JsonResponse({"ok": False, "error": "Noch keine Freigabe vorhanden."}, status=404)
    return document_response(document)


@login_required
@require_GET
def completion_pdf(request, pk):
    org, event = _event_for(request, pk)
    document = latest_completion(org, event)
    if document is None:
        return JsonResponse({"ok": False, "error": "Noch kein Einsatzabschluss vorhanden."}, status=404)
    return document_response(document)


@login_required
@require_GET
def room_plan_preview(request, pk):
    org, event = _event_for(request, pk)
    if event.project_id is None:
        return HttpResponse("", content_type="image/svg+xml", status=404)
    _, revision = latest_room_revision(event.project)
    if revision is None:
        return HttpResponse("", content_type="image/svg+xml", status=404)
    return HttpResponse(room_plan_svg(revision.state, title=f"Aktueller Raumplan · v{revision.revision}"), content_type="image/svg+xml")


@login_required
@require_POST
def authorization_ai(request, pk):
    org, event = _event_for(request, pk)
    raw = (request.POST.get("text") or "").strip()
    if not raw:
        return JsonResponse({"ok": False, "error": "Kein Diktat vorhanden."}, status=400)
    fallback = {"issue": raw, "scope": raw, "items": [], "ai": False}
    try:
        from erp.services.ai import SYSTEM_PROMPT, _create_response
        schema = {
            "type": "object",
            "properties": {
                "issue": {"type": "string"},
                "scope": {"type": "string"},
                "positions": {"type": "array", "maxItems": 20, "items": {"type": "object", "properties": {"description": {"type": "string"}, "quantity": {"type": "number"}, "unit": {"type": "string"}, "catalog_query": {"type": "string"}}, "required": ["description", "quantity", "unit", "catalog_query"], "additionalProperties": False}},
            },
            "required": ["issue", "scope", "positions"],
            "additionalProperties": False,
        }
        response = _create_response(
            org,
            input=[
                {"role": "developer", "content": SYSTEM_PROMPT},
                {"role": "user", "content": "Strukturiere dieses Vor-Ort-Diktat als Kundenfreigabe. Erfinde keine Preise, Mengen nur wenn genannt oder offensichtlich 1 Stück. Trenne festgestellten Zustand und freizugebenden Leistungsumfang. Erzeuge kurze Katalogsuchbegriffe für jede Position. Deutsch.\n\n" + raw},
            ],
            text={"format": {"type": "json_schema", "name": "field_authorization_draft", "schema": schema, "strict": True}},
            store=False,
        )
        data = json.loads(response.output_text)
        items = []
        for pos in data.get("positions") or []:
            catalog = _catalog_match(org, pos.get("catalog_query") or pos.get("description"))
            items.append({
                "description": pos.get("description") or "",
                "quantity": str(pos.get("quantity") or 1),
                "unit": pos.get("unit") or (catalog.unit if catalog else "Stk."),
                "unit_price": str(catalog.sales_price if catalog else Decimal("0.00")),
                "tax_rate": str(catalog.tax_rate if catalog else Decimal("19.00")),
                "catalog_id": catalog.pk if catalog else None,
                "catalog_name": catalog.name if catalog else None,
            })
        return JsonResponse({"ok": True, "issue": data.get("issue") or raw, "scope": data.get("scope") or raw, "items": items, "ai": True})
    except Exception:
        return JsonResponse({"ok": True, **fallback})


@login_required
@require_POST
def complete_job(request, pk):
    org, event = _event_for(request, pk)
    authorization = latest_authorization(org, event)
    if authorization is None:
        return JsonResponse({"ok": False, "error": "Ohne unterschriebene Auftragsfreigabe kann der Einsatz nicht abgeschlossen werden."}, status=409)
    snapshot = authorization.metadata.get("snapshot") if isinstance(authorization.metadata, dict) else None
    if not isinstance(snapshot, dict):
        return JsonResponse({"ok": False, "error": "Die Freigabe enthält keinen gültigen Snapshot."}, status=409)
    report = (request.POST.get("report_text") or "").strip()
    services = (request.POST.get("services") or "").strip()
    material = (request.POST.get("material") or "").strip()
    if not report and not services:
        return JsonResponse({"ok": False, "error": "Bitte Arbeitsbericht oder ausgeführte Leistungen dokumentieren."}, status=400)
    try:
        after_photos = uploaded_images(request.FILES.getlist("after_photos"))
    except ValueError as exc:
        return JsonResponse({"ok": False, "error": str(exc)}, status=400)
    completion_signature = decode_signature(request.POST.get("completion_signature_data") or "")
    before_photos = _phase_images(org, event, "before")
    before_revision = None
    room_meta = snapshot.get("room_revision") if isinstance(snapshot.get("room_revision"), dict) else None
    if room_meta and room_meta.get("id"):
        before_revision = m.RoomModelRevision.objects.filter(pk=room_meta["id"], organization=org, project=event.project).first()
    _, after_revision = latest_room_revision(event.project)
    before_svg = room_plan_svg(before_revision.state, title=f"Raumplan vor Arbeitsbeginn · v{before_revision.revision}") if before_revision else None
    after_svg = room_plan_svg(after_revision.state, title=f"Raumplan beim Abschluss · v{after_revision.revision}") if after_revision else None
    completed_at = timezone.now().isoformat()
    completed_by = request.user.get_full_name() or request.user.get_username()
    pdf = html_to_pdf_bytes(completion_html(
        org=org,
        authorization=snapshot,
        report=report,
        services=services,
        material=material,
        completion_signature=completion_signature,
        room_svg_before=before_svg,
        room_svg_after=after_svg,
        before_photos=before_photos,
        after_photos=after_photos,
        completed_by=completed_by,
        completed_at=completed_at,
    ))
    completion_snapshot = {
        "schema": "kayi.field_completion.v1",
        "event_id": event.pk,
        "authorization_document_id": authorization.pk,
        "authorization_snapshot_sha256": authorization.metadata.get("snapshot_sha256"),
        "report": report,
        "services": services,
        "material": material,
        "after_photos": [{"name": item["name"], "sha256": item["sha256"]} for item in after_photos],
        "room_revision_before": before_revision.pk if before_revision else None,
        "room_revision_after": after_revision.pk if after_revision else None,
        "completed_at": completed_at,
        "completed_by": completed_by,
    }
    completion_hash = sha256_json(completion_snapshot)
    with transaction.atomic():
        for photo in after_photos:
            save_binary_document(
                org=org, project=event.project, customer=event.project.customer, user=request.user,
                title=f"Nachher · {photo['name']}", category="photo", filename=f"after-{event.pk}-{photo['sha256'][:10]}-{photo['name']}", mime=photo["mime"], raw=photo["bytes"],
                metadata={"event_id": event.pk, "kind": "field_completion_photo", "phase": "after", "completion_snapshot_sha256": completion_hash, "file_sha256": photo["sha256"]},
            )
        signature_doc = None
        if completion_signature:
            signature_doc = save_binary_document(
                org=org, project=event.project, customer=event.project.customer, user=request.user,
                title="Kundenunterschrift Einsatzabschluss", category="other", filename=f"completion-signature-{event.pk}-{timezone.now():%Y%m%d%H%M%S}.png", mime="image/png", raw=completion_signature,
                metadata={"event_id": event.pk, "kind": "field_completion_signature", "phase": "after", "completion_snapshot_sha256": completion_hash},
            )
        completion = save_binary_document(
            org=org, project=event.project, customer=event.project.customer, user=request.user,
            title=f"Einsatzabschluss · {event.title} · {timezone.localdate():%d.%m.%Y}", category="report", filename=f"einsatzabschluss-{event.pk}-{timezone.now():%Y%m%d%H%M%S}.pdf", mime="application/pdf", raw=pdf,
            metadata={"event_id": event.pk, "kind": COMPLETION_KIND, "phase": "final", "status": "completed", "snapshot": completion_snapshot, "snapshot_sha256": completion_hash, "authorization_document_id": authorization.pk, "signature_document_id": signature_doc.pk if signature_doc else None},
        )
        employee = _employee(request, org)
        if employee:
            running = m.TimeEntry.objects.filter(organization=org, employee=employee, project=event.project, ended_at__isnull=True).order_by("-started_at").first()
            if running:
                running.ended_at = timezone.now()
                running.save(update_fields=["ended_at", "updated_at"])
    return JsonResponse({"ok": True, "completion_id": completion.pk, "pdf_url": f"/appointments/{event.pk}/completion/pdf/", "redirect": f"/appointments/{event.pk}/"})
