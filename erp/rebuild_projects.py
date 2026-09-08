from __future__ import annotations

from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import get_object_or_404, render

from . import models as m
from .rebuild_views import _employee, _invoice_total, _is_field_user, _org, _project_financials


def _projects_for(request, org):
    projects = m.Project.objects.filter(organization=org, archived=False)
    if _is_field_user(request):
        employee = _employee(request)
        if employee is None:
            return projects.none()
        projects = projects.filter(Q(manager=employee) | Q(members=employee)).distinct()
    return projects


@login_required
def project_list(request):
    org = _org(request)
    query = request.GET.get("q", "").strip()
    status = request.GET.get("status", "").strip()
    projects = _projects_for(request, org).select_related("customer", "manager", "object_location")
    if query:
        projects = projects.filter(
            Q(number__icontains=query)
            | Q(title__icontains=query)
            | Q(customer__company__icontains=query)
            | Q(customer__last_name__icontains=query)
        )
    if status:
        projects = projects.filter(status=status)
    return render(request, "rebuild/projects.html", {
        "projects": projects.order_by("-updated_at")[:250],
        "query": query,
        "status": status,
        "statuses": m.Project._meta.get_field("status").choices,
    })


@login_required
def project_detail(request, pk):
    org = _org(request)
    project = get_object_or_404(
        _projects_for(request, org).select_related("customer", "object_location", "manager"),
        pk=pk,
    )
    appointments = project.events.prefetch_related("attendees").order_by("-starts_at")[:20]
    quotes = project.quotes.prefetch_related("items").order_by("-created_at")
    invoices = project.invoices.prefetch_related("items", "payments").order_by("-created_at")
    documents = project.documents.order_by("-created_at")[:30]
    tasks = project.tasks.order_by("status", "due_at")[:20]
    materials = project.materials.order_by("-created_at")[:20]
    invoice_gross = sum((_invoice_total(invoice)["gross"] for invoice in invoices), Decimal("0"))
    finance = _project_financials(project)
    bando_report = None
    if hasattr(project, "site_reports"):
        try:
            bando_report = project.site_reports.order_by("-created_at").first()
        except Exception:
            bando_report = None
    return render(request, "rebuild/project_detail.html", {
        "project": project,
        "appointments": appointments,
        "quotes": quotes,
        "invoices": invoices,
        "documents": documents,
        "tasks": tasks,
        "materials": materials,
        "invoice_gross": invoice_gross,
        "finance": finance,
        "bando_report": bando_report,
        "field_user": _is_field_user(request),
    })


# A+BAU TOOLTIME PROJECTS EXACT PARITY 2026-08-21

def _tt_project_customer_label(customer):
    if customer is None:
        return ""
    value = getattr(customer, "display_name", "")
    if callable(value):
        try:
            value = value()
        except TypeError:
            pass
    if isinstance(value, str) and value.strip():
        return value.strip()
    company = (getattr(customer, "company", "") or "").strip()
    person = " ".join(
        part.strip()
        for part in (
            getattr(customer, "first_name", "") or "",
            getattr(customer, "last_name", "") or "",
        )
        if part.strip()
    )
    return company or person or ""


def _tt_project_site_address(project):
    location = getattr(project, "object_location", None)
    customer = getattr(project, "customer", None)
    source = location or customer
    if source is None:
        return "—"
    street = (getattr(source, "street", "") or "").strip()
    postal_code = (getattr(source, "postal_code", "") or "").strip()
    city = (getattr(source, "city", "") or "").strip()
    locality = " ".join(part for part in (postal_code, city) if part)
    parts = [part for part in (street, locality) if part]
    if parts:
        return ", ".join(parts)
    name = (getattr(source, "name", "") or "").strip()
    return name or "—"


def _tt_project_status(project):
    raw = (getattr(project, "status", "") or "inquiry").lower()
    try:
        has_quote = bool(list(project.quotes.all()))
    except Exception:
        has_quote = False
    if raw in {"inquiry", "new", "draft"} and has_quote:
        return "Angebot erstellt", "quote"
    mapping = {
        "inquiry": ("Neues Projekt", "new"),
        "new": ("Neues Projekt", "new"),
        "draft": ("Neues Projekt", "new"),
        "quoted": ("Angebot erstellt", "quote"),
        "quote_created": ("Angebot erstellt", "quote"),
        "planning": ("Planung", "planning"),
        "scheduled": ("Termin geplant", "planning"),
        "in_progress": ("In Bearbeitung", "progress"),
        "waiting": ("Wartet", "waiting"),
        "completed": ("Abgeschlossen", "done"),
        "done": ("Abgeschlossen", "done"),
        "cancelled": ("Storniert", "cancelled"),
        "canceled": ("Storniert", "cancelled"),
    }
    if raw in mapping:
        return mapping[raw]
    display = getattr(project, "get_status_display", lambda: raw.replace("_", " ").title())()
    return str(display), raw or "new"


def _tt_project_last_change(project):
    return getattr(project, "updated_at", None) or getattr(project, "created_at", None)


def _tt_project_next_number(org):
    """ToolTime-like YY-NNNNN project number, scoped to the organization."""
    from django.utils import timezone

    prefix = f"{timezone.localdate().year % 100:02d}-"
    highest = 0
    for value in m.Project.objects.filter(organization=org, number__startswith=prefix).values_list("number", flat=True):
        value = str(value or "")
        suffix = value[len(prefix):]
        if suffix.isdigit():
            highest = max(highest, int(suffix))
    candidate = highest + 1
    while True:
        number = f"{prefix}{candidate:05d}"
        if not m.Project.objects.filter(organization=org, number=number).exists():
            return number
        candidate += 1


def _tt_project_sort_value(row, sort_type):
    project = row["project"]
    if sort_type == "TITLE":
        return (getattr(project, "title", "") or "").casefold()
    if sort_type == "NUMBER":
        return (getattr(project, "number", "") or "").casefold()
    if sort_type == "CUSTOMER":
        return row["customer_label"].casefold()
    if sort_type == "SITE_ADDRESS":
        return row["site_address"].casefold()
    value = row["last_change"]
    try:
        return value.timestamp() if value is not None else 0
    except Exception:
        return 0


@login_required
def project_list(request):
    """Screenshot-parity ToolTime project index with modal create, sorting and offset paging."""
    from datetime import date as _date, datetime as _datetime, time as _time
    from urllib.parse import urlencode

    from django.contrib import messages
    from django.shortcuts import redirect
    from django.utils import timezone

    org = _org(request)
    create_errors = []
    create_values = {
        "title": "",
        "date_of_receipt": timezone.localdate().isoformat(),
        "description": "",
        "customer": "",
    }
    modal_open = request.GET.get("new") == "1"

    if request.method == "POST" and request.POST.get("intent") == "create_project":
        modal_open = True
        create_values = {
            "title": (request.POST.get("title") or "").strip(),
            "date_of_receipt": (request.POST.get("date_of_receipt") or "").strip(),
            "description": (request.POST.get("description") or "").strip(),
            "customer": (request.POST.get("customer") or "").strip(),
        }
        title = create_values["title"]
        customer = None
        if not title:
            create_errors.append("Bitte einen Projekttitel eingeben.")
        if not create_values["customer"]:
            create_errors.append("Bitte einen Kunden auswählen.")
        else:
            try:
                customer = m.Customer.objects.get(
                    organization=org,
                    active=True,
                    pk=int(create_values["customer"]),
                )
            except (m.Customer.DoesNotExist, TypeError, ValueError):
                create_errors.append("Der ausgewählte Kunde ist nicht verfügbar.")

        received_on = timezone.localdate()
        if create_values["date_of_receipt"]:
            try:
                received_on = _date.fromisoformat(create_values["date_of_receipt"])
            except ValueError:
                create_errors.append("Bitte ein gültiges Eingangsdatum wählen.")

        if not create_errors and customer is not None:
            values = {
                "organization": org,
                "number": _tt_project_next_number(org),
                "title": title,
                "customer": customer,
                "description": create_values["description"],
                "status": "inquiry",
                "priority": "normal",
            }
            model_fields = {field.name for field in m.Project._meta.get_fields()}
            values = {key: value for key, value in values.items() if key in model_fields}
            project = m.Project.objects.create(**values)

            # The current product schema already owns created_at. Reuse that stored
            # business timestamp as the ToolTime Eingangsdatum instead of inventing
            # a duplicate date column/migration. updated_at remains the real Last change.
            if "created_at" in model_fields:
                created_field = m.Project._meta.get_field("created_at")
                if created_field.get_internal_type() == "DateField":
                    m.Project.objects.filter(pk=project.pk).update(created_at=received_on)
                else:
                    received_dt = timezone.make_aware(
                        _datetime.combine(received_on, _time.min),
                        timezone.get_current_timezone(),
                    )
                    m.Project.objects.filter(pk=project.pk).update(created_at=received_dt)

            messages.success(request, "Projekt wurde angelegt.")
            return redirect("next-project-detail", pk=project.pk)

    search_text = (request.GET.get("searchText") or request.GET.get("q") or "").strip()
    status_filter = (request.GET.get("status") or "").strip()
    sort_type = (request.GET.get("sortType") or "LAST_CHANGED").strip().upper()
    sort_order = (request.GET.get("sortOrder") or "ASCENDING").strip().upper()
    if sort_type not in {"LAST_CHANGED", "TITLE", "NUMBER", "CUSTOMER", "SITE_ADDRESS"}:
        sort_type = "LAST_CHANGED"
    if sort_order not in {"ASCENDING", "DESCENDING"}:
        sort_order = "ASCENDING"

    try:
        amount = int(request.GET.get("amount") or 20)
    except (TypeError, ValueError):
        amount = 20
    if amount not in {20, 50, 100}:
        amount = 20
    try:
        offset = max(0, int(request.GET.get("offset") or 0))
    except (TypeError, ValueError):
        offset = 0

    projects = _projects_for(request, org).select_related(
        "customer", "manager", "object_location"
    ).prefetch_related("quotes")
    if search_text:
        projects = projects.filter(
            Q(number__icontains=search_text)
            | Q(title__icontains=search_text)
            | Q(customer__company__icontains=search_text)
            | Q(customer__first_name__icontains=search_text)
            | Q(customer__last_name__icontains=search_text)
            | Q(customer__street__icontains=search_text)
            | Q(customer__city__icontains=search_text)
            | Q(object_location__street__icontains=search_text)
            | Q(object_location__city__icontains=search_text)
        ).distinct()
    if status_filter:
        projects = projects.filter(status=status_filter)

    rows = []
    for project in projects[:2000]:
        status_label, status_key = _tt_project_status(project)
        rows.append({
            "project": project,
            "customer_label": _tt_project_customer_label(getattr(project, "customer", None)),
            "site_address": _tt_project_site_address(project),
            "status_label": status_label,
            "status_key": status_key,
            "last_change": _tt_project_last_change(project),
        })

    reverse = sort_order == "DESCENDING"
    rows.sort(
        key=lambda row: (_tt_project_sort_value(row, sort_type), row["project"].pk),
        reverse=reverse,
    )

    total_count = len(rows)
    if offset >= total_count and total_count:
        offset = max(0, ((total_count - 1) // amount) * amount)
    page_rows = rows[offset: offset + amount]
    first_item = offset + 1 if total_count else 0
    last_item = min(offset + amount, total_count)
    prev_offset = max(0, offset - amount) if offset else None
    next_offset = offset + amount if offset + amount < total_count else None

    base_params = {
        "amount": amount,
        "searchText": search_text,
        "status": status_filter,
        "sortType": sort_type,
        "sortOrder": sort_order,
    }

    def _query(**updates):
        params = dict(base_params)
        params.update(updates)
        return urlencode({key: value for key, value in params.items() if value not in ("", None)})

    next_sort_order = "DESCENDING" if sort_order == "ASCENDING" else "ASCENDING"
    customers = m.Customer.objects.filter(organization=org, active=True).order_by(
        "company", "last_name", "first_name", "number"
    )

    return render(request, "rebuild/projects.html", {
        "rows": page_rows,
        "projects": [row["project"] for row in page_rows],
        "customers": customers,
        "search_text": search_text,
        "status_filter": status_filter,
        "statuses": m.Project._meta.get_field("status").choices,
        "sort_type": sort_type,
        "sort_order": sort_order,
        "next_sort_order": next_sort_order,
        "last_change_query": _query(sortType="LAST_CHANGED", sortOrder=next_sort_order, offset=0),
        "amount": amount,
        "offset": offset,
        "total_count": total_count,
        "first_item": first_item,
        "last_item": last_item,
        "prev_offset": prev_offset,
        "next_offset": next_offset,
        "prev_query": _query(offset=prev_offset) if prev_offset is not None else "",
        "next_query": _query(offset=next_offset) if next_offset is not None else "",
        "create_errors": create_errors,
        "create_values": create_values,
        "modal_open": modal_open,
        "today_iso": timezone.localdate().isoformat(),
    })
