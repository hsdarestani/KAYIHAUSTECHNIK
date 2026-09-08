from __future__ import annotations

import re
from typing import Any

from django.db.models import Q

from . import models as m


ADMIN = "admin"
OFFICE = "office"
PROJECT_MANAGER = "project_manager"
TECHNICIAN = "technician"
ACCOUNTING = "accounting"
READONLY = "readonly"

PRICE_ROLES = {ADMIN, OFFICE, ACCOUNTING}
FIELD_AI_ROLES = {ADMIN, OFFICE, PROJECT_MANAGER, TECHNICIAN}
ROOM_AI_ROLES = {ADMIN, OFFICE, PROJECT_MANAGER, TECHNICIAN}
DRAFT_MUTATION_ROLES = {ADMIN, OFFICE, PROJECT_MANAGER, TECHNICIAN, ACCOUNTING}

_ALL_ROUTES = {
    "dashboard", "customers", "projects", "appointments", "tasks", "quotes",
    "invoices", "expenses", "time", "employees", "settings", "field",
}
_ROUTE_POLICY = {
    ADMIN: _ALL_ROUTES,
    OFFICE: _ALL_ROUTES - {"settings"},
    ACCOUNTING: {"dashboard", "customers", "projects", "quotes", "invoices", "expenses"},
    # Project managers get record-level KI navigation only; the generic rebuilt
    # list pages are broader than their assignment scope.
    PROJECT_MANAGER: {"dashboard", "field"},
    TECHNICIAN: {"dashboard", "projects", "appointments", "tasks", "time", "field"},
    READONLY: {"dashboard", "customers", "projects", "appointments", "tasks"},
}
_SEARCH_ROUTE_POLICY = {
    ADMIN: {"employees", "customers", "projects", "appointments"},
    OFFICE: {"employees", "customers", "projects", "appointments"},
    ACCOUNTING: {"customers", "projects"},
    PROJECT_MANAGER: {"employees", "customers", "projects", "appointments"},
    TECHNICIAN: {"employees", "customers", "projects", "appointments"},
    READONLY: {"customers", "projects", "appointments"},
}

_RECORD_ROUTE_POLICY = {
    ADMIN: {"employees", "customers", "projects", "appointments", "tasks", "quotes", "invoices", "expenses"},
    OFFICE: {"employees", "customers", "projects", "appointments", "tasks", "quotes", "invoices", "expenses"},
    ACCOUNTING: {"customers", "projects", "quotes", "invoices", "expenses"},
    PROJECT_MANAGER: {"employees", "customers", "projects", "appointments", "tasks"},
    TECHNICIAN: {"employees", "customers", "projects", "appointments", "tasks"},
    READONLY: {"customers", "projects", "appointments", "tasks"},
}

_PRICE_TOKEN_RE = re.compile(
    r"(?i)(?:"
    r"\bpreis(?:e|en|lich)?\b|\bkosten\b|\bkostet\b|\beinkauf(?:spreis)?\b|\bverkauf(?:spreis)?\b|"
    r"\bek\b|\bvk\b|\bmarge\b|\bmargin\b|\bmarkup\b|\baufschlag\b|\bgewinn\b|\bprofit\b|"
    r"\bumsatz\b|\brevenue\b|\bstundensatz\b|\bverrechnungssatz\b|\bnetto\b|\bbrutto\b|"
    r"\bunit[_ -]?price\b|\bsales[_ -]?price\b|\bpurchase[_ -]?price\b|\bprice\b|\bcosts?\b|"
    r"\bamount\b|\btotal\b|\bvat\b|\bmwst\b|€|\beur\b|\beuro\b"
    r")"
)
_SENSITIVE_FIELD_RE = re.compile(
    r"(?i)(?:"
    r"preis|price|kosten|cost|einkauf|verkauf|purchase|sales|"
    r"marge|margin|markup|aufschlag|gewinn|profit|umsatz|revenue|"
    r"stundensatz|hourly[_ -]?(?:cost|rate)|verrechnung|"
    r"netto|brutto|amount|total|summe|vat|mwst|tax[_ -]?rate"
    r")"
)
_INTERNAL_FIELD_RE = re.compile(
    r"(?i)(?:purchase|einkauf|hourly[_ -]?cost|interner[_ -]?stundensatz|"
    r"marge|margin|markup|aufschlag|gewinn|profit)"
)


def role_for(user) -> str:
    if getattr(user, "is_superuser", False):
        return ADMIN
    try:
        profile = user.profile
    except Exception:
        return READONLY
    role = str(getattr(profile, "role", "") or READONLY)
    # A non-admin mobile worker is deliberately treated like field staff for KI.
    # This prevents an accidentally broad office role from becoming a mobile data bypass.
    if role != ADMIN and bool(getattr(profile, "is_mobile_worker", False)):
        return TECHNICIAN
    return role if role in {ADMIN, OFFICE, PROJECT_MANAGER, TECHNICIAN, ACCOUNTING, READONLY} else READONLY


def can_view_prices(user) -> bool:
    return role_for(user) in PRICE_ROLES


def can_view_internal_prices(user) -> bool:
    return role_for(user) in PRICE_ROLES


def can_use_field_ai(user) -> bool:
    return role_for(user) in FIELD_AI_ROLES


def can_use_room_ai(user) -> bool:
    return role_for(user) in ROOM_AI_ROLES


def can_mutate_ai_drafts(user) -> bool:
    return role_for(user) in DRAFT_MUTATION_ROLES


def allowed_navigation_routes(user) -> set[str]:
    role = role_for(user)
    return set(_ROUTE_POLICY.get(role, {"dashboard"}))


def allowed_search_routes(user) -> set[str]:
    role = role_for(user)
    return set(_SEARCH_ROUTE_POLICY.get(role, set()))


def allowed_record_routes(user) -> set[str]:
    role = role_for(user)
    return set(_RECORD_ROUTE_POLICY.get(role, set()))


def employee_for(user, organization):
    if not getattr(user, "is_authenticated", False):
        return None
    employee = m.Employee.objects.filter(organization=organization, user=user, active=True).first()
    if employee is not None:
        return employee
    email = (getattr(user, "email", "") or "").strip()
    if email:
        return m.Employee.objects.filter(organization=organization, email__iexact=email, active=True).first()
    return None


def project_queryset(user, organization):
    base = m.Project.objects.filter(organization=organization, archived=False)
    role = role_for(user)
    if role in {ADMIN, OFFICE, ACCOUNTING, READONLY}:
        return base
    employee = employee_for(user, organization)
    if employee is None:
        return base.none()
    event_project_ids = m.CalendarEvent.objects.filter(
        organization=organization, attendees=employee, project_id__isnull=False
    ).values_list("project_id", flat=True)
    return base.filter(
        Q(manager=employee) | Q(members=employee) | Q(pk__in=event_project_ids)
    ).distinct()


def event_queryset(user, organization):
    base = m.CalendarEvent.objects.filter(organization=organization)
    role = role_for(user)
    if role in {ADMIN, OFFICE, READONLY}:
        return base
    if role == ACCOUNTING:
        return base.none()
    employee = employee_for(user, organization)
    if employee is None:
        return base.none()
    projects = project_queryset(user, organization).values_list("pk", flat=True)
    return base.filter(Q(attendees=employee) | Q(project_id__in=projects)).distinct()


def customer_queryset(user, organization):
    base = m.Customer.objects.filter(organization=organization, active=True)
    role = role_for(user)
    if role in {ADMIN, OFFICE, ACCOUNTING, READONLY}:
        return base
    project_customer_ids = project_queryset(user, organization).exclude(
        customer_id__isnull=True
    ).values_list("customer_id", flat=True)
    return base.filter(pk__in=project_customer_ids).distinct()


def employee_queryset(user, organization):
    base = m.Employee.objects.filter(organization=organization, active=True)
    role = role_for(user)
    if role in {ADMIN, OFFICE}:
        return base
    employee = employee_for(user, organization)
    if employee is None:
        return base.none()
    if role == TECHNICIAN:
        return base.filter(pk=employee.pk)
    if role == ACCOUNTING:
        return base.none()
    if role == READONLY:
        return base.none()
    projects = project_queryset(user, organization)
    manager_ids = projects.exclude(manager_id__isnull=True).values_list("manager_id", flat=True)
    member_ids = m.Employee.objects.filter(projects__in=projects).values_list("pk", flat=True)
    return base.filter(Q(pk=employee.pk) | Q(pk__in=manager_ids) | Q(pk__in=member_ids)).distinct()


def task_queryset(user, organization):
    base = m.Task.objects.filter(organization=organization)
    role = role_for(user)
    if role in {ADMIN, OFFICE, READONLY}:
        return base
    if role == ACCOUNTING:
        return base.none()
    employee = employee_for(user, organization)
    if employee is None:
        return base.none()
    projects = project_queryset(user, organization).values_list("pk", flat=True)
    if role == TECHNICIAN:
        return base.filter(Q(assigned_to=employee) | Q(project_id__in=projects, assigned_to=employee)).distinct()
    return base.filter(Q(assigned_to=employee) | Q(project_id__in=projects)).distinct()


def project_allowed(user, organization, project_id) -> bool:
    try:
        project_id = int(project_id)
    except (TypeError, ValueError):
        return False
    return project_queryset(user, organization).filter(pk=project_id).exists()


def event_allowed(user, organization, event_id) -> bool:
    try:
        event_id = int(event_id)
    except (TypeError, ValueError):
        return False
    return event_queryset(user, organization).filter(pk=event_id).exists()


def record_allowed(user, organization, route: str, record_id) -> bool:
    route = str(route or "")
    try:
        record_id = int(record_id)
    except (TypeError, ValueError):
        return False
    if route == "projects":
        return project_queryset(user, organization).filter(pk=record_id).exists()
    if route == "customers":
        return customer_queryset(user, organization).filter(pk=record_id).exists()
    if route == "appointments":
        return event_queryset(user, organization).filter(pk=record_id).exists()
    if route == "employees":
        return employee_queryset(user, organization).filter(pk=record_id).exists()
    if route == "tasks":
        return task_queryset(user, organization).filter(pk=record_id).exists()
    if route == "quotes":
        return role_for(user) in {ADMIN, OFFICE, ACCOUNTING} and m.Quote.objects.filter(
            organization=organization, pk=record_id
        ).exists()
    if route == "invoices":
        return role_for(user) in {ADMIN, OFFICE, ACCOUNTING} and m.Invoice.objects.filter(
            organization=organization, pk=record_id
        ).exists()
    if route == "expenses":
        return role_for(user) in {ADMIN, OFFICE, ACCOUNTING} and m.Expense.objects.filter(
            organization=organization, pk=record_id
        ).exists()
    return False


def is_price_request(message: str) -> bool:
    return bool(_PRICE_TOKEN_RE.search(message or ""))


def is_sensitive_field(name: str, label: str = "") -> bool:
    return bool(_SENSITIVE_FIELD_RE.search(f"{name or ''} {label or ''}"))


def is_internal_price_field(name: str, label: str = "") -> bool:
    return bool(_INTERNAL_FIELD_RE.search(f"{name or ''} {label or ''}"))


def _option_scope(field_name: str):
    normalized = (field_name or "").casefold()
    if normalized in {"customer", "customer_id", "kunde", "kunde_id"}:
        return "customers"
    if normalized in {"project", "project_id", "projekt", "projekt_id"}:
        return "projects"
    if normalized in {
        "assigned_to", "assigned_to_id", "manager", "manager_id", "members",
        "members_id", "attendees", "attendees_id", "employee", "employee_id",
    }:
        return "employees"
    return ""


def _allowed_ids_for_route(user, organization, route: str) -> set[str]:
    if route == "customers":
        qs = customer_queryset(user, organization)
    elif route == "projects":
        qs = project_queryset(user, organization)
    elif route == "employees":
        qs = employee_queryset(user, organization)
    elif route == "appointments":
        qs = event_queryset(user, organization)
    else:
        return set()
    return {str(value) for value in qs.values_list("pk", flat=True)}


def sanitize_assistant_payload(user, organization, payload: dict[str, Any]) -> dict[str, Any]:
    safe: dict[str, Any] = {}
    if not isinstance(payload, dict):
        return safe
    for key in ("message", "path", "title"):
        if key in payload:
            safe[key] = payload.get(key)

    price_ok = can_view_prices(user)
    fields = []
    for raw in (payload.get("fields") or [])[:80]:
        if not isinstance(raw, dict):
            continue
        name = str(raw.get("name") or "")[:120]
        label = str(raw.get("label") or "")[:220]
        if not price_ok and is_sensitive_field(name, label):
            continue
        item = dict(raw)
        route = _option_scope(name)
        if route:
            allowed_ids = _allowed_ids_for_route(user, organization, route)
            options = []
            for option in (raw.get("options") or [])[:100]:
                if not isinstance(option, dict):
                    continue
                value = str(option.get("value") or "")
                if not value or value in allowed_ids:
                    options.append(option)
            item["options"] = options
            current = str(item.get("value") or "")
            if current and current.isdigit() and current not in allowed_ids:
                item["value"] = ""
        fields.append(item)
    safe["fields"] = fields

    catalog = []
    # Catalog names/codes/units may help field staff document work, but prices never
    # cross the boundary unless the role has explicit commercial permission.
    if role_for(user) in {ADMIN, OFFICE, PROJECT_MANAGER, TECHNICIAN}:
        for raw in (payload.get("catalog") or [])[:160]:
            if not isinstance(raw, dict):
                continue
            item = dict(raw)
            if not price_ok:
                for key in list(item):
                    if is_sensitive_field(str(key), str(key)):
                        item.pop(key, None)
            catalog.append(item)
    safe["catalog"] = catalog

    # Client history is untrusted after a role downgrade. Admin can keep it; every
    # other role gets server-scoped entity continuity instead of replaying old text.
    safe["history"] = (payload.get("history") or [])[-10:] if role_for(user) == ADMIN else []
    return safe


def entity_search_context(user, organization, message: str) -> list[dict[str, Any]]:
    raw = re.findall(r"[\w@.+-]+", message or "", flags=re.UNICODE)
    stopwords = {
        "find", "search", "show", "open", "go", "to", "for", "the", "a", "an",
        "finde", "finden", "suche", "suchen", "zeig", "zeige", "öffne", "offne", "geh", "gehe", "nach",
        "mitarbeiter", "employee", "employees", "kunde", "kunden", "customer", "customers", "client", "clients",
        "projekt", "projekte", "project", "projects", "termin", "termine", "appointment", "appointments",
        "auftrag", "aufträge", "auftrage", "einsatz", "einsätze", "einsatze",
    }
    terms = []
    for token in raw:
        normalized = token.casefold().strip("._-+")
        if len(normalized) < 2 or normalized in stopwords:
            continue
        terms.append(token[:80])
    terms = terms[:6]
    if not terms:
        return []

    def and_query(fields):
        combined = Q()
        for term in terms:
            per_term = Q()
            for field in fields:
                per_term |= Q(**{f"{field}__icontains": term})
            combined &= per_term
        return combined

    allowed = allowed_search_routes(user)
    matches: list[dict[str, Any]] = []

    if "employees" in allowed:
        qs = employee_queryset(user, organization).filter(
            and_query(("first_name", "last_name", "email", "phone", "employee_number", "trade"))
        ).order_by("-active", "last_name", "first_name")[:8]
        role = role_for(user)
        for item in qs:
            detail_parts = [item.employee_number, item.trade]
            if role in {ADMIN, OFFICE}:
                detail_parts.insert(1, item.email)
            matches.append({
                "route": "employees", "id": item.pk,
                "label": f"{item.first_name} {item.last_name}".strip() or item.employee_number,
                "detail": " · ".join(part for part in detail_parts if part),
            })

    if "customers" in allowed:
        qs = customer_queryset(user, organization).filter(
            and_query(("company", "first_name", "last_name", "email", "phone", "mobile", "number"))
        ).order_by("-updated_at")[:8]
        role = role_for(user)
        for item in qs:
            detail_parts = [item.number, item.city]
            if role in {ADMIN, OFFICE, ACCOUNTING}:
                detail_parts.insert(1, item.email)
            matches.append({
                "route": "customers", "id": item.pk, "label": item.display_name,
                "detail": " · ".join(part for part in detail_parts if part),
            })

    if "projects" in allowed:
        qs = project_queryset(user, organization).filter(
            and_query(("number", "title", "description", "customer__company", "customer__first_name", "customer__last_name"))
        ).select_related("customer").order_by("-updated_at")[:8]
        for item in qs:
            matches.append({
                "route": "projects", "id": item.pk, "label": f"{item.number} · {item.title}",
                "detail": item.customer.display_name if item.customer_id else "",
            })

    if "appointments" in allowed:
        qs = event_queryset(user, organization).filter(
            and_query(("title", "location", "notes", "project__title", "project__number"))
        ).order_by("-starts_at")[:6]
        for item in qs:
            matches.append({
                "route": "appointments", "id": item.pk, "label": item.title,
                "detail": item.starts_at.strftime("%d.%m.%Y %H:%M") if item.starts_at else "",
            })
    return matches[:20]


def filter_results(user, organization, results):
    safe = []
    for item in results or []:
        if not isinstance(item, dict):
            continue
        route = str(item.get("route") or "")
        record_id = item.get("id")
        if route in allowed_search_routes(user) and record_allowed(user, organization, route, record_id):
            safe.append(item)
    return safe[:20]


def filter_actions(user, organization, payload: dict[str, Any], actions):
    field_names = {
        str(field.get("name") or "")
        for field in (payload.get("fields") or [])
        if isinstance(field, dict)
    }
    routes = allowed_navigation_routes(user)
    mutate = can_mutate_ai_drafts(user)
    catalog_available = bool(payload.get("catalog"))
    safe = []
    for action in actions or []:
        if not isinstance(action, dict):
            continue
        kind = str(action.get("type") or "")
        target = str(action.get("target") or "")
        value = str(action.get("value") or "")
        if kind == "none":
            safe.append(action)
        elif kind in {"set_field", "select_option"}:
            if mutate and target in field_names and not (not can_view_prices(user) and is_sensitive_field(target, target)):
                safe.append(action)
        elif kind == "focus":
            if target in field_names:
                safe.append(action)
        elif kind == "catalog_add":
            if mutate and catalog_available and role_for(user) in {ADMIN, OFFICE, PROJECT_MANAGER, TECHNICIAN}:
                safe.append(action)
        elif kind == "navigate":
            if target in routes:
                safe.append(action)
        elif kind == "navigate_record":
            if target in allowed_record_routes(user) and record_allowed(user, organization, target, value):
                safe.append(action)
    return safe[:14]


def sanitize_reply(user, reply: str) -> str:
    text = str(reply or "")
    if not can_view_prices(user) and _PRICE_TOKEN_RE.search(text):
        return "Auf Preisdaten, Einkauf, Verkauf, Margen und finanzielle Kennzahlen hast du mit deiner Rolle über A+Bau KI keinen Zugriff."
    return text


def strip_sensitive_data(user, value):
    if can_view_prices(user):
        return value
    if isinstance(value, dict):
        clean = {}
        for key, item in value.items():
            if is_sensitive_field(str(key), str(key)):
                continue
            clean[key] = strip_sensitive_data(user, item)
        return clean
    if isinstance(value, list):
        return [strip_sensitive_data(user, item) for item in value]
    if isinstance(value, tuple):
        return tuple(strip_sensitive_data(user, item) for item in value)
    if isinstance(value, str):
        return sanitize_reply(user, value)
    return value


def route_for_path(path: str) -> str:
    clean = str(path or "").split("?", 1)[0].strip()
    if clean in {"", "/"}:
        return "dashboard"
    first = clean.strip("/").split("/", 1)[0]
    mapping = {
        "customers": "customers",
        "projects": "projects",
        "appointments": "appointments",
        "tasks": "tasks",
        "quotes": "quotes",
        "invoices": "invoices",
        "expenses": "expenses",
        "time": "time",
        "employees": "employees",
        "settings": "settings",
        "field": "field",
    }
    return mapping.get(first, "")


def assistant_path_allowed(user, organization, path: str) -> bool:
    route = route_for_path(path)
    # Unknown/legacy pages are fail-closed for non-admins. Office may still use
    # the generic assistant on known office pages only; unrestricted fallback is
    # deliberately reserved for Admin because we cannot prove record scope on an
    # unrecognized route.
    if not route:
        return role_for(user) == ADMIN
    if route in allowed_navigation_routes(user):
        return True
    clean = str(path or "").split("?", 1)[0].strip("/")
    parts = clean.split("/") if clean else []
    if len(parts) >= 2 and parts[1].isdigit() and route in allowed_record_routes(user):
        return record_allowed(user, organization, route, parts[1])
    return False
