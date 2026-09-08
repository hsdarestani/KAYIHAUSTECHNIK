from __future__ import annotations

import csv
import io
import json
import re
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from pathlib import Path

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Count, Max, Q, Sum
from django.http import FileResponse, Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.text import slugify
from django.views.decorators.http import require_http_methods, require_POST

from erp.forms import (
    CalendarEventForm,
    CatalogItemForm,
    CustomerForm,
    DocumentForm,
    EmailDraftForm,
    EmployeeForm,
    ExpenseForm,
    InvoiceForm,
    InvoiceItemFormSet,
    ObjectLocationForm,
    PaymentForm,
    PriceSourceUploadForm,
    ProjectForm,
    ProjectMaterialForm,
    ProjectWizardForm,
    RoomMeasurementForm,
    QuoteForm,
    QuoteItemFormSet,
    SupplierForm,
    TaskForm,
    TimeEntryForm,
)
from erp.models import (
    ActivityLog,
    AIConversation,
    AutomationJob,
    CalendarEvent,
    CatalogItem,
    Customer,
    Document,
    EmailMessage,
    Employee,
    Expense,
    IntegrationConfig,
    Invoice,
    InvoiceItem,
    Notification,
    ObjectLocation,
    Organization,
    Payment,
    PriceItem,
    PriceSource,
    Project,
    ProjectMaterial,
    RoomMeasurement,
    RoomModelRevision,
    MeasurementCapture,
    NativeRoomScan,
    Quote,
    QuoteItem,
    Supplier,
    Task,
    TimeEntry, UserProfile,
)
from erp.services.ai import suggest_catalog_services, suggest_invoice_items, suggest_room_model_state
from erp.services.bundo import approve_job, build_position_suggestions
from erp.services.documents import extract_text, validate_upload
from erp.services.emailing import send_approved_email
from erp.services.importers import import_catalog, import_customers, import_tooltime
from erp.services.integrations import integration_available, integration_cards, integration_configured, test_integration_connection
from erp.services.numbering import next_number
from erp.services.pricing import commercial_price_sources, is_material_only_source, preferred_price_source, quantity_for_price_item, resolved_item_price
from erp.services.reference_data import import_price_file
from erp.services.pdf import build_invoice_pdf, build_quote_pdf
from erp.services.permissions import can_approve_automation, can_manage_finance, can_view_prices, can_write, role_for
from erp.services.room_models import initial_room_model_state, normalize_room_model_state, opening_area




def service_worker(request):
    worker_path = Path(__file__).resolve().parent.parent / "static" / "js" / "sw.js"
    response = HttpResponse(worker_path.read_text(encoding="utf-8"), content_type="application/javascript")
    response["Service-Worker-Allowed"] = "/"
    response["Cache-Control"] = "no-cache"
    return response

def healthcheck(request):
    return JsonResponse({"status": "ok", "time": timezone.now().isoformat()})


def _organization(request) -> Organization:
    profile = getattr(request.user, "profile", None)
    organization = getattr(profile, "organization", None)
    if organization:
        return organization
    organization = Organization.objects.first()
    if organization and profile:
        profile.organization = organization
        profile.save(update_fields=["organization", "updated_at"])
    if not organization:
        raise PermissionDenied("Keine Organisation konfiguriert.")
    return organization


def _require_write(request):
    if not can_write(request.user):
        raise PermissionDenied("Keine Schreibberechtigung.")


def _projects_for_user(request, organization, queryset=None):
    queryset = queryset if queryset is not None else Project.objects.filter(organization=organization)
    if role_for(request.user) == UserProfile.Role.TECHNICIAN:
        employee = getattr(request.user, "employee", None)
        return queryset.filter(Q(members=employee) | Q(manager=employee)).distinct() if employee else queryset.none()
    return queryset


def _unique_employee_username(email: str, first_name: str, last_name: str) -> str:
    base = (email.split("@", 1)[0] if email else slugify(f"{first_name}.{last_name}")) or "mitarbeiter"
    base = "".join(ch for ch in base if ch.isalnum() or ch in "._-")[:120] or "mitarbeiter"
    candidate = base
    suffix = 2
    while User.objects.filter(username=candidate).exists():
        candidate = f"{base[:110]}-{suffix}"
        suffix += 1
    return candidate


def _pagination(request, queryset, per_page=50):
    from django.core.paginator import Paginator
    return Paginator(queryset, per_page).get_page(request.GET.get("page"))


def _safe_json(value, default):
    if value in (None, ""):
        return default
    try:
        parsed = json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return default
    return parsed if isinstance(parsed, type(default)) else default


@login_required
def dashboard(request):
    org = _organization(request)
    today = timezone.localdate()
    month_start = today.replace(day=1)
    projects = _projects_for_user(request, org, Project.objects.filter(organization=org, archived=False))
    prices_allowed = can_view_prices(request.user)
    invoices = Invoice.objects.filter(organization=org) if prices_allowed else Invoice.objects.none()
    open_invoices = invoices.exclude(status__in=[Invoice.Status.PAID, Invoice.Status.CANCELLED])
    overdue = open_invoices.filter(due_date__lt=today)
    revenue_month = sum((inv.gross_total for inv in invoices.filter(issue_date__gte=month_start)), Decimal("0"))
    due_total = sum((inv.outstanding_total for inv in open_invoices), Decimal("0"))
    today_events = CalendarEvent.objects.filter(organization=org, starts_at__date=today).select_related("project")
    tasks = Task.objects.filter(organization=org).exclude(status__in=[Task.Status.DONE, Task.Status.CANCELLED]).select_related("project", "assigned_to")
    if role_for(request.user) == UserProfile.Role.TECHNICIAN:
        employee = getattr(request.user, "employee", None)
        today_events = today_events.filter(attendees=employee) if employee else today_events.none()
        tasks = tasks.filter(assigned_to=employee) if employee else tasks.none()
    open_tasks_count = tasks.count()
    tasks = tasks[:8]
    planned_minutes = sum((max(0, int((event.ends_at - event.starts_at).total_seconds() / 60)) for event in today_events), 0)
    recorded_entries = TimeEntry.objects.filter(organization=org, started_at__date=today)
    if role_for(request.user) == UserProfile.Role.TECHNICIAN:
        recorded_entries = recorded_entries.filter(employee=getattr(request.user, "employee", None))
    recorded_minutes = sum((entry.duration_minutes for entry in recorded_entries), 0)
    map_points = []
    map_projects = list(projects.select_related("customer", "object_location", "manager")[:12])
    fallback_positions = [(42, 37), (61, 28), (39, 59), (31, 25), (67, 51), (54, 67), (23, 65), (73, 34), (47, 48), (59, 78), (35, 75), (78, 62)]
    geo_projects = [p for p in map_projects if p.object_location and p.object_location.latitude is not None and p.object_location.longitude is not None]
    if geo_projects:
        lats = [float(p.object_location.latitude) for p in geo_projects]
        lngs = [float(p.object_location.longitude) for p in geo_projects]
        lat_span = max(max(lats) - min(lats), 0.01)
        lng_span = max(max(lngs) - min(lngs), 0.01)
    else:
        lats = lngs = []
        lat_span = lng_span = 1
    for index, project in enumerate(map_projects):
        is_geocoded = bool(project.object_location and project.object_location.latitude is not None and project.object_location.longitude is not None)
        if is_geocoded:
            left = 12 + ((float(project.object_location.longitude) - min(lngs)) / lng_span) * 76
            top = 82 - ((float(project.object_location.latitude) - min(lats)) / lat_span) * 68
        else:
            left, top = fallback_positions[index % len(fallback_positions)]
        map_points.append({"project": project, "left": round(left, 2), "top": round(top, 2), "is_geocoded": is_geocoded})
    context = {
        "active_projects": projects.exclude(status__in=[Project.Status.COMPLETED, Project.Status.CANCELLED]).count(),
        "open_tasks": open_tasks_count,
        "open_quotes": Quote.objects.filter(organization=org).exclude(status__in=[Quote.Status.ACCEPTED, Quote.Status.REJECTED, Quote.Status.EXPIRED]).count() if prices_allowed else 0,
        "overdue_count": overdue.count(),
        "revenue_month": revenue_month,
        "due_total": due_total,
        "planned_hours": f"{planned_minutes // 60}h {planned_minutes % 60:02d}m",
        "recorded_hours": f"{recorded_minutes // 60}h {recorded_minutes % 60:02d}m",
        "today_events": today_events,
        "tasks": tasks,
        "recent_projects": map_projects[:8],
        "map_points": map_points,
        "recent_activities": (ActivityLog.objects.filter(organization=org, user=request.user) if role_for(request.user) == UserProfile.Role.TECHNICIAN else ActivityLog.objects.filter(organization=org)).select_related("user")[:12],
        "status_counts": projects.values("status").annotate(count=Count("id")),
        "can_view_prices": prices_allowed,
        "is_technician_dashboard": role_for(request.user) == UserProfile.Role.TECHNICIAN,
    }
    return render(request, "erp/dashboard.html", context)


@login_required
def generic_list(request, resource):
    org = _organization(request)
    q = request.GET.get("q", "").strip()
    role = role_for(request.user)
    if role == "technician" and resource in {"suppliers", "payments", "customers", "objects", "employees", "catalog", "materials", "quotes", "invoices", "expenses", "emails", "automations"}:
        raise PermissionDenied("Mitarbeiter sehen ausschließlich ihre Einsätze, Aufgaben, Zeiten und freigegebenen Projektdaten.")
    configs = {
        "suppliers": (Supplier.objects.filter(organization=org), "Lieferanten", ["number", "name", "contact_name", "email", "phone", "city"], "supplier-create"),
        "payments": (Payment.objects.filter(invoice__organization=org).select_related("invoice", "invoice__project").order_by("-paid_at", "-pk"), "Zahlungen", ["paid_at", "invoice", "amount", "method", "reference"], None),
        "customers": (Customer.objects.filter(organization=org), "Kunden", ["number", "display_name", "email", "phone", "city"], "customer-create"),
        "objects": (ObjectLocation.objects.filter(organization=org).select_related("customer"), "Objekte", ["name", "customer", "street", "city"], "object-create"),
        "projects": (Project.objects.filter(organization=org).select_related("customer", "manager"), "Projekte", ["number", "title", "customer", "status", "progress"], "project-create"),
        "employees": (Employee.objects.filter(organization=org), "Mitarbeiter", ["employee_number", "full_name", "trade", "phone", "active"], "employee-create"),
        "tasks": (Task.objects.filter(organization=org).select_related("project", "assigned_to"), "Aufgaben", ["title", "project", "assigned_to", "status", "due_at"], "task-create"),
        "events": (CalendarEvent.objects.filter(organization=org).select_related("project"), "Kalender & Termine", ["title", "project", "starts_at", "ends_at", "location"], "event-create"),
        "catalog": (CatalogItem.objects.filter(organization=org), "Leistungskatalog", ["code", "name", "kind", "unit", "sales_price"], "catalog-create"),
        "materials": (ProjectMaterial.objects.filter(project__organization=org).select_related("project", "catalog_item"), "Material", ["project", "name", "quantity", "unit", "ordered", "delivered"], "material-create"),
        "time": (TimeEntry.objects.filter(organization=org).select_related("employee", "project"), "Zeiterfassung", ["employee", "project", "started_at", "ended_at", "duration_hours"], "time-create"),
        "documents": (Document.objects.filter(organization=org).select_related("project", "customer"), "Dokumente", ["title", "category", "project", "customer", "created_at"], "document-create"),
        "quotes": (Quote.objects.filter(organization=org).select_related("project", "project__customer"), "Angebote", ["number", "project", "status", "issue_date", "gross_total"], "quote-create"),
        "invoices": (Invoice.objects.filter(organization=org).select_related("project", "project__customer"), "Rechnungen", ["number", "project", "status", "due_date", "outstanding_total"], "invoice-create"),
        "expenses": (Expense.objects.filter(organization=org).select_related("project"), "Ausgaben", ["expense_date", "supplier", "description", "project", "amount_gross"], "expense-create"),
        "emails": (EmailMessage.objects.filter(organization=org).select_related("project", "customer"), "E-Mails", ["direction", "subject", "sender", "status", "received_at"], "email-create"),
        "automations": (AutomationJob.objects.filter(organization=org).select_related("project", "requested_by"), "Automationen", ["kind", "project", "status", "requested_by", "created_at"], None),
    }
    if resource not in configs:
        raise Http404
    queryset, title, columns, create_url = configs[resource]
    if role == "technician":
        employee = getattr(request.user, "employee", None)
        if not employee:
            queryset = queryset.none()
        elif resource == "projects":
            queryset = queryset.filter(Q(members=employee) | Q(manager=employee)).distinct()
        elif resource == "tasks":
            queryset = queryset.filter(assigned_to=employee)
        elif resource == "events":
            queryset = queryset.filter(attendees=employee)
        elif resource == "time":
            queryset = queryset.filter(employee=employee)
        elif resource == "documents":
            queryset = queryset.filter(project__members=employee).distinct()
    if q:
        searchable = {
            "suppliers": Q(number__icontains=q) | Q(name__icontains=q) | Q(contact_name__icontains=q) | Q(email__icontains=q),
            "payments": Q(invoice__number__icontains=q) | Q(reference__icontains=q),
            "customers": Q(number__icontains=q) | Q(company__icontains=q) | Q(first_name__icontains=q) | Q(last_name__icontains=q) | Q(email__icontains=q),
            "objects": Q(name__icontains=q) | Q(street__icontains=q) | Q(city__icontains=q) | Q(customer__company__icontains=q),
            "projects": Q(number__icontains=q) | Q(title__icontains=q) | Q(customer__company__icontains=q) | Q(customer__last_name__icontains=q),
            "employees": Q(employee_number__icontains=q) | Q(first_name__icontains=q) | Q(last_name__icontains=q) | Q(trade__icontains=q),
            "tasks": Q(title__icontains=q) | Q(description__icontains=q) | Q(project__title__icontains=q),
            "events": Q(title__icontains=q) | Q(location__icontains=q) | Q(project__title__icontains=q),
            "catalog": Q(code__icontains=q) | Q(name__icontains=q) | Q(description__icontains=q),
            "materials": Q(name__icontains=q) | Q(project__title__icontains=q),
            "documents": Q(title__icontains=q) | Q(project__title__icontains=q),
            "quotes": Q(number__icontains=q) | Q(project__title__icontains=q),
            "invoices": Q(number__icontains=q) | Q(project__title__icontains=q),
            "expenses": Q(supplier__icontains=q) | Q(description__icontains=q),
            "emails": Q(subject__icontains=q) | Q(sender__icontains=q) | Q(body_text__icontains=q),
            "automations": Q(kind__icontains=q) | Q(project__title__icontains=q),
        }.get(resource)
        if searchable:
            queryset = queryset.filter(searchable)
    return render(request, "erp/generic_list.html", {"resource": resource, "title": title, "columns": columns, "page_obj": _pagination(request, queryset), "create_url": create_url, "query": q})


FORM_CONFIG = {
    "supplier": (Supplier, SupplierForm, "Lieferant", "suppliers"),
    "customer": (Customer, CustomerForm, "Kunde", "customers"),
    "object": (ObjectLocation, ObjectLocationForm, "Objekt", "objects"),
    "employee": (Employee, EmployeeForm, "Mitarbeiter", "employees"),
    "project": (Project, ProjectForm, "Projekt", "projects"),
    "task": (Task, TaskForm, "Aufgabe", "tasks"),
    "event": (CalendarEvent, CalendarEventForm, "Termin", "events"),
    "catalog": (CatalogItem, CatalogItemForm, "Katalogposition", "catalog"),
    "material": (ProjectMaterial, ProjectMaterialForm, "Material", "materials"),
    "time": (TimeEntry, TimeEntryForm, "Zeiteintrag", "time"),
    "document": (Document, DocumentForm, "Dokument", "documents"),
    "expense": (Expense, ExpenseForm, "Ausgabe", "expenses"),
}


def _catalog_search_terms(value: str) -> set[str]:
    normalized = value.casefold().translate(str.maketrans({"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss"}))
    terms = {token for token in re.findall(r"[a-z0-9]+", normalized) if len(token) > 1}
    synonym_groups = (
        {"dach", "dachziegel", "ziegel", "deckung", "eindecken", "dachrinne", "regenrinne"},
        {"bad", "badezimmer", "sanitaer", "waschtisch", "dusche", "wc", "toilette"},
        {"fliese", "fliesen", "fuge", "fugen", "silikon", "bodenfliese", "wandfliese"},
        {"heizung", "heizkoerper", "waermepumpe", "kessel", "therme", "fussbodenheizung"},
        {"wasser", "wasserschaden", "leck", "rohrbruch", "trocknung", "abdichtung"},
        {"elektro", "steckdose", "schalter", "leitung", "beleuchtung"},
        {"maler", "streichen", "anstrich", "tapete", "spachteln"},
        {"boden", "estrich", "parkett", "laminat", "vinyl"},
        {"demontage", "abbruch", "ausbau", "entfernen", "entsorgung"},
    )
    for group in synonym_groups:
        if terms.intersection(group):
            terms.update(group)
    return terms


def _catalog_service_score(item, terms: set[str], raw_query: str) -> int:
    code = item.code.casefold()
    name = item.name.casefold().translate(str.maketrans({"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss"}))
    description = (item.description or "").casefold().translate(str.maketrans({"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss"}))
    raw = raw_query.casefold().strip()
    score = 0
    if raw and raw in f"{code} {name} {description}":
        score += 20
    for term in terms:
        if term in code:
            score += 8
        if term in name:
            score += 6
        if term in description:
            score += 2
    return score


@login_required
@require_POST
def project_service_suggestions(request):
    _require_write(request)
    if role_for(request.user) == "technician":
        raise PermissionDenied
    prompt = (request.POST.get("prompt") or "").strip()
    if len(prompt) < 3:
        return JsonResponse({"error": "Bitte die gewünschten Arbeiten etwas genauer beschreiben."}, status=400)
    org = _organization(request)
    terms = _catalog_search_terms(prompt)
    source_id = (request.POST.get("price_source") or "").strip()

    if source_id:
        source = get_object_or_404(commercial_price_sources(org), pk=source_id)
        items = list(
            PriceItem.objects.filter(organization=org, source=source, active=True)
            .filter(Q(sales_price__gt=0) | Q(purchase_price__gt=0))
            .only("id", "code", "description", "category", "unit", "sales_price", "purchase_price")
            .order_by("code")
        )

        def score(item):
            code = (item.code or "").casefold()
            text = f"{item.category or ''} {item.description or ''}".casefold().translate(
                str.maketrans({"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss"})
            )
            raw = prompt.casefold().strip()
            value = 20 if raw and raw in f"{code} {text}" else 0
            for term in terms:
                if term in code:
                    value += 8
                if term in text:
                    value += 4
            return value

        scored = sorted(((item, score(item)) for item in items), key=lambda pair: (-pair[1], pair[0].code))
        selected = [item for item, score_value in scored if score_value > 0][:12]
        if not selected:
            selected = items[:12]
        return JsonResponse({
            "summary": f"Passende Positionen aus {source.name} gefunden." if selected else "Keine eindeutige Position gefunden.",
            "warning": "",
            "selection_type": "price_item",
            "matches": [
                {
                    "id": item.pk,
                    "code": item.code,
                    "name": (item.description or item.code)[:160],
                    "description": item.description or "",
                    "unit": item.unit or "Stk.",
                    "price": str(resolved_item_price(item) or Decimal("0")),
                    "reason": "Treffer in der ausgewählten Preisliste",
                    "selection_type": "price_item",
                }
                for item in selected if resolved_item_price(item) is not None
            ],
        })

    items = list(
        CatalogItem.objects.filter(
            organization=org,
            active=True,
            kind=CatalogItem.Kind.SERVICE,
        ).only("id", "code", "name", "description", "unit", "sales_price").order_by("code")
    )
    scored = sorted(
        ((item, _catalog_service_score(item, terms, prompt)) for item in items),
        key=lambda pair: (-pair[1], pair[0].code),
    )
    lexical = [item for item, score in scored if score > 0]
    ai_pool = (lexical[:140] or items[:220])
    catalog_context = "\n".join(
        f"{item.code} | {item.name} | {item.description or ''} | {item.unit}"
        for item in ai_pool
    )
    item_by_code = {item.code.casefold(): item for item in ai_pool}
    selected = []
    reasons = {}
    warning = ""
    summary = ""
    try:
        data = suggest_catalog_services(org, prompt, catalog_context)
        summary = data.get("summary", "")
        warning = " ".join(data.get("warnings", []))
        for suggestion in data.get("suggestions", []):
            item = item_by_code.get(str(suggestion.get("code", "")).casefold())
            if item and item not in selected:
                selected.append(item)
                reasons[item.pk] = suggestion.get("reason", "Passend zur Beschreibung")
    except Exception:
        warning = "Die KI ist gerade nicht erreichbar. Die Treffer wurden direkt im Katalog gesucht."
    for item in lexical:
        if item not in selected:
            selected.append(item)
            reasons[item.pk] = "Treffer aus Name, Code oder Leistungsbeschreibung"
        if len(selected) >= 12:
            break
    selected = selected[:12]
    return JsonResponse({
        "summary": summary or ("Passende Katalogpositionen gefunden." if selected else "Keine eindeutige Position gefunden."),
        "warning": warning,
        "selection_type": "catalog",
        "matches": [
            {
                "id": item.pk,
                "code": item.code,
                "name": item.name,
                "description": item.description or "",
                "unit": item.unit,
                "price": str(item.sales_price),
                "reason": reasons.get(item.pk, "Passend zur Projektbeschreibung"),
                "selection_type": "catalog",
            }
            for item in selected
        ],
    })


@login_required
@require_http_methods(["GET"])
def project_wizard_price_items(request):
    """Return sellable positions from the commercial price source selected in the wizard."""
    if not can_view_prices(request.user):
        raise PermissionDenied("Mitarbeiter dürfen keine Preise oder Finanzdaten sehen.")
    org = _organization(request)
    source_id = (request.GET.get("price_source") or "").strip()
    if not source_id:
        return JsonResponse({"price_source": None, "count": 0, "items": []})
    source = get_object_or_404(commercial_price_sources(org), pk=source_id)
    query = (request.GET.get("q") or "").strip()
    queryset = PriceItem.objects.filter(organization=org, source=source, active=True).filter(
        Q(sales_price__gt=0) | Q(purchase_price__gt=0)
    )
    if query:
        queryset = queryset.filter(
            Q(code__icontains=query) | Q(description__icontains=query) | Q(category__icontains=query)
        )
    total = queryset.count()
    rows = []
    for item in queryset.only("id", "code", "description", "category", "unit", "sales_price", "purchase_price").order_by("code")[:1000]:
        price = resolved_item_price(item)
        if price is None:
            continue
        rows.append({
            "id": item.pk,
            "code": item.code,
            "description": item.description or item.code,
            "category": item.category or "",
            "unit": item.unit or "Stk.",
            "price": str(price),
        })
    return JsonResponse({"price_source": source.name, "count": total, "items": rows})


def _room_model_fallback(prompt: str, current_state: dict) -> dict:
    """Deterministic room-design fallback when the AI provider is unavailable."""
    state = json.loads(json.dumps(current_state))
    state.setdefault("room", {"length_m": "4", "width_m": "3", "height_m": "2.5"})
    state.setdefault("openings", [])
    state.setdefault("objects", [])
    materials = state.setdefault("materials", {})
    materials.setdefault("floor", "#3d434b")
    materials.setdefault("wall", "#eef2f6")
    materials.setdefault("ceiling", "#f8fafc")
    materials.setdefault("accent", "#6e8fa8")
    materials.setdefault("grout_color", "#c7cdd3")
    materials.setdefault("pattern", "straight")
    materials.setdefault("tile_width_cm", "60")
    materials.setdefault("tile_height_cm", "60")
    lighting = state.setdefault("lighting", {"brightness": "1", "warmth": "35"})
    state.setdefault("view", {"mode": "perspective", "rotation_deg": "0"})

    normalized = prompt.casefold().translate(str.maketrans({"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss"}))
    dimension_match = re.search(
        r"(\d+(?:[.,]\d+)?)\s*(?:m\s*)?[x×]\s*(\d+(?:[.,]\d+)?)\s*(?:m\s*)?[x×]\s*(\d+(?:[.,]\d+)?)",
        normalized,
    )
    if dimension_match:
        length, width, height = (value.replace(",", ".") for value in dimension_match.groups())
        state["room"].update({"length_m": length, "width_m": width, "height_m": height})

    color_words = {
        "weiss": "#f3f4f2", "white": "#f3f4f2", "سفید": "#f3f4f2",
        "schwarz": "#20242a", "black": "#20242a", "مشکی": "#20242a",
        "anthrazit": "#3d434b", "grau": "#aeb5bd", "grey": "#aeb5bd", "خاکستری": "#aeb5bd",
        "beige": "#d9cdbd", "sand": "#d9cdbd", "کرم": "#d9cdbd",
        "blau": "#5b7fa3", "blue": "#5b7fa3", "آبی": "#5b7fa3",
        "gruen": "#6c8b73", "green": "#6c8b73", "سبز": "#6c8b73",
        "holz": "#75533b", "wood": "#75533b", "چوب": "#75533b",
        "beton": "#aeb5bd", "concrete": "#aeb5bd",
    }

    def nearby_color(surface_words: tuple[str, ...], fallback_key: str):
        for surface in surface_words:
            position = normalized.find(surface)
            if position < 0:
                continue
            start, end = max(0, position - 35), min(len(normalized), position + 70)
            candidates = []
            for word, color in color_words.items():
                word_position = normalized.find(word, start, end)
                if word_position >= 0:
                    candidates.append((abs(word_position - position), color))
            if candidates:
                materials[fallback_key] = min(candidates, key=lambda item: item[0])[1]
                return

    nearby_color(("boden", "floor", "کف"), "floor")
    nearby_color(("wand", "waende", "wall", "دیوار"), "wall")
    nearby_color(("decke", "ceiling", "سقف"), "ceiling")
    for word, color in color_words.items():
        if word in normalized and any(token in normalized for token in ("akzent", "accent", "تاکیدی")):
            materials["accent"] = color
            break

    if "fischgraet" in normalized or "herringbone" in normalized or "جناغ" in normalized:
        materials["pattern"] = "herringbone"
    elif "diagonal" in normalized or "مورب" in normalized:
        materials["pattern"] = "diagonal"
    elif "gerade" in normalized or "straight" in normalized:
        materials["pattern"] = "straight"

    tile_match = re.search(r"(\d+(?:[.,]\d+)?)\s*[x×]\s*(\d+(?:[.,]\d+)?)\s*(?:cm|zentimeter)", normalized)
    if tile_match:
        materials["tile_width_cm"], materials["tile_height_cm"] = (value.replace(",", ".") for value in tile_match.groups())

    def metric_value(value: str, unit: str) -> str:
        amount = Decimal(value.replace(",", "."))
        if unit.startswith("cm") or unit.startswith("zentimeter"):
            amount = amount / Decimal("100")
        return str(amount.normalize())

    def entity_dimensions(entity_words: tuple[str, ...], stop_words: tuple[str, ...]) -> dict:
        positions = [normalized.find(word) for word in entity_words if normalized.find(word) >= 0]
        if not positions:
            return {}
        start = min(positions)
        end = min([pos for word in stop_words if (pos := normalized.find(word, start + 2)) >= 0] or [min(len(normalized), start + 260)])
        segment = normalized[start:end]
        result = {}
        for key, labels in (("width_m", ("breite", "width")), ("height_m", ("hoehe", "height"))):
            for label in labels:
                match = re.search(rf"{label}(?:\s+des?\s+\w+)?(?:\s+von|\s+ist|\s+betragt|\s+betraegt|\s+mit\s+einer)?\s*[:=]?\s*(\d+(?:[.,]\d+)?)\s*(m(?:eter)?|cm|zentimeter)", segment)
                if match:
                    result[key] = metric_value(match.group(1), match.group(2))
                    break
        # Common compact phrasing: "Fenster 1 x 1,5 m".
        compact = re.search(r"(\d+(?:[.,]\d+)?)\s*[x×]\s*(\d+(?:[.,]\d+)?)\s*(m(?:eter)?|cm|zentimeter)", segment)
        if compact:
            result.setdefault("width_m", metric_value(compact.group(1), compact.group(3)))
            result.setdefault("height_m", metric_value(compact.group(2), compact.group(3)))
        return result

    def upsert_opening(kind: str, values: dict, wall: str, defaults: dict):
        if not values and not any(word in normalized for word in (("fenster", "window") if kind == "window" else ("tuer", "tur", "door"))):
            return
        opening = next((item for item in state["openings"] if isinstance(item, dict) and item.get("kind") == kind), None)
        if opening is None:
            opening = {"id": f"opening-{kind}", "kind": kind}
            state["openings"].append(opening)
        opening.update(defaults)
        opening.update(values)
        opening["wall"] = wall
        span = Decimal(str(state["room"].get("length_m") if wall in {"back", "front"} else state["room"].get("width_m") or "3"))
        width = Decimal(str(opening.get("width_m") or defaults["width_m"]))
        opening["offset_m"] = str(max(Decimal("0"), (span - width) / Decimal("2")).quantize(Decimal("0.01")))

    surface_boundaries = ("waende", "wand", "boden", "fliese", "fliesen", "decke", "wall", "floor", "tile", "tiles")
    window_values = entity_dimensions(("fenster", "window"), ("tuer", "tur", "door", *surface_boundaries))
    door_values = entity_dimensions(("tuer", "tur", "door"), ("fenster", "window", *surface_boundaries))
    has_window = any(word in normalized for word in ("fenster", "window"))
    has_door = any(word in normalized for word in ("tuer", "tur", "door"))
    window_wall = "back"
    door_wall = "front" if has_window and has_door and any(word in normalized for word in ("gegenueber", "gegenuber", "opposite")) else "back"
    if has_window:
        upsert_opening("window", window_values, window_wall, {"width_m": "1.2", "height_m": "1", "sill_m": "0.9"})
    if has_door:
        upsert_opening("door", door_values, door_wall, {"width_m": "0.9", "height_m": "2", "sill_m": "0"})

    if any(word in normalized for word in ("heller", "bright", "روشن")):
        lighting["brightness"] = "1.25"
    if any(word in normalized for word in ("dunkler", "dark", "تیره")):
        lighting["brightness"] = "0.75"
    if any(word in normalized for word in ("warm", "waermer", "گرم")):
        lighting["warmth"] = "75"
    if any(word in normalized for word in ("kalt", "cool", "سرد")):
        lighting["warmth"] = "15"

    fixture_specs = {
        "shower": (("dusche", "shower", "دوش"), "#9fd8ee", ("1.2", "0.9", "2.1")),
        "vanity": (("waschtisch", "vanity", "روشویی"), "#d9d0c5", ("0.9", "0.5", "0.85")),
        "toilet": (("toilette", "wc", "toilet", "توالت"), "#f6f7f8", ("0.4", "0.7", "0.8")),
        "bathtub": (("badewanne", "bathtub", "وان"), "#f2f4f6", ("1.7", "0.75", "0.6")),
        "radiator": (("heizkoerper", "radiator", "رادیاتور"), "#e9ecef", ("0.8", "0.15", "0.7")),
        "cabinet": (("schrank", "cabinet", "کمد"), "#8a6a4d", ("0.8", "0.45", "1.8")),
    }
    existing = {item.get("kind") for item in state["objects"] if isinstance(item, dict)}
    for kind, (keywords, color, dimensions) in fixture_specs.items():
        if any(keyword in normalized for keyword in keywords) and kind not in existing:
            width, depth, height = dimensions
            state["objects"].append({
                "id": f"fixture-{kind}", "kind": kind, "x_m": "0.5", "z_m": "0.5",
                "width_m": width, "depth_m": depth, "height_m": height,
                "rotation_deg": "0", "color": color, "enabled": True,
            })

    return state


@login_required
@require_POST
def project_room_model_suggestions(request):
    _require_write(request)
    if role_for(request.user) == "technician":
        raise PermissionDenied
    try:
        payload = json.loads(request.body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return JsonResponse({"error": "Ungültige JSON-Daten."}, status=400)
    prompt = str(payload.get("prompt") or "").strip()
    if len(prompt) < 3:
        return JsonResponse({"error": "Bitte die gewünschte Änderung etwas genauer beschreiben."}, status=400)
    raw_state = payload.get("state") if isinstance(payload.get("state"), dict) else {}
    room = raw_state.get("room") if isinstance(raw_state.get("room"), dict) else {}
    measurement = RoomMeasurement(
        length_m=room.get("length_m") or Decimal("4"),
        width_m=room.get("width_m") or Decimal("3"),
        height_m=room.get("height_m") or Decimal("2.5"),
    )
    try:
        current_state = normalize_room_model_state(raw_state or initial_room_model_state(measurement), measurement)
    except ValidationError as exc:
        return JsonResponse({"error": "Der aktuelle Modellzustand ist ungültig.", "details": exc.message_dict}, status=400)

    warnings = []
    try:
        result = suggest_room_model_state(_organization(request), prompt, current_state)
        candidate = result.get("state")
        if not isinstance(candidate, dict):
            raise ValueError("AI returned no room state")
        # Apply deterministic metric parsing after AI. Explicit German sizes,
        # decimal commas and opposite-wall relations must win over a vague model
        # interpretation and may never destroy the current state.
        candidate = _room_model_fallback(prompt, candidate)
        summary = str(result.get("summary") or "Modelländerungen vorbereitet.")
        warnings.extend(str(item) for item in result.get("warnings", []) if item)
    except Exception:
        candidate = _room_model_fallback(prompt, current_state)
        summary = "Änderungen wurden direkt aus der Beschreibung übernommen."
        warnings.append("Die KI war nicht erreichbar; es wurde eine lokale Regelanalyse verwendet.")
    try:
        state = normalize_room_model_state(candidate, measurement)
    except ValidationError as exc:
        return JsonResponse({"error": "Die vorgeschlagenen Modellwerte sind ungültig.", "details": exc.message_dict}, status=400)
    return JsonResponse({"summary": summary, "warnings": warnings, "state": state})


@login_required
@require_POST
def project_wizard_price_preview(request):
    """Resolve all selected wizard positions using the chosen commercial source."""
    if not can_view_prices(request.user):
        raise PermissionDenied("Mitarbeiter dürfen keine Preise oder Finanzdaten sehen.")
    _require_write(request)
    org = _organization(request)
    source_id = (request.POST.get("price_source") or "").strip()
    selected_ids = []
    for key in ("services", "materials"):
        selected_ids.extend(request.POST.getlist(key))
    catalog_items = list(
        CatalogItem.objects.filter(organization=org, active=True, pk__in=selected_ids)
        .only("id", "code", "kind", "unit", "sales_price", "purchase_price")
    )
    source = None
    source_by_code = {}
    if source_id:
        source = get_object_or_404(commercial_price_sources(org), pk=source_id)
        if is_material_only_source(source):
            return JsonResponse({"error": "Lieferantenlisten sind keine Angebots-Preisbasis."}, status=400)
        source_by_code = {
            item.code.casefold(): item
            for item in PriceItem.objects.filter(organization=org, source=source, active=True).exclude(code="")
        }

    selected_price_item_ids = request.POST.getlist("price_items")
    price_items = []
    if selected_price_item_ids:
        if not source:
            return JsonResponse({"error": "Für Preislistenpositionen bitte zuerst eine Preisliste wählen."}, status=400)
        price_items = list(
            PriceItem.objects.filter(
                organization=org,
                source=source,
                active=True,
                pk__in=selected_price_item_ids,
            ).only("id", "code", "description", "unit", "sales_price", "purchase_price")
        )

    resolved = []
    priced_count = 0
    unresolved_count = 0
    for item in catalog_items:
        source_item = source_by_code.get((item.code or "").casefold())
        price = resolved_item_price(source_item) if source_item else (item.sales_price if item.sales_price and item.sales_price > 0 else None)
        if price is None:
            unresolved_count += 1
        else:
            priced_count += 1
        resolved.append({
            "selection_type": "catalog",
            "catalog_id": item.pk,
            "price": str(price) if price is not None else None,
            "cost": str(item.purchase_price or Decimal("0")),
            "unit": (source_item.unit if source_item else item.unit) or "Stk.",
            "source": source.name if source else "Katalog",
            "source_code": source_item.code if source_item else item.code,
        })

    for item in price_items:
        price = resolved_item_price(item)
        if price is None:
            unresolved_count += 1
        else:
            priced_count += 1
        resolved.append({
            "selection_type": "price_item",
            "price_item_id": item.pk,
            "price": str(price) if price is not None else None,
            "cost": "0",
            "unit": item.unit or "Stk.",
            "source": source.name if source else None,
            "source_code": item.code,
        })
    return JsonResponse({
        "price_source": source.name if source else None,
        "priced_count": priced_count,
        "unresolved_count": unresolved_count,
        "items": resolved,
    })


@login_required
@require_http_methods(["GET", "POST"])
def project_wizard(request):
    _require_write(request)
    if role_for(request.user) == "technician":
        raise PermissionDenied
    org = _organization(request)
    initial = {
        "title": request.GET.get("title", "Badsanierung"),
        "project_type": request.GET.get("type", "bathroom"),
        "waste_percent": Decimal("10"),
    }
    form = ProjectWizardForm(request.POST or None, organization=org, initial=initial)
    preview_measurement = RoomMeasurement(length_m=Decimal("4"), width_m=Decimal("3"), height_m=Decimal("2.5"))
    wizard_model_state = initial_room_model_state(preview_measurement)
    posted_model_state = _safe_json(request.POST.get("room_model_state"), {}) if request.method == "POST" else {}
    if isinstance(posted_model_state, dict) and posted_model_state:
        wizard_model_state = posted_model_state
    normalized_model_state = None
    if request.method == "POST" and form.is_valid():
        uploaded_images = request.FILES.getlist("room_photos")
        order_pdf = request.FILES.get("bando_order_pdf")
        if order_pdf:
            try:
                validate_upload(order_pdf)
                if not order_pdf.name.lower().endswith(".pdf"):
                    raise ValueError("Für den B&O-/Versicherungsauftrag bitte eine PDF-Datei verwenden.")
            except (ValueError, TypeError) as exc:
                form.add_error(None, str(exc))
        model_touched = request.POST.get("room_model_touched") == "1"
        if model_touched:
            data = form.cleaned_data
            model_measurement = RoomMeasurement(
                length_m=data.get("length_m") or Decimal("4"),
                width_m=data.get("width_m") or Decimal("3"),
                height_m=data.get("height_m") or Decimal("2.5"),
            )
            try:
                normalized_model_state = normalize_room_model_state(posted_model_state, model_measurement)
                wizard_model_state = normalized_model_state
            except ValidationError as exc:
                form.add_error(None, f"3D-Modell konnte nicht übernommen werden: {exc}")
        for upload in uploaded_images:
            if upload.size > 12 * 1024 * 1024 or getattr(upload, "content_type", "") not in {"image/jpeg", "image/png", "image/webp"}:
                form.add_error(None, f"{upload.name}: Bitte ein unterstütztes Bild bis 12 MB verwenden.")
        if not form.errors:
            model_revision = None
            with transaction.atomic():
                data = form.cleaned_data
                project = Project.objects.create(
                    organization=org,
                    number=next_number(org, "project"),
                    title=data["title"],
                    job_type=data.get("job_type") or Project.JobType.PRIVATE,
                    price_source=data.get("price_source"),
                    customer=data["customer"],
                    object_location=data.get("object_location"),
                    manager=data.get("manager"),
                    status=Project.Status.INQUIRY if request.POST.get("action") in {"draft", "scan"} else Project.Status.PLANNING,
                    priority=data["priority"],
                    description=data.get("description", ""),
                    internal_notes=f"Projektvorlage: {dict(ProjectWizardForm.PROJECT_TYPES).get(data['project_type'], data['project_type'])}",
                    planned_start=data.get("planned_start"),
                    planned_end=data.get("planned_end"),
                    budget=data.get("budget") or Decimal("0"),
                )
                project.members.set(data.get("members") or [])
                order_document = None
                if order_pdf:
                    project.job_type = Project.JobType.INSURANCE
                    if not project.price_source:
                        project.price_source = preferred_price_source(org, Project.JobType.INSURANCE)
                    project.save(update_fields=["job_type", "price_source", "updated_at"] if project.price_source else ["job_type", "updated_at"])
                    order_document = Document.objects.create(
                        organization=org,
                        project=project,
                        customer=project.customer,
                        title=f"B&O Auftrag · {order_pdf.name}",
                        category=Document.Category.CONTRACT,
                        file=order_pdf,
                        uploaded_by=request.user,
                        metadata={"source_order": True, "provider": "B&O", "created_in_project_wizard": True},
                    )
                    try:
                        order_document.extracted_text = extract_text(order_document.file.path)
                    except Exception as exc:
                        order_document.extracted_text = ""
                        order_document.metadata = {**order_document.metadata, "extraction_warning": str(exc)[:500]}
                    order_document.save(update_fields=["extracted_text", "metadata", "updated_at"])
                new_employee_name = (data.get("new_employee_name") or "").strip()
                if new_employee_name:
                    parts = new_employee_name.split(None, 1)
                    employee_email = data.get("new_employee_email") or ""
                    employee_user = None
                    if employee_email:
                        employee_user = User.objects.create(
                            username=_unique_employee_username(employee_email, parts[0], parts[1] if len(parts) > 1 else ""),
                            email=employee_email,
                            first_name=parts[0],
                            last_name=parts[1] if len(parts) > 1 else "",
                        )
                        employee_user.set_unusable_password()
                        employee_user.save(update_fields=["password"])
                        UserProfile.objects.update_or_create(
                            user=employee_user,
                            defaults={"organization": org, "role": UserProfile.Role.TECHNICIAN, "is_mobile_worker": True},
                        )
                    new_employee = Employee.objects.create(
                        organization=org,
                        user=employee_user,
                        employee_number=next_number(org, "employee"),
                        first_name=parts[0],
                        last_name=parts[1] if len(parts) > 1 else "",
                        email=employee_email,
                        can_view_prices=False,
                    )
                    project.members.add(new_employee)
                measurement = None
                model_dimensions = normalized_model_state.get("room", {}) if normalized_model_state else {}
                if all(data.get(key) is not None for key in ("length_m", "width_m", "height_m")) or uploaded_images or normalized_model_state:
                    measurement = RoomMeasurement.objects.create(
                        organization=org,
                        project=project,
                        name=data.get("room_name") or "Raum",
                        method=data.get("measurement_method") or RoomMeasurement.Method.MANUAL,
                        status=RoomMeasurement.Status.REVIEW if data.get("measurement_method") != RoomMeasurement.Method.MANUAL else RoomMeasurement.Status.DRAFT,
                        length_m=Decimal(model_dimensions["length_m"]) if normalized_model_state else data.get("length_m"),
                        width_m=Decimal(model_dimensions["width_m"]) if normalized_model_state else data.get("width_m"),
                        height_m=Decimal(model_dimensions["height_m"]) if normalized_model_state else data.get("height_m"),
                        deductions_area_m2=opening_area(normalized_model_state) if normalized_model_state else (data.get("deductions_area_m2") or Decimal("0")),
                        waste_percent=data.get("waste_percent") or Decimal("10"),
                        confidence=min(Decimal("1"), max(Decimal("0"), Decimal(str(request.POST.get("measurement_confidence") or "0")))),
                        reference_type=data.get("reference_type") or "",
                        reference_width_cm=data.get("reference_width_cm"),
                        reference_height_cm=data.get("reference_height_cm"),
                        ai_summary=request.POST.get("measurement_ai_summary", ""),
                        ai_warnings=_safe_json(request.POST.get("measurement_ai_warnings"), []),
                        ai_payload=_safe_json(request.POST.get("measurement_ai_payload"), {}),
                        created_by=request.user,
                    )
                    capture_kinds = list(MeasurementCapture.Kind.values)
                    for index, upload in enumerate(uploaded_images):
                        MeasurementCapture.objects.create(
                            measurement=measurement,
                            kind=capture_kinds[index] if index < len(capture_kinds) else MeasurementCapture.Kind.OTHER,
                            image=upload,
                            created_by=request.user,
                        )
                    if normalized_model_state:
                        model_revision = RoomModelRevision.objects.create(
                            organization=org,
                            project=project,
                            measurement=measurement,
                            revision=1,
                            label="Projektassistent · bearbeiteter Ausgangsstand",
                            state=normalized_model_state,
                            created_by=request.user,
                        )
                for item in data.get("materials") or []:
                    ProjectMaterial.objects.create(
                        project=project,
                        catalog_item=item,
                        name=item.name,
                        quantity=1,
                        unit=item.unit,
                        unit_cost=item.purchase_price,
                        unit_price=item.sales_price,
                    )
                quote = None
                selected_items = list(data.get("services") or []) + list(data.get("materials") or [])
                selected_price_items = list(data.get("price_items") or [])
                skipped_zero_items = 0
                if request.POST.get("action") == "quote" and (selected_items or selected_price_items):
                    source_items = {}
                    if project.price_source_id:
                        source_items = {
                            price_item.code.casefold(): price_item
                            for price_item in PriceItem.objects.filter(
                                organization=org,
                                source=project.price_source,
                                active=True,
                            ).exclude(code="")
                        }
                    prepared_items = []
                    for item in selected_items:
                        source_item = source_items.get((item.code or "").casefold())
                        price = resolved_item_price(source_item) if source_item else (item.sales_price if item.sales_price and item.sales_price > 0 else None)
                        if price is None:
                            skipped_zero_items += 1
                            continue
                        prepared_items.append({
                            "catalog_item": item,
                            "source_item": source_item,
                            "code": source_item.code if source_item else item.code,
                            "description": source_item.description if source_item else (item.description or item.name),
                            "quantity": quantity_for_price_item(source_item, measurement) if source_item and measurement else Decimal("1"),
                            "unit": (source_item.unit if source_item else item.unit) or "Stk.",
                            "unit_price": price,
                            "tax_rate": source_item.tax_rate if source_item else item.tax_rate,
                        })
                    for source_item in selected_price_items:
                        if not project.price_source_id or source_item.source_id != project.price_source_id:
                            skipped_zero_items += 1
                            continue
                        price = resolved_item_price(source_item)
                        if price is None:
                            skipped_zero_items += 1
                            continue
                        prepared_items.append({
                            "catalog_item": None,
                            "source_item": source_item,
                            "code": source_item.code,
                            "description": source_item.description or source_item.code,
                            "quantity": quantity_for_price_item(source_item, measurement) if measurement else Decimal("1"),
                            "unit": source_item.unit or "Stk.",
                            "unit_price": price,
                            "tax_rate": source_item.tax_rate,
                        })
                    if prepared_items:
                        quote = Quote.objects.create(
                            organization=org,
                            project=project,
                            number=next_number(org, "quote"),
                            status=Quote.Status.REVIEW,
                            intro_text=(
                                f"Automatisch aus dem Projektassistenten erstellt. Preisgrundlage: {project.price_source}. Bitte Positionen prüfen."
                                if project.price_source_id else
                                "Automatisch aus dem Projektassistenten erstellt. Bitte Positionen prüfen."
                            ),
                            created_by=request.user,
                        )
                        for position, prepared in enumerate(prepared_items, start=1):
                            QuoteItem.objects.create(
                                quote=quote,
                                position=position,
                                catalog_item=prepared["catalog_item"],
                                code=prepared["code"],
                                description=prepared["description"],
                                quantity=prepared["quantity"],
                                unit=prepared["unit"],
                                unit_price=prepared["unit_price"],
                                tax_rate=prepared["tax_rate"],
                                approved=True,
                            )
                ActivityLog.objects.create(
                    organization=org,
                    user=request.user,
                    verb="project_wizard_created",
                    entity_type="project",
                    entity_id=str(project.pk),
                    description=f"Projekt {project.number} über den 9-Schritte-Assistenten angelegt.",
                    metadata={
                        "measurement_id": measurement.pk if measurement else None,
                        "model_revision_id": model_revision.pk if model_revision else None,
                        "quote_id": quote.pk if quote else None,
                    },
                )
            if request.POST.get("action") == "scan":
                messages.success(request, "Projekt gespeichert. Jetzt den Raum einmal mit der A+Bau App erfassen.")
                scan_url = reverse("room-measurement-create", kwargs={"project_pk": project.pk})
                return redirect(f"{scan_url}?scan=1")
            if skipped_zero_items:
                messages.warning(request, f"{skipped_zero_items} Positionen ohne belastbaren Preis wurden nicht in das Angebot übernommen.")
            messages.success(request, "Projekt wurde angelegt. Die nächsten Schritte sind direkt in der Projektakte sichtbar.")
            if order_pdf or request.POST.get("action") in {"quote", "pricing"}:
                return redirect("quote-detail", pk=quote.pk) if quote else redirect("project-pricing", pk=project.pk)
            return redirect("project-detail", pk=project.pk)
    return render(request, "erp/project_wizard.html", {"form": form, "wizard_model_state": wizard_model_state})


@login_required
@require_http_methods(["GET", "POST"])
def room_measurement(request, project_pk, measurement_pk=None):
    org = _organization(request)
    project = get_object_or_404(_projects_for_user(request, org), pk=project_pk)
    measurement = None
    if measurement_pk:
        measurement = get_object_or_404(RoomMeasurement, organization=org, project=project, pk=measurement_pk)
    form = RoomMeasurementForm(request.POST or None, instance=measurement)
    if request.method == "POST":
        _require_write(request)
        if form.is_valid():
            measurement = form.save(commit=False)
            measurement.organization = org
            measurement.project = project
            measurement.created_by = measurement.created_by or request.user
            measurement.confidence = min(Decimal("1"), max(Decimal("0"), Decimal(str(request.POST.get("confidence") or measurement.confidence or 0))))
            measurement.ai_summary = request.POST.get("ai_summary", measurement.ai_summary)
            measurement.ai_warnings = _safe_json(request.POST.get("ai_warnings"), measurement.ai_warnings or [])
            measurement.ai_payload = _safe_json(request.POST.get("ai_payload"), measurement.ai_payload or {})
            measurement.status = RoomMeasurement.Status.REVIEW if measurement.method != RoomMeasurement.Method.MANUAL else measurement.status
            measurement.save()
            for upload in request.FILES.getlist("room_photos"):
                if upload.size <= 12 * 1024 * 1024 and getattr(upload, "content_type", "") in {"image/jpeg", "image/png", "image/webp"}:
                    MeasurementCapture.objects.create(measurement=measurement, image=upload, created_by=request.user)
            messages.success(request, "Aufmaß wurde gespeichert. KI-Werte bleiben bis zur Bestätigung als Entwurf markiert.")
            return redirect("room-measurement-edit", project_pk=project.pk, measurement_pk=measurement.pk)
    return render(request, "erp/room_measurement.html", {
        "project": project,
        "measurement": measurement,
        "form": form,
        "captures": measurement.captures.all() if measurement else [],
        "native_scans": project.native_room_scans.select_related("measurement").all(),
        "ai_warnings_json": json.dumps(measurement.ai_warnings if measurement else [], ensure_ascii=False),
        "ai_payload_json": json.dumps(measurement.ai_payload if measurement else {}, ensure_ascii=False),
    })


@login_required
@require_POST
def room_measurement_confirm(request, project_pk, measurement_pk):
    _require_write(request)
    org = _organization(request)
    project = get_object_or_404(_projects_for_user(request, org), pk=project_pk)
    measurement = get_object_or_404(RoomMeasurement, organization=org, project=project, pk=measurement_pk)
    if None in (measurement.length_m, measurement.width_m, measurement.height_m):
        messages.error(request, "Länge, Breite und Höhe müssen vor der Bestätigung geprüft werden.")
    else:
        measurement.status = RoomMeasurement.Status.CONFIRMED
        measurement.confirmed_by = request.user
        measurement.confirmed_at = timezone.now()
        measurement.save(update_fields=["status", "confirmed_by", "confirmed_at", "updated_at"])
        if hasattr(measurement, "native_scan"):
            native_scan = measurement.native_scan
            native_scan.status = NativeRoomScan.Status.CONFIRMED
            native_scan.confirmed_by = request.user
            native_scan.confirmed_at = measurement.confirmed_at
            native_scan.save(update_fields=["status", "confirmed_by", "confirmed_at", "updated_at"])
        messages.success(request, "Aufmaß wurde durch einen Benutzer bestätigt.")
    return redirect("room-measurement-edit", project_pk=project_pk, measurement_pk=measurement_pk)


@login_required
def configurator(request):
    org = _organization(request)
    project_id = request.GET.get("project")
    measurement_id = request.GET.get("measurement")
    revision_id = request.GET.get("revision")
    projects = _projects_for_user(request, org, Project.objects.filter(organization=org, archived=False).select_related("customer"))
    selected_project = projects.filter(pk=project_id).first() if project_id else projects.first()
    measurements = RoomMeasurement.objects.filter(organization=org).select_related("project")
    if selected_project:
        measurements = measurements.filter(project=selected_project)
    selected_measurement = measurements.filter(pk=measurement_id).first() if measurement_id else measurements.first()
    selected_native_scan = getattr(selected_measurement, "native_scan", None) if selected_measurement else None
    revisions = RoomModelRevision.objects.none()
    selected_revision = None
    model_state = None
    if selected_measurement:
        revisions = RoomModelRevision.objects.filter(organization=org, measurement=selected_measurement).select_related("created_by", "source_scan")
        selected_revision = revisions.filter(pk=revision_id).first() if revision_id else revisions.first()
        model_state = selected_revision.state if selected_revision else initial_room_model_state(selected_measurement, selected_native_scan)
    return render(request, "erp/configurator.html", {
        "projects": projects,
        "selected_project": selected_project,
        "measurements": measurements,
        "selected_measurement": selected_measurement,
        "selected_native_scan": selected_native_scan,
        "model_revisions": revisions,
        "selected_revision": selected_revision,
        "model_state": model_state,
    })


@login_required
@require_POST
def configurator_model_save(request):
    _require_write(request)
    org = _organization(request)
    try:
        payload = json.loads(request.body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return JsonResponse({"error": "Ungültige JSON-Daten."}, status=400)
    measurement_id = payload.get("measurement_id")
    measurement = get_object_or_404(
        RoomMeasurement.objects.select_related("project"),
        organization=org,
        pk=measurement_id,
    )
    if not _projects_for_user(request, org).filter(pk=measurement.project_id).exists():
        raise PermissionDenied
    scan = getattr(measurement, "native_scan", None)
    try:
        state = normalize_room_model_state(payload.get("state"), measurement, scan)
    except ValidationError as exc:
        return JsonResponse({"error": "Modell konnte nicht gespeichert werden.", "details": exc.message_dict}, status=400)

    with transaction.atomic():
        measurement = RoomMeasurement.objects.select_for_update().get(pk=measurement.pk, organization=org)
        next_revision = (RoomModelRevision.objects.filter(measurement=measurement).aggregate(value=Max("revision"))["value"] or 0) + 1
        revision = RoomModelRevision.objects.create(
            organization=org,
            project=measurement.project,
            measurement=measurement,
            source_scan=scan,
            revision=next_revision,
            label=str(payload.get("label") or "").strip()[:160],
            state=state,
            created_by=request.user,
        )
        dimensions = state["room"]
        new_values = {
            "length_m": Decimal(dimensions["length_m"]),
            "width_m": Decimal(dimensions["width_m"]),
            "height_m": Decimal(dimensions["height_m"]),
            "deductions_area_m2": opening_area(state),
        }
        geometry_changed = any(getattr(measurement, field) != value for field, value in new_values.items())
        for field, value in new_values.items():
            setattr(measurement, field, value)
        update_fields = [*new_values.keys(), "updated_at"]
        if geometry_changed and measurement.status == RoomMeasurement.Status.CONFIRMED:
            measurement.status = RoomMeasurement.Status.REVIEW
            measurement.confirmed_by = None
            measurement.confirmed_at = None
            update_fields.extend(["status", "confirmed_by", "confirmed_at"])
        measurement.save(update_fields=update_fields)

    return JsonResponse({
        "saved": True,
        "revision": revision.revision,
        "revision_id": revision.pk,
        "measurement_status": measurement.status,
        "measurement_status_label": measurement.get_status_display(),
        "deductions_area_m2": str(measurement.deductions_area_m2),
    }, status=201)


@login_required
@require_http_methods(["GET", "POST"])
def model_form(request, resource, pk=None):
    _require_write(request)
    if role_for(request.user) == "technician" and resource not in {"time", "document"}:
        raise PermissionDenied("Mitarbeiter dürfen nur Zeiten und Baustellendokumente erfassen.")
    org = _organization(request)
    if resource not in FORM_CONFIG:
        raise Http404
    model, form_class, label, list_resource = FORM_CONFIG[resource]
    instance = None
    if pk:
        filters = {"pk": pk}
        if hasattr(model, "organization"):
            filters["organization"] = org
        elif model is ProjectMaterial:
            filters["project__organization"] = org
        instance = get_object_or_404(model, **filters)
        if role_for(request.user) == UserProfile.Role.TECHNICIAN:
            employee = getattr(request.user, "employee", None)
            if isinstance(instance, Document):
                allowed = instance.project_id and _projects_for_user(request, org).filter(pk=instance.project_id).exists()
                if not allowed:
                    raise PermissionDenied
            if isinstance(instance, TimeEntry) and instance.employee_id != getattr(employee, "pk", None):
                raise PermissionDenied
    form = form_class(request.POST or None, request.FILES or None, instance=instance, organization=org, user=request.user)
    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False)
        if hasattr(obj, "organization_id") and not obj.organization_id:
            obj.organization = org
        if not instance:
            if isinstance(obj, Customer):
                obj.number = next_number(org, "customer")
            elif isinstance(obj, Project):
                obj.number = next_number(org, "project")
            elif isinstance(obj, Employee):
                obj.employee_number = next_number(org, "employee")
            elif isinstance(obj, Supplier):
                obj.number = next_number(org, "supplier")
            elif isinstance(obj, Document):
                obj.uploaded_by = request.user
            elif isinstance(obj, CalendarEvent):
                obj.created_by = request.user
        if isinstance(obj, TimeEntry) and obj.employee.user_id != request.user.id and not request.user.is_superuser:
            profile = getattr(request.user, "profile", None)
            if not profile or profile.role not in {"admin", "office", "project_manager"}:
                raise PermissionDenied
        obj.save()
        if hasattr(form, "save_m2m"):
            form.save_m2m()
        if isinstance(obj, CalendarEvent):
            Notification.objects.filter(url=f"/calendar/?event={obj.pk}", read_at__isnull=True).delete()
            for employee in obj.attendees.select_related("user"):
                if not employee.user_id:
                    continue
                reminders = obj.reminder_minutes or [60]
                for minutes in reminders:
                    scheduled = obj.starts_at - timedelta(minutes=int(minutes))
                    Notification.objects.create(
                        user=employee.user,
                        title=f"Termin: {obj.title}",
                        message=f"{obj.starts_at:%d.%m.%Y %H:%M} · {obj.location}",
                        level="info",
                        url=f"/calendar/?event={obj.pk}",
                        scheduled_for=scheduled,
                    )
        if isinstance(obj, Document):
            try:
                obj.extracted_text = extract_text(obj.file.path)
                obj.save(update_fields=["extracted_text", "updated_at"])
            except Exception as exc:
                messages.warning(request, f"Datei gespeichert; Textextraktion nicht möglich: {exc}")
        messages.success(request, f"{label} wurde gespeichert.")
        return redirect("resource-list", resource=list_resource)
    return render(request, "erp/form.html", {"form": form, "title": f"{label} {'bearbeiten' if instance else 'anlegen'}", "instance": instance})


@login_required
def project_detail(request, pk):
    org = _organization(request)
    projects = Project.objects.select_related("customer", "object_location", "manager").filter(organization=org)
    if role_for(request.user) == "technician":
        employee = getattr(request.user, "employee", None)
        projects = projects.filter(Q(members=employee) | Q(manager=employee)).distinct() if employee else projects.none()
    project = get_object_or_404(projects, pk=pk)
    latest_report = project.site_reports.order_by("-created_at", "-pk").first() if hasattr(project, "site_reports") else None
    draft_report = project.site_reports.filter(signed_at__isnull=True).order_by("-created_at", "-pk").first() if hasattr(project, "site_reports") else None
    has_order_pdf = project.documents.filter(metadata__source_order=True).exists()
    return render(request, "erp/project_detail.html", {
        "project": project,
        "tasks": project.tasks.select_related("assigned_to")[:20],
        "events": project.events.all()[:20],
        "documents": project.documents.all()[:20],
        "site_reports": project.site_reports.all()[:20] if hasattr(project, "site_reports") else [],
        "time_entries": project.time_entries.select_related("employee")[:20],
        "quotes": project.quotes.all(),
        "invoices": project.invoices.all(),
        "materials": project.materials.all(),
        "measurements": project.room_measurements.prefetch_related("captures").all(),
        "activities": ActivityLog.objects.filter(organization=org, entity_type="project", entity_id=str(project.pk))[:20],
        "change_orders": project.change_orders.all() if hasattr(project, "change_orders") else [],
        "work_media": project.work_media.all()[:12] if hasattr(project, "work_media") else [],
        "can_view_prices": can_view_prices(request.user),
        "latest_site_report": latest_report,
        "draft_site_report": draft_report,
        "has_order_pdf": has_order_pdf,
    })


@login_required
@require_http_methods(["GET", "POST"])
def quote_edit(request, pk=None):
    if not can_view_prices(request.user):
        raise PermissionDenied("Mitarbeiter dürfen keine Preise oder Finanzdaten sehen.")
    _require_write(request)
    org = _organization(request)
    quote = get_object_or_404(Quote, organization=org, pk=pk) if pk else Quote(organization=org, number=next_number(org, "quote"), created_by=request.user)
    form = QuoteForm(request.POST or None, instance=quote, organization=org, user=request.user)
    formset = QuoteItemFormSet(request.POST or None, instance=quote, prefix="items")
    if request.method == "POST" and form.is_valid() and formset.is_valid():
        with transaction.atomic():
            quote = form.save(commit=False)
            quote.organization = org
            quote.created_by = quote.created_by or request.user
            quote.save()
            formset.instance = quote
            formset.save()
        messages.success(request, "Angebot wurde gespeichert.")
        return redirect("quote-detail", pk=quote.pk)
    return render(request, "erp/document_edit.html", {"title": "Angebot bearbeiten", "form": form, "formset": formset, "document": quote if quote.pk else None, "kind": "quote"})


@login_required
def quote_detail(request, pk):
    if not can_view_prices(request.user):
        raise PermissionDenied("Mitarbeiter dürfen keine Preise oder Finanzdaten sehen.")
    org = _organization(request)
    quote = get_object_or_404(Quote.objects.select_related("project", "project__customer"), organization=org, pk=pk)
    return render(request, "erp/financial_detail.html", {"kind": "quote", "document": quote, "items": quote.items.all()})


@login_required
def quote_pdf(request, pk):
    if not can_view_prices(request.user):
        raise PermissionDenied("Mitarbeiter dürfen keine Preise oder Finanzdaten sehen.")
    quote = get_object_or_404(Quote, organization=_organization(request), pk=pk)
    return HttpResponse(build_quote_pdf(quote), content_type="application/pdf", headers={"Content-Disposition": f'inline; filename="{quote.number}.pdf"'})


@login_required
@require_POST
def quote_to_invoice(request, pk):
    if not can_view_prices(request.user):
        raise PermissionDenied("Mitarbeiter dürfen keine Preise oder Finanzdaten sehen.")
    _require_write(request)
    org = _organization(request)
    quote = get_object_or_404(Quote, organization=org, pk=pk)
    if quote.items.filter(ai_generated=True, approved=False).exists():
        messages.error(request, "KI-generierte Positionen müssen vor der Rechnungsstellung freigegeben werden.")
        return redirect("quote-detail", pk=quote.pk)
    if not quote.items.exists():
        messages.error(request, "Ein leeres Angebot kann nicht in eine Rechnung umgewandelt werden.")
        return redirect("quote-detail", pk=quote.pk)
    due_days = int(org.settings.get("invoice_due_days", 14))
    with transaction.atomic():
        invoice = Invoice.objects.create(
            organization=org,
            project=quote.project,
            quote=quote,
            number=next_number(org, "invoice"),
            issue_date=timezone.localdate(),
            due_date=timezone.localdate() + timedelta(days=due_days),
            intro_text=f"Vielen Dank für Ihren Auftrag zu {quote.project.title}.",
            outro_text="Bitte überweisen Sie den Rechnungsbetrag unter Angabe der Rechnungsnummer.",
            created_by=request.user,
        )
        for item in quote.items.all():
            InvoiceItem.objects.create(invoice=invoice, position=item.position, catalog_item=item.catalog_item, code=item.code, description=item.description, quantity=item.quantity, unit=item.unit, unit_price=item.unit_price, tax_rate=item.tax_rate, ai_generated=item.ai_generated, approved=item.approved)
    messages.success(request, f"Rechnung {invoice.number} wurde aus dem Angebot erstellt.")
    return redirect("invoice-detail", pk=invoice.pk)


@login_required
@require_http_methods(["GET", "POST"])
def invoice_edit(request, pk=None):
    if not can_view_prices(request.user):
        raise PermissionDenied("Mitarbeiter dürfen keine Preise oder Finanzdaten sehen.")
    _require_write(request)
    if not can_manage_finance(request.user):
        raise PermissionDenied
    org = _organization(request)
    invoice = get_object_or_404(Invoice, organization=org, pk=pk) if pk else Invoice(organization=org, number=next_number(org, "invoice"), created_by=request.user, due_date=timezone.localdate() + timedelta(days=int(org.settings.get("invoice_due_days", 14))))
    form = InvoiceForm(request.POST or None, instance=invoice, organization=org, user=request.user)
    formset = InvoiceItemFormSet(request.POST or None, instance=invoice, prefix="items")
    if request.method == "POST" and form.is_valid() and formset.is_valid():
        with transaction.atomic():
            invoice = form.save(commit=False)
            invoice.organization = org
            invoice.created_by = invoice.created_by or request.user
            invoice.save()
            formset.instance = invoice
            formset.save()
        messages.success(request, "Rechnung wurde gespeichert.")
        return redirect("invoice-detail", pk=invoice.pk)
    return render(request, "erp/document_edit.html", {"title": "Rechnung bearbeiten", "form": form, "formset": formset, "document": invoice if invoice.pk else None, "kind": "invoice"})


@login_required
def invoice_detail(request, pk):
    if not can_view_prices(request.user):
        raise PermissionDenied("Mitarbeiter dürfen keine Preise oder Finanzdaten sehen.")
    org = _organization(request)
    invoice = get_object_or_404(Invoice.objects.select_related("project", "project__customer"), organization=org, pk=pk)
    payment_form = PaymentForm(initial={"invoice": invoice, "amount": invoice.outstanding_total}, organization=org, user=request.user)
    return render(request, "erp/financial_detail.html", {"kind": "invoice", "document": invoice, "items": invoice.items.all(), "payment_form": payment_form})


@login_required
def invoice_pdf(request, pk):
    if not can_view_prices(request.user):
        raise PermissionDenied("Mitarbeiter dürfen keine Preise oder Finanzdaten sehen.")
    invoice = get_object_or_404(Invoice, organization=_organization(request), pk=pk)
    return HttpResponse(build_invoice_pdf(invoice), content_type="application/pdf", headers={"Content-Disposition": f'inline; filename="{invoice.number}.pdf"'})


@login_required
@require_POST
def payment_create(request, invoice_pk):
    if not can_view_prices(request.user):
        raise PermissionDenied("Mitarbeiter dürfen keine Preise oder Finanzdaten sehen.")
    _require_write(request)
    if not can_manage_finance(request.user):
        raise PermissionDenied
    invoice = get_object_or_404(Invoice, organization=_organization(request), pk=invoice_pk)
    form = PaymentForm(request.POST, organization=org, user=request.user)
    if form.is_valid():
        payment = form.save(commit=False)
        payment.invoice = invoice
        payment.recorded_by = request.user
        payment.save()
        messages.success(request, "Zahlung wurde verbucht.")
    else:
        messages.error(request, "Zahlung konnte nicht gespeichert werden.")
    return redirect("invoice-detail", pk=invoice.pk)


@login_required
@require_http_methods(["GET", "POST"])
def email_edit(request, pk=None):
    _require_write(request)
    org = _organization(request)
    instance = get_object_or_404(EmailMessage, organization=org, pk=pk) if pk else EmailMessage(organization=org, direction=EmailMessage.Direction.DRAFT, status=EmailMessage.Status.REVIEW)
    form = EmailDraftForm(request.POST or None, instance=instance, organization=org, user=request.user)
    if request.method == "POST" and form.is_valid():
        message = form.save(commit=False)
        message.organization = org
        message.direction = EmailMessage.Direction.DRAFT
        message.status = EmailMessage.Status.REVIEW
        message.approved_by = None
        message.save()
        messages.success(request, "E-Mail-Entwurf gespeichert. Vor Versand ist eine Freigabe erforderlich.")
        return redirect("email-detail", pk=message.pk)
    return render(request, "erp/form.html", {"form": form, "title": "E-Mail-Entwurf", "instance": instance if instance.pk else None})


@login_required
def email_detail(request, pk):
    message = get_object_or_404(EmailMessage, organization=_organization(request), pk=pk)
    return render(request, "erp/email_detail.html", {"email_message": message})


@login_required
@require_POST
def email_approve(request, pk):
    if not can_approve_automation(request.user):
        raise PermissionDenied
    message = get_object_or_404(EmailMessage, organization=_organization(request), pk=pk)
    message.status = EmailMessage.Status.APPROVED
    message.approved_by = request.user
    message.save(update_fields=["status", "approved_by", "updated_at"])
    messages.success(request, "E-Mail wurde freigegeben.")
    return redirect("email-detail", pk=pk)


@login_required
@require_POST
def email_send(request, pk):
    if not can_approve_automation(request.user):
        raise PermissionDenied
    message = get_object_or_404(EmailMessage, organization=_organization(request), pk=pk)
    try:
        send_approved_email(message)
        messages.success(request, "E-Mail wurde versendet.")
    except Exception as exc:
        message.status = EmailMessage.Status.FAILED
        message.save(update_fields=["status", "updated_at"])
        messages.error(request, f"Versand fehlgeschlagen: {exc}")
    return redirect("email-detail", pk=pk)


@login_required
@require_http_methods(["GET", "POST"])
def import_center(request):
    if not can_view_prices(request.user):
        raise PermissionDenied("Mitarbeiter dürfen keine Preise oder Finanzdaten sehen.")
    _require_write(request)
    org = _organization(request)
    result = None
    if request.method == "POST":
        upload = request.FILES.get("file")
        kind = request.POST.get("kind")
        if not upload:
            messages.error(request, "Bitte Datei auswählen.")
        else:
            validate_upload(upload)
            temp_dir = Path("/tmp/kayi-imports")
            temp_dir.mkdir(parents=True, exist_ok=True)
            temp_path = temp_dir / f"{timezone.now().timestamp()}-{Path(upload.name).name}"
            with temp_path.open("wb") as handle:
                for chunk in upload.chunks():
                    handle.write(chunk)
            try:
                if kind == "catalog":
                    result = import_catalog(str(temp_path), org)
                elif kind == "customers":
                    result = import_customers(str(temp_path), org)
                else:
                    result = import_tooltime(str(temp_path), org, request.user)
                messages.success(request, "Import abgeschlossen.")
            except Exception as exc:
                messages.error(request, f"Import fehlgeschlagen: {exc}")
            finally:
                temp_path.unlink(missing_ok=True)
    return render(request, "erp/import_center.html", {"result": result})


@login_required
def ai_workspace(request):
    if role_for(request.user) == "technician":
        raise PermissionDenied
    org = _organization(request)
    conversations = AIConversation.objects.filter(organization=org, user=request.user)[:20]
    projects = Project.objects.filter(organization=org, archived=False)[:100]
    return render(request, "erp/ai_workspace.html", {"conversations": conversations, "projects": projects})


@login_required
@require_POST
def create_ai_suggestions(request, document_pk):
    _require_write(request)
    org = _organization(request)
    document = get_object_or_404(Document, organization=org, pk=document_pk)
    project = document.project
    if not project:
        messages.error(request, "Dokument muss einem Projekt zugeordnet sein.")
        return redirect("resource-list", resource="documents")
    catalog = CatalogItem.objects.filter(organization=org, active=True)[:1000]
    catalog_context = "\n".join(f"{i.code} | {i.name} | {i.unit} | {i.sales_price}" for i in catalog)
    try:
        data = suggest_invoice_items(org, document.extracted_text or "", catalog_context)
    except Exception as exc:
        data = {"summary": "Deterministischer Fallback", "items": build_position_suggestions(document.extracted_text or "", org), "warnings": [str(exc)]}
    job = AutomationJob.objects.create(
        organization=org,
        project=project,
        kind="invoice_item_suggestions",
        status=AutomationJob.Status.REVIEW,
        input_data={"document_id": document.pk},
        output_data=data,
        requested_by=request.user,
    )
    messages.success(request, "Vorschläge wurden erstellt und warten auf menschliche Prüfung.")
    return redirect("automation-detail", pk=job.pk)


@login_required
def automation_detail(request, pk):
    job = get_object_or_404(AutomationJob, organization=_organization(request), pk=pk)
    return render(request, "erp/automation_detail.html", {"job": job})


@login_required
@require_POST
def automation_approve(request, pk):
    if not can_approve_automation(request.user):
        raise PermissionDenied
    job = get_object_or_404(AutomationJob, organization=_organization(request), pk=pk)
    approve_job(job, request.user)
    messages.success(request, "Automation wurde freigegeben.")
    return redirect("automation-detail", pk=pk)


@login_required
@require_POST
def automation_apply(request, pk):
    if not can_approve_automation(request.user):
        raise PermissionDenied
    job = get_object_or_404(AutomationJob, organization=_organization(request), pk=pk, status=AutomationJob.Status.APPROVED)
    if job.kind != "invoice_item_suggestions" or not job.project:
        messages.error(request, "Dieser Job kann nicht auf ein Dokument angewendet werden.")
        return redirect("automation-detail", pk=pk)
    org = job.organization
    quote = Quote.objects.create(organization=org, project=job.project, number=next_number(org, "quote"), status=Quote.Status.REVIEW, intro_text="Auf Grundlage des Arbeitsberichts erstellen wir folgendes Angebot.", created_by=request.user)
    catalog_by_code = {i.code: i for i in CatalogItem.objects.filter(organization=org)}
    for pos, item in enumerate(job.output_data.get("items", []), start=1):
        catalog_item = catalog_by_code.get(str(item.get("code", "")))
        QuoteItem.objects.create(
            quote=quote,
            position=pos,
            catalog_item=catalog_item,
            code=str(item.get("code", "")),
            description=str(item.get("description", "")),
            quantity=Decimal(str(item.get("quantity", 1))),
            unit=str(item.get("unit", "Stk.")),
            unit_price=catalog_item.sales_price if catalog_item else Decimal(str(item.get("unit_price", 0) or 0)),
            ai_generated=True,
            approved=False,
        )
    job.status = AutomationJob.Status.COMPLETED
    job.output_data["quote_id"] = quote.pk
    job.save(update_fields=["status", "output_data", "updated_at"])
    messages.success(request, "Vorschläge wurden als prüfpflichtiger Angebotsentwurf übernommen.")
    return redirect("quote-edit", pk=quote.pk)


@login_required
def reports(request):
    if not can_view_prices(request.user):
        raise PermissionDenied("Mitarbeiter dürfen keine Preise oder Finanzdaten sehen.")
    org = _organization(request)
    today = timezone.localdate()
    year_start = today.replace(month=1, day=1)
    invoices = Invoice.objects.filter(organization=org, issue_date__gte=year_start).select_related("project")
    expenses = Expense.objects.filter(organization=org, expense_date__gte=year_start)
    revenue = sum((x.gross_total for x in invoices), Decimal("0"))
    expense_total = sum((x.amount_gross for x in expenses), Decimal("0"))
    project_rows = []
    for project in Project.objects.filter(organization=org).select_related("customer"):
        billed = sum((i.net_total for i in project.invoices.all()), Decimal("0"))
        costs = project.expenses.aggregate(v=Sum("amount_net"))["v"] or Decimal("0")
        hours = sum((t.duration_hours for t in project.time_entries.all()), Decimal("0"))
        project_rows.append({"project": project, "billed": billed, "costs": costs, "hours": hours, "margin": billed - costs})

    def shift_month(value, delta):
        index = value.year * 12 + value.month - 1 + delta
        return date(index // 12, index % 12 + 1, 1)

    monthly_rows = []
    for offset in range(-5, 1):
        start = shift_month(today.replace(day=1), offset)
        end = shift_month(start, 1)
        month_invoices = Invoice.objects.filter(organization=org, issue_date__gte=start, issue_date__lt=end)
        month_expenses = Expense.objects.filter(organization=org, expense_date__gte=start, expense_date__lt=end)
        month_revenue = sum((item.gross_total for item in month_invoices), Decimal("0"))
        month_cost = sum((item.amount_gross for item in month_expenses), Decimal("0"))
        monthly_rows.append({"label": start.strftime("%b"), "revenue": month_revenue, "expenses": month_cost})
    chart_max = max([row["revenue"] for row in monthly_rows] + [row["expenses"] for row in monthly_rows] + [Decimal("1")])
    for row in monthly_rows:
        row["revenue_pct"] = int(row["revenue"] / chart_max * 100)
        row["expense_pct"] = int(row["expenses"] / chart_max * 100)

    project_statuses = list(Project.objects.filter(organization=org, archived=False).values("status").annotate(count=Count("id")))
    status_total = sum(row["count"] for row in project_statuses) or 1
    status_labels = dict(Project.Status.choices)
    for row in project_statuses:
        row["label"] = status_labels.get(row["status"], row["status"])
        row["percent"] = round(row["count"] / status_total * 100, 1)

    return render(request, "erp/reports.html", {
        "revenue": revenue,
        "expense_total": expense_total,
        "profit": revenue - expense_total,
        "project_rows": project_rows,
        "monthly_rows": monthly_rows,
        "project_statuses": project_statuses,
    })


@login_required
def settings_page(request):
    org = _organization(request)
    integrations = {i.provider: i for i in IntegrationConfig.objects.filter(organization=org)}
    return render(request, "erp/settings.html", {
        "organization": org,
        "integrations": integrations,
        "integration_cards": integration_cards(org),
    })


@login_required
@require_POST
def integration_toggle(request, provider):
    if not request.user.is_superuser and getattr(request.user.profile, "role", "") != "admin":
        raise PermissionDenied
    if provider not in set(IntegrationConfig.Provider.values):
        raise Http404
    org = _organization(request)
    integration, _ = IntegrationConfig.objects.get_or_create(organization=org, provider=provider)
    if not integration_available(provider):
        messages.warning(request, f"{integration.get_provider_display()} ist noch nicht für den Live-Betrieb freigegeben.")
        return redirect(f"{reverse('settings')}#integrations")
    if integration.enabled:
        integration.enabled = False
        integration.save(update_fields=["enabled", "updated_at"])
        messages.success(request, f"{integration.get_provider_display()} wurde deaktiviert.")
        return redirect(f"{reverse('settings')}#integrations")
    if not integration_configured(org, provider, integration):
        messages.error(request, f"{integration.get_provider_display()} kann erst aktiviert werden, wenn die Einrichtung vollständig ist.")
        return redirect(f"{reverse('settings')}#integrations")
    integration.enabled = True
    integration.last_error = ""
    integration.save(update_fields=["enabled", "last_error", "updated_at"])
    messages.success(request, f"{integration.get_provider_display()} wurde aktiviert.")
    return redirect(f"{reverse('settings')}#integrations")


@login_required
@require_POST
def integration_test(request, provider):
    if not request.user.is_superuser and getattr(request.user.profile, "role", "") != "admin":
        raise PermissionDenied
    if provider not in set(IntegrationConfig.Provider.values):
        raise Http404
    org = _organization(request)
    integration, _ = IntegrationConfig.objects.get_or_create(organization=org, provider=provider)
    try:
        detail = test_integration_connection(org, provider)
    except Exception as exc:
        integration.last_error = str(exc)[:2000]
        integration.save(update_fields=["last_error", "updated_at"])
        messages.error(request, f"Verbindungstest fehlgeschlagen: {integration.last_error}")
    else:
        integration.last_error = ""
        integration.last_sync_at = timezone.now()
        integration.save(update_fields=["last_error", "last_sync_at", "updated_at"])
        messages.success(request, f"Verbindung erfolgreich: {detail}")
    return redirect(f"{reverse('settings')}#integrations")


@login_required
def mobile_app(request):
    org = _organization(request)
    employee = getattr(request.user, "employee", None)
    if not employee:
        return render(request, "erp/mobile.html", {"employee": None, "projects": [], "tasks": [], "events": []})
    projects = Project.objects.filter(organization=org, archived=False).filter(
        Q(members=employee) | Q(manager=employee)
    ).distinct().exclude(status__in=[Project.Status.COMPLETED, Project.Status.CANCELLED])
    tasks = employee.tasks.exclude(status__in=[Task.Status.DONE, Task.Status.CANCELLED])[:20]
    events = employee.events.filter(starts_at__gte=timezone.now() - timedelta(days=1))[:20]
    measurements = RoomMeasurement.objects.filter(organization=org, project__in=projects).select_related("project")[:8]
    return render(request, "erp/mobile.html", {"employee": employee, "projects": projects, "tasks": tasks, "events": events, "measurements": measurements, "native_scan_enabled": True})


@login_required
@require_POST
def notification_read(request, pk):
    notification = get_object_or_404(Notification, user=request.user, pk=pk)
    notification.read_at = timezone.now()
    notification.save(update_fields=["read_at"])
    return redirect(notification.url or "dashboard")


@login_required
def export_csv(request, resource):
    org = _organization(request)
    if resource in {"customers", "invoices"} and role_for(request.user) == UserProfile.Role.TECHNICIAN:
        raise PermissionDenied
    if resource == "invoices" and not can_view_prices(request.user):
        raise PermissionDenied
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="{resource}.csv"'
    response.write("\ufeff")
    writer = csv.writer(response, delimiter=";")
    if resource == "customers":
        writer.writerow(["Nummer", "Name", "E-Mail", "Telefon", "Straße", "PLZ", "Ort"])
        for obj in Customer.objects.filter(organization=org):
            writer.writerow([obj.number, obj.display_name, obj.email, obj.phone, obj.street, obj.postal_code, obj.city])
    elif resource == "projects":
        project_qs = _projects_for_user(request, org, Project.objects.filter(organization=org).select_related("customer"))
        if can_view_prices(request.user):
            writer.writerow(["Nummer", "Projekt", "Kunde", "Status", "Start", "Ende", "Budget"])
            for obj in project_qs:
                writer.writerow([obj.number, obj.title, obj.customer.display_name, obj.get_status_display(), obj.planned_start, obj.planned_end, obj.budget])
        else:
            writer.writerow(["Nummer", "Projekt", "Kunde", "Status", "Start", "Ende"])
            for obj in project_qs:
                writer.writerow([obj.number, obj.title, obj.customer.display_name, obj.get_status_display(), obj.planned_start, obj.planned_end])
    elif resource == "invoices":
        writer.writerow(["Nummer", "Projekt", "Datum", "Fällig", "Status", "Brutto", "Offen"])
        for obj in Invoice.objects.filter(organization=org).select_related("project"):
            writer.writerow([obj.number, obj.project.title, obj.issue_date, obj.due_date, obj.get_status_display(), obj.gross_total, obj.outstanding_total])
    else:
        raise Http404
    return response


@login_required
def calendar_view(request):
    org = _organization(request)
    mode = request.GET.get("mode", "week")
    try:
        anchor = date.fromisoformat(request.GET.get("date", ""))
    except ValueError:
        anchor = timezone.localdate()
    employee_id = request.GET.get("employee")
    events = CalendarEvent.objects.filter(organization=org).select_related("project", "project__customer").prefetch_related("attendees")
    employee_options = Employee.objects.filter(organization=org, active=True)
    if role_for(request.user) == UserProfile.Role.TECHNICIAN:
        employee = getattr(request.user, "employee", None)
        events = events.filter(attendees=employee).distinct() if employee else events.none()
        employee_options = employee_options.filter(pk=getattr(employee, "pk", None))
        employee_id = getattr(employee, "pk", None)
    elif employee_id:
        events = events.filter(attendees__pk=employee_id)
    if mode == "day":
        range_start = anchor
        days = [anchor]
    elif mode == "month":
        range_start = anchor.replace(day=1)
        month_end = (range_start.replace(day=28) + timedelta(days=4)).replace(day=1)
        days = [range_start + timedelta(days=i) for i in range((month_end - range_start).days)]
    else:
        mode = "week"
        range_start = anchor - timedelta(days=anchor.weekday())
        days = [range_start + timedelta(days=i) for i in range(7)]
    range_end = days[-1] + timedelta(days=1)
    events = list(events.filter(starts_at__date__gte=range_start, starts_at__date__lt=range_end).order_by("starts_at"))
    grouped = {day: [] for day in days}
    for event in events:
        grouped.setdefault(timezone.localtime(event.starts_at).date(), []).append(event)
    if mode == "month":
        previous_date = (range_start - timedelta(days=1)).replace(day=1)
        next_date = range_end
    else:
        step = 1 if mode == "day" else 7
        previous_date = range_start - timedelta(days=step)
        next_date = range_start + timedelta(days=step)
    return render(request, "erp/calendar.html", {
        "mode": mode,
        "anchor": anchor,
        "days": days,
        "grouped_events": grouped,
        "hours": list(range(7, 20)),
        "employees": employee_options,
        "selected_employee": str(employee_id or ""),
        "previous_date": previous_date,
        "next_date": next_date,
        "event_count": len(events),
    })


@login_required
@require_http_methods(["GET", "POST"])
def price_library(request):
    if not can_view_prices(request.user):
        raise PermissionDenied("Mitarbeiter dürfen keine Preise oder Finanzdaten sehen.")
    org = _organization(request)
    _require_write(request) if request.method == "POST" else None
    form = PriceSourceUploadForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        upload = form.cleaned_data["file"]
        temp_dir = Path("/tmp/kayi-price-imports")
        temp_dir.mkdir(parents=True, exist_ok=True)
        temp_path = temp_dir / f"{timezone.now().timestamp()}-{Path(upload.name).name}"
        with temp_path.open("wb") as handle:
            for chunk in upload.chunks():
                handle.write(chunk)
        try:
            result = import_price_file(temp_path, org)
            messages.success(request, f"{result['source']}: {result['rows']} Preispositionen importiert.")
        except Exception as exc:
            messages.error(request, f"Preisimport fehlgeschlagen: {exc}")
        finally:
            temp_path.unlink(missing_ok=True)
        return redirect("price-library")
    q = request.GET.get("q", "").strip()
    source_id = (request.GET.get("source") or "").strip()
    sources = commercial_price_sources(org, include_empty=True)
    source_ids = list(sources.values_list("pk", flat=True))
    selected = None
    if source_id:
        selected = sources.filter(pk=source_id).first()
        if selected is None:
            source_id = ""
    items = PriceItem.objects.filter(organization=org, source_id__in=source_ids, active=True).filter(Q(sales_price__gt=0) | Q(purchase_price__gt=0)).select_related("source")
    if selected:
        items = items.filter(source=selected)
    if q:
        items = items.filter(Q(code__icontains=q) | Q(description__icontains=q) | Q(category__icontains=q) | Q(source__name__icontains=q))
    total_items = PriceItem.objects.filter(organization=org, source_id__in=source_ids, active=True).filter(Q(sales_price__gt=0) | Q(purchase_price__gt=0)).count()
    return render(request, "erp/price_library.html", {
        "form": form,
        "sources": sources,
        "page_obj": _pagination(request, items, 75),
        "query": q,
        "selected_source": str(source_id),
        "selected_source_obj": selected,
        "total_items": total_items,
    })


def privacy_policy(request):
    return render(request, "store/privacy.html", {"ai_consent_version": "2026-08-10"})


def terms_of_use(request):
    return render(request, "erp/terms.html")


@login_required
@require_POST
def request_account_deletion(request):
    profile = request.user.profile
    profile.preferences = {**profile.preferences, "deletion_requested_at": timezone.now().isoformat()}
    profile.save(update_fields=["preferences", "updated_at"])
    messages.success(request, "Die Löschanfrage wurde dokumentiert. Ein Administrator prüft die betrieblichen Aufbewahrungspflichten.")
    return redirect("settings")
