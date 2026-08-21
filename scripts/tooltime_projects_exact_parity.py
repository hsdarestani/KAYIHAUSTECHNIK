from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MARKER = "A+BAU TOOLTIME PROJECTS EXACT PARITY 2026-08-21"


def read(rel: str) -> str:
    path = ROOT / rel
    if not path.exists():
        raise RuntimeError(f"ToolTime projects parity target missing: {rel}")
    return path.read_text(encoding="utf-8")


def write(rel: str, text: str) -> None:
    path = ROOT / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def patch_project_view() -> None:
    rel = "erp/rebuild_projects.py"
    text = read(rel)
    if f"# {MARKER}" not in text:
        text += r'''

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
'''
        write(rel, text)
    compile(read(rel), str(ROOT / rel), "exec")


def install_template() -> None:
    write("templates/rebuild/projects.html", r'''{% extends 'rebuild/base.html' %}{% load static %}
{% block title %}Projekte · A+Bau{% endblock %}
{% block content %}
<link rel="stylesheet" href="{% static 'css/tooltime-projects-exact.css' %}?v=20260821-projects-exact">
<script src="{% static 'js/tooltime-projects-exact.js' %}?v=20260821-projects-exact" defer></script>
<div class="ttp-page" data-tooltime-projects-exact data-modal-open="{% if modal_open %}1{% else %}0{% endif %}">
  <div class="ttp-topbar">
    <div class="ttp-heading"><h1>Projekte</h1><span class="ttp-help" title="Projekte verwalten" aria-label="Hilfe">?</span></div>
    <div class="ttp-top-actions">
      <form class="ttp-search" method="get" role="search">
        <input type="hidden" name="amount" value="{{ amount }}">
        <input type="hidden" name="status" value="{{ status_filter }}">
        <input type="hidden" name="sortType" value="{{ sort_type }}">
        <input type="hidden" name="sortOrder" value="{{ sort_order }}">
        <span aria-hidden="true">⌕</span>
        <input type="search" name="searchText" value="{{ search_text }}" placeholder="Suchen" aria-label="Projekte suchen">
        <button class="sr-only" type="submit">Suchen</button>
      </form>
      <button class="ttp-new" type="button" data-project-modal-open>＋ Neues Projekt</button>
    </div>
  </div>

  <form class="ttp-toolbar" method="get" data-auto-filter>
    <input type="hidden" name="searchText" value="{{ search_text }}">
    <input type="hidden" name="sortType" value="{{ sort_type }}">
    <input type="hidden" name="sortOrder" value="{{ sort_order }}">
    <input type="hidden" name="offset" value="0">
    <label class="ttp-filter-select"><span class="sr-only">Projektstatus</span><select name="status" aria-label="Projektstatus">
      <option value="" {% if not status_filter %}selected{% endif %}>Alle Projekte</option>
      {% for value,label in statuses %}<option value="{{ value }}" {% if status_filter == value %}selected{% endif %}>{{ label }}</option>{% endfor %}
    </select></label>
    <label class="ttp-mobile-sort"><span>Sortieren</span><select name="sortType" aria-label="Sortierung">
      <option value="LAST_CHANGED" {% if sort_type == 'LAST_CHANGED' %}selected{% endif %}>Letzte Änderung</option>
      <option value="TITLE" {% if sort_type == 'TITLE' %}selected{% endif %}>Titel</option>
      <option value="NUMBER" {% if sort_type == 'NUMBER' %}selected{% endif %}>Nr.</option>
      <option value="CUSTOMER" {% if sort_type == 'CUSTOMER' %}selected{% endif %}>Kunde</option>
      <option value="SITE_ADDRESS" {% if sort_type == 'SITE_ADDRESS' %}selected{% endif %}>Ausführungsort</option>
    </select></label>
    <label class="ttp-mobile-sort"><span>Reihenfolge</span><select name="sortOrder" aria-label="Reihenfolge">
      <option value="ASCENDING" {% if sort_order == 'ASCENDING' %}selected{% endif %}>Aufsteigend</option>
      <option value="DESCENDING" {% if sort_order == 'DESCENDING' %}selected{% endif %}>Absteigend</option>
    </select></label>
    <input type="hidden" name="amount" value="{{ amount }}">
    <button class="sr-only" type="submit">Anwenden</button>
  </form>

  <div class="ttp-table-wrap">
    <table class="ttp-table" data-project-table>
      <thead><tr>
        <th data-col="title">Titel</th>
        <th data-col="no">Nr.</th>
        <th data-col="status">Status</th>
        <th data-col="address">Ausführungsort</th>
        <th data-col="customer">Kunde</th>
        <th data-col="changed"><a class="ttp-sort-link" href="?{{ last_change_query }}">Letzte Änderung <span aria-hidden="true">{% if sort_type == 'LAST_CHANGED' and sort_order == 'ASCENDING' %}↑{% else %}↓{% endif %}</span></a></th>
        <th class="ttp-config-head"><details class="ttp-columns"><summary aria-label="Spalten auswählen" title="Spalten auswählen">⚙</summary><div class="ttp-columns-card">
          <strong>Spalten</strong>
          <label><input type="checkbox" data-column-toggle="no" checked> Nr.</label>
          <label><input type="checkbox" data-column-toggle="status" checked> Status</label>
          <label><input type="checkbox" data-column-toggle="address" checked> Ausführungsort</label>
          <label><input type="checkbox" data-column-toggle="customer" checked> Kunde</label>
          <label><input type="checkbox" data-column-toggle="changed" checked> Letzte Änderung</label>
        </div></details></th>
      </tr></thead>
      <tbody>
      {% for row in rows %}<tr data-project-row data-href="{% url 'next-project-detail' row.project.pk %}" tabindex="0">
        <td data-col="title" data-label="Titel"><a class="ttp-title" href="{% url 'next-project-detail' row.project.pk %}">{{ row.project.title }}</a></td>
        <td data-col="no" data-label="Nr."><strong>{{ row.project.number|default:'—' }}</strong></td>
        <td data-col="status" data-label="Status"><span class="ttp-status ttp-status-{{ row.status_key }}">{{ row.status_label }}</span></td>
        <td data-col="address" data-label="Ausführungsort">{{ row.site_address }}</td>
        <td data-col="customer" data-label="Kunde"><span class="ttp-customer-icon" aria-hidden="true">⌂</span>{{ row.customer_label|default:'—' }}</td>
        <td data-col="changed" data-label="Letzte Änderung">{% if row.last_change %}{{ row.last_change|date:'d/m/Y' }}{% else %}—{% endif %}</td>
        <td class="ttp-row-actions"><details><summary aria-label="Projektaktionen">•••</summary><div class="ttp-row-menu">
          <a href="{% url 'next-project-detail' row.project.pk %}">Projekt öffnen</a>
          <a href="{% url 'next-quote-create' %}?project={{ row.project.pk }}">Angebot erstellen</a>
          <a href="{% url 'next-appointment-create' %}?project={{ row.project.pk }}">Termin planen</a>
        </div></details></td>
      </tr>{% empty %}<tr><td colspan="7"><div class="ttp-empty"><strong>Keine Projekte gefunden.</strong><span>Suche oder Filter anpassen oder ein neues Projekt anlegen.</span></div></td></tr>{% endfor %}
      </tbody>
    </table>
  </div>

  <div class="ttp-pagination" aria-label="Seitennavigation">
    <div class="ttp-page-summary">{% if total_count %}{{ first_item }}–{{ last_item }} von {{ total_count }}{% else %}0 Projekte{% endif %}</div>
    <label>Zeilen <select data-page-size aria-label="Zeilen pro Seite"><option value="20" {% if amount == 20 %}selected{% endif %}>20</option><option value="50" {% if amount == 50 %}selected{% endif %}>50</option><option value="100" {% if amount == 100 %}selected{% endif %}>100</option></select></label>
    <div class="ttp-page-buttons">
      {% if prev_offset != None %}<a href="?{{ prev_query }}" aria-label="Vorherige Seite">‹</a>{% else %}<span aria-disabled="true">‹</span>{% endif %}
      {% if next_offset != None %}<a href="?{{ next_query }}" aria-label="Nächste Seite">›</a>{% else %}<span aria-disabled="true">›</span>{% endif %}
    </div>
  </div>

  <div class="ttp-modal" data-project-modal {% if not modal_open %}hidden{% endif %}>
    <button class="ttp-modal-backdrop" type="button" data-project-modal-close aria-label="Dialog schließen"></button>
    <form class="ttp-modal-card" method="post" action="{% url 'next-projects' %}" data-project-create-form>{% csrf_token %}
      <input type="hidden" name="intent" value="create_project">
      <header><h2>Projekt erstellen</h2><button type="button" data-project-modal-close aria-label="Schließen">×</button></header>
      {% if create_errors %}<div class="ttp-form-errors" role="alert">{% for error in create_errors %}<div>{{ error }}</div>{% endfor %}</div>{% endif %}
      <div class="ttp-create-grid">
        <label class="ttp-field ttp-title-field"><span>Projekttitel</span><input name="title" value="{{ create_values.title }}" maxlength="200" autofocus required data-project-title></label>
        <label class="ttp-field"><span>Eingangsdatum</span><input type="date" name="date_of_receipt" value="{{ create_values.date_of_receipt|default:today_iso }}" required></label>
        <label class="ttp-field ttp-span-2"><span>Projektbeschreibung</span><textarea name="description" rows="3" placeholder="Projektspezifische Informationen und Notizen (optional)">{{ create_values.description }}</textarea></label>
      </div>
      <div class="ttp-customer-section">
        <h3>Kunde</h3>
        <label class="ttp-field"><span class="sr-only">Kunde auswählen</span><select name="customer" required data-project-customer><option value="">Kunde auswählen …</option>{% for customer in customers %}<option value="{{ customer.pk }}" {% if create_values.customer == customer.pk|stringformat:'s' %}selected{% endif %}>{{ customer.display_name }}{% if customer.city %} · {{ customer.city }}{% endif %}</option>{% endfor %}</select></label>
        <a href="{% url 'next-customer-create' %}?next=project" class="ttp-customer-create">＋ Neuen Kunden anlegen</a>
      </div>
      <footer><button class="ttp-cancel" type="button" data-project-modal-close>Abbrechen</button><button class="ttp-create" type="submit">＋ Erstellen</button></footer>
    </form>
  </div>
</div>
{% endblock %}
''')


def install_css() -> None:
    write("static/css/tooltime-projects-exact.css", r'''
.ttp-page{--ttp-blue:#147dcc;--ttp-navy:#17344e;--ttp-line:#dbe3ea;--ttp-muted:#718293;color:#263d52;min-width:0}.ttp-topbar{display:flex;align-items:center;justify-content:space-between;gap:22px;margin:2px 0 28px}.ttp-heading{display:flex;align-items:center;gap:10px}.ttp-heading h1{margin:0;font-size:25px;line-height:1.2;color:#20384f;font-weight:750}.ttp-help{display:grid;place-items:center;width:18px;height:18px;border:1.5px solid #1681cf;border-radius:50%;color:#1681cf;font-size:11px;font-weight:800}.ttp-top-actions{display:flex;align-items:center;gap:14px}.ttp-search{display:flex;align-items:center;gap:8px;width:235px;height:38px;padding:0 12px;border:1px solid #ccd6df;border-radius:7px;background:#fff}.ttp-search span{color:#6c7d8d;font-size:20px;line-height:1}.ttp-search input{width:100%;border:0;outline:0;background:transparent;font:inherit;color:#334a5e}.ttp-search input::placeholder{color:#758696}.ttp-new{height:38px;border:0;border-radius:6px;background:var(--ttp-blue);color:#fff;padding:0 17px;font:700 13px/1 inherit;cursor:pointer;box-shadow:0 1px 1px rgba(10,75,125,.12)}.ttp-new:hover{background:#096dbb}.ttp-toolbar{display:flex;align-items:center;gap:12px;margin-bottom:18px}.ttp-filter-select select,.ttp-mobile-sort select{height:36px;border:1px solid #cad5df;border-radius:6px;background:#fff;padding:0 34px 0 11px;font:inherit;color:#3f5264}.ttp-mobile-sort{display:none}.ttp-table-wrap{overflow:visible;border-top:1px solid #cfd8e0}.ttp-table{width:100%;border-collapse:collapse;table-layout:auto}.ttp-table th{height:43px;padding:0 12px;border-bottom:1px solid #cfd8e0;color:#667789;font-size:11px;text-align:left;font-weight:700;white-space:nowrap}.ttp-table td{padding:14px 12px;border-bottom:1px solid #e1e6eb;font-size:12px;vertical-align:middle;color:#526678}.ttp-table tbody tr{position:relative;transition:background .12s ease}.ttp-table tbody tr[data-project-row]{cursor:pointer}.ttp-table tbody tr[data-project-row]:hover{background:#f8fafc}.ttp-table th:first-child,.ttp-table td:first-child{padding-left:14px}.ttp-title{color:#293f54;text-decoration:none;font-weight:750;display:block;max-width:330px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.ttp-table td[data-col=no] strong{color:#274159}.ttp-sort-link{display:inline-flex;align-items:center;gap:5px;color:#31475b;text-decoration:none;font-weight:800}.ttp-status{display:inline-flex;align-items:center;justify-content:center;min-height:22px;padding:2px 8px;border-radius:11px;font-size:10px;font-weight:750;white-space:nowrap;background:#d8edf8;color:#31769a}.ttp-status-quote{background:#5f7d8e;color:#fff}.ttp-status-progress{background:#e0edf9;color:#216da5}.ttp-status-planning{background:#e7edf3;color:#526b7d}.ttp-status-waiting{background:#fff1d5;color:#906a25}.ttp-status-done{background:#dff2e8;color:#2d7a50}.ttp-status-cancelled{background:#f7e5e5;color:#a44e4e}.ttp-customer-icon{margin-right:7px;color:#60788b;font-size:13px}.ttp-config-head,.ttp-row-actions{width:42px;text-align:right!important}.ttp-columns,.ttp-row-actions details{position:relative}.ttp-columns summary,.ttp-row-actions summary{list-style:none;cursor:pointer;user-select:none;color:#426177}.ttp-columns summary::-webkit-details-marker,.ttp-row-actions summary::-webkit-details-marker{display:none}.ttp-columns-card,.ttp-row-menu{position:absolute;right:0;top:calc(100% + 8px);z-index:40;min-width:190px;padding:9px;background:#fff;border:1px solid #d7e0e8;border-radius:8px;box-shadow:0 12px 30px rgba(20,47,71,.15)}.ttp-columns-card strong{display:block;padding:7px 8px;color:#324b60;font-size:11px}.ttp-columns-card label{display:flex;align-items:center;gap:8px;padding:7px 8px;font-size:12px;font-weight:500;cursor:pointer}.ttp-row-menu{min-width:165px}.ttp-row-menu a{display:block;padding:8px 9px;border-radius:5px;text-decoration:none;color:#344b60;font-size:12px;white-space:nowrap}.ttp-row-menu a:hover{background:#f2f6f9}.ttp-empty{display:grid;gap:4px;text-align:center;padding:44px;color:#7b8b98}.ttp-empty strong{color:#42586a;font-size:14px}.ttp-pagination{display:flex;align-items:center;justify-content:flex-end;gap:18px;padding:15px 6px;color:#687a8b;font-size:11px}.ttp-pagination label{display:flex;align-items:center;gap:7px}.ttp-pagination select{height:30px;border:1px solid #d2dbe3;border-radius:5px;background:#fff}.ttp-page-buttons{display:flex;gap:5px}.ttp-page-buttons a,.ttp-page-buttons span{display:grid;place-items:center;width:30px;height:30px;border:1px solid #d7e0e7;border-radius:5px;text-decoration:none;color:#40586d;background:#fff;font-size:18px}.ttp-page-buttons span{opacity:.4}.ttp-modal{position:fixed;inset:0;z-index:1600;display:grid;place-items:center;padding:22px}.ttp-modal[hidden]{display:none}.ttp-modal-backdrop{position:absolute;inset:0;border:0;background:rgba(21,34,47,.42);cursor:default}.ttp-modal-card{position:relative;z-index:1;width:min(520px,calc(100vw - 34px));max-height:calc(100vh - 40px);overflow:auto;background:#fff;border-radius:11px;box-shadow:0 24px 60px rgba(20,38,54,.25);padding:25px 30px 24px}.ttp-modal-card header{display:flex;align-items:center;justify-content:space-between;margin-bottom:25px}.ttp-modal-card h2{margin:0;color:#314255;font-size:19px;font-weight:750}.ttp-modal-card header button{border:0;background:transparent;color:#81909c;font-size:24px;line-height:1;cursor:pointer}.ttp-create-grid{display:grid;grid-template-columns:1fr 118px;gap:17px 15px}.ttp-span-2{grid-column:1/-1}.ttp-field{display:grid;gap:7px}.ttp-field>span,.ttp-customer-section h3{color:#506172;font-size:11px;font-weight:750}.ttp-field input,.ttp-field select,.ttp-field textarea{width:100%;box-sizing:border-box;border:1px solid #cbd7e2;border-radius:6px;background:#fff;padding:9px 10px;font:inherit;color:#344b60;outline:none}.ttp-field input,.ttp-field select{height:38px}.ttp-field textarea{resize:vertical;min-height:78px}.ttp-field input:focus,.ttp-field select:focus,.ttp-field textarea:focus{border-color:#1684d5;box-shadow:0 0 0 1px #1684d5}.ttp-customer-section{margin-top:18px}.ttp-customer-section h3{margin:0 0 9px;font-size:13px;color:#435568}.ttp-customer-create{display:inline-block;margin-top:8px;color:#147dcc;font-size:11px;text-decoration:none}.ttp-form-errors{margin:-10px 0 16px;padding:10px 12px;border-radius:6px;background:#fff0f0;color:#a64b4b;font-size:11px}.ttp-modal-card footer{display:flex;justify-content:flex-end;gap:10px;margin-top:25px}.ttp-cancel,.ttp-create{height:36px;border-radius:6px;padding:0 14px;font:700 12px/1 inherit;cursor:pointer}.ttp-cancel{border:0;background:#eef1f3;color:#536474}.ttp-create{border:0;background:var(--ttp-blue);color:#fff}.ttp-create:hover{background:#096dbb}body.ttp-modal-lock{overflow:hidden}.ttp-col-hidden{display:none!important}
@media(max-width:900px){.ttp-topbar{align-items:flex-start}.ttp-top-actions{width:min(100%,430px)}.ttp-search{flex:1;width:auto}.ttp-mobile-sort{display:grid;gap:3px;color:#738394;font-size:10px}.ttp-table-wrap{overflow-x:auto}.ttp-table{min-width:900px}}
@media(max-width:620px){.ttp-topbar{display:grid;margin-bottom:20px}.ttp-top-actions{width:100%;display:grid;grid-template-columns:1fr auto}.ttp-search{width:auto}.ttp-toolbar{overflow-x:auto;padding-bottom:3px}.ttp-pagination{justify-content:space-between;gap:8px}.ttp-page-summary{margin-right:auto}.ttp-modal{padding:10px}.ttp-modal-card{width:calc(100vw - 20px);padding:20px;border-radius:9px}.ttp-create-grid{grid-template-columns:1fr}.ttp-span-2{grid-column:auto}.ttp-title-field{grid-column:auto}.ttp-table{min-width:820px}}
''')


def install_js() -> None:
    write("static/js/tooltime-projects-exact.js", r'''(() => {
  "use strict";
  const page = document.querySelector("[data-tooltime-projects-exact]");
  if (!page) return;

  const modal = page.querySelector("[data-project-modal]");
  const title = page.querySelector("[data-project-title]");
  const openModal = () => {
    if (!modal) return;
    modal.hidden = false;
    document.body.classList.add("ttp-modal-lock");
    window.setTimeout(() => title && title.focus(), 0);
  };
  const closeModal = () => {
    if (!modal) return;
    modal.hidden = true;
    document.body.classList.remove("ttp-modal-lock");
  };
  page.querySelectorAll("[data-project-modal-open]").forEach((button) => button.addEventListener("click", openModal));
  page.querySelectorAll("[data-project-modal-close]").forEach((button) => button.addEventListener("click", closeModal));
  if (page.dataset.modalOpen === "1") openModal();
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && modal && !modal.hidden) closeModal();
  });

  page.querySelectorAll("[data-auto-filter] select").forEach((select) => {
    select.addEventListener("change", () => select.form && select.form.submit());
  });

  const size = page.querySelector("[data-page-size]");
  if (size) size.addEventListener("change", () => {
    const url = new URL(window.location.href);
    url.searchParams.set("amount", size.value);
    url.searchParams.set("offset", "0");
    window.location.assign(url.toString());
  });

  page.querySelectorAll("[data-project-row]").forEach((row) => {
    const go = () => row.dataset.href && window.location.assign(row.dataset.href);
    row.addEventListener("click", (event) => {
      if (event.target.closest("a,button,input,select,textarea,summary,details,label")) return;
      go();
    });
    row.addEventListener("keydown", (event) => {
      if ((event.key === "Enter" || event.key === " ") && !event.target.closest("a,button,input,select,textarea,summary,details")) {
        event.preventDefault();
        go();
      }
    });
  });

  const storageKey = "ab-bau-tooltime-project-columns-v1";
  let state = {};
  try { state = JSON.parse(window.localStorage.getItem(storageKey) || "{}"); } catch (_) { state = {}; }
  const applyColumn = (name, visible) => {
    page.querySelectorAll(`[data-col="${name}"]`).forEach((cell) => cell.classList.toggle("ttp-col-hidden", !visible));
  };
  page.querySelectorAll("[data-column-toggle]").forEach((input) => {
    const name = input.dataset.columnToggle;
    if (Object.prototype.hasOwnProperty.call(state, name)) input.checked = Boolean(state[name]);
    applyColumn(name, input.checked);
    input.addEventListener("change", () => {
      state[name] = input.checked;
      applyColumn(name, input.checked);
      try { window.localStorage.setItem(storageKey, JSON.stringify(state)); } catch (_) {}
    });
  });
})();
''')


def install_tests() -> None:
    write("tests/test_tooltime_projects_exact_parity.py", r'''from pathlib import Path

from django.test import SimpleTestCase

ROOT = Path(__file__).resolve().parents[1]


class ToolTimeProjectsExactParityContract(SimpleTestCase):
    def test_project_index_has_reference_structure(self):
        template = (ROOT / "templates/rebuild/projects.html").read_text(encoding="utf-8")
        for token in (
            "data-tooltime-projects-exact",
            "Alle Projekte",
            "Neues Projekt",
            "data-project-modal",
            "Projekttitel",
            "Eingangsdatum",
            "Projektbeschreibung",
            "Kunde auswählen",
            "data-col=\"title\"",
            "data-col=\"no\"",
            "data-col=\"status\"",
            "data-col=\"address\"",
            "data-col=\"customer\"",
            "data-col=\"changed\"",
            "Letzte Änderung",
            "data-column-toggle",
            "Projektaktionen",
            "data-page-size",
        ):
            self.assertIn(token, template)

    def test_project_view_uses_tooltime_query_contract_and_real_create(self):
        source = (ROOT / "erp/rebuild_projects.py").read_text(encoding="utf-8")
        for token in (
            "searchText",
            "sortType",
            "sortOrder",
            "LAST_CHANGED",
            "ASCENDING",
            "DESCENDING",
            "amount",
            "offset",
            "create_project",
            "_tt_project_next_number",
            'f"{timezone.localdate().year % 100:02d}-"',
            "m.Project.objects.create",
            "updated_at",
            "prefetch_related(\"quotes\")",
        ):
            self.assertIn(token, source)

    def test_project_assets_have_modal_row_and_column_behaviour(self):
        js = (ROOT / "static/js/tooltime-projects-exact.js").read_text(encoding="utf-8")
        css = (ROOT / "static/css/tooltime-projects-exact.css").read_text(encoding="utf-8")
        for token in ("data-project-modal-open", "data-project-row", "localStorage", "data-page-size"):
            self.assertIn(token, js)
        for token in (".ttp-modal", ".ttp-row-menu", ".ttp-status", ".ttp-pagination"):
            self.assertIn(token, css)
''')


def final_guard() -> None:
    view = read("erp/rebuild_projects.py")
    template = read("templates/rebuild/projects.html")
    for required in (
        MARKER,
        "searchText",
        "sortType",
        "sortOrder",
        "_tt_project_next_number",
        "create_project",
    ):
        if required not in view:
            raise RuntimeError(f"Project parity view contract missing: {required}")
    for required in (
        "data-tooltime-projects-exact",
        "data-project-modal",
        "data-column-toggle",
        "Letzte Änderung",
        "Projektaktionen",
        "data-page-size",
    ):
        if required not in template:
            raise RuntimeError(f"Project parity template contract missing: {required}")
    compile(view, str(ROOT / "erp/rebuild_projects.py"), "exec")


def main() -> None:
    patch_project_view()
    install_template()
    install_css()
    install_js()
    install_tests()
    final_guard()
    print(f"{MARKER}: project list, modal creation, ToolTime sorting/paging, columns and row actions installed.")


if __name__ == "__main__":
    main()
