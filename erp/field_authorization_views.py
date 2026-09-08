# A+Bau scope engine completion 2026-08-18
from __future__ import annotations

import base64
import json
import os
import re
from datetime import timedelta
from decimal import Decimal
from pathlib import Path

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.files.base import ContentFile
from django.db import transaction
from django.db.models import Q
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_GET, require_http_methods, require_POST
from django.views.decorators.csrf import ensure_csrf_cookie

from . import models as m
from .rebuild_views import _appointment_apply_field_services, _appointment_service_snapshot, _employee, _is_field_user, _org, _unique_number
from .services.effective_pricing import effective_price_for_catalog_item
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
    qs = m.CalendarEvent.objects.filter(organization=org).select_related("project", "project__customer", "project__object_location", "customer").prefetch_related("attendees")
    if _is_field_user(request):
        employee = _employee(request, org)
        if employee is None:
            return org, get_object_or_404(qs.none(), pk=pk)
        qs = qs.filter(Q(attendees=employee) | Q(project__manager=employee) | Q(project__members=employee)).distinct()
    return org, get_object_or_404(qs, pk=pk)


def _employee_identity_matches(user, employee):
    if getattr(employee, "user_id", None) == getattr(user, "id", None):
        return True
    user_email = (getattr(user, "email", "") or "").strip().lower()
    employee_email = (getattr(employee, "email", "") or "").strip().lower()
    if user_email and employee_email and user_email == employee_email:
        return True
    user_name = " ".join(part for part in [getattr(user, "first_name", ""), getattr(user, "last_name", "")] if part).strip().casefold()
    employee_name = " ".join(part for part in [getattr(employee, "first_name", ""), getattr(employee, "last_name", "")] if part).strip().casefold()
    return bool(user_name and employee_name and user_name == employee_name)


def _next_user_employee_number(org, user):
    base = f"USR-{getattr(user, 'pk', 0):05d}"
    number = base
    suffix = 1
    while m.Employee.objects.filter(organization=org, employee_number=number).exists():
        suffix += 1
        number = f"{base}-{suffix}"
    return number


def _resolve_time_employee(request, org, event=None):
    """Resolve the authenticated person to an Employee without guessing another person's time.

    Existing explicit user/email links win. For a project appointment we may also
    accept an attendee/manager/member whose identity exactly matches the current
    user's name or email. Office/admin users are finally auto-provisioned as their
    own Employee record so owners can track their own work even when the account
    was created before Employee profiles existed.
    """
    employee = _employee(request, org)
    if employee is not None:
        return employee

    employee = m.Employee.objects.filter(organization=org, user=request.user, active=True).first()
    if employee is not None:
        return employee

    email = (getattr(request.user, "email", "") or "").strip()
    if email:
        employee = m.Employee.objects.filter(organization=org, email__iexact=email, active=True).first()
        if employee is not None:
            if getattr(employee, "user_id", None) is None:
                employee.user = request.user
                employee.save(update_fields=["user", "updated_at"])
            return employee

    if event is not None and event.project_id:
        candidates = list(event.attendees.filter(active=True))
        if event.project.manager_id:
            candidates.append(event.project.manager)
        candidates.extend(list(event.project.members.filter(active=True)))
        seen = set()
        for candidate in candidates:
            if candidate is None or candidate.pk in seen:
                continue
            seen.add(candidate.pk)
            if _employee_identity_matches(request.user, candidate):
                if getattr(candidate, "user_id", None) is None:
                    candidate.user = request.user
                    candidate.save(update_fields=["user", "updated_at"])
                return candidate

    if _is_field_user(request):
        return None

    # Owners/office/admin users may legitimately work on-site themselves. Give
    # them their own auditable employee identity rather than attributing time to
    # some arbitrary project member.
    defaults = {
        "employee_number": _next_user_employee_number(org, request.user),
        "first_name": (getattr(request.user, "first_name", "") or getattr(request.user, "username", "") or "Benutzer")[:120],
        "last_name": (getattr(request.user, "last_name", "") or "")[:120],
        "email": email[:200],
        "active": True,
    }
    employee, _created = m.Employee.objects.get_or_create(
        organization=org,
        user=request.user,
        defaults=defaults,
    )
    return employee


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
@require_POST
def attach_project(request, pk):
    org, event = _event_for(request, pk)
    if event.project_id is not None:
        messages.info(request, "Dieser Termin ist bereits einem Projekt zugeordnet.")
        return redirect("next-appointment-detail", pk=event.pk)
    project = get_object_or_404(
        m.Project.objects.select_related("customer", "object_location"),
        organization=org,
        archived=False,
        pk=request.POST.get("project_id"),
    )
    event.project = project
    if not event.location and project.object_location:
        location = project.object_location
        event.location = ", ".join(
            part for part in [location.street, f"{location.postal_code} {location.city}".strip()] if part
        )
    event.save()
    messages.success(request, f"Termin wurde mit Projekt {project.number} · {project.title} verbunden.")
    return redirect("next-appointment-detail", pk=event.pk)


@login_required
@ensure_csrf_cookie
def field_job_detail(request, pk):
    org, event = _event_for(request, pk)
    # A_BAU_PROJECT_APPROVAL_HANDOFF
    from .project_intake_views import redirect_field_project_flow
    approval_response = redirect_field_project_flow(request, event)
    if approval_response is not None:
        return approval_response
    if event.project_id is None:
        available_projects = (
            m.Project.objects.filter(organization=org, archived=False)
            .select_related("customer", "object_location")
            .exclude(status="cancelled")
            .order_by("-updated_at", "-pk")[:150]
        )
        return render(request, "rebuild/appointment_detail.html", {
            "event": event,
            "project_missing": True,
            "available_projects": available_projects,
        })
    authorization = latest_authorization(org, event)
    completion = latest_completion(org, event)
    employee = _resolve_time_employee(request, org, event)
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
        "documented": completion is not None or m.Document.objects.filter(organization=org, metadata__event_id=event.pk, category="report").exists(),
        "service_groups": event.service_groups.prefetch_related("items__catalog_item").all().order_by("position", "id"),
        "appointment_catalog": m.CatalogItem.objects.filter(organization=org, active=True).order_by("name")[:500],
    })


@login_required
@require_POST
def gated_time_toggle(request, event_pk):
    org, event = _event_for(request, event_pk)
    employee = _resolve_time_employee(request, org, event)
    if employee is None or event.project_id is None:
        return JsonResponse({"ok": False, "error": "Für dieses Benutzerkonto konnte kein Mitarbeiterprofil ermittelt werden. Bitte Teamzuordnung prüfen."}, status=400)
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
@require_GET
def authorization_catalog_search(request, pk):
    org, _event = _event_for(request, pk)
    query = (request.GET.get("q") or "").strip()
    if len(query) < 2:
        return JsonResponse({"ok": True, "results": []})
    condition = Q(code__icontains=query) | Q(name__icontains=query) | Q(description__icontains=query)
    candidates = list(m.CatalogItem.objects.filter(organization=org, active=True).filter(condition).order_by("name")[:30])
    rows = []
    for item in candidates:
        price = effective_price_for_catalog_item(org, item)
        if price <= Decimal("0"):
            continue
        rows.append({
            "id": item.pk,
            "code": item.code,
            "name": item.name,
            "unit": item.unit or "Stk.",
            "price": str(price),
            "tax_rate": str(item.tax_rate or Decimal("19.00")),
        })
    return JsonResponse({"ok": True, "results": rows[:20]})



def _reprice_catalog_items(org, items):
    """Never trust a browser-posted price for a catalog-backed authorization row."""
    for item in items:
        catalog_id = item.get("catalog_id")
        if not catalog_id:
            item["price_source"] = "manual"
            continue
        catalog = m.CatalogItem.objects.filter(organization=org, active=True, pk=catalog_id).first()
        if catalog is None:
            raise ValueError("Eine ausgewählte Katalogposition ist nicht mehr verfügbar.")
        price = effective_price_for_catalog_item(org, catalog)
        if price <= Decimal("0"):
            raise ValueError(f"Für {catalog.name} ist aktuell kein freigegebener Preis hinterlegt.")
        qty = money(item.get("quantity") or "1")
        tax = money(catalog.tax_rate or item.get("tax_rate") or "19")
        net = (qty * price).quantize(Decimal("0.01"))
        tax_amount = (net * tax / Decimal("100")).quantize(Decimal("0.01"))
        item.update({
            "description": catalog.name,
            "unit": catalog.unit or item.get("unit") or "Stk.",
            "unit_price": str(price),
            "tax_rate": str(tax),
            "net": str(net),
            "tax": str(tax_amount),
            "gross": str(net + tax_amount),
            "catalog_code": catalog.code,
            "price_source": "catalog",
        })
    return items


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
    try:
        items = _reprice_catalog_items(org, items)
    except ValueError as exc:
        return JsonResponse({"ok": False, "error": str(exc)}, status=400)
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


class _AppointmentScopeSession:
    def __init__(self, session, event_id: int):
        from .ai_scope_planner import STATE_KEY
        self.session = session
        self.state_key = f"{STATE_KEY}:appointment:{event_id}"
    def get(self, key, default=None):
        from .ai_scope_planner import STATE_KEY
        return self.session.get(self.state_key if key == STATE_KEY else key, default)
    def __setitem__(self, key, value):
        from .ai_scope_planner import STATE_KEY
        self.session[self.state_key if key == STATE_KEY else key] = value
    def pop(self, key, default=None):
        from .ai_scope_planner import STATE_KEY
        return self.session.pop(self.state_key if key == STATE_KEY else key, default)
    @property
    def modified(self): return bool(getattr(self.session, "modified", False))
    @modified.setter
    def modified(self, value):
        try: self.session.modified = bool(value)
        except Exception: pass


def _scope_catalog_candidate(org, scope_item):
    from .ai_scope_planner import _catalog_score, catalog_semantic_match
    terms = list(scope_item.get("catalog_terms") or []) + [scope_item.get("label") or ""]
    tokens, seen = [], set()
    for term in terms:
        for token in re.findall(r"[A-Za-zÄÖÜäöüß]{4,}", str(term or "")):
            folded = token.casefold()
            if folded not in seen: seen.add(folded); tokens.append(token)
    condition = Q()
    for token in tokens[:10]:
        condition |= Q(code__icontains=token) | Q(name__icontains=token) | Q(description__icontains=token)
    if not condition: return None
    candidates = list(m.CatalogItem.objects.filter(organization=org, active=True).filter(condition).order_by("name")[:120])
    ranked = []
    for candidate in candidates:
        payload = {"code": candidate.code, "name": candidate.name, "description": candidate.description, "unit": candidate.unit}
        if catalog_semantic_match(scope_item, payload): ranked.append((_catalog_score(payload, scope_item), candidate))
    ranked.sort(key=lambda pair: pair[0], reverse=True)
    return ranked[0][1] if ranked and ranked[0][0] >= 180 else None


def _scope_authorization_items(org, scope_items):
    rows, price_fn = [], globals().get("effective_price_for_catalog_item")
    for scope_item in scope_items or []:
        if not isinstance(scope_item, dict): continue
        catalog = _scope_catalog_candidate(org, scope_item)
        price = Decimal("0.00")
        if catalog is not None:
            try:
                raw_price = price_fn(org, catalog) if callable(price_fn) else getattr(catalog, "sales_price", None)
                price = Decimal(str(raw_price or "0"))
            except Exception: price = Decimal("0.00")
        quantity = scope_item.get("quantity")
        rows.append({
            "description": scope_item.get("label") or "",
            "quantity": "" if quantity is None else str(quantity),
            "unit": scope_item.get("unit") or (catalog.unit if catalog else "Stk."),
            "unit_price": str(price if price > Decimal("0") else Decimal("0.00")),
            "tax_rate": str((catalog.tax_rate if catalog else Decimal("19.00")) or Decimal("19.00")),
            "catalog_id": catalog.pk if catalog is not None and price > Decimal("0") else None,
            "catalog_name": catalog.name if catalog is not None and price > Decimal("0") else None,
            "scope_key": scope_item.get("key") or "",
            "catalog_safe": bool(catalog is not None and price > Decimal("0")),
        })
    return rows


def _scope_text(scope_items):
    lines = []
    for item in scope_items or []:
        if isinstance(item, dict): lines.append(f"{item.get('label') or 'Leistung'} – {item.get('quantity_display') or 'offen'} {item.get('unit') or ''}".strip())
    return "\n".join(lines)




@login_required
@require_POST
def authorization_ai(request, pk):
    org, event = _event_for(request, pk)
    from .store_views import has_ai_consent
    if not has_ai_consent(request.user):
        return JsonResponse({"ok": False, "error": "Vor der KI-Verarbeitung ist deine ausdrückliche Einwilligung in den Einstellungen erforderlich.", "consent_required": True, "settings_url": "/settings/next/"}, status=428)
    raw = (request.POST.get("text") or "").strip()
    if not raw:
        return JsonResponse({"ok": False, "error": "Kein Diktat vorhanden."}, status=400)
    from .ai_scope_planner import plan_scope_message
    scoped_session = _AppointmentScopeSession(request.session, event.pk)
    scope_plan = plan_scope_message(raw, scoped_session, [])
    if scope_plan is not None:
        scope_items = scope_plan.get("scope_items") or []
        return JsonResponse({
            "ok": True, "mode": "scope", "issue": raw, "scope": _scope_text(scope_items),
            "items": _scope_authorization_items(org, scope_items), "ai": True,
            "reply": scope_plan.get("reply") or "", "scope_question": scope_plan.get("scope_question") or "",
            "scope_complete": bool(scope_plan.get("scope_complete")), "scope_kind": scope_plan.get("scope_kind") or "",
            "scope_items": scope_items,
        })
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
                "unit_price": str(effective_price_for_catalog_item(org, catalog) if catalog else Decimal("0.00")),
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
    # Store structured appointment positions. Prices remain server-side.
    _appointment_apply_field_services(event, request)
    report = (request.POST.get("report_text") or "").strip()
    services = (request.POST.get("services") or "").strip()
    material = (request.POST.get("material") or "").strip()
    # KAYI_FINAL_CUSTOMER_HANDOFF
    voice_transcript = (request.POST.get("voice_transcript") or "").strip()
    customer_reviewed = request.POST.get("customer_reviewed") == "1"
    if not customer_reviewed:
        return JsonResponse({"ok": False, "error": "Bitte Bericht, Leistungen und Material gemeinsam mit dem Kunden prüfen."}, status=400)
    if not report and not services:
        return JsonResponse({"ok": False, "error": "Bitte Arbeitsbericht oder ausgeführte Leistungen dokumentieren."}, status=400)
    try:
        after_photos = uploaded_images(request.FILES.getlist("after_photos"))
    except ValueError as exc:
        return JsonResponse({"ok": False, "error": str(exc)}, status=400)
    completion_signature = decode_signature(request.POST.get("completion_signature_data") or "")
    if not completion_signature:
        return JsonResponse({"ok": False, "error": "Bitte den Kunden den Einsatzabschluss unterschreiben lassen."}, status=400)
    voice_upload = request.FILES.get("voice_note")
    voice_raw = b""
    voice_mime = ""
    voice_name = ""
    if voice_upload is not None:
        if getattr(voice_upload, "size", 0) > 20 * 1024 * 1024:
            return JsonResponse({"ok": False, "error": "Die Sprachaufnahme ist größer als 20 MB."}, status=400)
        voice_mime = (getattr(voice_upload, "content_type", "") or "audio/webm")[:120]
        if not voice_mime.startswith("audio/"):
            return JsonResponse({"ok": False, "error": "Die Sprachaufnahme hat ein ungültiges Dateiformat."}, status=400)
        voice_name = Path(getattr(voice_upload, "name", "einsatz.webm") or "einsatz.webm").name
        voice_raw = voice_upload.read()
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
        "service_items": _appointment_service_snapshot(event),
        "voice_transcript": voice_transcript,
        "customer_reviewed": customer_reviewed,
        "before_photos": [{"name": item["name"], "sha256": item["sha256"]} for item in before_photos],
        "after_photos": [{"name": item["name"], "sha256": item["sha256"]} for item in after_photos],
        "room_revision_before": before_revision.pk if before_revision else None,
        "room_revision_after": after_revision.pk if after_revision else None,
        "completed_at": completed_at,
        "completed_by": completed_by,
    }
    completion_hash = sha256_json(completion_snapshot)
    with transaction.atomic():
        if voice_raw:
            save_binary_document(
                org=org, project=event.project, customer=event.project.customer, user=request.user,
                title=f"Vor-Ort-Sprachnotiz · {event.title}", category="other",
                filename=f"voice-{event.pk}-{timezone.now():%Y%m%d%H%M%S}-{voice_name}", mime=voice_mime, raw=voice_raw,
                metadata={"event_id": event.pk, "kind": "field_voice_note", "phase": "after", "transcript": voice_transcript, "completion_snapshot_sha256": completion_hash},
            )
        for photo in after_photos:
            save_binary_document(
                org=org, project=event.project, customer=event.project.customer, user=request.user,
                title=f"Nachher · {photo['name']}", category="photo", filename=f"after-{event.pk}-{photo['sha256'][:10]}-{photo['name']}", mime=photo["mime"], raw=photo["bytes"],
                metadata={"event_id": event.pk, "kind": "field_completion_photo", "phase": "after", "completion_snapshot_sha256": completion_hash, "file_sha256": photo["sha256"]},
            )
        signature_doc = save_binary_document(
            org=org, project=event.project, customer=event.project.customer, user=request.user,
            title="Kundenunterschrift Einsatzabschluss", category="other", filename=f"completion-signature-{event.pk}-{timezone.now():%Y%m%d%H%M%S}.png", mime="image/png", raw=completion_signature,
            metadata={"event_id": event.pk, "kind": "field_completion_signature", "phase": "after", "completion_snapshot_sha256": completion_hash},
        )
        completion = save_binary_document(
            org=org, project=event.project, customer=event.project.customer, user=request.user,
            title=f"Einsatzabschluss · {event.title} · {timezone.localdate():%d.%m.%Y}", category="report", filename=f"einsatzabschluss-{event.pk}-{timezone.now():%Y%m%d%H%M%S}.pdf", mime="application/pdf", raw=pdf,
            metadata={"event_id": event.pk, "kind": COMPLETION_KIND, "phase": "final", "status": "pending_review", "billing_ready": False, "snapshot": completion_snapshot, "snapshot_sha256": completion_hash, "authorization_document_id": authorization.pk, "signature_document_id": signature_doc.pk},
        )
        # KAYI_MANAGER_REVIEW_PROJECT_STATE
        if event.project.status not in {"invoiced", "completed", "cancelled"}:
            event.project.status = "review"
            event.project.save(update_fields=["status", "updated_at"])
        employee = _employee(request, org)
        if employee:
            running = m.TimeEntry.objects.filter(organization=org, employee=employee, project=event.project, ended_at__isnull=True).order_by("-started_at").first()
            if running:
                running.ended_at = timezone.now()
                running.save(update_fields=["ended_at", "updated_at"])
    return JsonResponse({"ok": True, "completion_id": completion.pk, "pdf_url": f"/appointments/{event.pk}/completion/pdf/", "redirect": f"/appointments/{event.pk}/"})

# A_BAU_AI_ROLE_SCOPE_HARDENING 2026-08-12
from . import ai_role_permissions as _ai_perm

_ab_role_original_authorization_ai = authorization_ai


@login_required
@require_POST
def authorization_ai(request, pk):
    organization = _org(request)
    if not _ai_perm.can_use_field_ai(request.user):
        return JsonResponse({"ok": False, "error": "A+Bau KI ist für diesen Arbeitsbereich nicht freigeschaltet."}, status=403)
    if not _ai_perm.event_allowed(request.user, organization, pk):
        return JsonResponse({"ok": False, "error": "Einsatz nicht gefunden."}, status=404)

    response = _ab_role_original_authorization_ai(request, pk)
    if response.status_code >= 400 or _ai_perm.can_view_prices(request.user):
        return response
    try:
        data = json.loads(response.content.decode("utf-8"))
    except Exception:
        return response

    # The old field KI enriches suggested catalog positions with sales_price/tax.
    # Remove ALL commercial fields at the server boundary for field roles.
    data = _ai_perm.strip_sensitive_data(request.user, data)
    if isinstance(data, dict):
        data["pricing_locked"] = True
        data["requires_office_pricing"] = True
    return JsonResponse(data, status=response.status_code)
