from __future__ import annotations

import base64
import json
import re
import secrets
from datetime import timedelta
from decimal import Decimal
from io import BytesIO

import requests
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core.paginator import Paginator
from django.core.exceptions import PermissionDenied
from django.core.files.base import ContentFile
from django.core.mail import EmailMessage as DjangoEmailMessage
from django.db import transaction
from django.db.models import Q
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.text import slugify
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods, require_POST

from erp.models import (
    ActivityLog,
    AutomationJob,
    BugReport,
    CalendarEvent,
    CatalogItem,
    ChangeOrder,
    ChangeOrderAttachment,
    Customer,
    CustomerSurvey,
    CustomerPortalAccess,
    Document,
    EmailMessage,
    Employee,
    IntegrationConfig,
    Invoice,
    InvoiceItem,
    MeasurementCapture,
    Notification,
    Organization,
    PriceItem,
    PriceSource,
    Project,
    PurchaseDocument,
    PurchaseOrder,
    Quote,
    QuoteItem,
    RoomMeasurement,
    SiteReport,
    Supplier,
    Task,
    UserProfile,
    WorkMedia,
)
from erp.services.ai import suggest_invoice_items
from erp.services.documents import extract_text, validate_upload
from erp.services.numbering import next_number
from erp.services.pricing import (
    commercial_price_sources,
    is_material_only_source,
    is_sellable_item,
    price_source_matches_job_type,
    preferred_price_source,
    quantity_for_price_item,
    resolved_item_price,
)
from erp.services.pdf import build_change_order_pdf, build_site_report_pdf
from erp.services.permissions import can_approve_automation, can_manage_finance, can_write
from erp.workflow_forms import (
    BugReportForm,
    ChangeOrderForm,
    EmployeeAccountForm,
    PurchaseOrderForm,
    SiteReportForm,
    SurveyForm,
    WorkMediaForm,
)


def _org(request):
    profile = getattr(request.user, "profile", None)
    org = getattr(profile, "organization", None)
    if not org:
        org = Organization.objects.first()
    if not org:
        raise PermissionDenied
    return org


def _write(request):
    if not can_write(request.user):
        raise PermissionDenied


def _prices_allowed(request):
    if request.user.is_superuser:
        return True
    profile = getattr(request.user, "profile", None)
    if profile and profile.role in {UserProfile.Role.ADMIN, UserProfile.Role.OFFICE, UserProfile.Role.PROJECT_MANAGER, UserProfile.Role.ACCOUNTING}:
        return True
    employee = getattr(request.user, "employee", None)
    return bool(employee and employee.can_view_prices)




def _extract_bando_order_fields(text: str) -> dict:
    """Extract reviewable B&O order data without silently overwriting a project."""
    clean = re.sub(r"[ \t]+", " ", text or "")

    def first(*patterns):
        for pattern in patterns:
            match = re.search(pattern, clean, re.IGNORECASE | re.MULTILINE)
            if match:
                return re.sub(r"\s+", " ", match.group(1)).strip(" :-\n\r\t")[:500]
        return ""

    return {
        "auftrag": first(r"(?:Auftrag|Auftragsnummer|Auftrag-Nr\.?)[ :#-]*([A-Z0-9/-]{5,})"),
        "datum": first(r"(?:Auftragsdatum|Datum)[ :]*([0-3]?\d[.]?[01]?\d[.]?20\d{2})"),
        "mieter": first(r"(?:Mieter(?:in)?|Bewohner(?:in)?)[ :]*([^\n\r]+)"),
        "adresse": first(r"(?:Objektanschrift|Adresse|Schadenort)[ :]*([^\n\r]+)"),
        "etage": first(r"(?:Etage|Lage)[ :]*([^\n\r]+)"),
        "raum": first(r"(?:Raum|Bereich)[ :]*([^\n\r]+)"),
        "schaden": first(r"(?:Schadenbeschreibung|Leistungsbeschreibung|Störung|Schaden)[ :]*([^\n\r]+)"),
        "telefon": first(r"(?:Telefon|Tel\.?|Mobil)[ :]*([+0-9() /-]{6,})"),
        "schadstoff": bool(re.search(r"schadstoff|asbest|eternit", clean, re.IGNORECASE)),
    }


def _order_document_metadata(document: Document) -> dict:
    metadata = document.metadata if isinstance(document.metadata, dict) else {}
    parsed = metadata.get("bando_order")
    if isinstance(parsed, dict):
        return parsed
    return _extract_bando_order_fields(document.extracted_text or "")

def _project_for_request(request, pk):
    qs = Project.objects.filter(organization=_org(request))
    if role_for_user(request) == UserProfile.Role.TECHNICIAN:
        employee = getattr(request.user, "employee", None)
        qs = qs.filter(Q(members=employee) | Q(manager=employee)).distinct() if employee else qs.none()
    return get_object_or_404(qs, pk=pk)


def role_for_user(request):
    profile = getattr(request.user, "profile", None)
    return getattr(profile, "role", UserProfile.Role.READONLY)


def _unique_username(email: str, first_name: str, last_name: str) -> str:
    base = (email.split("@", 1)[0] if email else slugify(f"{first_name}.{last_name}")) or "mitarbeiter"
    base = re.sub(r"[^a-zA-Z0-9._-]+", "", base)[:120] or "mitarbeiter"
    candidate = base
    suffix = 2
    while User.objects.filter(username=candidate).exists():
        candidate = f"{base[:110]}-{suffix}"
        suffix += 1
    return candidate

def _best_measurement(project):
    return project.room_measurements.filter(status=RoomMeasurement.Status.CONFIRMED).first() or project.room_measurements.first()



@login_required
@require_http_methods(["GET", "POST"])
def employee_account_create(request):
    _write(request)
    if role_for_user(request) == UserProfile.Role.TECHNICIAN:
        raise PermissionDenied
    org = _org(request)
    form = EmployeeAccountForm(request.POST or None, organization=org)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            employee = form.save(commit=False)
            employee.organization = org
            employee.employee_number = next_number(org, "employee")
            if form.cleaned_data.get("create_account"):
                username = form.cleaned_data.get("username") or _unique_username(employee.email, employee.first_name, employee.last_name)
                user = User(
                    username=username,
                    email=employee.email,
                    first_name=employee.first_name,
                    last_name=employee.last_name,
                )
                password = form.cleaned_data.get("password")
                if password:
                    user.set_password(password)
                else:
                    user.set_unusable_password()
                user.save()
                UserProfile.objects.update_or_create(
                    user=user,
                    defaults={
                        "organization": org,
                        "role": form.cleaned_data.get("role") or UserProfile.Role.TECHNICIAN,
                        "phone": employee.phone,
                        "is_mobile_worker": form.cleaned_data.get("role") == UserProfile.Role.TECHNICIAN,
                    },
                )
                employee.user = user
            employee.save()
        messages.success(request, "Mitarbeiter und App-Zugang wurden angelegt." if employee.user_id else "Mitarbeiter wurde angelegt.")
        return redirect("resource-list", resource="employees")
    return render(request, "erp/form.html", {"form": form, "title": "Mitarbeiter anlegen", "instance": None})


@login_required
@require_http_methods(["GET", "POST"])
def task_mobile_update(request, pk):
    employee = getattr(request.user, "employee", None)
    task = get_object_or_404(Task.objects.select_related("project"), organization=_org(request), pk=pk)
    if role_for_user(request) == UserProfile.Role.TECHNICIAN and task.assigned_to_id != getattr(employee, "pk", None):
        raise PermissionDenied
    _write(request)
    if request.method == "POST":
        allowed = {Task.Status.OPEN, Task.Status.IN_PROGRESS, Task.Status.BLOCKED, Task.Status.DONE}
        status = request.POST.get("status")
        if status not in allowed:
            messages.error(request, "Ungültiger Aufgabenstatus.")
        else:
            task.status = status
            task.description = request.POST.get("description", task.description)[:10000]
            task.completed_at = timezone.now() if status == Task.Status.DONE else None
            task.save(update_fields=["status", "description", "completed_at", "updated_at"])
            ActivityLog.objects.create(
                organization=task.organization,
                user=request.user,
                verb="task_mobile_updated",
                entity_type="task",
                entity_id=str(task.pk),
                description=f"Aufgabe {task.title} auf {task.get_status_display()} gesetzt.",
            )
            messages.success(request, "Aufgabe wurde aktualisiert.")
            if task.project_id and role_for_user(request) != UserProfile.Role.TECHNICIAN:
                return redirect("project-detail", pk=task.project_id)
            return redirect("mobile-app")
    return render(request, "erp/task_mobile.html", {"task": task})


@login_required
def project_operations(request, pk):
    org = _org(request)
    project = _project_for_request(request, pk)
    return render(request, "erp/project_operations.html", {
        "project": project,
        "media": project.work_media.select_related("employee", "uploaded_by")[:50],
        "change_orders": project.change_orders.all(),
        "site_reports": project.site_reports.select_related("employee")[:20],
        "purchase_orders": project.purchase_orders.select_related("supplier")[:20],
        "survey": getattr(project, "survey", None),
        "customer_portal": CustomerPortalAccess.objects.filter(project=project).first(),
        "measurement": _best_measurement(project),
        "can_view_prices": _prices_allowed(request),
    })


@login_required
@require_http_methods(["GET", "POST"])
def project_pricing(request, pk):
    if not _prices_allowed(request):
        raise PermissionDenied("Mitarbeiter dürfen keine Preise sehen.")
    _write(request)
    org = _org(request)
    project = get_object_or_404(Project, organization=org, pk=pk)
    measurement = _best_measurement(project)
    sources = commercial_price_sources(org)

    if request.method == "POST":
        action = request.POST.get("action")
        if action == "upload-order-pdf":
            upload = request.FILES.get("order_pdf")
            if not upload:
                messages.error(request, "Bitte eine PDF-Auftragsdatei auswählen.")
                return redirect("project-pricing", pk=project.pk)
            try:
                validate_upload(upload)
                if not upload.name.lower().endswith(".pdf"):
                    raise ValueError("Für den Auftrag wird eine PDF-Datei erwartet.")
            except (ValueError, TypeError) as exc:
                messages.error(request, str(exc))
                return redirect("project-pricing", pk=project.pk)
            document = Document.objects.create(
                organization=org,
                project=project,
                customer=project.customer,
                title=f"B&O Auftrag · {upload.name}",
                category=Document.Category.CONTRACT,
                file=upload,
                uploaded_by=request.user,
                metadata={"source_order": True, "provider": "B&O"},
            )
            try:
                document.extracted_text = extract_text(document.file.path)
            except Exception as exc:
                document.extracted_text = ""
                document.metadata = {**document.metadata, "extraction_warning": str(exc)[:500]}
            parsed = _extract_bando_order_fields(document.extracted_text)
            document.metadata = {**document.metadata, "bando_order": parsed}
            document.save(update_fields=["extracted_text", "metadata", "updated_at"])
            messages.success(request, "Auftrags-PDF wurde gespeichert und zur Prüfung ausgelesen.")
            return redirect("project-pricing", pk=project.pk)

        if action == "apply-order-data":
            document = get_object_or_404(Document, organization=org, project=project, pk=request.POST.get("document_id"))
            parsed = _order_document_metadata(document)
            update_fields = ["updated_at"]
            if parsed.get("auftrag"):
                project.external_reference = parsed["auftrag"][:100]
                update_fields.append("external_reference")
            details = []
            for label, key in (("Mieter", "mieter"), ("Adresse", "adresse"), ("Etage", "etage"), ("Raum", "raum"), ("Schaden", "schaden"), ("Telefon", "telefon")):
                if parsed.get(key):
                    details.append(f"{label}: {parsed[key]}")
            if parsed.get("schadstoff"):
                details.append("⚠ Schadstoff-/Eternit-Hinweis im Auftrag erkannt; vor Ausführung prüfen.")
            if details:
                block = "B&O-Auftrag aus PDF:\n" + "\n".join(details)
                if block not in project.internal_notes:
                    project.internal_notes = (project.internal_notes + "\n\n" + block).strip()
                    update_fields.append("internal_notes")
            project.job_type = Project.JobType.INSURANCE
            update_fields.append("job_type")
            if not project.price_source:
                suggested = preferred_price_source(org, Project.JobType.INSURANCE)
                if suggested:
                    project.price_source = suggested
                    update_fields.append("price_source")
            project.save(update_fields=list(dict.fromkeys(update_fields)))
            messages.success(request, "Geprüfte Auftragsdaten wurden auf das Projekt übernommen.")
            return redirect("project-pricing", pk=project.pk)

        if action == "set-source":
            source = get_object_or_404(sources, pk=request.POST.get("price_source"))
            if is_material_only_source(source):
                messages.error(request, "JOKA und Lieferantenlisten sind nur für Material, nicht für Angebot & Kalkulation.")
                return redirect("project-pricing", pk=project.pk)
            target_job_type = Project.JobType.INSURANCE if source.kind == PriceSource.Kind.INSURANCE else Project.JobType.PRIVATE
            if not price_source_matches_job_type(source, target_job_type):
                messages.error(request, "Diese Preisliste kann nicht als Preisbasis verwendet werden.")
                return redirect("project-pricing", pk=project.pk)
            project.price_source = source
            project.job_type = target_job_type
            project.save(update_fields=["price_source", "job_type", "updated_at"])
            messages.success(request, f"{source.name} wurde als Preisbasis verknüpft.")
            return redirect("project-pricing", pk=project.pk)

        if action in {"add-items", "recalculate"}:
            source = project.price_source
            if not source or not sources.filter(pk=source.pk).exists():
                messages.error(request, "Zuerst eine gültige B&O-, Privat- oder Leistungspreisliste auswählen.")
                return redirect("project-pricing", pk=project.pk)
            quote = project.quotes.filter(status__in=[Quote.Status.DRAFT, Quote.Status.REVIEW]).first()
            if action == "add-items":
                requested_ids = request.POST.getlist("price_items")
                selected = list(PriceItem.objects.filter(
                    organization=org,
                    source=source,
                    active=True,
                    pk__in=requested_ids,
                ))
                sellable = [(item, resolved_item_price(item)) for item in selected]
                sellable = [(item, price) for item, price in sellable if price is not None]
                skipped = max(0, len(requested_ids) - len(sellable))
                if not sellable:
                    messages.error(request, "Keine ausgewählte Position besitzt einen belastbaren Preis. Es wurde kein leeres Angebot erstellt.")
                    return redirect("project-pricing", pk=project.pk)
                if not quote:
                    quote = Quote.objects.create(
                        organization=org,
                        project=project,
                        number=next_number(org, "quote"),
                        status=Quote.Status.REVIEW,
                        intro_text=f"Preisgrundlage: {source.name}. Mengen aus dem bestätigten Aufmaß müssen geprüft werden.",
                        created_by=request.user,
                    )
                position = quote.items.count() + 1
                added = 0
                for item, price in sellable:
                    if quote.items.filter(code=item.code, description=item.description).exists():
                        continue
                    QuoteItem.objects.create(
                        quote=quote,
                        position=position,
                        code=item.code,
                        description=item.description,
                        quantity=quantity_for_price_item(item, measurement),
                        unit=item.unit or "Stk.",
                        unit_price=price,
                        tax_rate=item.tax_rate,
                        ai_generated=False,
                        approved=True,
                    )
                    position += 1
                    added += 1
                if added:
                    messages.success(request, f"{added} Positionen wurden mit echten Preisen und aufmaßabhängigen Mengen übernommen.")
                elif quote:
                    messages.info(request, "Die ausgewählten Positionen waren bereits im Angebot vorhanden.")
                if skipped:
                    messages.warning(request, f"{skipped} Positionen ohne belastbaren Preis wurden nicht übernommen.")
            else:
                if not quote:
                    messages.error(request, "Es gibt noch kein Angebot zum Neuberechnen.")
                    return redirect("project-pricing", pk=project.pk)
                source_by_code = {
                    x.code: x
                    for x in PriceItem.objects.filter(organization=org, source=source, active=True).exclude(code="")
                    if is_sellable_item(x)
                }
                changed = 0
                for qitem in quote.items.all():
                    source_item = source_by_code.get(qitem.code)
                    if source_item:
                        qitem.quantity = quantity_for_price_item(source_item, measurement)
                        qitem.unit_price = resolved_item_price(source_item) or qitem.unit_price
                        qitem.save(update_fields=["quantity", "unit_price", "updated_at"])
                        changed += 1
                messages.success(request, f"{changed} Positionen wurden aus Aufmaß und aktueller Preisliste neu berechnet.")
            return redirect("quote-edit", pk=quote.pk)

    # For an existing insurance project without a source, propose B&O PL1658 but
    # do not silently bind it; the user confirms the dropdown once.
    suggested_source = None
    if not project.price_source:
        suggested_source = preferred_price_source(org, project.job_type)

    q = request.GET.get("q", "").strip()
    items = PriceItem.objects.none()
    open_price_count = 0
    if project.price_source and sources.filter(pk=project.price_source_id).exists():
        base_items = PriceItem.objects.filter(organization=org, source=project.price_source, active=True)
        if q:
            base_items = base_items.filter(reduce_q(q))
        all_items = list(base_items[:500])
        open_price_count = sum(1 for item in all_items if resolved_item_price(item) is None)
        items = [item for item in all_items if resolved_item_price(item) is not None][:160]
        for item in items:
            item.resolved_price = resolved_item_price(item)
    order_documents = []
    for document in project.documents.filter(metadata__source_order=True).order_by("-created_at")[:10]:
        document.parsed_order = _order_document_metadata(document)
        order_documents.append(document)
    current_quote = project.quotes.filter(status__in=[Quote.Status.DRAFT, Quote.Status.REVIEW]).first()
    if project.job_type == Project.JobType.INSURANCE and not order_documents:
        active_step = 1
    elif not project.price_source:
        active_step = 2
    elif not current_quote:
        active_step = 3
    else:
        active_step = 4
    selected_source_id = project.price_source_id or getattr(suggested_source, "pk", None)
    return render(request, "erp/project_pricing.html", {
        "project": project,
        "sources": sources,
        "items": items,
        "measurement": measurement,
        "q": q,
        "suggested_source": suggested_source,
        "open_price_count": open_price_count,
        "order_documents": order_documents,
        "current_quote": current_quote,
        "active_step": active_step,
        "selected_source_id": selected_source_id,
    })


def reduce_q(q):
    from django.db.models import Q
    return Q(code__icontains=q) | Q(description__icontains=q) | Q(category__icontains=q)


@login_required
@require_http_methods(["GET", "POST"])
def work_media_create(request, project_pk):
    _write(request)
    org = _org(request)
    project = _project_for_request(request, project_pk)
    form = WorkMediaForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        media = form.save(commit=False)
        media.organization = org
        media.project = project
        media.uploaded_by = request.user
        media.employee = getattr(request.user, "employee", None)
        media.save()
        messages.success(request, "Foto/Video wurde zum Projekt hochgeladen.")
        return redirect("work-media-edit", pk=media.pk)
    return render(request, "erp/form.html", {"form": form, "title": "Foto, Video oder Audio hinzufügen", "instance": None})


@login_required
@require_http_methods(["GET", "POST"])
def work_media_edit(request, pk):
    _write(request)
    media = get_object_or_404(WorkMedia, organization=_org(request), pk=pk)
    _project_for_request(request, media.project_id)
    if request.method == "POST":
        try:
            annotations = json.loads(request.POST.get("annotations", "[]"))
            if not isinstance(annotations, list):
                raise ValueError
        except ValueError:
            annotations = []
        media.annotations = annotations[:500]
        media.caption = request.POST.get("caption", media.caption)[:5000]
        media.visible_to_customer = request.POST.get("visible_to_customer") == "on"
        media.save(update_fields=["annotations", "caption", "visible_to_customer", "updated_at"])
        messages.success(request, "Bildmarkierungen wurden gespeichert.")
        return redirect("project-operations", pk=media.project_id)
    return render(request, "erp/media_edit.html", {"media": media, "annotations_json": json.dumps(media.annotations)})


@login_required
@require_http_methods(["GET", "POST"])
def capture_annotate(request, pk):
    _write(request)
    capture = get_object_or_404(MeasurementCapture, measurement__organization=_org(request), pk=pk)
    _project_for_request(request, capture.measurement.project_id)
    if request.method == "POST":
        try:
            data = json.loads(request.POST.get("annotations", "[]"))
        except json.JSONDecodeError:
            data = []
        capture.annotations = data if isinstance(data, list) else []
        capture.save(update_fields=["annotations", "updated_at"])
        messages.success(request, "Aufmaßfoto wurde markiert.")
        return redirect("room-measurement-edit", project_pk=capture.measurement.project_id, measurement_pk=capture.measurement_id)
    return render(request, "erp/capture_edit.html", {"capture": capture, "annotations_json": json.dumps(capture.annotations)})


@login_required
@require_http_methods(["GET", "POST"])
def change_order_create(request, project_pk):
    _write(request)
    org = _org(request)
    project = _project_for_request(request, project_pk)
    form = ChangeOrderForm(request.POST or None, can_view_prices=_prices_allowed(request))
    if request.method == "POST" and form.is_valid():
        order = form.save(commit=False)
        order.organization = org
        order.project = project
        order.number = next_number(org, "change_order")
        order.requested_by = request.user
        order.save()
        for upload in request.FILES.getlist("attachments"):
            ChangeOrderAttachment.objects.create(change_order=order, file=upload, title=upload.name, uploaded_by=request.user)
        messages.success(request, "Zusatzarbeit wurde erstellt und kann digital unterschrieben werden.")
        return redirect("change-order-detail", pk=order.pk)
    return render(request, "erp/change_order_form.html", {"form": form, "project": project})


@login_required
def change_order_detail(request, pk):
    order = get_object_or_404(ChangeOrder.objects.select_related("project", "project__customer"), organization=_org(request), pk=pk)
    _project_for_request(request, order.project_id)
    return render(request, "erp/change_order_detail.html", {
        "order": order,
        "can_view_prices": _prices_allowed(request),
        "can_invoice": can_manage_finance(request.user),
    })


@login_required
def change_order_pdf(request, pk):
    order = get_object_or_404(ChangeOrder, organization=_org(request), pk=pk)
    _project_for_request(request, order.project_id)
    if not _prices_allowed(request):
        raise PermissionDenied
    return HttpResponse(build_change_order_pdf(order), content_type="application/pdf", headers={"Content-Disposition": f'inline; filename="{order.number}.pdf"'})


@require_http_methods(["GET", "POST"])
def change_order_sign(request, token):
    order = get_object_or_404(ChangeOrder, public_token=token)
    if request.method == "POST" and order.status != ChangeOrder.Status.ACCEPTED:
        signed_name = request.POST.get("signed_name", "").strip()
        signature = request.POST.get("signature_data", "")
        decision = request.POST.get("decision")
        if decision == "accept" and signed_name and signature.startswith("data:image/"):
            order.status = ChangeOrder.Status.ACCEPTED
            order.signed_name = signed_name[:180]
            order.signature_data = signature[:1_500_000]
            order.signed_at = timezone.now()
            order.customer_comment = request.POST.get("comment", "")[:5000]
            order.save()
        elif decision == "reject":
            order.status = ChangeOrder.Status.REJECTED
            order.customer_comment = request.POST.get("comment", "")[:5000]
            order.save(update_fields=["status", "customer_comment", "updated_at"])
        return redirect("change-order-sign", token=token)
    return render(request, "erp/change_order_sign.html", {"order": order})


@login_required
@require_POST
def change_order_to_invoice(request, pk):
    _write(request)
    if not can_manage_finance(request.user):
        raise PermissionDenied
    org = _org(request)
    order = get_object_or_404(ChangeOrder, organization=org, pk=pk, status=ChangeOrder.Status.ACCEPTED)
    invoice = order.project.invoices.exclude(status=Invoice.Status.CANCELLED).first()
    if not invoice:
        invoice = Invoice.objects.create(
            organization=org,
            project=order.project,
            number=next_number(org, "invoice"),
            due_date=timezone.localdate() + timedelta(days=14),
            created_by=request.user,
        )
    InvoiceItem.objects.create(
        invoice=invoice,
        position=invoice.items.count() + 1,
        code=order.number,
        description=f"Zusatzarbeit: {order.title}\n{order.description}",
        quantity=1,
        unit="Psch.",
        unit_price=order.amount_net,
        tax_rate=order.tax_rate,
    )
    order.status = ChangeOrder.Status.INVOICED
    order.save(update_fields=["status", "updated_at"])
    messages.success(request, "Bestätigte Zusatzarbeit wurde der Rechnung hinzugefügt.")
    return redirect("invoice-edit", pk=invoice.pk)


def _site_report_order_data(project):
    for document in project.documents.order_by("-created_at"):
        metadata = document.metadata or {}
        if metadata.get("source_order") or metadata.get("provider") == "B&O":
            return document, _order_document_metadata(document)
    return None, {}


def _site_report_default_lines(project):
    quote = project.quotes.prefetch_related("items").first()
    service_lines = []
    if quote:
        for item in quote.items.all()[:40]:
            service_lines.append({
                "code": item.code or "",
                "description": item.description or "",
                "quantity": str(item.quantity),
                "unit": item.unit or "",
            })
    material_lines = []
    for item in project.materials.select_related("catalog_item").all()[:40]:
        material_lines.append({
            "material_id": item.pk,
            "code": getattr(item.catalog_item, "code", "") or "",
            "description": item.name or "",
            "quantity": str(item.quantity),
            "unit": item.unit or "",
            "price": str(item.unit_price) if item.unit_price is not None else "",
        })
    return service_lines or [{"code": "", "description": "", "quantity": "", "unit": ""}], material_lines or [{"material_id": "", "code": "", "description": "", "quantity": "", "unit": "", "price": ""}]


def _posted_site_report_lines(request, project):
    def clean_text(value, limit):
        return (value or "").strip()[:limit]

    service_lines = []
    service_codes = request.POST.getlist("service_code[]")
    service_descriptions = request.POST.getlist("service_description[]")
    service_quantities = request.POST.getlist("service_quantity[]")
    service_units = request.POST.getlist("service_unit[]")
    for index in range(min(50, max(map(len, [service_codes, service_descriptions, service_quantities, service_units]), default=0))):
        line = {
            "code": clean_text(service_codes[index] if index < len(service_codes) else "", 80),
            "description": clean_text(service_descriptions[index] if index < len(service_descriptions) else "", 500),
            "quantity": clean_text(service_quantities[index] if index < len(service_quantities) else "", 40),
            "unit": clean_text(service_units[index] if index < len(service_units) else "", 30),
        }
        if any(line.values()):
            service_lines.append(line)

    material_lookup = {str(item.pk): item for item in project.materials.select_related("catalog_item").all()}
    material_lines = []
    ids = request.POST.getlist("material_id[]")
    codes = request.POST.getlist("material_code[]")
    descriptions = request.POST.getlist("material_description[]")
    quantities = request.POST.getlist("material_quantity[]")
    units = request.POST.getlist("material_unit[]")
    for index in range(min(50, max(map(len, [ids, codes, descriptions, quantities, units]), default=0))):
        material_id = clean_text(ids[index] if index < len(ids) else "", 30)
        material = material_lookup.get(material_id)
        line = {
            "material_id": material_id,
            "code": clean_text(codes[index] if index < len(codes) else "", 80),
            "description": clean_text(descriptions[index] if index < len(descriptions) else "", 500),
            "quantity": clean_text(quantities[index] if index < len(quantities) else "", 40),
            "unit": clean_text(units[index] if index < len(units) else "", 30),
            # Prices are resolved server-side and never trusted from a field employee's browser.
            "price": str(material.unit_price) if material is not None and material.unit_price is not None else "",
        }
        if any(line[key] for key in ("code", "description", "quantity", "unit")):
            material_lines.append(line)
    return service_lines, material_lines


@login_required
def site_report_list(request):
    org = _org(request)
    reports = SiteReport.objects.select_related(
        "project", "project__customer", "employee"
    ).filter(organization=org)
    insurance_projects = Project.objects.select_related("customer").filter(
        organization=org,
        job_type=Project.JobType.INSURANCE,
    )

    profile = getattr(request.user, "profile", None)
    if profile and profile.role == UserProfile.Role.TECHNICIAN:
        employee = getattr(request.user, "employee", None)
        if employee is None:
            reports = reports.none()
            insurance_projects = insurance_projects.none()
        else:
            reports = reports.filter(
                Q(project__members=employee) | Q(project__manager=employee)
            ).distinct()
            insurance_projects = insurance_projects.filter(
                Q(members=employee) | Q(manager=employee)
            ).distinct()

    scoped_reports = reports
    summary = {
        "total": scoped_reports.count(),
        "signed": scoped_reports.filter(signed_at__isnull=False).count(),
        "draft": scoped_reports.filter(signed_at__isnull=True).count(),
        "bando": scoped_reports.filter(kind=SiteReport.Kind.BANDO).count(),
    }

    query = request.GET.get("q", "").strip()[:120]
    status_filter = request.GET.get("status", "").strip()
    kind_filter = request.GET.get("kind", "").strip()

    if query:
        reports = reports.filter(
            Q(project__number__icontains=query)
            | Q(project__title__icontains=query)
            | Q(project__customer__number__icontains=query)
            | Q(project__customer__company__icontains=query)
            | Q(signed_name__icontains=query)
            | Q(title__icontains=query)
        )
    if status_filter == "signed":
        reports = reports.filter(signed_at__isnull=False)
    elif status_filter == "draft":
        reports = reports.filter(signed_at__isnull=True)
    else:
        status_filter = ""
    if kind_filter in {SiteReport.Kind.BANDO, SiteReport.Kind.GENERIC}:
        reports = reports.filter(kind=kind_filter)
    else:
        kind_filter = ""

    reports = reports.order_by("-created_at", "-pk")
    page_obj = Paginator(reports, 30).get_page(request.GET.get("page"))

    pending_queryset = insurance_projects.exclude(
        site_reports__kind=SiteReport.Kind.BANDO,
        site_reports__signed_at__isnull=False,
    ).order_by("-created_at", "-pk").distinct()
    pending_count = pending_queryset.count()
    pending_projects = list(pending_queryset[:8])
    for pending_project in pending_projects:
        pending_project.draft_report = pending_project.site_reports.filter(
            kind=SiteReport.Kind.BANDO, signed_at__isnull=True
        ).order_by("-created_at", "-pk").first()

    return render(request, "erp/site_report_list.html", {
        "page_obj": page_obj,
        "reports": page_obj.object_list,
        "summary": summary,
        "query": query,
        "status_filter": status_filter,
        "kind_filter": kind_filter,
        "pending_projects": pending_projects,
        "pending_count": pending_count,
        "can_create_reports": can_write(request.user),
    })


@login_required
@require_http_methods(["GET", "POST"])
def site_report_create(request, project_pk):
    _write(request)
    org = _org(request)
    project = _project_for_request(request, project_pk)
    form = SiteReportForm(request.POST or None, request.FILES or None)
    order_document, order_data = _site_report_order_data(project)
    service_lines, material_lines = _site_report_default_lines(project)
    if request.method == "POST":
        service_lines, material_lines = _posted_site_report_lines(request, project)
    if request.method == "POST" and form.is_valid():
        action = request.POST.get("action", "draft")
        signature_touched = request.POST.get("signature_touched") == "1"
        signature_data = request.POST.get("signature_data", "")
        signed_name = request.POST.get("signed_name", "").strip()[:180]
        valid_signature = signature_touched and signature_data.startswith("data:image/")
        if action == "confirm" and (not signed_name or not valid_signature):
            messages.error(request, "Für die Kundenbestätigung bitte Namen und digitale Unterschrift erfassen.")
        else:
            report = form.save(commit=False)
            report.organization = org
            report.project = project
            report.employee = getattr(request.user, "employee", None)
            report.created_by = request.user
            report.kind = SiteReport.Kind.BANDO if project.job_type == Project.JobType.INSURANCE else SiteReport.Kind.GENERIC
            report.service_lines = service_lines
            report.material_lines = material_lines
            if action == "confirm":
                report.customer_signature = signature_data[:1_500_000]
                report.signed_name = signed_name
                report.signed_at = timezone.now()
            report.save()
            if report.kind == SiteReport.Kind.BANDO:
                messages.success(request, "B&O Leistungsnachweis / Regiebericht wurde gespeichert.")
            else:
                messages.success(request, "Vor-Ort-Bericht mit Text/Sprachnotiz wurde gespeichert.")
            return redirect("project-operations", pk=project.pk)
    return render(request, "erp/site_report_form.html", {
        "form": form, "project": project, "order_document": order_document, "order_data": order_data,
        "service_lines": service_lines, "material_lines": material_lines, "can_view_prices": _prices_allowed(request),
        "is_bando": project.job_type == Project.JobType.INSURANCE,
    })


@login_required
@require_http_methods(["GET", "POST"])
def site_report_edit(request, pk):
    _write(request)
    org = _org(request)
    report = get_object_or_404(SiteReport, organization=org, pk=pk, signed_at__isnull=True)
    project = _project_for_request(request, report.project_id)
    form = SiteReportForm(request.POST or None, request.FILES or None, instance=report)
    order_document, order_data = _site_report_order_data(project)
    service_lines = report.service_lines or _site_report_default_lines(project)[0]
    material_lines = report.material_lines or _site_report_default_lines(project)[1]
    if request.method == "POST":
        service_lines, material_lines = _posted_site_report_lines(request, project)
    if request.method == "POST" and form.is_valid():
        action = request.POST.get("action", "draft")
        signature_touched = request.POST.get("signature_touched") == "1"
        signature_data = request.POST.get("signature_data", "")
        signed_name = request.POST.get("signed_name", "").strip()[:180]
        valid_signature = signature_touched and signature_data.startswith("data:image/")
        if action == "confirm" and (not signed_name or not valid_signature):
            messages.error(request, "Für die Kundenbestätigung bitte Namen und digitale Unterschrift erfassen.")
        else:
            report = form.save(commit=False)
            report.service_lines = service_lines
            report.material_lines = material_lines
            if action == "confirm":
                report.customer_signature = signature_data[:1_500_000]
                report.signed_name = signed_name
                report.signed_at = timezone.now()
            report.save()
            messages.success(request, "Leistungsnachweis wurde aktualisiert." if action == "draft" else "Leistungsnachweis wurde unterschrieben und abgeschlossen.")
            return redirect("site-report-list")
    return render(request, "erp/site_report_form.html", {
        "form": form, "project": project, "report": report, "order_document": order_document, "order_data": order_data,
        "service_lines": service_lines, "material_lines": material_lines, "can_view_prices": _prices_allowed(request),
        "is_bando": report.kind == SiteReport.Kind.BANDO, "is_editing": True,
    })


@login_required
def site_report_pdf(request, pk):
    report = get_object_or_404(SiteReport, organization=_org(request), pk=pk)
    _project_for_request(request, report.project_id)
    return HttpResponse(build_site_report_pdf(report, include_prices=_prices_allowed(request)), content_type="application/pdf", headers={"Content-Disposition": f'inline; filename="site-report-{report.pk}.pdf"'})


@login_required
@require_POST
def survey_create(request, project_pk):
    _write(request)
    project = _project_for_request(request, project_pk)
    survey, _ = CustomerSurvey.objects.get_or_create(organization=project.organization, project=project)
    survey.sent_at = timezone.now()
    survey.save(update_fields=["sent_at", "updated_at"])
    if request.POST.get("send_email") and project.customer.email:
        link = request.build_absolute_uri(f"/survey/{survey.token}/")
        email = EmailMessage.objects.create(
            organization=project.organization,
            project=project,
            customer=project.customer,
            direction=EmailMessage.Direction.DRAFT,
            status=EmailMessage.Status.REVIEW,
            recipients=[project.customer.email],
            subject=f"Ihre Rückmeldung zum Projekt {project.title}",
            body_text=f"Guten Tag {project.customer.display_name},\n\nvielen Dank für Ihr Vertrauen. Bitte bewerten Sie unser Projekt über diesen Link:\n{link}\n\nMit freundlichen Grüßen\n{project.organization.name}",
            classification={"survey_id": survey.pk, "public_url": link},
        )
        messages.success(request, "Umfrage und prüfpflichtiger E-Mail-Entwurf wurden erstellt.")
        return redirect("email-detail", pk=email.pk)
    messages.success(request, "Umfragelink wurde erstellt.")
    return redirect("project-operations", pk=project.pk)


@require_http_methods(["GET", "POST"])
def survey_public(request, token):
    survey = get_object_or_404(CustomerSurvey.objects.select_related("project", "project__customer"), token=token)
    form = SurveyForm(request.POST or None, instance=survey)
    if request.method == "POST" and form.is_valid() and not survey.completed_at:
        survey = form.save(commit=False)
        survey.completed_at = timezone.now()
        survey.save()
        return render(request, "erp/survey_public.html", {"survey": survey, "form": None, "thanks": True})
    return render(request, "erp/survey_public.html", {"survey": survey, "form": form, "thanks": False})


@login_required
@require_POST
def customer_portal_toggle(request, project_pk):
    _write(request)
    if role_for_user(request) == UserProfile.Role.TECHNICIAN:
        raise PermissionDenied
    project = _project_for_request(request, project_pk)
    portal, created = CustomerPortalAccess.objects.get_or_create(organization=project.organization, project=project)
    if not created:
        portal.active = not portal.active
        portal.save(update_fields=["active", "updated_at"])
    messages.success(request, "Kundenportal wurde aktiviert." if portal.active else "Kundenportal wurde deaktiviert.")
    return redirect("project-operations", pk=project.pk)


@login_required
@require_POST
def customer_portal_email(request, project_pk):
    _write(request)
    if role_for_user(request) == UserProfile.Role.TECHNICIAN:
        raise PermissionDenied
    project = _project_for_request(request, project_pk)
    portal, _ = CustomerPortalAccess.objects.get_or_create(organization=project.organization, project=project, defaults={"active": True})
    if not portal.active:
        portal.active = True
        portal.save(update_fields=["active", "updated_at"])
    link = request.build_absolute_uri(f"/customer-portal/{portal.token}/")
    email = EmailMessage.objects.create(
        organization=project.organization,
        project=project,
        customer=project.customer,
        direction=EmailMessage.Direction.DRAFT,
        status=EmailMessage.Status.REVIEW,
        recipients=[project.customer.email] if project.customer.email else [],
        subject=f"Projektportal – {project.title}",
        body_text=f"Guten Tag {project.customer.display_name},\n\nhier finden Sie den freigegebenen Projektstand, Fotos und Bestätigungen:\n{link}\n\nMit freundlichen Grüßen\n{project.organization.name}",
        classification={"customer_portal_id": portal.pk, "public_url": link},
    )
    messages.success(request, "Kundenportal-Link wurde als prüfpflichtiger E-Mail-Entwurf vorbereitet.")
    return redirect("email-detail", pk=email.pk)


@require_http_methods(["GET"])
def customer_portal_public(request, token):
    portal = get_object_or_404(
        CustomerPortalAccess.objects.select_related("project", "project__customer", "organization"),
        token=token,
        active=True,
    )
    portal.last_viewed_at = timezone.now()
    portal.save(update_fields=["last_viewed_at", "updated_at"])
    project = portal.project
    media = project.work_media.filter(visible_to_customer=True).order_by("stage", "created_at")
    change_orders = project.change_orders.exclude(status=ChangeOrder.Status.DRAFT)
    survey = CustomerSurvey.objects.filter(project=project).first()
    return render(request, "erp/customer_portal.html", {
        "portal": portal,
        "project": project,
        "media": media,
        "change_orders": change_orders,
        "survey": survey,
    })


@login_required
@require_http_methods(["GET", "POST"])
def purchase_order_create(request):
    _write(request)
    if not _prices_allowed(request):
        raise PermissionDenied
    org = _org(request)
    form = PurchaseOrderForm(request.POST or None, organization=org)
    if request.method == "POST" and form.is_valid():
        order = form.save(commit=False)
        order.organization = org
        order.number = next_number(org, "purchase_order")
        order.created_by = request.user
        order.save()
        for upload in request.FILES.getlist("documents"):
            PurchaseDocument.objects.create(purchase_order=order, kind=PurchaseDocument.Kind.RECEIPT, file=upload, title=upload.name, uploaded_by=request.user)
        messages.success(request, "Bestellung und Einkaufsdokumente wurden gespeichert.")
        return redirect("purchase-order-detail", pk=order.pk)
    return render(request, "erp/purchase_order_form.html", {"form": form})


@login_required
@require_http_methods(["GET", "POST"])
def purchase_order_detail(request, pk):
    _write(request)
    if not _prices_allowed(request):
        raise PermissionDenied
    order = get_object_or_404(PurchaseOrder, organization=_org(request), pk=pk)
    if request.method == "POST" and request.FILES.get("file"):
        PurchaseDocument.objects.create(
            purchase_order=order,
            kind=request.POST.get("kind", PurchaseDocument.Kind.RECEIPT),
            file=request.FILES["file"],
            title=request.POST.get("title", request.FILES["file"].name),
            uploaded_by=request.user,
        )
        return redirect("purchase-order-detail", pk=pk)
    return render(request, "erp/purchase_order_detail.html", {"order": order})


@login_required
@require_http_methods(["GET", "POST"])
def marketplace(request):
    if not _prices_allowed(request):
        raise PermissionDenied
    _write(request)
    org = _org(request)
    q = request.GET.get("q", "").strip()
    results = []
    error = ""
    integration = IntegrationConfig.objects.filter(organization=org, provider=IntegrationConfig.Provider.MARKETPLACE, enabled=True).first()
    if q and integration and integration.config.get("search_url"):
        try:
            response = requests.get(
                integration.config["search_url"],
                params={integration.config.get("query_param", "q"): q},
                headers={"Authorization": f"Bearer {integration.config.get('token', '')}"} if integration.config.get("token") else {},
                timeout=8,
            )
            response.raise_for_status()
            payload = response.json()
            raw_items = payload.get("items", payload if isinstance(payload, list) else [])
            for item in raw_items[:40]:
                results.append({
                    "code": str(item.get("code") or item.get("sku") or ""),
                    "name": str(item.get("name") or item.get("title") or "Material"),
                    "description": str(item.get("description") or ""),
                    "unit": str(item.get("unit") or "Stk."),
                    "purchase_price": str(item.get("purchase_price") or item.get("price") or 0),
                    "supplier": str(item.get("supplier") or item.get("brand") or "Marketplace"),
                })
        except Exception as exc:
            error = str(exc)
    elif q:
        results = [
            {"code": x.code, "name": x.name, "description": x.description, "unit": x.unit, "purchase_price": str(x.purchase_price), "supplier": x.supplier}
            for x in CatalogItem.objects.filter(organization=org, kind=CatalogItem.Kind.MATERIAL, name__icontains=q)[:40]
        ]
    for result in results:
        result["item_json"] = json.dumps(result, ensure_ascii=False)
    if request.method == "POST":
        try:
            data = json.loads(request.POST.get("item", "{}"))
        except json.JSONDecodeError:
            messages.error(request, "Materialdaten sind ungültig.")
            return redirect("marketplace")
        code = data.get("code") or f"MKT-{secrets.token_hex(4).upper()}"
        item, created = CatalogItem.objects.update_or_create(
            organization=org,
            code=code,
            defaults={
                "name": data.get("name", "Marketplace Material")[:240],
                "description": data.get("description", ""),
                "kind": CatalogItem.Kind.MATERIAL,
                "unit": data.get("unit", "Stk.")[:30],
                "purchase_price": Decimal(str(data.get("purchase_price") or 0)),
                "sales_price": Decimal(str(data.get("sales_price") or data.get("purchase_price") or 0)),
                "supplier": data.get("supplier", "Marketplace")[:160],
                "external_codes": {"marketplace": data},
            },
        )
        messages.success(request, "Material wurde in den eigenen Katalog übernommen.")
        return redirect("model-edit", resource="catalog", pk=item.pk)
    return render(request, "erp/marketplace.html", {"q": q, "results": results, "error": error, "integration": integration})


@login_required
@require_http_methods(["GET", "POST"])
def service_assistant(request, project_pk):
    if not _prices_allowed(request):
        raise PermissionDenied
    _write(request)
    org = _org(request)
    project = _project_for_request(request, project_pk)
    suggestions = []
    warning = ""
    prompt = request.POST.get("prompt", "") if request.method == "POST" else ""
    if request.method == "POST" and request.POST.get("action") == "analyze" and prompt:
        source_items = PriceItem.objects.filter(organization=org, source=project.price_source)[:1000] if project.price_source else PriceItem.objects.filter(organization=org)[:1000]
        context = "\n".join(f"{x.code} | {x.description} | {x.unit} | {x.sales_price or x.purchase_price or 0}" for x in source_items)
        try:
            data = suggest_invoice_items(org, prompt, context)
            suggestions = data.get("items", [])
            warning = " ".join(data.get("warnings", []))
        except Exception as exc:
            warning = str(exc)
    elif request.method == "POST" and request.POST.get("action") == "apply":
        quote = project.quotes.filter(status__in=[Quote.Status.DRAFT, Quote.Status.REVIEW]).first()
        if not quote:
            quote = Quote.objects.create(organization=org, project=project, number=next_number(org, "quote"), status=Quote.Status.REVIEW, created_by=request.user)
        rows = int(request.POST.get("row_count", "0") or 0)
        for index in range(rows):
            description = request.POST.get(f"description_{index}", "").strip()
            if not description:
                continue
            QuoteItem.objects.create(
                quote=quote,
                position=quote.items.count() + 1,
                code=request.POST.get(f"code_{index}", "")[:80],
                description=description,
                quantity=Decimal(request.POST.get(f"quantity_{index}", "1") or "1"),
                unit=request.POST.get(f"unit_{index}", "Stk.")[:30],
                unit_price=Decimal(request.POST.get(f"unit_price_{index}", "0") or "0"),
                tax_rate=Decimal("19"),
                ai_generated=True,
                approved=False,
            )
        messages.success(request, "Live bearbeitete KI-Vorschläge wurden als prüfpflichtige Positionen übernommen.")
        return redirect("quote-edit", pk=quote.pk)
    return render(request, "erp/service_assistant.html", {"project": project, "prompt": prompt, "suggestions": suggestions, "warning": warning})


@login_required
@require_http_methods(["GET", "POST"])
def bug_report(request):
    org = _org(request)
    form = BugReportForm(request.POST or None, request.FILES or None, organization=org, initial={"page_url": request.META.get("HTTP_REFERER", "")})
    if request.method == "POST" and form.is_valid():
        report = form.save(commit=False)
        report.organization = org
        report.reported_by = request.user
        report.save()
        admins = User.objects.filter(profile__organization=org, profile__role=UserProfile.Role.ADMIN, is_active=True)
        for user in admins:
            Notification.objects.create(user=user, title="Neuer Fehlerbericht", message=report.title, url=f"/admin/erp/bugreport/{report.pk}/change/")
        messages.success(request, "Fehlerbericht wurde an die Administration gesendet.")
        return redirect("dashboard")
    return render(request, "erp/form.html", {"form": form, "title": "Fehler melden", "instance": None})


@login_required
def notification_feed(request):
    org = _org(request)
    if not IntegrationConfig.objects.filter(organization=org, provider=IntegrationConfig.Provider.WEBPUSH, enabled=True).exists():
        return JsonResponse({"notifications": [], "enabled": False})
    due = Notification.objects.filter(user=request.user, read_at__isnull=True, delivered_at__isnull=True).filter(
        models_q_due()
    ).order_by("-created_at")[:30]
    payload = []
    now = timezone.now()
    for item in due:
        payload.append({"id": item.pk, "title": item.title, "message": item.message, "url": item.url, "level": item.level})
        if not item.delivered_at:
            item.delivered_at = now
            item.save(update_fields=["delivered_at", "updated_at"])
    return JsonResponse({"notifications": payload, "enabled": True})


def models_q_due():
    from django.db.models import Q
    return Q(scheduled_for__isnull=True) | Q(scheduled_for__lte=timezone.now())


@csrf_exempt
@require_POST
def inbound_email_webhook(request):
    try:
        payload = json.loads(request.body.decode("utf-8"))
    except Exception:
        return JsonResponse({"error": "invalid_json"}, status=400)
    supplied = request.headers.get("X-KAYI-Inbound-Token") or request.GET.get("token")
    org_id = payload.get("organization_id")
    integrations = IntegrationConfig.objects.filter(provider=IntegrationConfig.Provider.GMX, enabled=True).select_related("organization")
    if org_id:
        integrations = integrations.filter(organization_id=org_id)
    integration = None
    for candidate in integrations:
        expected = (candidate.config or {}).get("inbound_token")
        if expected and secrets.compare_digest(str(expected), str(supplied or "")):
            integration = candidate
            break
    if not integration:
        return JsonResponse({"error": "forbidden"}, status=403)
    org = integration.organization
    sender = payload.get("sender", "")
    subject = payload.get("subject", "")
    body = payload.get("body_text", "")
    claim = payload.get("claim_number")
    if not claim:
        match = re.search(r"(?:Schaden|Claim|BO)[-\s:#]*([A-Z0-9\-/]{4,})", f"{subject}\n{body}", re.I)
        claim = match.group(1) if match else ""
    project = Project.objects.filter(organization=org, insurance_claim_number__iexact=claim).first() if claim else None
    customer = Customer.objects.filter(organization=org, email__iexact=sender).first() if sender else None
    message, created = EmailMessage.objects.get_or_create(
        organization=org,
        message_id=payload.get("message_id") or f"webhook-{secrets.token_hex(16)}",
        defaults={
            "project": project,
            "customer": customer,
            "direction": EmailMessage.Direction.INBOUND,
            "status": EmailMessage.Status.CLASSIFIED if project or customer else EmailMessage.Status.NEW,
            "sender": sender,
            "recipients": payload.get("recipients", []),
            "subject": subject,
            "body_text": body[:500000],
            "body_html": payload.get("body_html", "")[:500000],
            "received_at": timezone.now(),
            "classification": {"claim_number": claim, "auto_linked": bool(project or customer), "source": "api_webhook"},
        },
    )
    attachment_ids = []
    if created:
        for attachment in (payload.get("attachments") or [])[:10]:
            filename = str(attachment.get("filename") or "email-attachment.bin")[:220]
            encoded = attachment.get("content_base64") or ""
            try:
                raw = base64.b64decode(encoded, validate=True)
            except Exception:
                continue
            if not raw or len(raw) > 15 * 1024 * 1024:
                continue
            document = Document(
                organization=org,
                project=project,
                customer=customer,
                title=filename,
                category=Document.Category.OTHER,
                metadata={"source": "inbound_email", "email_message_id": message.pk, "content_type": attachment.get("content_type", "")},
            )
            document.file.save(filename, ContentFile(raw), save=True)
            attachment_ids.append(document.pk)
        if attachment_ids:
            message.classification = {**(message.classification or {}), "attachment_document_ids": attachment_ids}
            message.save(update_fields=["classification", "updated_at"])
    return JsonResponse({"id": message.pk, "created": created, "project_id": project.pk if project else None, "attachment_document_ids": attachment_ids})


@login_required
@require_POST
def create_document_email(request, kind, pk):
    _write(request)
    org = _org(request)
    builders = {
        "quote": (Quote, "Angebot"),
        "invoice": (Invoice, "Rechnung"),
        "change_order": (ChangeOrder, "Zusatzarbeit"),
        "site_report": (SiteReport, "Vor-Ort-Bericht"),
    }
    if kind not in builders:
        raise Http404
    model, label = builders[kind]
    document = get_object_or_404(model, organization=org, pk=pk)
    project = document.project
    customer = project.customer
    email = EmailMessage.objects.create(
        organization=org,
        project=project,
        customer=customer,
        direction=EmailMessage.Direction.DRAFT,
        status=EmailMessage.Status.REVIEW,
        recipients=[customer.email] if customer.email else [],
        subject=f"{label} – {project.title}",
        body_text=f"Guten Tag {customer.display_name},\n\nim Anhang erhalten Sie {label.lower()} zum Projekt {project.title}.\n\nMit freundlichen Grüßen\n{org.name}",
        classification={"attachment_kind": kind, "attachment_id": document.pk},
    )
    messages.success(request, "E-Mail mit PDF-Anhang wurde als prüfpflichtiger Entwurf vorbereitet.")
    return redirect("email-detail", pk=email.pk)

@login_required
@require_POST
def integration_config_update(request, provider):
    if not request.user.is_superuser and role_for_user(request) != UserProfile.Role.ADMIN:
        raise PermissionDenied
    org = _org(request)
    valid = set(IntegrationConfig.Provider.values)
    if provider not in valid:
        raise Http404
    integration, _ = IntegrationConfig.objects.get_or_create(organization=org, provider=provider)
    config = dict(integration.config or {})
    if provider == IntegrationConfig.Provider.MARKETPLACE:
        config.update({
            "search_url": request.POST.get("search_url", "").strip(),
            "query_param": request.POST.get("query_param", "q").strip() or "q",
        })
        token = request.POST.get("token", "").strip()
        if token:
            config["token"] = token
    elif provider == IntegrationConfig.Provider.GMX:
        inbound_token = request.POST.get("inbound_token", "").strip()
        config["inbound_token"] = inbound_token or config.get("inbound_token") or secrets.token_urlsafe(32)
    elif provider == IntegrationConfig.Provider.WEBPUSH:
        config["browser_notifications"] = request.POST.get("browser_notifications") == "on"
    integration.config = config
    integration.save(update_fields=["config", "updated_at"])
    messages.success(request, f"Konfiguration für {integration.get_provider_display()} wurde gespeichert.")
    return redirect("settings")

@login_required
@require_POST
def price_source_share_toggle(request, pk):
    if not _prices_allowed(request):
        raise PermissionDenied
    _write(request)
    source = get_object_or_404(PriceSource, organization=_org(request), pk=pk)
    source.share_enabled = not source.share_enabled
    source.save(update_fields=["share_enabled", "updated_at"])
    messages.success(request, "Öffentlicher Verkaufs-/Suchlink wurde aktiviert." if source.share_enabled else "Öffentlicher Link wurde deaktiviert.")
    return redirect(f"/prices/?source={source.pk}")


def price_source_public(request, token):
    source = get_object_or_404(PriceSource, share_token=token, share_enabled=True, active=True)
    q = request.GET.get("q", "").strip()
    items = source.items.filter(active=True)
    if q:
        items = items.filter(reduce_q(q))
    return render(request, "erp/price_source_public.html", {"source": source, "items": items[:250], "q": q})


@login_required
def price_source_export(request, pk):
    if not _prices_allowed(request):
        raise PermissionDenied
    source = get_object_or_404(PriceSource, organization=_org(request), pk=pk)
    import csv
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="price-list-{source.pk}.csv"'
    response.write("\ufeff")
    writer = csv.writer(response, delimiter=";")
    writer.writerow(["Code", "Beschreibung", "Kategorie", "Einheit", "Verkaufspreis", "MwSt."])
    for item in source.items.filter(active=True):
        writer.writerow([item.code, item.description, item.category, item.unit, item.sales_price or "", item.tax_rate])
    return response
