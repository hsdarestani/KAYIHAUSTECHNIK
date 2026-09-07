from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MARKER = "/* KAYI TOOLTIME CUSTOMER DETAIL PARITY 2026-09-07 */"
VERSION = "20260907-tooltime-customer-detail1"


def read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def write(rel: str, text: str) -> None:
    path = ROOT / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def patch_view() -> None:
    path = "erp/rebuild_views.py"
    text = read(path)

    pattern = re.compile(
        r'@login_required\n@require_http_methods\(\["GET", "POST"\]\)\ndef customer_detail\(request, pk\):.*?(?=\n@login_required\ndef customer_locations_api\(|\n@login_required\ndef project_list\()',
        re.S,
    )

    replacement = r'''@login_required
@require_http_methods(["GET", "POST"])
def customer_detail(request, pk):
    """ToolTime-style customer cockpit while keeping KAYI's existing data model."""
    org = _org(request)
    customer = get_object_or_404(m.Customer, pk=pk, organization=org)
    active_tab = request.GET.get("tab", "overview")
    if active_tab not in {"overview", "tasks", "documents"}:
        active_tab = "overview"
    edit_mode = request.GET.get("edit") == "1"
    add_object_open = request.GET.get("add_object") == "1"

    if request.method == "POST" and request.POST.get("action") == "add_location":
        form = CustomerForm(instance=customer)
        location_form = ObjectLocationForm(request.POST, prefix="site")
        add_object_open = True
        if location_form.is_valid():
            location = location_form.save(commit=False)
            location.organization = org
            location.customer = customer
            location.save()
            messages.success(request, "Einsatzort wurde hinzugefügt.")
            return redirect(f"/customers/{customer.pk}/#weitere-kontakte")
    elif request.method == "POST":
        form = CustomerForm(request.POST, instance=customer)
        location_form = ObjectLocationForm(prefix="site")
        edit_mode = True
        if form.is_valid():
            form.save()
            messages.success(request, "Kundendaten gespeichert.")
            return redirect("next-customer-detail", pk=customer.pk)
    else:
        form = CustomerForm(instance=customer)
        location_form = ObjectLocationForm(prefix="site")

    projects = (
        customer.projects.filter(organization=org)
        .select_related("object_location", "manager")
        .order_by("-updated_at")
    )
    locations = customer.object_locations.filter(organization=org).order_by("name", "city", "street")
    appointments = (
        m.CalendarEvent.objects.filter(organization=org, project__customer=customer)
        .select_related("project")
        .prefetch_related("attendees")
        .order_by("-starts_at")
    )
    quotes = (
        m.Quote.objects.filter(organization=org, project__customer=customer)
        .select_related("project", "created_by")
        .prefetch_related("items")
        .order_by("-issue_date", "-created_at")
    )
    invoices = (
        m.Invoice.objects.filter(organization=org, project__customer=customer)
        .select_related("project", "created_by")
        .prefetch_related("items", "payments")
        .order_by("-issue_date", "-created_at")
    )
    expenses = (
        m.Expense.objects.filter(organization=org, project__customer=customer)
        .select_related("project", "document")
        .order_by("-expense_date", "-created_at")
    )
    tasks = (
        m.Task.objects.filter(project__customer=customer)
        .select_related("project")
        .order_by("status", "due_at", "-created_at")
    )
    documents = (
        m.Document.objects.filter(organization=org)
        .filter(Q(customer=customer) | Q(project__customer=customer))
        .select_related("project", "uploaded_by")
        .distinct()
        .order_by("-created_at")
    )

    def document_totals(document, with_payments=False):
        net = Decimal("0")
        tax = Decimal("0")
        for item in document.items.all():
            line_net = (item.quantity or Decimal("0")) * (item.unit_price or Decimal("0"))
            net += line_net
            tax += line_net * (item.tax_rate or Decimal("0")) / Decimal("100")
        if hasattr(document, "discount_percent") and document.discount_percent:
            factor = (Decimal("100") - document.discount_percent) / Decimal("100")
            net *= factor
            tax *= factor
        gross = net + tax
        paid = Decimal("0")
        if with_payments:
            paid = sum((payment.amount or Decimal("0") for payment in document.payments.all()), Decimal("0"))
        return {
            "net": net,
            "tax": tax,
            "gross": gross,
            "paid": paid,
            "open": max(Decimal("0"), gross - paid),
        }

    quote_rows = []
    for quote in quotes:
        try:
            totals = _quote_total(quote)
        except Exception:
            totals = document_totals(quote)
        quote.tt_totals = totals
        quote_rows.append(quote)

    invoice_rows = []
    revenue_net = Decimal("0")
    open_invoice_gross = Decimal("0")
    for invoice in invoices:
        try:
            totals = _invoice_total(invoice)
        except Exception:
            totals = document_totals(invoice, with_payments=True)
        invoice.tt_totals = totals
        invoice_rows.append(invoice)
        if invoice.status != "cancelled":
            revenue_net += totals["net"]
            open_invoice_gross += totals["open"]

    expenditure_net = sum((expense.amount_net or Decimal("0") for expense in expenses), Decimal("0"))

    return render(request, "rebuild/customer_detail.html", {
        "customer": customer,
        "form": form,
        "projects": projects,
        "locations": locations,
        "location_form": location_form,
        "add_object_open": add_object_open,
        "edit_mode": edit_mode,
        "active_tab": active_tab,
        "appointments": appointments,
        "quotes": quote_rows,
        "invoices": invoice_rows,
        "expenses": expenses,
        "tasks": tasks,
        "documents": documents,
        "revenue_net": revenue_net,
        "expenditure_net": expenditure_net,
        "open_invoice_gross": open_invoice_gross,
    })
'''

    text, count = pattern.subn(replacement, text, count=1)
    if count != 1:
        raise RuntimeError("Could not replace final customer_detail view")
    write(path, text)


def patch_template() -> None:
    template = r'''{% extends 'rebuild/base.html' %}
{% block title %}{{ customer.display_name }} · A+Bau{% endblock %}
{% block content %}
<div class="tt-customer-shell" id="kundendaten">
  <aside class="tt-customer-profile">
    <div class="tt-profile-top">
      <div class="tt-customer-avatar" aria-hidden="true"><span>▦</span></div>
      <a class="tt-edit-icon" href="?edit=1&tab={{ active_tab }}#kundendaten" title="Kundendaten bearbeiten" aria-label="Kundendaten bearbeiten">✎</a>
    </div>

    <h1>{{ customer.display_name }}</h1>
    <div class="tt-customer-type">{{ customer.get_type_display|default:'Kunde' }}</div>

    <div class="tt-address-map">
      <div class="tt-primary-address">
        {% if customer.street %}<strong>{{ customer.street }}</strong>{% endif %}
        <span>{{ customer.postal_code }} {{ customer.city }}</span>
      </div>
      {% if customer.street or customer.city %}
      <iframe title="Karte für {{ customer.display_name }}" loading="lazy" referrerpolicy="no-referrer-when-downgrade" src="https://www.google.com/maps?q={{ customer.street|urlencode }}%20{{ customer.postal_code|urlencode }}%20{{ customer.city|urlencode }}&output=embed"></iframe>
      {% else %}
      <a class="tt-map-empty" href="?edit=1#kundendaten">Adresse hinzufügen</a>
      {% endif %}
    </div>

    <div class="tt-profile-rule"></div>
    <section class="tt-profile-section">
      <h2>Kundendetails</h2>
      <a href="?edit=1#kundendaten" class="tt-detail-line"><span class="tt-line-icon">☺</span><span>{% if customer.contact_name %}{{ customer.contact_name }}{% elif customer.first_name or customer.last_name %}{{ customer.first_name }} {{ customer.last_name }}{% else %}Ansprechpartner hinzufügen{% endif %}</span></a>
      <a href="?edit=1#kundendaten" class="tt-detail-line"><span class="tt-line-icon">⌕</span><span>{{ customer.phone|default:'Festnetznummer hinzufügen' }}</span></a>
      <a href="?edit=1#kundendaten" class="tt-detail-line"><span class="tt-line-icon">▯</span><span>{{ customer.mobile|default:'Mobilnummer hinzufügen' }}</span></a>
      <a href="{% if customer.email %}mailto:{{ customer.email }}{% else %}?edit=1#kundendaten{% endif %}" class="tt-detail-line"><span class="tt-line-icon">✉</span><span>{{ customer.email|default:'E-Mail-Adresse hinzufügen' }}</span></a>
    </section>

    <div class="tt-profile-rule"></div>
    <section class="tt-profile-section tt-number-block">
      <h2>Kundennummer</h2>
      <div class="tt-detail-line muted"><span class="tt-line-icon">▣</span><span>{{ customer.customer_number|default:customer.number|default:'Kundennummer hinzufügen' }}</span></div>
      <h2>Debitorennummer</h2>
      <div class="tt-detail-line muted"><span class="tt-line-icon">#</span><span>{{ customer.debtor_number|default:'–' }}</span></div>
    </section>

    <section class="tt-more-card" id="weitere-kontakte">
      <div class="tt-more-head"><h2>Weitere Standorte & Kontakte</h2><a href="?add_object=1#weitere-kontakte" title="Einsatzort hinzufügen">＋</a></div>
      {% if locations %}
      <div class="tt-location-list">
        {% for location in locations %}
        <div class="tt-location-row"><span class="tt-location-pin">⌖</span><div><b>{{ location.name|default:'Einsatzort' }}</b><small>{{ location.street }}{% if location.street %}, {% endif %}{{ location.postal_code }} {{ location.city }}</small></div></div>
        {% endfor %}
      </div>
      {% else %}
      <div class="tt-more-empty">Hier lassen sich zusätzliche Adressen oder Einsatzorte für diesen Kunden anlegen.</div>
      {% endif %}

      {% if add_object_open or location_form.errors %}
      <form class="tt-location-form" method="post">{% csrf_token %}<input type="hidden" name="action" value="add_location">
        <h3>Neuen Einsatzort erfassen</h3>
        {% for field in location_form %}<label>{{ field.label }}{{ field }}{{ field.errors }}</label>{% endfor %}
        <div class="tt-form-actions"><a href="?#weitere-kontakte" class="tt-btn tt-btn-ghost">Abbrechen</a><button class="tt-btn tt-btn-primary" type="submit">Einsatzort speichern</button></div>
      </form>
      {% endif %}
    </section>

    <div class="tt-profile-meta">
      <span>Erstellt am: <b>{{ customer.created_at|date:'d.m.Y' }}</b></span>
      <span>Zuletzt geändert: <b>{{ customer.updated_at|date:'d.m.Y' }}</b></span>
    </div>
  </aside>

  <main class="tt-customer-main">
    <div class="tt-kpis">
      <div class="tt-kpi"><span>Umsatz (netto)</span><strong>{{ revenue_net|floatformat:2 }} €</strong></div>
      <div class="tt-kpi"><span>Ausgaben (netto)</span><strong>{{ expenditure_net|floatformat:2 }} €</strong>{% if projects %}<a href="{% url 'next-expense-create' %}?project={{ projects.0.pk }}">▣ Ausgabe hinzufügen</a>{% else %}<a href="{% url 'next-expense-create' %}">▣ Ausgabe hinzufügen</a>{% endif %}</div>
      <div class="tt-kpi"><span>Offener Rechnungsbetrag (inkl. MwSt.)</span><strong class="tt-kpi-danger">{{ open_invoice_gross|floatformat:2 }} €</strong></div>
    </div>

    <section class="tt-cockpit">
      <nav class="tt-tabs" aria-label="Kundenbereiche">
        <a class="{% if active_tab == 'overview' %}is-active{% endif %}" href="?tab=overview">Übersicht</a>
        <a class="{% if active_tab == 'tasks' %}is-active{% endif %}" href="?tab=tasks">Aufgaben{% if tasks %}<span>{{ tasks|length }}</span>{% endif %}</a>
        <a class="{% if active_tab == 'documents' %}is-active{% endif %}" href="?tab=documents">Dokumente{% if documents %}<span>{{ documents|length }}</span>{% endif %}</a>
      </nav>

      {% if active_tab == 'overview' %}
      <div class="tt-tab-panel">
        <section class="tt-section">
          <div class="tt-section-title"><h2>Projekte <span>· {{ projects|length }}</span></h2><a class="tt-section-action" href="{% url 'next-project-create' %}?customer={{ customer.pk }}">＋ Projekt</a></div>
          {% if projects %}
          <div class="tt-table-wrap"><table class="tt-table"><thead><tr><th>Titel</th><th>Nr.</th><th>Status</th><th>Projektadresse</th><th></th></tr></thead><tbody>
          {% for project in projects %}<tr><td><a class="tt-row-title" href="{% url 'next-project-detail' project.pk %}">{{ project.title }}</a></td><td>{{ project.number }}</td><td><span class="tt-status tt-status-{{ project.status }}">{{ project.get_status_display }}</span></td><td>{% if project.object_location %}{{ project.object_location.street }}, {{ project.object_location.postal_code }} {{ project.object_location.city }}{% else %}{{ customer.street }}, {{ customer.postal_code }} {{ customer.city }}{% endif %}</td><td><a class="tt-more-link" href="{% url 'next-project-detail' project.pk %}">•••</a></td></tr>{% endfor %}
          </tbody></table></div>
          {% else %}<div class="tt-empty">Für diesen Kunden wurde noch kein Projekt angelegt.<a href="{% url 'next-project-create' %}?customer={{ customer.pk }}">Erstes Projekt anlegen →</a></div>{% endif %}
        </section>

        <section class="tt-section">
          <div class="tt-section-title"><h2>Termine <span>· {{ appointments|length }}</span></h2>{% if projects %}<a class="tt-section-action" href="{% url 'next-appointment-create' %}?project={{ projects.0.pk }}">＋ Termin</a>{% endif %}</div>
          {% if appointments %}<div class="tt-table-wrap"><table class="tt-table"><thead><tr><th>Datum</th><th>Titel</th><th>Projekt</th><th>Ort</th><th></th></tr></thead><tbody>{% for appointment in appointments %}<tr><td>{{ appointment.starts_at|date:'d.m.Y H:i' }}</td><td><a class="tt-row-title" href="{% url 'next-appointment-detail' appointment.pk %}">{{ appointment.title }}</a></td><td>{{ appointment.project.title|default:'–' }}</td><td>{{ appointment.location|default:'–' }}</td><td><a class="tt-more-link" href="{% url 'next-appointment-detail' appointment.pk %}">•••</a></td></tr>{% endfor %}</tbody></table></div>{% else %}<div class="tt-empty">Es wurden noch keine Termine erstellt.</div>{% endif %}
        </section>

        <section class="tt-section">
          <div class="tt-section-title"><h2>Angebote <span>· {{ quotes|length }}</span></h2>{% if projects %}<a class="tt-section-action" href="{% url 'next-quote-create' %}?project={{ projects.0.pk }}">＋ Angebot</a>{% endif %}</div>
          {% if quotes %}<div class="tt-table-wrap"><table class="tt-table"><thead><tr><th>Datum</th><th>Nr.</th><th>Status</th><th>Angebotstitel</th><th>Erstellt von</th><th class="tt-money">Betrag</th><th></th></tr></thead><tbody>{% for quote in quotes %}<tr><td>{{ quote.issue_date|date:'d.m.Y' }}</td><td>{{ quote.number }}</td><td><span class="tt-status tt-status-{{ quote.status }}">{{ quote.get_status_display }}</span></td><td>{{ quote.title|default:quote.project.title|default:'Angebot' }}</td><td>{% if quote.created_by %}{{ quote.created_by.get_full_name|default:quote.created_by.username }}{% else %}–{% endif %}</td><td class="tt-money">{{ quote.tt_totals.gross|floatformat:2 }} €</td><td><a class="tt-more-link" href="{% url 'next-quote-edit' quote.pk %}">•••</a></td></tr>{% endfor %}</tbody></table></div>{% else %}<div class="tt-empty">Es wurden noch keine Angebote erstellt.</div>{% endif %}
        </section>

        <section class="tt-section">
          <div class="tt-section-title"><h2>Rechnungen <span>· {{ invoices|length }}</span></h2>{% if projects %}<a class="tt-section-action" href="{% url 'next-invoice-create' %}?project={{ projects.0.pk }}">＋ Rechnung</a>{% endif %}</div>
          {% if invoices %}<div class="tt-table-wrap"><table class="tt-table"><thead><tr><th>Datum</th><th>Nr.</th><th>Status</th><th>Projekt</th><th class="tt-money">Betrag</th><th class="tt-money">Offen</th><th></th></tr></thead><tbody>{% for invoice in invoices %}<tr><td>{{ invoice.issue_date|date:'d.m.Y' }}</td><td>{{ invoice.number }}</td><td><span class="tt-status tt-status-{{ invoice.status }}">{{ invoice.get_status_display }}</span></td><td>{{ invoice.project.title }}</td><td class="tt-money">{{ invoice.tt_totals.gross|floatformat:2 }} €</td><td class="tt-money">{{ invoice.tt_totals.open|floatformat:2 }} €</td><td><a class="tt-more-link" href="{% url 'next-invoice-edit' invoice.pk %}">•••</a></td></tr>{% endfor %}</tbody></table></div>{% else %}<div class="tt-empty">Es wurden noch keine Rechnungen erstellt.</div>{% endif %}
        </section>

        <section class="tt-section tt-section-last">
          <div class="tt-section-title"><h2>Belege <span>· {{ expenses|length }}</span></h2>{% if projects %}<a class="tt-section-action" href="{% url 'next-expense-create' %}?project={{ projects.0.pk }}">＋ Ausgabe</a>{% endif %}</div>
          {% if expenses %}<div class="tt-table-wrap"><table class="tt-table"><thead><tr><th>Datum</th><th>Lieferant</th><th>Beschreibung</th><th>Projekt</th><th class="tt-money">Netto</th><th></th></tr></thead><tbody>{% for expense in expenses %}<tr><td>{{ expense.expense_date|date:'d.m.Y' }}</td><td>{{ expense.supplier }}</td><td>{{ expense.description }}</td><td>{{ expense.project.title|default:'–' }}</td><td class="tt-money">{{ expense.amount_net|floatformat:2 }} €</td><td><a class="tt-more-link" href="{% url 'next-expense-edit' expense.pk %}">•••</a></td></tr>{% endfor %}</tbody></table></div>{% else %}<div class="tt-empty">Es wurden noch keine Belege erfasst.</div>{% endif %}
        </section>
      </div>

      {% elif active_tab == 'tasks' %}
      <div class="tt-tab-panel">
        <section class="tt-section tt-section-last">
          <div class="tt-section-title"><h2>Aufgaben <span>· {{ tasks|length }}</span></h2>{% if projects %}<a class="tt-section-action" href="{% url 'next-task-create' %}?project={{ projects.0.pk }}">＋ Aufgabe</a>{% endif %}</div>
          {% if tasks %}<div class="tt-table-wrap"><table class="tt-table"><thead><tr><th>Aufgabe</th><th>Projekt</th><th>Status</th><th>Fällig</th><th></th></tr></thead><tbody>{% for task in tasks %}<tr><td><a class="tt-row-title" href="{% url 'next-task-edit' task.pk %}">{{ task.title }}</a></td><td>{{ task.project.title }}</td><td><span class="tt-status tt-status-{{ task.status }}">{{ task.get_status_display }}</span></td><td>{{ task.due_at|date:'d.m.Y'|default:'–' }}</td><td><a class="tt-more-link" href="{% url 'next-task-edit' task.pk %}">•••</a></td></tr>{% endfor %}</tbody></table></div>{% else %}<div class="tt-empty">Für diesen Kunden gibt es noch keine Aufgaben.</div>{% endif %}
        </section>
      </div>

      {% else %}
      <div class="tt-tab-panel">
        <section class="tt-section tt-section-last">
          <div class="tt-section-title"><h2>Dokumente <span>· {{ documents|length }}</span></h2>{% if projects %}<a class="tt-section-action" href="{% url 'next-project-detail' projects.0.pk %}#dokumente">＋ Dokument</a>{% endif %}</div>
          {% if documents %}<div class="tt-table-wrap"><table class="tt-table"><thead><tr><th>Dokument</th><th>Kategorie</th><th>Projekt</th><th>Datum</th><th></th></tr></thead><tbody>{% for document in documents %}<tr><td>{% if document.file %}<a class="tt-row-title" href="{{ document.file.url }}" target="_blank" rel="noopener">{{ document.title }}</a>{% else %}<span class="tt-row-title">{{ document.title }}</span>{% endif %}</td><td>{{ document.get_category_display }}</td><td>{{ document.project.title|default:'Kunde' }}</td><td>{{ document.created_at|date:'d.m.Y' }}</td><td>{% if document.file %}<a class="tt-more-link" href="{{ document.file.url }}" target="_blank" rel="noopener">↗</a>{% endif %}</td></tr>{% endfor %}</tbody></table></div>{% else %}<div class="tt-empty">Für diesen Kunden gibt es noch keine Dokumente.</div>{% endif %}
        </section>
      </div>
      {% endif %}
    </section>
  </main>
</div>

{% if edit_mode %}
<div class="tt-editor-backdrop" role="presentation">
  <section class="tt-editor" role="dialog" aria-modal="true" aria-labelledby="tt-editor-title">
    <div class="tt-editor-head"><div><span>Kunde bearbeiten</span><h2 id="tt-editor-title">{{ customer.display_name }}</h2></div><a href="?tab={{ active_tab }}#kundendaten" aria-label="Schließen">×</a></div>
    <form method="post" class="tt-editor-form">{% csrf_token %}<input type="hidden" name="action" value="update_customer">
      <div class="tt-editor-grid">{% for field in form %}<label class="{% if field.name == 'street' or field.name == 'notes' %}is-wide{% endif %}"><span>{{ field.label }}</span>{{ field }}{{ field.errors }}</label>{% endfor %}</div>
      <div class="tt-form-actions"><a class="tt-btn tt-btn-ghost" href="?tab={{ active_tab }}#kundendaten">Abbrechen</a><button class="tt-btn tt-btn-primary" type="submit">Änderungen speichern</button></div>
    </form>
  </section>
</div>
{% endif %}
{% endblock %}
'''
    write("templates/rebuild/customer_detail.html", template)


def patch_css() -> None:
    css_path = "static/css/kayi-readability.css" if (ROOT / "static/css/kayi-readability.css").exists() else "static/css/kayi-next.css"
    css = read(css_path)
    if MARKER not in css:
        css += r'''

/* KAYI TOOLTIME CUSTOMER DETAIL PARITY 2026-09-07 */
.tt-customer-shell{display:grid;grid-template-columns:310px minmax(0,1fr);gap:0;margin:-28px -34px -42px;min-height:calc(100vh - 68px);background:#f7f8fa;color:#24313d}.tt-customer-profile{position:relative;background:#fff;border-right:1px solid #e7eaee;padding:34px 26px 40px;min-width:0}.tt-profile-top{display:flex;align-items:flex-start;justify-content:space-between;gap:18px}.tt-customer-avatar{width:70px;height:70px;border-radius:50%;display:grid;place-items:center;background:#f0f3f5;color:#8292a2;font-size:34px}.tt-edit-icon{display:grid;place-items:center;width:34px;height:34px;border-radius:8px;color:#577a9b;text-decoration:none;font-size:21px}.tt-edit-icon:hover{background:#f1f5f8}.tt-customer-profile>h1{font-size:23px;line-height:1.2;margin:18px 0 4px;color:#2f3b46}.tt-customer-type{font-size:13px;color:#788592}.tt-address-map{display:grid;grid-template-columns:minmax(0,1fr) 116px;gap:16px;align-items:center;margin-top:48px;min-height:74px}.tt-primary-address{display:grid;gap:3px;font-size:13px;line-height:1.35}.tt-primary-address strong{font-weight:700}.tt-primary-address span{color:#465562}.tt-address-map iframe{width:116px;height:72px;border:0;border-radius:2px;background:#eef1f4}.tt-map-empty{display:grid;place-items:center;height:72px;padding:8px;border-radius:5px;background:#f7f8fa;color:#2583d8;text-decoration:none;font-size:12px;text-align:center}.tt-profile-rule{height:1px;background:#e4e8ec;margin:34px 0 26px}.tt-profile-section h2,.tt-number-block h2{margin:0 0 9px;font-size:12px;font-weight:500;color:#8a96a2}.tt-detail-line{display:flex;align-items:center;gap:11px;min-height:27px;color:#1476d4;text-decoration:none;font-size:13px;overflow:hidden}.tt-detail-line span:last-child{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.tt-detail-line.muted{color:#586675}.tt-line-icon{display:inline-grid;place-items:center;width:18px;color:#71899e}.tt-number-block h2:not(:first-child){margin-top:17px}.tt-more-card{margin-top:42px;padding:18px;border:1px solid #e8ebef;border-radius:10px;box-shadow:0 1px 4px rgba(26,39,52,.04)}.tt-more-head{display:flex;align-items:center;justify-content:space-between;gap:12px}.tt-more-head h2{margin:0;font-size:14px}.tt-more-head>a{display:grid;place-items:center;width:30px;height:30px;border-radius:7px;color:#264d70;text-decoration:none;font-size:23px}.tt-more-empty{margin-top:15px;padding:18px 13px;border-radius:7px;background:#f8f9fb;color:#8a97a4;font-size:12px;line-height:1.45;text-align:center}.tt-location-list{display:grid;margin-top:12px}.tt-location-row{display:grid;grid-template-columns:22px minmax(0,1fr);gap:8px;padding:10px 0;border-top:1px solid #edf0f2}.tt-location-row:first-child{border-top:0}.tt-location-row>div{display:grid;gap:2px}.tt-location-row b{font-size:12.5px}.tt-location-row small{color:#7d8994;font-size:11px}.tt-location-pin{color:#6a8093}.tt-location-form{display:grid;gap:10px;margin-top:15px;padding-top:14px;border-top:1px solid #edf0f2}.tt-location-form h3{margin:0 0 2px;font-size:13px}.tt-location-form label{display:grid;gap:5px;color:#596775;font-size:11px}.tt-location-form input,.tt-location-form textarea,.tt-location-form select{width:100%;min-height:36px;border:1px solid #dce1e6;border-radius:6px;background:#fff;padding:7px 9px}.tt-profile-meta{display:grid;gap:8px;margin-top:36px;padding:0 8px;color:#8994a0;font-size:10.5px}.tt-profile-meta b{color:#6b7782;font-weight:500}.tt-customer-main{padding:14px 20px 34px;min-width:0}.tt-kpis{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px}.tt-kpi{min-height:70px;display:flex;flex-direction:column;justify-content:center;padding:12px 16px;border:1px solid #eef0f3;border-radius:8px;background:#fff}.tt-kpi>span{font-size:11px;color:#7f8b97}.tt-kpi>strong{margin-top:3px;font-size:16px}.tt-kpi>a{margin-top:4px;color:#1479d7;text-decoration:none;font-size:11px;font-weight:600}.tt-kpi-danger{color:#ea4949}.tt-cockpit{margin-top:14px;border:1px solid #eef0f2;border-radius:10px;background:#fff;overflow:hidden;min-height:700px}.tt-tabs{display:flex;gap:30px;padding:0 20px;border-bottom:1px solid #dfe4e8}.tt-tabs>a{position:relative;display:flex;align-items:center;gap:6px;height:48px;color:#7d8893;text-decoration:none;font-size:12px;font-weight:600}.tt-tabs>a.is-active{color:#37434f}.tt-tabs>a.is-active:after{content:"";position:absolute;left:0;right:0;bottom:-1px;height:2px;background:#1685ed}.tt-tabs span{display:grid;place-items:center;min-width:18px;height:18px;padding:0 5px;border-radius:9px;background:#f0f3f5;color:#65727e;font-size:10px}.tt-tab-panel{padding:0 20px 24px}.tt-section{padding:22px 0 26px;border-bottom:1px solid #edf0f2}.tt-section-last{border-bottom:0}.tt-section-title{display:flex;align-items:center;justify-content:space-between;gap:12px;margin-bottom:14px}.tt-section-title h2{margin:0;font-size:13px}.tt-section-title h2 span{color:#82909d;font-weight:500}.tt-section-action{padding:6px 9px;border:1px solid #e0e5e9;border-radius:6px;color:#36556f;text-decoration:none;font-size:11px;font-weight:600;background:#fff}.tt-section-action:hover{background:#f7f9fb}.tt-table-wrap{overflow:auto;border:1px solid #edf0f2;border-radius:7px}.tt-table{width:100%;border-collapse:collapse;min-width:690px;background:#fff}.tt-table th{padding:10px 12px;border-bottom:1px solid #dfe4e8;color:#84909c;font-size:10px;font-weight:500;text-align:left;white-space:nowrap}.tt-table td{padding:12px;border-bottom:1px solid #edf0f2;color:#3e4b57;font-size:11.5px;vertical-align:middle}.tt-table tbody tr:last-child td{border-bottom:0}.tt-row-title{color:#33414d;text-decoration:none;font-weight:700}.tt-row-title:hover{color:#147bd9}.tt-money{text-align:right!important;font-variant-numeric:tabular-nums;font-weight:650}.tt-more-link{display:inline-grid;place-items:center;min-width:28px;color:#476783;text-decoration:none;font-weight:700;letter-spacing:1px}.tt-status{display:inline-flex;align-items:center;min-height:22px;padding:3px 8px;border-radius:11px;background:#e9eef2;color:#597083;font-size:10px;font-weight:650;white-space:nowrap}.tt-status-draft,.tt-status-review,.tt-status-inquiry{background:#dceffd;color:#3c83ad}.tt-status-sent,.tt-status-waiting,.tt-status-planning,.tt-status-overdue{background:#fff1c6;color:#9d7622}.tt-status-accepted,.tt-status-paid,.tt-status-confirmed,.tt-status-in_progress,.tt-status-completed,.tt-status-done{background:#dff3e8;color:#3d805b}.tt-status-rejected,.tt-status-cancelled{background:#fde3e3;color:#a15353}.tt-empty{display:grid;justify-items:center;gap:8px;padding:32px 18px;color:#929eaa;font-size:12px;text-align:center}.tt-empty a{color:#167bcf;text-decoration:none;font-weight:700}.tt-editor-backdrop{position:fixed;z-index:9000;inset:0;display:flex;justify-content:flex-end;background:rgba(25,35,44,.32);backdrop-filter:blur(2px)}.tt-editor{width:min(680px,94vw);height:100%;overflow:auto;background:#fff;box-shadow:-18px 0 48px rgba(18,28,38,.18);padding:24px}.tt-editor-head{display:flex;align-items:flex-start;justify-content:space-between;gap:20px;padding-bottom:20px;border-bottom:1px solid #e9ecef}.tt-editor-head span{font-size:11px;color:#8b96a1}.tt-editor-head h2{margin:4px 0 0;font-size:22px}.tt-editor-head>a{display:grid;place-items:center;width:36px;height:36px;border-radius:8px;color:#52616e;text-decoration:none;font-size:28px}.tt-editor-form{padding-top:20px}.tt-editor-grid{display:grid;grid-template-columns:1fr 1fr;gap:15px}.tt-editor-grid label{display:grid;gap:6px;color:#53616d;font-size:11px;font-weight:600}.tt-editor-grid label.is-wide{grid-column:1/-1}.tt-editor-grid input,.tt-editor-grid select,.tt-editor-grid textarea{width:100%;min-height:42px;border:1px solid #d8dee4;border-radius:7px;background:#fff;padding:8px 10px;font:inherit}.tt-form-actions{display:flex;justify-content:flex-end;gap:9px;margin-top:20px}.tt-btn{display:inline-flex;align-items:center;justify-content:center;min-height:38px;padding:8px 13px;border-radius:7px;text-decoration:none;font-size:12px;font-weight:700;cursor:pointer}.tt-btn-primary{border:1px solid #c38c15;background:#d5a326;color:#151719}.tt-btn-ghost{border:1px solid #dce2e7;background:#fff;color:#4b5965}
@media(max-width:1180px){.tt-customer-shell{grid-template-columns:270px minmax(0,1fr)}.tt-address-map{grid-template-columns:1fr}.tt-address-map iframe{width:100%}.tt-kpis{grid-template-columns:1fr 1fr}.tt-kpi:last-child{grid-column:1/-1}}
@media(max-width:860px){.tt-customer-shell{grid-template-columns:1fr;margin:-20px -18px -32px}.tt-customer-profile{border-right:0;border-bottom:1px solid #e6eaed;padding:24px 20px}.tt-address-map{grid-template-columns:minmax(0,1fr) 140px;margin-top:26px}.tt-customer-main{padding:14px 12px 28px}.tt-kpis{grid-template-columns:1fr}.tt-kpi:last-child{grid-column:auto}.tt-cockpit{min-height:0}.tt-tabs{gap:18px;overflow:auto}.tt-tab-panel{padding:0 12px 16px}.tt-profile-meta{margin-top:24px}.tt-more-card{margin-top:26px}}
@media(max-width:560px){.tt-address-map{grid-template-columns:1fr}.tt-address-map iframe{width:100%;height:120px}.tt-editor{width:100vw;padding:18px}.tt-editor-grid{grid-template-columns:1fr}.tt-editor-grid label.is-wide{grid-column:auto}.tt-tabs{padding:0 14px}.tt-section-title{align-items:flex-start}.tt-section-action{white-space:nowrap}.tt-kpi{min-height:62px}}
'''
        write(css_path, css)

    base_path = "templates/rebuild/base.html"
    base = read(base_path)
    asset = Path(css_path).name
    pattern = re.compile(rf"(static 'css/{re.escape(asset)}' %\}}\?v=)[^\"']+")
    updated, count = pattern.subn(rf"\g<1>{VERSION}", base, count=1)
    if count == 0:
        raw = f"static 'css/{asset}' %}}"
        updated = base.replace(raw, raw + f"?v={VERSION}", 1) if raw in base else base
    write(base_path, updated)


def install_tests() -> None:
    write("tests/test_tooltime_customer_detail_exact_parity.py", r'''from pathlib import Path
from django.test import SimpleTestCase

ROOT = Path(__file__).resolve().parents[1]


class ToolTimeCustomerDetailParityContract(SimpleTestCase):
    def test_customer_surface_contains_tooltime_sections_and_tabs(self):
        template = (ROOT / "templates/rebuild/customer_detail.html").read_text(encoding="utf-8")
        for marker in (
            "Umsatz (netto)", "Ausgaben (netto)", "Offener Rechnungsbetrag (inkl. MwSt.)",
            "Übersicht", "Aufgaben", "Dokumente", "Projekte", "Termine", "Angebote",
            "Rechnungen", "Belege", "Weitere Standorte & Kontakte",
        ):
            self.assertIn(marker, template)
        self.assertIn('?edit=1&tab={{ active_tab }}', template)
        self.assertIn('name="action" value="add_location"', template)

    def test_customer_view_scopes_operational_data_to_customer(self):
        views = (ROOT / "erp/rebuild_views.py").read_text(encoding="utf-8")
        self.assertIn('project__customer=customer', views)
        self.assertIn('Q(customer=customer) | Q(project__customer=customer)', views)
        self.assertIn('revenue_net', views)
        self.assertIn('open_invoice_gross', views)
        self.assertIn('expenditure_net', views)

    def test_surface_is_responsive_and_has_read_only_default(self):
        css_candidates = [ROOT / "static/css/kayi-readability.css", ROOT / "static/css/kayi-next.css"]
        css = next(path for path in css_candidates if path.exists()).read_text(encoding="utf-8")
        template = (ROOT / "templates/rebuild/customer_detail.html").read_text(encoding="utf-8")
        self.assertIn("KAYI TOOLTIME CUSTOMER DETAIL PARITY", css)
        self.assertIn("@media(max-width:860px)", css)
        self.assertIn("{% if edit_mode %}", template)
''')


def guard() -> None:
    template = read("templates/rebuild/customer_detail.html")
    views = read("erp/rebuild_views.py")
    css_path = "static/css/kayi-readability.css" if (ROOT / "static/css/kayi-readability.css").exists() else "static/css/kayi-next.css"
    css = read(css_path)
    for marker in ("Umsatz (netto)", "Weitere Standorte & Kontakte", "tt-customer-shell", "tt-editor-backdrop"):
        if marker not in template:
            raise RuntimeError(f"ToolTime customer surface missing: {marker}")
    for marker in ("open_invoice_gross", "project__customer=customer", "Q(customer=customer) | Q(project__customer=customer)"):
        if marker not in views:
            raise RuntimeError(f"ToolTime customer data wiring missing: {marker}")
    if MARKER not in css:
        raise RuntimeError("ToolTime customer detail CSS was not installed")


def main() -> None:
    patch_view()
    patch_template()
    patch_css()
    install_tests()
    guard()
    print("ToolTime customer detail parity installed and guarded.")


if __name__ == "__main__":
    main()
