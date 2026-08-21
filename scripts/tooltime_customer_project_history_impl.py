from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MARKER = "A+BAU TOOLTIME CUSTOMER PROJECT HISTORY 2026-08-21"
CACHE_VERSION = "20260821-customer-project-history-1"


def read(rel: str) -> str:
    path = ROOT / rel
    if not path.exists():
        raise RuntimeError(f"Customer/project parity target missing: {rel}")
    return path.read_text(encoding="utf-8")


def write(rel: str, text: str) -> None:
    path = ROOT / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def replace_function(text: str, start: str, end_candidates: tuple[str, ...], replacement: str, label: str) -> str:
    start_pos = text.find(start)
    if start_pos < 0:
        raise RuntimeError(f"Customer/project parity start missing: {label}")
    ends = [text.find(candidate, start_pos + len(start)) for candidate in end_candidates]
    ends = [value for value in ends if value >= 0]
    if not ends:
        raise RuntimeError(f"Customer/project parity end missing: {label}")
    end_pos = min(ends)
    return text[:start_pos] + replacement + text[end_pos:]


def patch_views() -> None:
    rel = "erp/rebuild_views.py"
    text = read(rel)

    customer_start = '@login_required\n@require_http_methods(["GET", "POST"])\ndef customer_detail(request, pk):\n'
    customer_view = r'''@login_required
@require_http_methods(["GET", "POST"])
def customer_detail(request, pk):
    org = _org(request)
    customer = get_object_or_404(m.Customer, pk=pk, organization=org)
    add_object_open = request.GET.get("add_object") == "1"

    if request.method == "POST" and request.POST.get("action") == "add_location":
        form = CustomerForm(instance=customer, organization=org)
        location_form = ObjectLocationForm(request.POST, prefix="site")
        add_object_open = True
        if location_form.is_valid():
            location = location_form.save(commit=False)
            location.organization = org
            location.customer = customer
            location.save()
            messages.success(request, "Ausführungsort wurde hinzugefügt.")
            return redirect(f"/customers/{customer.pk}/#adressen")
    elif request.method == "POST":
        form = CustomerForm(request.POST, instance=customer, organization=org)
        location_form = ObjectLocationForm(prefix="site")
        if form.is_valid():
            form.save()
            messages.success(request, "Kundendaten gespeichert.")
            return redirect("next-customer-detail", pk=customer.pk)
    else:
        form = CustomerForm(instance=customer, organization=org)
        location_form = ObjectLocationForm(prefix="site")

    direct_title = f"Direktdokumente · Kunde {customer.pk}"
    projects = customer.projects.filter(organization=org).exclude(title=direct_title).order_by("-updated_at")
    locations = customer.object_locations.filter(organization=org).order_by("name", "city", "street")
    appointments = (
        m.CalendarEvent.objects.filter(organization=org)
        .filter(Q(customer=customer) | Q(project__customer=customer))
        .select_related("project", "customer")
        .distinct()
        .order_by("-starts_at")[:100]
    )
    quotes = m.Quote.objects.filter(organization=org, project__customer=customer).select_related("project").order_by("-created_at")[:100]
    invoices = m.Invoice.objects.filter(organization=org, project__customer=customer).select_related("project").order_by("-created_at")[:100]

    documented_event_ids = set(
        m.Document.objects.filter(organization=org, customer=customer, category="report", metadata__event_id__isnull=False)
        .values_list("metadata__event_id", flat=True)
    )
    history = []
    for project in projects[:100]:
        history.append({"kind": "project", "at": project.updated_at, "object": project, "status": project.get_status_display()})
    for event in appointments:
        history.append({"kind": "appointment", "at": event.starts_at, "object": event, "status": "Termin dokumentiert" if event.pk in documented_event_ids else "Termin geplant", "documented": event.pk in documented_event_ids})
    for quote in quotes:
        history.append({"kind": "quote", "at": quote.created_at, "object": quote, "status": quote.get_status_display()})
    for invoice in invoices:
        history.append({"kind": "invoice", "at": invoice.created_at, "object": invoice, "status": invoice.get_status_display()})
    history.sort(key=lambda row: row["at"], reverse=True)

    return render(request, "rebuild/customer_detail.html", {
        "customer": customer,
        "form": form,
        "projects": projects,
        "locations": locations,
        "location_form": location_form,
        "add_object_open": add_object_open,
        "history": history,
    })


@login_required
@require_POST
def customer_quote_create(request, pk):
    org = _org(request)
    if _is_field_user(request):
        messages.error(request, "Angebote können nur im Büro erstellt werden.")
        return redirect("next-customer-detail", pk=pk)
    customer = get_object_or_404(m.Customer, pk=pk, organization=org, active=True)
    project = _customer_direct_document_project(org, customer)
    quote = m.Quote.objects.create(
        organization=org, project=project, number="", status="draft",
        issue_date=timezone.localdate(), discount_percent=0, created_by=request.user,
    )
    _customer_bind_document_meta(quote, "quote", customer)
    return redirect("next-quote-edit", pk=quote.pk)


@login_required
@require_POST
def customer_invoice_create(request, pk):
    org = _org(request)
    if _is_field_user(request):
        messages.error(request, "Rechnungen können nur im Büro erstellt werden.")
        return redirect("next-customer-detail", pk=pk)
    customer = get_object_or_404(m.Customer, pk=pk, organization=org, active=True)
    project = _customer_direct_document_project(org, customer)
    today = timezone.localdate()
    invoice = m.Invoice.objects.create(
        organization=org, project=project, number="", status="draft",
        issue_date=today, due_date=today + timedelta(days=14), service_date=today,
        created_by=request.user,
    )
    _customer_bind_document_meta(invoice, "invoice", customer)
    return redirect("next-invoice-edit", pk=invoice.pk)


'''
    text = replace_function(
        text,
        customer_start,
        ("\n\n@login_required\ndef customer_locations_api(request, pk):\n", "\n\n@login_required\ndef project_list(request):\n"),
        customer_view,
        "customer_detail",
    )

    helper_anchor = customer_start
    if "def _customer_direct_document_project(" not in text:
        helper_pos = text.find(helper_anchor)
        if helper_pos < 0:
            raise RuntimeError("Customer direct-document helper anchor missing")
        helpers = r'''def _customer_direct_document_project(org, customer):
    title = f"Direktdokumente · Kunde {customer.pk}"
    project = m.Project.objects.filter(organization=org, customer=customer, title=title).order_by("pk").first()
    if project is None:
        project = m.Project.objects.create(
            organization=org, customer=customer, number=_unique_number(m.Project, org, "P"),
            title=title, status="inquiry", archived=True,
        )
    return project


def _customer_bind_document_meta(document, kind, customer):
    if not hasattr(m, "ToolTimeDocumentMeta"):
        return
    lookup = {"organization": document.organization, kind: document}
    meta, _ = m.ToolTimeDocumentMeta.objects.get_or_create(**lookup)
    if hasattr(meta, "customer_id"):
        meta.customer = customer
        meta.save(update_fields=["customer", "updated_at"])


'''
        text = text[:helper_pos] + helpers + text[helper_pos:]

    project_start = '@login_required\ndef project_detail(request, pk):\n'
    project_view = r'''@login_required
def project_detail(request, pk):
    org = _org(request)
    project = get_object_or_404(
        m.Project.objects.select_related("customer", "object_location", "manager"),
        pk=pk, organization=org,
    )
    appointments = project.events.prefetch_related("attendees").order_by("-starts_at")[:100]
    quotes = project.quotes.prefetch_related("items").order_by("-created_at")[:100]
    invoices = project.invoices.prefetch_related("items", "payments").order_by("-created_at")[:100]
    documents = project.documents.order_by("-created_at")[:100]
    tasks = project.tasks.order_by("status", "due_at")[:100]
    materials = project.materials.order_by("-created_at")[:20]
    invoice_gross = sum((_invoice_total(invoice)["gross"] for invoice in invoices), Decimal("0"))

    documented_event_ids = set(
        m.Document.objects.filter(organization=org, project=project, category="report", metadata__event_id__isnull=False)
        .values_list("metadata__event_id", flat=True)
    )
    history = []
    for event in appointments:
        history.append({"kind": "appointment", "at": event.starts_at, "object": event, "status": "Termin dokumentiert" if event.pk in documented_event_ids else "Termin geplant", "documented": event.pk in documented_event_ids})
    for quote in quotes:
        history.append({"kind": "quote", "at": quote.created_at, "object": quote, "status": quote.get_status_display()})
    for invoice in invoices:
        history.append({"kind": "invoice", "at": invoice.created_at, "object": invoice, "status": invoice.get_status_display()})
    for document in documents:
        history.append({"kind": "document", "at": document.created_at, "object": document, "status": document.get_category_display()})
    history.sort(key=lambda row: row["at"], reverse=True)

    latest_invoice = invoices[0] if invoices else None
    latest_quote = quotes[0] if quotes else None
    if project.status == "completed":
        tooltime_status = "Projekt abgeschlossen"
    elif project.status == "cancelled":
        tooltime_status = "Projekt abgebrochen"
    elif latest_invoice is not None:
        if latest_invoice.status == "paid":
            tooltime_status = "Rechnung bezahlt"
        elif latest_invoice.status == "overdue":
            tooltime_status = "Rechnung überfällig"
        elif latest_invoice.status in {"dunned", "reminded"}:
            tooltime_status = "Rechnung angemahnt"
        else:
            tooltime_status = "Rechnung angelegt"
    elif latest_quote is not None:
        tooltime_status = "Angebot angenommen" if latest_quote.status == "accepted" else "Angebot erstellt"
    elif documented_event_ids:
        tooltime_status = "Termin dokumentiert"
    elif appointments:
        tooltime_status = "Termin geplant"
    else:
        tooltime_status = "Neues Projekt"

    return render(request, "rebuild/project_detail.html", {
        "project": project,
        "appointments": appointments,
        "quotes": quotes,
        "invoices": invoices,
        "documents": documents,
        "tasks": tasks,
        "materials": materials,
        "invoice_gross": invoice_gross,
        "history": history,
        "tooltime_status": tooltime_status,
        "has_planned_appointments": any(event.pk not in documented_event_ids for event in appointments),
    })


@login_required
@require_POST
def project_lifecycle(request, pk):
    org = _org(request)
    if _is_field_user(request):
        messages.error(request, "Projektstatus kann nur im Büro geändert werden.")
        return redirect("next-project-detail", pk=pk)
    project = get_object_or_404(m.Project, pk=pk, organization=org)
    action = (request.POST.get("action") or "").strip()

    if action in {"complete", "cancel"}:
        event_ids = list(project.events.values_list("pk", flat=True))
        documented = set(
            m.Document.objects.filter(organization=org, project=project, category="report", metadata__event_id__in=event_ids)
            .values_list("metadata__event_id", flat=True)
        )
        if any(event_id not in documented for event_id in event_ids):
            messages.error(request, "Das Projekt kann erst abgeschlossen oder abgebrochen werden, wenn keine geplanten Termine mehr enthalten sind.")
            return redirect("next-project-detail", pk=project.pk)
        project.status = "completed" if action == "complete" else "cancelled"
        project.archived = True
        if action == "complete" and hasattr(project, "progress"):
            project.progress = 100
        fields = ["status", "archived", "updated_at"]
        if action == "complete" and hasattr(project, "progress"):
            fields.append("progress")
        project.save(update_fields=fields)
        messages.success(request, "Projekt wurde abgeschlossen." if action == "complete" else "Projekt wurde abgebrochen.")
    elif action == "reactivate":
        project.status = "inquiry"
        project.archived = False
        project.save(update_fields=["status", "archived", "updated_at"])
        messages.success(request, "Projekt wurde reaktiviert.")
    else:
        messages.error(request, "Unbekannte Projektaktion.")
    return redirect("next-project-detail", pk=project.pk)


'''
    text = replace_function(
        text,
        project_start,
        ("\n\n@login_required\ndef appointment_list(request):\n",),
        project_view,
        "project_detail",
    )

    write(rel, text)
    compile(text, str(ROOT / rel), "exec")


def patch_urls() -> None:
    rel = "erp/rebuild_urls.py"
    text = read(rel)
    customer_anchor = '    path("customers/<int:pk>/", views.customer_detail, name="next-customer-detail"),\n'
    customer_routes = (
        '    path("customers/<int:pk>/angebot/neu/", views.customer_quote_create, name="next-customer-quote-create"),\n'
        '    path("customers/<int:pk>/rechnung/neu/", views.customer_invoice_create, name="next-customer-invoice-create"),\n'
    )
    if customer_routes[0] not in text:
        if customer_anchor not in text:
            raise RuntimeError("Customer detail URL anchor missing")
        text = text.replace(customer_anchor, customer_anchor + "".join(customer_routes), 1)

    project_anchor = '    path("projects/<int:pk>/", views.project_detail, name="next-project-detail"),\n'
    project_route = '    path("projects/<int:pk>/aktionen/", views.project_lifecycle, name="next-project-lifecycle"),\n'
    if project_route not in text:
        if project_anchor not in text:
            raise RuntimeError("Project detail URL anchor missing")
        text = text.replace(project_anchor, project_anchor + project_route, 1)
    write(rel, text)
    compile(text, str(ROOT / rel), "exec")


CUSTOMER_TEMPLATE = r'''{% extends 'rebuild/base.html' %}
{% block title %}{{ customer.display_name }} · A+Bau{% endblock %}
{% block content %}
<div class="tt-history-shell" data-tooltime-customer-history>
  <header class="tt-history-head">
    <div><a class="tt-back" href="{% url 'next-customers' %}">← Kunden</a><div class="tt-eyebrow">{{ customer.number }}</div><h1>{{ customer.display_name }}</h1></div>
    <details class="tt-action-menu"><summary class="nx-btn nx-btn-primary">Hinzufügen ▾</summary><div class="tt-action-popover">
      <a href="{% url 'next-project-create' %}?customer={{ customer.pk }}">Projekt</a>
      <a href="{% url 'next-appointment-create' %}?customer={{ customer.pk }}">Termin</a>
      <form method="post" action="{% url 'next-customer-quote-create' customer.pk %}">{% csrf_token %}<button type="submit">Angebot</button></form>
      <form method="post" action="{% url 'next-customer-invoice-create' customer.pk %}">{% csrf_token %}<button type="submit">Rechnung</button></form>
    </div></details>
  </header>

  <div class="tt-history-layout">
    <main class="tt-history-main">
      <section class="nx-card tt-history-card">
        <div class="tt-history-title"><h2>Kundenverlauf</h2></div>
        <div class="tt-history-list">
          {% for row in history %}
          <article class="tt-history-row">
            <div class="tt-history-date">{{ row.at|date:'d.m.Y' }}<small>{{ row.at|date:'H:i' }}</small></div>
            <div class="tt-history-icon">{% if row.kind == 'project' %}P{% elif row.kind == 'appointment' %}T{% elif row.kind == 'quote' %}A{% else %}R{% endif %}</div>
            <div class="tt-history-copy">
              {% if row.kind == 'project' %}<a href="{% url 'next-project-detail' row.object.pk %}"><strong>{{ row.object.title }}</strong></a><span>Projekt · {{ row.object.number }}</span>
              {% elif row.kind == 'appointment' %}<a href="{% url 'next-appointment-detail' row.object.pk %}"><strong>{{ row.object.title }}</strong></a><span>Termin{% if row.object.project %} · {{ row.object.project.title }}{% endif %}</span>
              {% elif row.kind == 'quote' %}<a href="{% url 'next-quote-edit' row.object.pk %}"><strong>{{ row.object.number|default:'Angebotsentwurf' }}</strong></a><span>Angebot{% if row.object.project and not row.object.project.archived %} · {{ row.object.project.title }}{% endif %}</span>
              {% elif row.kind == 'invoice' %}<a href="{% url 'next-invoice-edit' row.object.pk %}"><strong>{{ row.object.number|default:'Rechnungsentwurf' }}</strong></a><span>Rechnung{% if row.object.project and not row.object.project.archived %} · {{ row.object.project.title }}{% endif %}</span>{% endif %}
            </div>
            <span class="tt-history-status">{{ row.status }}</span>
          </article>
          {% empty %}<div class="tt-history-empty"><strong>Noch keine Einträge im Kundenverlauf.</strong><span>Über „Hinzufügen“ kannst Du Projekt, Termin, Angebot oder Rechnung anlegen.</span></div>{% endfor %}
        </div>
      </section>
    </main>

    <aside class="tt-history-side">
      <details class="nx-card tt-side-card" open><summary>Kundendaten</summary><form class="nx-form tt-side-form" method="post">{% csrf_token %}
        <div class="tt-side-fields">{% for field in form %}<div class="nx-field"><label for="{{ field.id_for_label }}">{{ field.label }}</label>{{ field }}{{ field.errors }}</div>{% endfor %}</div>
        <button class="nx-btn nx-btn-primary" type="submit">Änderungen speichern</button>
      </form></details>

      <section class="nx-card tt-side-card" id="adressen"><div class="tt-side-head"><h3>Ausführungsorte</h3><a href="?add_object=1#adressen">＋ Hinzufügen</a></div>
        {% for location in locations %}<div class="tt-address-row"><strong>{{ location.name|default:'Ausführungsort' }}</strong><span>{{ location.street }}{% if location.street and location.city %}, {% endif %}{{ location.postal_code }} {{ location.city }}</span></div>{% empty %}<p class="nx-muted">Keine abweichenden Ausführungsorte.</p>{% endfor %}
        <details class="tt-inline-create" {% if add_object_open or location_form.errors %}open{% endif %}><summary>Neuen Ausführungsort anlegen</summary><form method="post" class="nx-form">{% csrf_token %}<input type="hidden" name="action" value="add_location">{% for field in location_form %}<div class="nx-field"><label>{{ field.label }}</label>{{ field }}{{ field.errors }}</div>{% endfor %}<button class="nx-btn nx-btn-primary" type="submit">Speichern</button></form></details>
      </section>
    </aside>
  </div>
</div>
{% endblock %}'''


PROJECT_TEMPLATE = r'''{% extends 'rebuild/base.html' %}
{% block title %}{{ project.title }} · A+Bau{% endblock %}
{% block content %}
<div class="tt-history-shell" data-tooltime-project-history>
  <header class="tt-history-head">
    <div><a class="tt-back" href="{% url 'next-projects' %}">← Projekte</a><div class="tt-eyebrow">{{ project.number }}</div><h1>{{ project.title }}</h1><div class="tt-project-meta"><a href="{% url 'next-customer-detail' project.customer.pk %}">{{ project.customer.display_name }}</a><span>·</span><span>{{ tooltime_status }}</span></div></div>
    <div class="tt-history-head-actions">
      {% if not project.archived %}<details class="tt-action-menu"><summary class="nx-btn nx-btn-primary">Hinzufügen ▾</summary><div class="tt-action-popover">
        <a href="{% url 'next-appointment-create' %}?project={{ project.pk }}">Termin</a>
        <a href="{% url 'next-quote-create' %}?project={{ project.pk }}">Angebot</a>
        <a href="{% url 'next-invoice-create' %}?project={{ project.pk }}">Rechnung</a>
      </div></details>{% endif %}
      <details class="tt-action-menu"><summary class="nx-btn">Aktionen ▾</summary><div class="tt-action-popover">
        {% if project.archived %}<form method="post" action="{% url 'next-project-lifecycle' project.pk %}">{% csrf_token %}<input type="hidden" name="action" value="reactivate"><button type="submit">Projekt reaktivieren</button></form>
        {% else %}<form method="post" action="{% url 'next-project-lifecycle' project.pk %}">{% csrf_token %}<input type="hidden" name="action" value="complete"><button type="submit" {% if has_planned_appointments %}title="Geplante Termine müssen zuerst dokumentiert werden"{% endif %}>Projekt abschließen</button></form><form method="post" action="{% url 'next-project-lifecycle' project.pk %}">{% csrf_token %}<input type="hidden" name="action" value="cancel"><button type="submit">Projekt abbrechen</button></form>{% endif %}
      </div></details>
    </div>
  </header>

  {% if project.archived %}<div class="tt-archive-note">Dieses Projekt ist archiviert. Reaktiviere es über „Aktionen“, um wieder Änderungen vorzunehmen.</div>{% endif %}

  <div class="tt-history-layout">
    <main class="tt-history-main">
      <section class="nx-card tt-history-card">
        <div class="tt-history-title"><h2>Projektverlauf</h2></div>
        <div class="tt-history-list">
          {% for row in history %}<article class="tt-history-row">
            <div class="tt-history-date">{{ row.at|date:'d.m.Y' }}<small>{{ row.at|date:'H:i' }}</small></div>
            <div class="tt-history-icon">{% if row.kind == 'appointment' %}T{% elif row.kind == 'quote' %}A{% elif row.kind == 'invoice' %}R{% else %}D{% endif %}</div>
            <div class="tt-history-copy">
              {% if row.kind == 'appointment' %}<a href="{% url 'next-appointment-detail' row.object.pk %}"><strong>{{ row.object.title }}</strong></a><span>Termin</span>
              {% elif row.kind == 'quote' %}<a href="{% url 'next-quote-edit' row.object.pk %}"><strong>{{ row.object.number|default:'Angebotsentwurf' }}</strong></a><span>Angebot</span>
              {% elif row.kind == 'invoice' %}<a href="{% url 'next-invoice-edit' row.object.pk %}"><strong>{{ row.object.number|default:'Rechnungsentwurf' }}</strong></a><span>Rechnung</span>
              {% else %}{% if row.object.file %}<a href="{{ row.object.file.url }}" target="_blank"><strong>{{ row.object.title }}</strong></a>{% else %}<strong>{{ row.object.title }}</strong>{% endif %}<span>Dokument</span>{% endif %}
            </div><span class="tt-history-status">{{ row.status }}</span>
          </article>{% empty %}<div class="tt-history-empty"><strong>Noch keine Einträge im Projektverlauf.</strong><span>Über „Hinzufügen“ kannst Du den nächsten Schritt anlegen.</span></div>{% endfor %}
        </div>
      </section>

      <section class="nx-card tt-history-card tt-task-card"><div class="tt-history-title"><h2>Aufgaben</h2></div>{% for task in tasks %}<div class="tt-task-row"><strong>{{ task.title }}</strong><span>{{ task.get_status_display }}{% if task.due_at %} · {{ task.due_at|date:'d.m.Y' }}{% endif %}</span></div>{% empty %}<p class="nx-muted">Keine Aufgaben für dieses Projekt.</p>{% endfor %}</section>
    </main>

    <aside class="tt-history-side">
      <section class="nx-card tt-side-card"><h3>Projektdetails</h3><dl class="tt-detail-list"><div><dt>Status</dt><dd>{{ tooltime_status }}</dd></div><div><dt>Kunde</dt><dd><a href="{% url 'next-customer-detail' project.customer.pk %}">{{ project.customer.display_name }}</a></dd></div><div><dt>Ausführungsort</dt><dd>{% if project.object_location %}{{ project.object_location.street }}, {{ project.object_location.postal_code }} {{ project.object_location.city }}{% else %}{{ project.customer.street }}, {{ project.customer.postal_code }} {{ project.customer.city }}{% endif %}</dd></div>{% if project.description %}<div><dt>Beschreibung</dt><dd>{{ project.description }}</dd></div>{% endif %}</dl></section>

      <section class="nx-card tt-side-card"><h3>A+Bau Werkzeuge</h3><div class="tt-extra-actions"><a href="{% url 'configurator' %}?project={{ project.pk }}">Aufmaß & 3D</a>{% if project.job_type == 'insurance' %}{% if bando_report %}<a href="{% url 'site-report-edit' bando_report.pk %}">B&O Leistungsnachweis</a>{% else %}<a href="{% url 'site-report-create' project.pk %}">B&O Leistungsnachweis erstellen</a>{% endif %}{% endif %}</div></section>
    </aside>
  </div>
</div>
{% endblock %}'''


def install_templates_and_css() -> None:
    write("templates/rebuild/customer_detail.html", CUSTOMER_TEMPLATE)
    write("templates/rebuild/project_detail.html", PROJECT_TEMPLATE)
    css_rel = "static/css/kayi-next.css"
    css = read(css_rel)
    if MARKER not in css:
        css += r'''

/* A+BAU TOOLTIME CUSTOMER PROJECT HISTORY 2026-08-21 */
.tt-history-shell{max-width:1320px;margin:0 auto;padding:4px 0 64px}.tt-history-head{display:flex;align-items:flex-start;justify-content:space-between;gap:24px;margin:6px 0 22px}.tt-history-head h1{font-size:30px;line-height:1.15;margin:6px 0 0}.tt-eyebrow{font-size:12px;color:#827968;margin-top:12px}.tt-history-head-actions{display:flex;gap:9px;align-items:center}.tt-action-menu{position:relative}.tt-action-menu>summary{list-style:none;cursor:pointer}.tt-action-menu>summary::-webkit-details-marker{display:none}.tt-action-popover{position:absolute;right:0;top:calc(100% + 7px);z-index:40;min-width:210px;padding:7px;background:#fff;border:1px solid #dedad2;border-radius:10px;box-shadow:0 14px 36px rgba(25,25,25,.12);display:grid}.tt-action-popover a,.tt-action-popover button{display:block;width:100%;box-sizing:border-box;border:0;background:transparent;text-align:left;padding:10px 11px;border-radius:7px;color:#292722;font:inherit;text-decoration:none;cursor:pointer}.tt-action-popover a:hover,.tt-action-popover button:hover{background:#f5f3ee}.tt-history-layout{display:grid;grid-template-columns:minmax(0,1fr) 330px;gap:18px;align-items:start}.tt-history-card{overflow:hidden}.tt-history-title{padding:18px 20px;border-bottom:1px solid #ebe8e2}.tt-history-title h2{margin:0;font-size:18px}.tt-history-list{display:grid}.tt-history-row{display:grid;grid-template-columns:82px 34px minmax(0,1fr) auto;gap:12px;align-items:center;padding:15px 20px;border-bottom:1px solid #efede8}.tt-history-row:last-child{border-bottom:0}.tt-history-date{font-size:12px;color:#635f57;display:grid}.tt-history-date small{color:#98928a;margin-top:2px}.tt-history-icon{width:30px;height:30px;border-radius:8px;background:#f2eee5;color:#715b32;display:grid;place-items:center;font-weight:800;font-size:12px}.tt-history-copy{display:grid;gap:3px;min-width:0}.tt-history-copy a{color:#24221e;text-decoration:none}.tt-history-copy a:hover{text-decoration:underline}.tt-history-copy span{font-size:12px;color:#858078}.tt-history-status{font-size:12px;padding:5px 8px;border-radius:999px;background:#f4f3f0;color:#625e57;white-space:nowrap}.tt-history-empty{padding:34px 20px;display:grid;gap:5px;color:#777168}.tt-history-empty strong{color:#38352f}.tt-history-side{display:grid;gap:14px}.tt-side-card{padding:18px}.tt-side-card>summary{font-weight:750;cursor:pointer;list-style:none}.tt-side-card>summary::-webkit-details-marker{display:none}.tt-side-card h3{margin:0 0 14px}.tt-side-form{margin-top:17px}.tt-side-fields{display:grid;gap:10px;margin-bottom:14px}.tt-side-fields .nx-field label{font-size:12px}.tt-side-head{display:flex;align-items:center;justify-content:space-between;gap:10px;margin-bottom:12px}.tt-side-head h3{margin:0}.tt-side-head a{font-size:12px;color:#6f5933}.tt-address-row{display:grid;gap:3px;padding:10px 0;border-top:1px solid #efede8}.tt-address-row span{font-size:12px;color:#777168}.tt-inline-create{margin-top:10px}.tt-inline-create>summary{font-size:12px;font-weight:700;cursor:pointer}.tt-inline-create form{margin-top:12px;display:grid;gap:10px}.tt-project-meta{display:flex;gap:7px;align-items:center;margin-top:7px;font-size:13px;color:#716c64}.tt-project-meta a{color:inherit}.tt-archive-note{margin-bottom:16px;padding:12px 15px;border:1px solid #e4cf9d;background:#fff8e7;border-radius:9px;color:#6b5422}.tt-task-card{margin-top:16px;padding-bottom:8px}.tt-task-row{display:flex;justify-content:space-between;gap:14px;padding:12px 20px;border-bottom:1px solid #efede8}.tt-task-row span{font-size:12px;color:#777168}.tt-detail-list{display:grid;gap:0;margin:0}.tt-detail-list>div{padding:10px 0;border-top:1px solid #efede8}.tt-detail-list dt{font-size:11px;color:#918b82}.tt-detail-list dd{margin:4px 0 0;font-size:13px}.tt-extra-actions{display:grid;gap:8px}.tt-extra-actions a{display:block;padding:9px 10px;border:1px solid #e6e1d8;border-radius:8px;color:#3a342a;text-decoration:none;font-size:13px}.tt-extra-actions a:hover{background:#f7f5f0}@media(max-width:900px){.tt-history-layout{grid-template-columns:1fr}.tt-history-side{grid-row:1}.tt-history-head{flex-direction:column}.tt-history-row{grid-template-columns:68px 30px minmax(0,1fr)}.tt-history-status{grid-column:3;justify-self:start}.tt-history-head-actions{width:100%}.tt-history-head-actions .tt-action-menu{flex:1}.tt-history-head-actions summary{justify-content:center}.tt-action-popover{left:0;right:auto;min-width:100%}}@media(max-width:560px){.tt-history-row{padding:13px 14px;grid-template-columns:56px 28px minmax(0,1fr);gap:9px}.tt-history-title{padding:16px 14px}.tt-history-date{font-size:11px}.tt-history-head h1{font-size:26px}}
'''
        write(css_rel, css)
    base_rel = "templates/rebuild/base.html"
    base = read(base_rel)
    base = re.sub(r"(kayi-next\.css[^\"']*\?v=)[^\"']+", rf"\g<1>{CACHE_VERSION}", base)
    write(base_rel, base)


def install_tests() -> None:
    test = r'''from __future__ import annotations

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from erp.models import CalendarEvent, Customer, Organization, Project, Quote, UserProfile


class ToolTimeCustomerProjectHistoryTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name="A+Bau History Test")
        User = get_user_model()
        self.user = User.objects.create_user(username="history-office", password="secret")
        UserProfile.objects.create(user=self.user, organization=self.org, role="office", is_mobile_worker=False)
        self.client.force_login(self.user)
        self.customer = Customer.objects.create(organization=self.org, number="K-H1", type="private", first_name="Mara", last_name="Muster", active=True)
        self.project = Project.objects.create(organization=self.org, customer=self.customer, number="P-H1", title="Badmodernisierung", status="inquiry", archived=False)

    def test_customer_detail_is_a_tooltime_customer_history(self):
        response = self.client.get(reverse("next-customer-detail", args=[self.customer.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Kundenverlauf")
        self.assertContains(response, "Hinzufügen")
        for label in ("Projekt", "Termin", "Angebot", "Rechnung"):
            self.assertContains(response, label)

    def test_customer_can_start_direct_quote(self):
        response = self.client.post(reverse("next-customer-quote-create", args=[self.customer.pk]))
        self.assertEqual(response.status_code, 302)
        quote = Quote.objects.get(organization=self.org)
        self.assertEqual(quote.project.customer_id, self.customer.pk)
        self.assertTrue(quote.project.archived)
        self.assertEqual(quote.status, "draft")

    def test_project_detail_is_a_tooltime_project_history(self):
        response = self.client.get(reverse("next-project-detail", args=[self.project.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Projektverlauf")
        self.assertContains(response, "Aktionen")
        self.assertContains(response, "Projekt abschließen")
        self.assertContains(response, "Projekt abbrechen")
        self.assertContains(response, "A+Bau Werkzeuge")

    def test_planned_appointment_blocks_project_completion(self):
        CalendarEvent.objects.create(
            organization=self.org, project=self.project, customer=self.customer, created_by=self.user,
            title="Montage", type="installation", starts_at=timezone.now() + timedelta(days=1),
            ends_at=timezone.now() + timedelta(days=1, hours=1),
        )
        response = self.client.post(reverse("next-project-lifecycle", args=[self.project.pk]), {"action": "complete"})
        self.assertEqual(response.status_code, 302)
        self.project.refresh_from_db()
        self.assertFalse(self.project.archived)
        self.assertNotEqual(self.project.status, "completed")

    def test_empty_project_can_be_completed_and_reactivated(self):
        self.client.post(reverse("next-project-lifecycle", args=[self.project.pk]), {"action": "complete"})
        self.project.refresh_from_db()
        self.assertTrue(self.project.archived)
        self.assertEqual(self.project.status, "completed")
        self.client.post(reverse("next-project-lifecycle", args=[self.project.pk]), {"action": "reactivate"})
        self.project.refresh_from_db()
        self.assertFalse(self.project.archived)
        self.assertEqual(self.project.status, "inquiry")
'''
    write("tests/test_tooltime_customer_project_history.py", test)


def guard() -> None:
    views = read("erp/rebuild_views.py")
    urls = read("erp/rebuild_urls.py")
    customer = read("templates/rebuild/customer_detail.html")
    project = read("templates/rebuild/project_detail.html")
    css = read("static/css/kayi-next.css")
    for needle in ("def customer_quote_create", "def customer_invoice_create", "def project_lifecycle", 'tooltime_status = "Neues Projekt"'):
        if needle not in views:
            raise RuntimeError(f"Customer/project view guard missing: {needle}")
    for needle in ("next-customer-quote-create", "next-customer-invoice-create", "next-project-lifecycle"):
        if needle not in urls:
            raise RuntimeError(f"Customer/project route guard missing: {needle}")
    for needle in ("Kundenverlauf", "Hinzufügen", "Angebot", "Rechnung"):
        if needle not in customer:
            raise RuntimeError(f"Customer history UI guard missing: {needle}")
    for needle in ("Projektverlauf", "Projekt abschließen", "Projekt abbrechen", "A+Bau Werkzeuge"):
        if needle not in project:
            raise RuntimeError(f"Project history UI guard missing: {needle}")
    if "· KAYI" in customer or "· KAYI" in project:
        raise RuntimeError("Legacy product name reintroduced in customer/project UI")
    if MARKER not in css:
        raise RuntimeError("Customer/project CSS guard missing")
    compile(views, str(ROOT / "erp/rebuild_views.py"), "exec")
    compile(urls, str(ROOT / "erp/rebuild_urls.py"), "exec")


patch_views()
patch_urls()
install_templates_and_css()
install_tests()
guard()
print(f"{MARKER}: Kundenverlauf und Projektverlauf folgen dem ToolTime-Kernflow; A+Bau-Zusatzwerkzeuge bleiben getrennt erhalten.")
