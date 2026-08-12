from __future__ import annotations

import base64
import hashlib
import io
import json
import os
from datetime import timedelta
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from django.contrib.auth.decorators import login_required
from django.core.files.base import ContentFile
from django.db import transaction
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from . import models as m
from .rebuild_views import _employee, _is_field_user, _org, _unique_number
from .services.ai import SYSTEM_PROMPT, _create_response
from .services.bo_direct_search import bo_source_ids, search_bo_prices
from .services.effective_pricing import effective_price_for_catalog_item
from .store_views import has_ai_consent


MONEY = Decimal("0.01")
ALLOWED_UNITS = {"Stk.", "Psch.", "Std.", "m", "m²", "m³", "lfm", "Tag", "Set"}
OFFICE_ROLES = {"admin", "office", "project_manager", "accounting"}


def _money(value, default="0"):
    try:
        return Decimal(str(value if value not in (None, "") else default).replace(",", "."))
    except (InvalidOperation, TypeError, ValueError):
        return Decimal(default)


def _field_guard(request):
    return _is_field_user(request)


def _office_guard(request):
    profile = getattr(request.user, "profile", None)
    return not _is_field_user(request) and getattr(profile, "role", "office") in OFFICE_ROLES


def _notify_office(org, *, title, message, url):
    profiles = m.UserProfile.objects.filter(organization=org, role__in=OFFICE_ROLES).select_related("user")
    seen = set()
    for profile in profiles:
        user = profile.user
        if not user or user.pk in seen:
            continue
        seen.add(user.pk)
        m.Notification.objects.create(user=user, title=title[:220], message=message, level="info", url=url[:300])


def _notify_user(user, *, title, message, url):
    if user:
        m.Notification.objects.create(user=user, title=title[:220], message=message, level="info", url=url[:300])


def _parse_positions(raw):
    try:
        rows = json.loads(raw or "[]")
    except json.JSONDecodeError:
        rows = []
    result = []
    if not isinstance(rows, list):
        return result
    for row in rows[:60]:
        if not isinstance(row, dict):
            continue
        title = str(row.get("title") or row.get("description") or "").strip()[:260]
        description = str(row.get("description") or title).strip()[:3000]
        if not title:
            continue
        quantity = max(Decimal("0.001"), min(Decimal("999999"), _money(row.get("quantity"), "1")))
        unit = str(row.get("unit") or "Stk.").strip()[:30]
        if unit not in ALLOWED_UNITS:
            unit = "Stk."
        position_type = str(row.get("position_type") or "mixed")
        if position_type not in {"material", "labour", "mixed", "other"}:
            position_type = "mixed"
        catalog_id = row.get("catalog_id")
        try:
            catalog_id = int(catalog_id) if catalog_id else None
        except (TypeError, ValueError):
            catalog_id = None
        result.append({"title": title, "description": description, "quantity": quantity, "unit": unit, "position_type": position_type, "catalog_id": catalog_id})
    return result


def _catalog_hint(org, title):
    words = [part for part in title.replace("/", " ").split() if len(part) >= 3][:5]
    qs = m.CatalogItem.objects.filter(organization=org, active=True)
    best = None
    best_score = 0
    for item in qs.order_by("name")[:800]:
        hay = f"{item.code} {item.name} {item.description}".casefold()
        score = sum(1 for word in words if word.casefold() in hay)
        if score > best_score:
            best, best_score = item, score
    return best if best_score else None


def _save_intake_photos(org, project, customer, request, event):
    documents = []
    for upload in request.FILES.getlist("photos")[:12]:
        if getattr(upload, "size", 0) > 15 * 1024 * 1024:
            continue
        raw = upload.read()
        if not raw:
            continue
        doc = m.Document(
            organization=org,
            customer=customer,
            project=project,
            title=f"Vor-Ort-Foto · {getattr(upload, 'name', 'Foto')}",
            category="photo",
            mime_type=getattr(upload, "content_type", "") or "image/jpeg",
            size=len(raw),
            sha256=hashlib.sha256(raw).hexdigest(),
            metadata={"kind": "project_intake_photo", "phase": "before", "event_id": event.pk, "source": "technician_project_intake"},
            uploaded_by=request.user,
        )
        doc.file.save(getattr(upload, "name", "vor-ort.jpg") or "vor-ort.jpg", ContentFile(raw), save=False)
        doc.save()
        documents.append(doc)
    return documents


def _structured_schema():
    return {
        "type": "object",
        "properties": {
            "title": {"type": "string"},
            "summary": {"type": "string"},
            "positions": {
                "type": "array",
                "maxItems": 40,
                "items": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string"},
                        "description": {"type": "string"},
                        "quantity": {"type": "number", "minimum": 0.001},
                        "unit": {"type": "string"},
                        "position_type": {"type": "string", "enum": ["material", "labour", "mixed", "other"]},
                    },
                    "required": ["title", "description", "quantity", "unit", "position_type"],
                    "additionalProperties": False,
                },
            },
        },
        "required": ["title", "summary", "positions"],
        "additionalProperties": False,
    }


def _structure_intake(org, text):
    prompt = (
        "Du strukturierst eine technische Vor-Ort-Aufnahme für A+Bau. Der Mitarbeiter beschreibt nur, was beim Kunden gemacht werden soll. "
        "Erzeuge einen kurzen Projekttitel, eine sachliche Zusammenfassung und konkrete Leistungs-/Materialpositionen. "
        "WICHTIG: Niemals Preise, Einkaufspreise, Verkaufspreise, Margen, Rabatte oder Geldbeträge erzeugen oder erwähnen. "
        "Positionstitel müssen fachlich eindeutig genug sein, damit das Büro sie später gegen echte Preislisten/B&O zuordnen kann. "
        "Mengen nur übernehmen, wenn sie genannt oder technisch eindeutig als 1 Position gemeint sind; sonst 1 verwenden. Antworte auf Deutsch.\n\n"
        f"Vor-Ort-Notiz:\n{text}"
    )
    response = _create_response(
        org,
        input=[{"role": "developer", "content": SYSTEM_PROMPT}, {"role": "user", "content": [{"type": "input_text", "text": prompt}]}],
        text={"format": {"type": "json_schema", "name": "ab_bau_project_intake", "schema": _structured_schema(), "strict": True}},
        store=False,
    )
    return json.loads(response.output_text)


@login_required
@require_POST
def intake_ai(request):
    if not _field_guard(request):
        return JsonResponse({"ok": False, "error": "Diese Aufnahme ist für Mitarbeiter vor Ort."}, status=403)
    if not has_ai_consent(request.user):
        return JsonResponse({"ok": False, "error": "KI-Einwilligung erforderlich.", "consent_required": True, "settings_url": "/settings/next/"}, status=428)
    try:
        payload = json.loads(request.body.decode("utf-8"))
    except Exception:
        return JsonResponse({"ok": False, "error": "Ungültige Anfrage."}, status=400)
    text = str(payload.get("text") or "").strip()
    if not text:
        return JsonResponse({"ok": False, "error": "Bitte die Arbeiten kurz beschreiben."}, status=400)
    try:
        data = _structure_intake(_org(request), text[:6000])
    except Exception:
        return JsonResponse({"ok": False, "error": "KI-Auswertung momentan nicht möglich."}, status=502)
    return JsonResponse({"ok": True, **data})


@login_required
@require_POST
def intake_voice(request):
    if not _field_guard(request):
        return JsonResponse({"ok": False, "error": "Diese Aufnahme ist für Mitarbeiter vor Ort."}, status=403)
    if not has_ai_consent(request.user):
        return JsonResponse({"ok": False, "error": "KI-Einwilligung erforderlich.", "consent_required": True, "settings_url": "/settings/next/"}, status=428)
    upload = request.FILES.get("voice")
    if upload is None or getattr(upload, "size", 0) > 20 * 1024 * 1024:
        return JsonResponse({"ok": False, "error": "Keine gültige Sprachaufnahme empfangen."}, status=400)
    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not api_key:
        return JsonResponse({"ok": False, "error": "Sprach-KI ist nicht konfiguriert."}, status=503)
    try:
        from openai import OpenAI
        audio = io.BytesIO(upload.read())
        audio.name = getattr(upload, "name", "aufnahme.webm") or "aufnahme.webm"
        transcript = str(OpenAI(api_key=api_key).audio.transcriptions.create(model=os.environ.get("OPENAI_TRANSCRIBE_MODEL", "gpt-4o-mini-transcribe"), file=audio, language="de").text or "").strip()
        data = _structure_intake(_org(request), transcript)
    except Exception:
        return JsonResponse({"ok": False, "error": "Sprachaufnahme konnte nicht ausgewertet werden."}, status=502)
    return JsonResponse({"ok": True, "transcript": transcript, **data})


@login_required
@require_http_methods(["GET", "POST"])
def technician_quick_job(request):
    if not _field_guard(request):
        return redirect("next-project-create")
    org = _org(request)
    employee = _employee(request, org)
    customers = m.Customer.objects.filter(organization=org, active=True).order_by("company", "last_name", "first_name")[:300]
    if request.method == "GET":
        return render(request, "rebuild/field_quick_job.html", {"customers": customers, "employee": employee})

    positions = _parse_positions(request.POST.get("positions_json"))
    if not positions:
        return render(request, "rebuild/field_quick_job.html", {"customers": customers, "employee": employee, "error": "Bitte mindestens eine Arbeitsposition erfassen."}, status=400)
    mode = request.POST.get("customer_mode") or "existing"
    title = (request.POST.get("title") or "Vor-Ort-Aufnahme").strip()[:220]
    intake_text = (request.POST.get("issue") or "").strip()[:12000]
    transcript = (request.POST.get("voice_transcript") or "").strip()[:12000]
    street = (request.POST.get("street") or "").strip()[:180]
    postal_code = (request.POST.get("postal_code") or "").strip()[:20]
    city = (request.POST.get("city") or "").strip()[:120]

    with transaction.atomic():
        if mode == "existing":
            customer = get_object_or_404(m.Customer, organization=org, active=True, pk=request.POST.get("customer_id"))
        else:
            company = (request.POST.get("company") or "").strip()[:180]
            first_name = (request.POST.get("first_name") or "").strip()[:100]
            last_name = (request.POST.get("last_name") or "").strip()[:100]
            if not company and not (first_name or last_name):
                return render(request, "rebuild/field_quick_job.html", {"customers": customers, "employee": employee, "error": "Bitte Kundenname oder Firma angeben."}, status=400)
            customer = m.Customer.objects.create(
                organization=org, number=_unique_number(m.Customer, org, "K"), type="business" if company else "private",
                company=company, first_name=first_name, last_name=last_name,
                mobile=(request.POST.get("mobile") or "").strip()[:60], email=(request.POST.get("email") or "").strip()[:254],
                street=street, postal_code=postal_code, city=city, country="DE",
            )
        location = None
        if street or postal_code or city:
            location = m.ObjectLocation.objects.create(organization=org, customer=customer, name="Einsatzort", street=street or customer.street or "-", postal_code=postal_code or customer.postal_code, city=city or customer.city)
        project = m.Project.objects.create(
            organization=org, number=_unique_number(m.Project, org, "P"), title=title, description=intake_text,
            customer=customer, object_location=location, manager=employee, status="review", priority="normal",
        )
        if employee:
            project.members.add(employee)
        quote = m.Quote.objects.create(
            organization=org, project=project, number=_unique_number(m.Quote, org, "A"), status="review",
            issue_date=timezone.localdate(), valid_until=timezone.localdate() + timedelta(days=30), created_by=request.user,
            intro_text="Vor-Ort-Aufnahme durch Mitarbeiter – Preise werden ausschließlich durch das Büro freigegeben.",
        )
        settings = m.CommercialDocumentSettings.objects.create(organization=org, quote=quote, tax_code="19", tax_rate=Decimal("19"), payment_due_days=14)
        for index, row in enumerate(positions, 1):
            catalog = None
            if row["catalog_id"]:
                catalog = m.CatalogItem.objects.filter(pk=row["catalog_id"], organization=org, active=True).first()
            if catalog is None:
                catalog = _catalog_hint(org, row["title"])
            item = m.QuoteItem.objects.create(
                quote=quote, position=index, code=catalog.code if catalog else "", description=row["title"] + (f"\n{row['description']}" if row["description"] and row["description"] != row["title"] else ""),
                quantity=row["quantity"], unit=row["unit"], unit_price=Decimal("0"), tax_rate=Decimal("19"), ai_generated=True, approved=False, catalog_item=catalog,
            )
            m.CommercialItemMeta.objects.create(organization=org, quote_item=item, position_type=row["position_type"], purchase_price=Decimal("0"), markup_percent=Decimal("0"), service_model="normal", detail_text=row["description"])
        now = timezone.now().replace(second=0, microsecond=0)
        address = ", ".join(part for part in [street or customer.street, f"{postal_code or customer.postal_code} {city or customer.city}".strip()] if part)
        event = m.CalendarEvent.objects.create(organization=org, project=project, title=title, type="site", starts_at=now, ends_at=now + timedelta(hours=2), location=address, notes=intake_text, created_by=request.user)
        if employee:
            event.attendees.add(employee)
        flow = m.ProjectApprovalFlow.objects.create(
            organization=org, project=project, quote=quote, requested_by=request.user, mode="technician", status="submitted",
            intake_text=intake_text, voice_transcript=transcript, submitted_at=timezone.now(),
        )
        _save_intake_photos(org, project, customer, request, event)
        m.ActivityLog.objects.create(organization=org, user=request.user, verb="project_intake_submitted", entity_type="Project", entity_id=str(project.pk), description="Vor-Ort-Aufnahme ohne Preise zur Bürofreigabe eingereicht.", metadata={"flow_id": flow.pk, "quote_id": quote.pk, "positions": len(positions)})
        _notify_office(org, title="Neue Projektfreigabe", message=f"{request.user.get_full_name() or request.user.username} hat {project.number} · {project.title} ohne Preise zur Freigabe eingereicht.", url=f"/projektfreigaben/{project.pk}/")
    return redirect("field-project-approval", pk=project.pk)


def _flow_for_project(request, pk):
    org = _org(request)
    return get_object_or_404(m.ProjectApprovalFlow.objects.select_related("project", "project__customer", "quote", "requested_by"), organization=org, project_id=pk)


def _line_title(item):
    return (item.description or "").splitlines()[0].strip()


def _candidate_payload(org, item):
    title = _line_title(item)
    rows = search_bo_prices(org, title, limit=6)
    result = []
    for row in rows:
        price = row.sales_price if row.sales_price and row.sales_price > 0 else row.purchase_price
        result.append({"id": row.pk, "code": row.code, "description": row.description, "unit": row.unit, "price": price, "source": row.source.name})
    return result


@login_required
@require_GET
def approval_queue(request):
    if not _office_guard(request):
        return HttpResponseForbidden("Keine Berechtigung für Projektfreigaben.")
    org = _org(request)
    flows = m.ProjectApprovalFlow.objects.filter(organization=org, mode="technician").select_related("project", "project__customer", "requested_by").order_by("status", "-submitted_at")[:200]
    return render(request, "rebuild/project_approval_queue.html", {"flows": flows})


@login_required
@require_http_methods(["GET", "POST"])
def approval_review(request, pk):
    if not _office_guard(request):
        return HttpResponseForbidden("Keine Berechtigung für Projektfreigaben.")
    org = _org(request)
    flow = _flow_for_project(request, pk)
    quote = flow.quote
    if quote is None:
        return HttpResponseForbidden("Kein Freigabeangebot vorhanden.")
    items = list(quote.items.select_related("catalog_item").order_by("position"))

    if request.method == "POST":
        if flow.status not in {"submitted", "changes_requested"}:
            return JsonResponse({"ok": False, "error": "Diese Projektfreigabe wurde bereits verarbeitet."}, status=409)
        tax_code = (request.POST.get("tax_code") or "19")[:20]
        tax_rate = {"19": Decimal("19"), "7": Decimal("7"), "0_19": Decimal("0"), "0_13b": Decimal("0"), "0_4": Decimal("0"), "0": Decimal("0")}.get(tax_code, Decimal("19"))
        unresolved = []
        with transaction.atomic():
            settings, _ = m.CommercialDocumentSettings.objects.get_or_create(organization=org, quote=quote)
            settings.tax_code = tax_code
            settings.tax_rate = tax_rate
            settings.discount_type = "fixed" if request.POST.get("discount_type") == "fixed" else "percent"
            settings.discount_value = max(Decimal("0"), _money(request.POST.get("discount_value")))
            settings.payment_due_days = max(0, min(365, int(_money(request.POST.get("payment_due_days"), "14"))))
            settings.early_payment_discount_percent = max(Decimal("0"), min(Decimal("100"), _money(request.POST.get("skonto_percent"))))
            settings.early_payment_discount_days = max(0, min(365, int(_money(request.POST.get("skonto_days")))))
            settings.closing_text = (request.POST.get("closing_text") or "").strip()[:12000]
            settings.save()
            allowed_bo = set(bo_source_ids(org))
            for item in items:
                meta, _ = m.CommercialItemMeta.objects.get_or_create(organization=org, quote_item=item)
                markup = max(Decimal("0"), min(Decimal("10000"), _money(request.POST.get(f"markup_{item.pk}"))))
                position_type = request.POST.get(f"position_type_{item.pk}") or meta.position_type or "mixed"
                if position_type not in {"material", "labour", "mixed", "other"}:
                    position_type = "mixed"
                service_model = request.POST.get(f"service_model_{item.pk}") or "normal"
                if service_model not in {"normal", "alternative", "contingent"}:
                    service_model = "normal"
                purchase = Decimal("0")
                source_id = request.POST.get(f"price_source_{item.pk}")
                if source_id:
                    try:
                        row = m.PriceItem.objects.select_related("source").get(pk=int(source_id), organization=org, source_id__in=allowed_bo, source__active=True)
                        purchase = row.sales_price if row.sales_price and row.sales_price > 0 else (row.purchase_price or Decimal("0"))
                        item.code = row.code or item.code
                        if row.unit:
                            item.unit = row.unit
                    except (m.PriceItem.DoesNotExist, TypeError, ValueError):
                        purchase = Decimal("0")
                if purchase <= 0 and item.catalog_item_id:
                    purchase = effective_price_for_catalog_item(org, item.catalog_item)
                if purchase <= 0:
                    auto = search_bo_prices(org, _line_title(item), limit=1)
                    if auto:
                        row = auto[0]
                        purchase = row.sales_price if row.sales_price and row.sales_price > 0 else (row.purchase_price or Decimal("0"))
                        item.code = row.code or item.code
                        if row.unit:
                            item.unit = row.unit
                if purchase <= 0:
                    manual = _money(request.POST.get(f"manual_ek_{item.pk}"))
                    if manual > 0:
                        purchase = manual
                if purchase <= 0:
                    unresolved.append(_line_title(item))
                    continue
                sale = (purchase * (Decimal("1") + markup / Decimal("100"))).quantize(MONEY, rounding=ROUND_HALF_UP)
                item.unit_price = sale
                item.tax_rate = tax_rate
                item.approved = True
                item.save(update_fields=["code", "unit", "unit_price", "tax_rate", "approved", "updated_at"])
                meta.purchase_price = purchase.quantize(MONEY, rounding=ROUND_HALF_UP)
                meta.markup_percent = markup
                meta.position_type = position_type
                meta.service_model = service_model
                meta.save()
            if unresolved:
                transaction.set_rollback(True)
            else:
                flow.status = "confirmed"
                flow.confirmed_by = request.user
                flow.confirmed_at = timezone.now()
                flow.review_note = (request.POST.get("review_note") or "").strip()[:5000]
                flow.save()
                flow.project.status = "confirmed"
                flow.project.save(update_fields=["status", "updated_at"])
                quote.status = "sent"
                quote.sent_at = timezone.now()
                quote.save(update_fields=["status", "sent_at", "updated_at"])
                m.ActivityLog.objects.create(organization=org, user=request.user, verb="project_commercial_confirmed", entity_type="Project", entity_id=str(flow.project_id), description="Einkaufspreise und Aufschläge geprüft; Projekt für Kundenfreigabe bestätigt.", metadata={"flow_id": flow.pk, "quote_id": quote.pk})
                _notify_user(flow.requested_by, title="Projekt freigegeben", message=f"{flow.project.number} · {flow.project.title} wurde bestätigt. Die finalen Verkaufspreise sind jetzt sichtbar und können dem Kunden zur Unterschrift vorgelegt werden.", url=f"/field/projects/{flow.project_id}/freigabe/")
        if unresolved:
            rows = [{"item": item, "candidates": _candidate_payload(org, item), "meta": getattr(item, "commercial_meta", None)} for item in items]
            return render(request, "rebuild/project_approval_review.html", {"flow": flow, "project": flow.project, "quote": quote, "rows": rows, "settings": getattr(quote, "commercial_settings", None), "error": "Für folgende Positionen fehlt eine Preisgrundlage: " + ", ".join(unresolved)}, status=400)
        return redirect("project-approval-review", pk=flow.project_id)

    rows = [{"item": item, "candidates": _candidate_payload(org, item), "meta": getattr(item, "commercial_meta", None)} for item in items]
    photos = m.Document.objects.filter(organization=org, project=flow.project, metadata__kind="project_intake_photo").order_by("created_at")
    try:
        settings = quote.commercial_settings
    except Exception:
        settings = None
    return render(request, "rebuild/project_approval_review.html", {"flow": flow, "project": flow.project, "quote": quote, "rows": rows, "photos": photos, "settings": settings})


@login_required
@require_http_methods(["GET", "POST"])
def technician_project_approval(request, pk):
    flow = _flow_for_project(request, pk)
    if _field_guard(request):
        employee = _employee(request, flow.organization)
        allowed = flow.requested_by_id == request.user.id
        if employee:
            allowed = allowed or flow.project.manager_id == employee.id or flow.project.members.filter(pk=employee.pk).exists()
        if not allowed:
            return HttpResponseForbidden("Dieses Projekt ist dir nicht zugewiesen.")
    elif not _office_guard(request):
        return HttpResponseForbidden("Keine Berechtigung.")
    quote = flow.quote
    items = list(quote.items.select_related("commercial_meta").order_by("position")) if quote else []
    photos = m.Document.objects.filter(organization=flow.organization, project=flow.project, metadata__kind="project_intake_photo").order_by("created_at")
    total_net = sum((item.quantity * item.unit_price for item in items if getattr(getattr(item, "commercial_meta", None), "service_model", "normal") == "normal"), Decimal("0"))
    tax_rate = Decimal("19")
    discount = Decimal("0")
    try:
        settings = quote.commercial_settings
        tax_rate = settings.tax_rate
        if settings.discount_type == "fixed":
            discount = min(total_net, settings.discount_value)
        else:
            discount = total_net * settings.discount_value / Decimal("100")
    except Exception:
        settings = None
    net = max(Decimal("0"), total_net - discount)
    gross = net * (Decimal("1") + tax_rate / Decimal("100"))

    if request.method == "POST":
        if flow.status != "confirmed":
            return JsonResponse({"ok": False, "error": "Das Projekt ist noch nicht vom Büro freigegeben."}, status=409)
        signer = (request.POST.get("signer_name") or "").strip()[:220]
        signature = (request.POST.get("signature_data") or "").strip()
        if not signer or not signature.startswith("data:image/png;base64,"):
            return JsonResponse({"ok": False, "error": "Name und Kundenunterschrift sind erforderlich."}, status=400)
        try:
            raw = base64.b64decode(signature.split(",", 1)[1], validate=True)
        except Exception:
            return JsonResponse({"ok": False, "error": "Ungültige Unterschrift."}, status=400)
        with transaction.atomic():
            flow.status = "signed"
            flow.signer_name = signer
            flow.signature_data = signature
            flow.signed_at = timezone.now()
            flow.save()
            flow.project.status = "in_progress"
            flow.project.actual_start = timezone.localdate()
            flow.project.save(update_fields=["status", "actual_start", "updated_at"])
            if quote:
                quote.status = "accepted"
                quote.save(update_fields=["status", "updated_at"])
            doc = m.Document(organization=flow.organization, customer=flow.project.customer, project=flow.project, title=f"Kundenfreigabe · {flow.project.number}", category="contract", mime_type="image/png", size=len(raw), sha256=hashlib.sha256(raw).hexdigest(), metadata={"kind": "project_customer_approval_signature", "flow_id": flow.pk, "signed_by": signer, "signed_at": flow.signed_at.isoformat(), "gross_total": str(gross.quantize(MONEY))}, uploaded_by=request.user)
            doc.file.save(f"kundenfreigabe-{flow.project.number}.png", ContentFile(raw), save=False)
            doc.save()
            m.ActivityLog.objects.create(organization=flow.organization, user=request.user, verb="project_customer_signed", entity_type="Project", entity_id=str(flow.project_id), description="Kunde hat die final freigegebenen Verkaufspreise unterschrieben; Projekt gestartet.", metadata={"flow_id": flow.pk, "signer": signer, "gross": str(gross.quantize(MONEY))})
            _notify_office(flow.organization, title="Projekt vom Kunden unterschrieben", message=f"{flow.project.number} · {flow.project.title} wurde von {signer} unterschrieben und ist jetzt in Ausführung.", url=f"/projects/{flow.project_id}/")
        return redirect("field-project-approval", pk=flow.project_id)

    return render(request, "rebuild/field_project_approval.html", {"flow": flow, "project": flow.project, "quote": quote, "items": items, "photos": photos, "settings": settings, "net": net, "gross": gross, "tax_rate": tax_rate, "discount": discount})


def redirect_field_project_flow(request, event):
    if not event.project_id:
        return None
    try:
        flow = event.project.approval_flow
    except (m.ProjectApprovalFlow.DoesNotExist, AttributeError):
        return None
    if flow.mode != "technician":
        return None
    return redirect("field-project-approval", pk=event.project_id)
