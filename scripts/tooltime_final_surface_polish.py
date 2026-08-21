from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MARKER = "KAYI TOOLTIME FINAL SURFACE 2026-08-21"


def read(rel: str) -> str:
    path = ROOT / rel
    if not path.exists():
        raise RuntimeError(f"Final surface target missing: {rel}")
    return path.read_text(encoding="utf-8")


def write(rel: str, text: str) -> None:
    path = ROOT / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


PROJECT_VIEW = '''@login_required
def project_detail(request, pk):
    org = _org(request)
    project = get_object_or_404(
        m.Project.objects.select_related("customer", "object_location", "manager"),
        pk=pk,
        organization=org,
    )
    appointments = project.events.prefetch_related("attendees").order_by("-starts_at")[:20]
    quotes = list(project.quotes.prefetch_related("items").order_by("-created_at"))
    invoices = list(project.invoices.prefetch_related("items", "payments").order_by("-created_at"))
    documents = list(project.documents.order_by("-created_at")[:30])
    tasks = project.tasks.order_by("status", "due_at")[:20]
    materials = project.materials.order_by("-created_at")[:20]

    quote_rows = [{"quote": quote, "total": _quote_total(quote)} for quote in quotes]
    invoice_rows = [{"invoice": invoice, "total": _invoice_total(invoice)} for invoice in invoices]
    invoice_gross = sum((row["total"]["gross"] for row in invoice_rows), Decimal("0"))
    turnover_net = sum((row["total"]["net"] for row in invoice_rows), Decimal("0"))
    open_amount = sum(
        (row["total"]["gross"] for row in invoice_rows if row["invoice"].status not in {"paid", "cancelled", "canceled", "void"}),
        Decimal("0"),
    )

    project_expenditure = Decimal("0")
    expense_model = getattr(m, "Expense", None)
    if expense_model is not None:
        try:
            fields = {field.name for field in expense_model._meta.get_fields()}
            expense_qs = expense_model.objects.filter(organization=org)
            if "project" in fields:
                expense_qs = expense_qs.filter(project=project)
            for expense in expense_qs[:500]:
                raw = getattr(expense, "net_amount", None)
                if raw is None:
                    raw = getattr(expense, "amount_net", None)
                if raw is None:
                    raw = getattr(expense, "amount", 0)
                project_expenditure += Decimal(str(raw or 0))
        except Exception:
            project_expenditure = Decimal("0")

    time_entries = m.TimeEntry.objects.filter(
        organization=org,
        project=project,
    ).select_related("employee").order_by("-started_at")[:30]
    receipts = [
        document for document in documents
        if str(getattr(document, "category", "")) in {"receipt", "expense", "beleg"}
        or str((getattr(document, "metadata", {}) or {}).get("kind", "")) in {"receipt", "expense", "beleg"}
    ]

    return render(request, "rebuild/project_detail.html", {
        "project": project,
        "appointments": appointments,
        "quotes": quotes,
        "quote_rows": quote_rows,
        "invoices": invoices,
        "invoice_rows": invoice_rows,
        "documents": documents,
        "receipts": receipts,
        "tasks": tasks,
        "materials": materials,
        "time_entries": time_entries,
        "invoice_gross": invoice_gross,
        "turnover_net": turnover_net,
        "project_expenditure": project_expenditure,
        "open_amount": open_amount,
    })
'''


def patch_project_view() -> None:
    rel = "erp/rebuild_views.py"
    source = read(rel)
    pattern = re.compile(
        r'@login_required\ndef project_detail\(request, pk\):.*?(?=\n\n@login_required\ndef appointment_list\(request\):)',
        re.S,
    )
    source, count = pattern.subn(PROJECT_VIEW.rstrip(), source, count=1)
    if count != 1:
        raise RuntimeError("Could not install final ToolTime project detail context")
    write(rel, source)


PROJECT_TEMPLATE = r'''{% extends 'rebuild/base.html' %}
{% block title %}{{ project.title }} · KAYI{% endblock %}
{% block content %}
<div class="tt-project-page" data-tooltime-project-detail>
  <aside class="tt-project-rail">
    <section class="tt-project-identity">
      <div class="tt-project-title-row">
        <h1>{{ project.title }}</h1>
        <span class="tt-icon-button" title="Projektdaten">
          <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 20h9"/><path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L8 18l-4 1 1-4Z"/></svg>
        </span>
      </div>
      <div class="tt-project-meta-grid">
        <div><span>Projektnummer</span><strong>{{ project.number }}</strong></div>
        <div><span>Erstellt am</span><strong>{{ project.created_at|date:'d.m.Y' }}</strong></div>
      </div>
      <div class="tt-project-description"><span>Projektbeschreibung</span><p>{{ project.description|default:'Keine Beschreibung hinterlegt.'|linebreaksbr }}</p></div>
    </section>

    <section class="tt-rail-card">
      <a class="tt-customer-link" href="{% url 'next-customer-detail' project.customer.pk %}">
        <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3 11.5 12 4l9 7.5"/><path d="M5.5 10.5V20h13v-9.5"/><path d="M9.5 20v-6h5v6"/></svg>
        <strong>{{ project.customer.display_name }}</strong>
      </a>
      <div class="tt-rail-divider"></div>
      <span class="tt-small-label">Kundendaten</span>
      <div class="tt-contact-line"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M20 10c0 5-8 11-8 11S4 15 4 10a8 8 0 1 1 16 0Z"/><circle cx="12" cy="10" r="2.5"/></svg><span>{{ project.customer.street|default:'Keine Straße' }}, {{ project.customer.postal_code }} {{ project.customer.city }}</span></div>
      {% if project.customer.email %}<div class="tt-contact-line"><svg viewBox="0 0 24 24" aria-hidden="true"><rect x="3" y="5" width="18" height="14" rx="2"/><path d="m3 7 9 6 9-6"/></svg><a href="mailto:{{ project.customer.email }}">{{ project.customer.email }}</a></div>{% endif %}
      {% if project.customer.mobile or project.customer.phone %}<div class="tt-contact-line"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M22 16.9v3a2 2 0 0 1-2.2 2 19.8 19.8 0 0 1-8.6-3.1 19.4 19.4 0 0 1-6-6A19.8 19.8 0 0 1 2.1 4.2 2 2 0 0 1 4.1 2h3a2 2 0 0 1 2 1.7c.1 1 .4 2 .7 2.9a2 2 0 0 1-.5 2.1L8.1 9.9a16 16 0 0 0 6 6l1.2-1.2a2 2 0 0 1 2.1-.5c.9.3 1.9.6 2.9.7A2 2 0 0 1 22 16.9Z"/></svg><a href="tel:{{ project.customer.mobile|default:project.customer.phone }}">{{ project.customer.mobile|default:project.customer.phone }}</a></div>{% endif %}
    </section>

    <section class="tt-rail-card tt-site-card">
      <span class="tt-small-label">Einsatzort</span>
      {% if project.object_location %}
        {% if project.object_location.contact_name %}<div class="tt-contact-line"><svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="8" r="4"/><path d="M4 21c1.5-5 4.2-7 8-7s6.5 2 8 7"/></svg><span>{{ project.object_location.contact_name }}</span></div>{% endif %}
        {% if project.object_location.mobile %}<div class="tt-contact-line"><svg viewBox="0 0 24 24" aria-hidden="true"><rect x="7" y="2" width="10" height="20" rx="2"/><path d="M11 18h2"/></svg><a href="tel:{{ project.object_location.mobile }}">{{ project.object_location.mobile }}</a></div>{% endif %}
        {% if project.object_location.phone %}<div class="tt-contact-line"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M22 16.9v3a2 2 0 0 1-2.2 2 19.8 19.8 0 0 1-8.6-3.1 19.4 19.4 0 0 1-6-6A19.8 19.8 0 0 1 2.1 4.2 2 2 0 0 1 4.1 2h3a2 2 0 0 1 2 1.7c.1 1 .4 2 .7 2.9a2 2 0 0 1-.5 2.1L8.1 9.9a16 16 0 0 0 6 6l1.2-1.2a2 2 0 0 1 2.1-.5c.9.3 1.9.6 2.9.7A2 2 0 0 1 22 16.9Z"/></svg><a href="tel:{{ project.object_location.phone }}">{{ project.object_location.phone }}</a></div>{% endif %}
        {% if project.object_location.email %}<div class="tt-contact-line"><svg viewBox="0 0 24 24" aria-hidden="true"><rect x="3" y="5" width="18" height="14" rx="2"/><path d="m3 7 9 6 9-6"/></svg><a href="mailto:{{ project.object_location.email }}">{{ project.object_location.email }}</a></div>{% endif %}
        <div class="tt-contact-line"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M20 10c0 5-8 11-8 11S4 15 4 10a8 8 0 1 1 16 0Z"/><circle cx="12" cy="10" r="2.5"/></svg><a target="_blank" rel="noopener" href="https://www.google.com/maps/search/?api=1&query={{ project.object_location.street|urlencode }}%20{{ project.object_location.postal_code|urlencode }}%20{{ project.object_location.city|urlencode }}">{{ project.object_location.street }}, {{ project.object_location.postal_code }} {{ project.object_location.city }}</a></div>
        <div class="tt-map-frame"><iframe title="Karte Einsatzort" loading="lazy" referrerpolicy="no-referrer-when-downgrade" src="https://www.google.com/maps?q={{ project.object_location.street|urlencode }}%20{{ project.object_location.postal_code|urlencode }}%20{{ project.object_location.city|urlencode }}&output=embed"></iframe></div>
      {% else %}
        <div class="tt-contact-line"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M20 10c0 5-8 11-8 11S4 15 4 10a8 8 0 1 1 16 0Z"/><circle cx="12" cy="10" r="2.5"/></svg><a target="_blank" rel="noopener" href="https://www.google.com/maps/search/?api=1&query={{ project.customer.street|urlencode }}%20{{ project.customer.postal_code|urlencode }}%20{{ project.customer.city|urlencode }}">{{ project.customer.street }}, {{ project.customer.postal_code }} {{ project.customer.city }}</a></div>
        <div class="tt-map-frame"><iframe title="Karte Einsatzort" loading="lazy" referrerpolicy="no-referrer-when-downgrade" src="https://www.google.com/maps?q={{ project.customer.street|urlencode }}%20{{ project.customer.postal_code|urlencode }}%20{{ project.customer.city|urlencode }}&output=embed"></iframe></div>
      {% endif %}
    </section>

    <section class="tt-project-tools">
      <span class="tt-small-label">Projektwerkzeuge</span>
      <div class="tt-tool-links">
        <a href="{% url 'next-appointment-create' %}?project={{ project.pk }}"><svg viewBox="0 0 24 24"><rect x="3" y="5" width="18" height="16" rx="2"/><path d="M8 3v4M16 3v4M3 10h18"/></svg>Termin</a>
        <a href="{% url 'configurator' %}?project={{ project.pk }}"><svg viewBox="0 0 24 24"><path d="m4 7 8-4 8 4-8 4Z"/><path d="m4 12 8 4 8-4M4 17l8 4 8-4"/></svg>Aufmaß & 3D</a>
        {% if not field_user %}<a href="{% url 'next-quote-create' %}?project={{ project.pk }}"><svg viewBox="0 0 24 24"><path d="M6 2h9l4 4v16H6Z"/><path d="M14 2v5h5M9 12h7M9 16h7"/></svg>Angebot</a><a href="{% url 'next-invoice-create' %}?project={{ project.pk }}"><svg viewBox="0 0 24 24"><path d="M6 2h12v20l-3-2-3 2-3-2-3 2Z"/><path d="M9 8h6M9 12h6M9 16h4"/></svg>Rechnung</a>{% endif %}
        {% if field_user %}<a href="{% url 'next-field' %}"><svg viewBox="0 0 24 24"><path d="M14.7 6.3a4 4 0 0 0-5 5L3 18v3h3l6.7-6.7a4 4 0 0 0 5-5l-2.4 2.4-3-3Z"/></svg>Dokumentieren</a>{% endif %}
      </div>
    </section>

    <div class="tt-created-meta">
      <div><span>Erstellt am:</span> {{ project.created_at|date:'d.m.Y' }}</div>
      <div><span>Verantwortlich:</span> {% if project.manager %}{{ project.manager.first_name }} {{ project.manager.last_name }}{% else %}–{% endif %}</div>
      <div><span>Letzte Änderung:</span> {{ project.updated_at|date:'d.m.Y' }}</div>
    </div>
  </aside>

  <main class="tt-project-main">
    <div class="tt-project-kpis">
      <div class="tt-kpi"><span>Umsatz (netto)</span><strong>€{{ turnover_net|floatformat:2 }}</strong></div>
      <div class="tt-kpi"><span>Ausgaben (netto)</span><strong>€{{ project_expenditure|floatformat:2 }}</strong><a href="{% url 'next-expenses' %}"><svg viewBox="0 0 24 24"><path d="M6 2h12v20l-3-2-3 2-3-2-3 2Z"/><path d="M9 8h6M9 12h6"/></svg>Ausgabe hinzufügen</a></div>
      <div class="tt-kpi tt-kpi-open"><span>Offener Betrag (brutto)</span><strong>€{{ open_amount|floatformat:2 }}</strong></div>
    </div>

    <section class="tt-project-panel" data-tabs>
      <div class="tt-project-tabs">
        <button type="button" class="is-active" data-tab="overview">Übersicht</button>
        <button type="button" data-tab="tasks">Aufgaben{% if tasks %}<span class="tt-count">{{ tasks|length }}</span>{% endif %}</button>
        <button type="button" data-tab="documents">Dokumente{% if documents %}<span class="tt-count">{{ documents|length }}</span>{% endif %}</button>
      </div>

      <div class="nx-tab-panel is-active tt-overview" data-tab-panel="overview">
        <section class="tt-project-section">
          <div class="tt-section-head"><h2>Termine</h2><a href="{% url 'next-appointment-create' %}?project={{ project.pk }}">+ Termin</a></div>
          {% for event in appointments %}<a class="tt-list-row tt-appointment-row" href="{% url 'next-appointment-detail' event.pk %}"><div><strong>{{ event.starts_at|date:'d.m.Y' }} · {{ event.starts_at|date:'H:i' }}</strong><span>{{ event.title }}</span></div><span class="tt-status">{{ event.get_type_display }}</span></a>{% empty %}<div class="tt-empty">Noch keine Termine angelegt.</div>{% endfor %}
        </section>

        <section class="tt-project-section">
          <div class="tt-section-head"><h2>Angebote <span>· {{ quote_rows|length }}</span></h2>{% if not field_user %}<a href="{% url 'next-quote-create' %}?project={{ project.pk }}">+ Angebot</a>{% endif %}</div>
          {% if quote_rows %}<div class="tt-project-table-wrap"><table class="tt-project-table"><thead><tr><th>Datum</th><th>Nr.</th><th>Status</th><th>Titel</th><th class="tt-money">Betrag</th><th></th></tr></thead><tbody>{% for row in quote_rows %}<tr><td>{{ row.quote.issue_date|date:'d.m.Y' }}</td><td><strong>{{ row.quote.number }}</strong></td><td><span class="tt-status">{{ row.quote.get_status_display }}</span></td><td>Angebot</td><td class="tt-money">€{{ row.total.gross|floatformat:2 }}</td><td class="tt-more"><a href="{% url 'next-quote-edit' row.quote.pk %}" aria-label="Angebot öffnen">•••</a></td></tr>{% endfor %}</tbody></table></div>{% else %}<div class="tt-empty">Noch keine Angebote erstellt.</div>{% endif %}
        </section>

        <section class="tt-project-section">
          <div class="tt-section-head"><h2>Rechnungen</h2>{% if not field_user %}<a href="{% url 'next-invoice-create' %}?project={{ project.pk }}">+ Rechnung</a>{% endif %}</div>
          {% if invoice_rows %}<div class="tt-project-table-wrap"><table class="tt-project-table"><thead><tr><th>Datum</th><th>Nr.</th><th>Status</th><th class="tt-money">Betrag</th><th></th></tr></thead><tbody>{% for row in invoice_rows %}<tr><td>{{ row.invoice.issue_date|date:'d.m.Y' }}</td><td><strong>{{ row.invoice.number }}</strong></td><td><span class="tt-status {% if row.invoice.status == 'paid' %}is-paid{% elif row.invoice.status == 'overdue' %}is-overdue{% endif %}">{{ row.invoice.get_status_display }}</span></td><td class="tt-money">€{{ row.total.gross|floatformat:2 }}</td><td class="tt-more"><a href="{% url 'next-invoice-edit' row.invoice.pk %}" aria-label="Rechnung öffnen">•••</a></td></tr>{% endfor %}</tbody></table></div>{% else %}<div class="tt-empty">Noch keine Rechnungen erstellt.</div>{% endif %}
        </section>

        <section class="tt-project-section">
          <div class="tt-section-head"><h2>Belege</h2></div>
          {% for receipt in receipts %}<div class="tt-list-row"><div><strong>{{ receipt.title }}</strong><span>{{ receipt.created_at|date:'d.m.Y H:i' }}</span></div>{% if receipt.file %}<a href="{{ receipt.file.url }}" target="_blank" rel="noopener">Öffnen</a>{% endif %}</div>{% empty %}<div class="tt-empty">Noch keine Belege angelegt.</div>{% endfor %}
        </section>

        <section class="tt-project-section">
          <div class="tt-section-head"><h2>Zeiteinträge</h2><a href="{% url 'next-time' %}">Zeiterfassung</a></div>
          {% for entry in time_entries %}<div class="tt-list-row"><div><strong>{% if entry.employee %}{{ entry.employee.first_name }} {{ entry.employee.last_name }}{% else %}Mitarbeiter{% endif %}</strong><span>{{ entry.started_at|date:'d.m.Y H:i' }}{% if entry.ended_at %} – {{ entry.ended_at|date:'H:i' }}{% else %} · läuft{% endif %}</span></div><span>{{ entry.description|default:''|truncatechars:60 }}</span></div>{% empty %}<div class="tt-empty">Noch keine Zeiteinträge angelegt.</div>{% endfor %}
        </section>
      </div>

      <div class="nx-tab-panel" data-tab-panel="tasks">
        <section class="tt-project-section tt-tab-section"><div class="tt-section-head"><h2>Aufgaben</h2></div>{% for task in tasks %}<div class="tt-list-row"><div><strong>{{ task.title }}</strong><span>{% if task.due_at %}Fällig {{ task.due_at|date:'d.m.Y H:i' }}{% else %}Ohne Fälligkeit{% endif %}</span></div><span class="tt-status {% if task.status == 'done' %}is-paid{% endif %}">{{ task.get_status_display }}</span></div>{% empty %}<div class="tt-empty">Keine offenen Aufgaben.</div>{% endfor %}</section>
      </div>

      <div class="nx-tab-panel" data-tab-panel="documents">
        <section class="tt-project-section tt-tab-section"><div class="tt-section-head"><h2>Dokumente & Fotos</h2></div>{% for document in documents %}<div class="tt-list-row"><div><strong>{{ document.title }}</strong><span>{{ document.get_category_display }} · {{ document.created_at|date:'d.m.Y H:i' }}</span></div>{% if document.file %}<a href="{{ document.file.url }}" target="_blank" rel="noopener">Öffnen</a>{% endif %}</div>{% empty %}<div class="tt-empty">Noch keine Dokumente vorhanden.</div>{% endfor %}</section>
      </div>
    </section>
  </main>
</div>
{% endblock %}
'''


def install_project_template() -> None:
    write("templates/rebuild/project_detail.html", PROJECT_TEMPLATE)


FINAL_CSS = r'''/* KAYI TOOLTIME FINAL SURFACE 2026-08-21 */
:root{--tt-blue:#087ff5;--tt-blue-dark:#066fd6;--tt-sidebar:#12344e;--tt-bg:#f5f7fa;--tt-panel:#fff;--tt-line:#e3e8ef;--tt-text:#2f3742;--tt-muted:#7f8b99;--tt-danger:#f24b4b}
html,body{background:var(--tt-bg)}
.nx-body{background:var(--tt-bg);color:var(--tt-text)}
.nx-sidebar{background:var(--tt-sidebar)!important;border-right:0!important;box-shadow:none!important}
.nx-brand,.nx-sidebar-foot,.nx-nav-label{color:#fff!important}
.nx-nav a{color:rgba(255,255,255,.82)!important;border-radius:6px!important;background:transparent!important}
.nx-nav a:hover{background:rgba(255,255,255,.08)!important;color:#fff!important}
.nx-nav a.is-active{background:rgba(255,255,255,.14)!important;color:#fff!important;box-shadow:inset 3px 0 0 var(--tt-blue)!important}
.nx-ico{width:18px!important;height:18px!important;display:inline-grid!important;place-items:center!important;flex:0 0 18px!important}
.nx-ico svg{width:17px;height:17px;fill:none;stroke:currentColor;stroke-width:1.8;stroke-linecap:round;stroke-linejoin:round}
.nx-main{background:var(--tt-bg)!important}
.nx-topbar{background:#fff!important;border-bottom:1px solid var(--tt-line)!important;box-shadow:none!important}
.nx-content{max-width:none!important;padding:26px 30px 42px!important}
.nx-card,.tt-create-card{background:#fff!important;border:1px solid var(--tt-line)!important;box-shadow:none!important;border-radius:8px!important}
.nx-btn{border-color:#dfe5ec!important;background:#fff!important;color:#33404d!important;box-shadow:none!important}
.nx-btn:hover{border-color:#bdc8d4!important;background:#f8fafc!important}
.nx-btn-primary{background:var(--tt-blue)!important;border-color:var(--tt-blue)!important;color:#fff!important}
.nx-btn-primary:hover{background:var(--tt-blue-dark)!important;border-color:var(--tt-blue-dark)!important}
.nx-tabs{border-bottom:1px solid var(--tt-line)!important;background:transparent!important}
.nx-tabs button.is-active{color:var(--tt-text)!important;border-color:var(--tt-blue)!important}
.nx-table th,.tt-project-table th{color:#8793a1!important;font-weight:600!important}
a{color:var(--tt-blue)}

.tt-project-page{display:grid;grid-template-columns:minmax(290px,360px) minmax(0,1fr);gap:28px;align-items:start;margin:-4px 0 0}
.tt-project-rail{min-width:0;padding:0 6px 30px 0}
.tt-project-identity{padding:0 0 22px}
.tt-project-title-row{display:flex;align-items:flex-start;justify-content:space-between;gap:12px}
.tt-project-title-row h1{font-size:24px;line-height:1.2;margin:0;color:var(--tt-text);font-weight:750;letter-spacing:-.02em}
.tt-icon-button{width:32px;height:32px;display:grid;place-items:center;color:#718299;border-radius:6px}
.tt-icon-button svg,.tt-project-page svg{fill:none;stroke:currentColor;stroke-width:1.8;stroke-linecap:round;stroke-linejoin:round}
.tt-icon-button svg{width:18px;height:18px}
.tt-project-meta-grid{display:grid;grid-template-columns:1fr 1fr;gap:20px;margin-top:28px}
.tt-project-meta-grid span,.tt-project-description>span,.tt-small-label,.tt-created-meta span{display:block;color:#8b97a5;font-size:11px;line-height:1.4}
.tt-project-meta-grid strong{display:block;color:#3b4552;font-size:13px;margin-top:7px}
.tt-project-description{margin-top:28px}
.tt-project-description p{margin:7px 0 0;font-size:13px;line-height:1.55;color:#3c4652}
.tt-rail-card{background:#fff;border:1px solid var(--tt-line);border-radius:7px;padding:20px;margin:16px 0}
.tt-customer-link{display:flex;align-items:center;gap:9px;color:var(--tt-blue);text-decoration:none;font-size:13px}
.tt-customer-link svg,.tt-contact-line svg{width:17px;height:17px;flex:0 0 17px}
.tt-rail-divider{height:1px;background:var(--tt-line);margin:16px 0}
.tt-contact-line{display:flex;align-items:flex-start;gap:10px;margin-top:11px;color:#718092;font-size:12px;line-height:1.5}
.tt-contact-line a{color:var(--tt-blue);text-decoration:none;overflow-wrap:anywhere}
.tt-map-frame{margin:18px -20px -20px;height:150px;border-radius:0 0 7px 7px;overflow:hidden;border-top:1px solid var(--tt-line);background:#eef2f5}
.tt-map-frame iframe{border:0;width:100%;height:100%}
.tt-project-tools{padding:18px 0 8px}
.tt-tool-links{display:flex;flex-wrap:wrap;gap:8px;margin-top:10px}
.tt-tool-links a{display:inline-flex;align-items:center;gap:6px;padding:7px 9px;border:1px solid var(--tt-line);border-radius:6px;background:#fff;text-decoration:none;font-size:11px;font-weight:650;color:#536171}
.tt-tool-links a:hover{color:var(--tt-blue);border-color:#b9d9fb}
.tt-tool-links svg{width:14px;height:14px}
.tt-created-meta{margin-top:24px;display:grid;gap:8px;color:#596778;font-size:11px}
.tt-created-meta span{display:inline;margin-right:8px}

.tt-project-main{min-width:0}
.tt-project-kpis{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px;margin-bottom:16px}
.tt-kpi{background:#f8f9fb;border-radius:8px;min-height:78px;padding:15px 18px;display:flex;flex-direction:column;align-items:flex-start;justify-content:center}
.tt-kpi>span{font-size:11px;color:#7e8a98}
.tt-kpi>strong{font-size:18px;color:#38424f;margin-top:5px;font-weight:750}
.tt-kpi>a{display:flex;align-items:center;gap:6px;font-size:11px;font-weight:700;text-decoration:none;margin-top:5px}
.tt-kpi>a svg{width:13px;height:13px}
.tt-kpi-open>strong{color:var(--tt-danger)}
.tt-project-panel{background:#f8f9fb;border-radius:9px;min-height:720px;padding:0 22px 28px}
.tt-project-tabs{height:60px;display:flex;align-items:flex-end;gap:28px;border-bottom:1px solid #dfe4ea}
.tt-project-tabs button{height:60px;border:0;border-bottom:3px solid transparent;background:transparent;color:#8995a3;font:inherit;font-size:12px;font-weight:700;padding:0 12px;cursor:pointer}
.tt-project-tabs button.is-active{color:#36414e;border-bottom-color:var(--tt-blue)}
.tt-count{display:inline-grid;place-items:center;min-width:18px;height:18px;margin-left:5px;border-radius:9px;background:#e8edf3;color:#6a7785;font-size:10px;padding:0 5px}
.tt-project-panel .nx-tab-panel{display:none}
.tt-project-panel .nx-tab-panel.is-active{display:block}
.tt-overview{padding-top:4px}
.tt-project-section{padding:24px 0;border-bottom:0}
.tt-tab-section{padding-top:26px}
.tt-section-head{display:flex;align-items:center;justify-content:space-between;gap:12px;margin-bottom:14px}
.tt-section-head h2{font-size:14px;margin:0;color:#3f4955;font-weight:750}
.tt-section-head h2 span{color:#9aa4af;font-weight:600}
.tt-section-head>a{font-size:11px;text-decoration:none;font-weight:700}
.tt-empty{min-height:58px;display:flex;align-items:center;justify-content:center;color:#95a0ad;font-size:12px;text-align:center;padding:14px}
.tt-list-row{display:flex;align-items:center;justify-content:space-between;gap:20px;background:#fff;border:1px solid #edf0f4;border-radius:6px;padding:12px 14px;text-decoration:none;color:#45515e;margin-top:8px;font-size:12px}
.tt-list-row>div{display:grid;gap:4px}
.tt-list-row strong{font-size:12px;color:#36414d}
.tt-list-row span{color:#8995a2;font-size:11px}
.tt-status{display:inline-flex!important;align-items:center!important;justify-content:center!important;border-radius:999px!important;background:#ebd465!important;color:#675d21!important;font-size:10px!important;font-weight:750!important;padding:5px 9px!important;white-space:nowrap}
.tt-status.is-paid{background:#d8f1e1!important;color:#287348!important}
.tt-status.is-overdue{background:#fde1e1!important;color:#b83f3f!important}
.tt-project-table-wrap{overflow:auto;background:#fff;border-radius:7px}
.tt-project-table{width:100%;border-collapse:collapse;min-width:650px;font-size:11px}
.tt-project-table th{height:38px;text-align:left;border-bottom:1px solid var(--tt-line);padding:0 14px;white-space:nowrap}
.tt-project-table td{height:52px;padding:0 14px;border-bottom:1px solid #eef1f4;color:#596675;white-space:nowrap}
.tt-project-table tbody tr:last-child td{border-bottom:0}
.tt-project-table td strong{color:#394550}
.tt-project-table .tt-money{text-align:right;font-weight:700;color:#313d49}
.tt-project-table .tt-more{width:36px;text-align:center;padding-right:10px}
.tt-project-table .tt-more a{text-decoration:none;color:#526475;letter-spacing:1px}

@media (max-width:1180px){.tt-project-page{grid-template-columns:300px minmax(0,1fr);gap:18px}.tt-project-kpis{grid-template-columns:1fr}.tt-kpi{min-height:64px}}
@media (max-width:880px){.nx-content{padding:18px 16px 92px!important}.tt-project-page{display:block}.tt-project-rail{padding-right:0}.tt-project-main{margin-top:20px}.tt-project-kpis{grid-template-columns:1fr}.tt-project-panel{padding:0 14px 22px;min-height:0}.tt-project-tabs{gap:4px;overflow-x:auto}.tt-project-tabs button{padding:0 10px;white-space:nowrap}.tt-map-frame{height:190px}.tt-project-meta-grid{gap:12px}.tt-project-title-row h1{font-size:22px}}
/* END KAYI TOOLTIME FINAL SURFACE */'''


def patch_css() -> None:
    rel = "static/css/kayi-next.css"
    css = read(rel)
    pattern = re.compile(r'/\* KAYI TOOLTIME FINAL SURFACE 2026-08-21 \*/.*?/\* END KAYI TOOLTIME FINAL SURFACE \*/', re.S)
    if pattern.search(css):
        css = pattern.sub(FINAL_CSS, css, count=1)
    else:
        css = css.rstrip() + "\n\n" + FINAL_CSS + "\n"
    write(rel, css)


def svg_icon(paths: str) -> str:
    return f'<span class="nx-ico"><svg viewBox="0 0 24 24" aria-hidden="true">{paths}</svg></span>'


def patch_base_icons_and_cache() -> None:
    rel = "templates/rebuild/base.html"
    html = read(rel)
    icons = {
        "⌂": '<path d="M3 11.5 12 4l9 7.5"/><path d="M5.5 10.5V20h13v-9.5"/>',
        "◫": '<rect x="3" y="5" width="18" height="16" rx="2"/><path d="M8 3v4M16 3v4M3 10h18"/>',
        "▣": '<path d="M3 7h7l2 2h9v11H3Z"/><path d="M3 7V5h7l2 2"/>',
        "◎": '<circle cx="12" cy="8" r="4"/><path d="M4 21c1.5-5 4.2-7 8-7s6.5 2 8 7"/>',
        "✓": '<path d="m5 12 4 4L19 6"/><rect x="3" y="3" width="18" height="18" rx="3"/>',
        "◇": '<path d="M6 2h9l4 4v16H6Z"/><path d="M14 2v5h5M9 12h7M9 16h7"/>',
        "€": '<path d="M18 7a7 7 0 1 0 0 10"/><path d="M5 10h9M5 14h8"/>',
        "↘": '<path d="M5 5l14 14M19 11v8h-8"/>',
        "◷": '<circle cx="12" cy="12" r="9"/><path d="M12 7v6l4 2"/>',
        "◉": '<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.9M16 3.1a4 4 0 0 1 0 7.8"/>',
        "⌁": '<path d="M14.7 6.3a4 4 0 0 0-5 5L3 18v3h3l6.7-6.7a4 4 0 0 0 5-5l-2.4 2.4-3-3Z"/>',
        "⇄": '<path d="M7 7h12l-3-3M19 7l-3 3M17 17H5l3 3M5 17l3-3"/>',
        "⚙": '<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.9l.1.1-2.8 2.8-.1-.1a1.7 1.7 0 0 0-1.9-.3 1.7 1.7 0 0 0-1 1.6v.2h-4V21a1.7 1.7 0 0 0-1-1.6 1.7 1.7 0 0 0-1.9.3l-.1.1L4.2 17l.1-.1a1.7 1.7 0 0 0 .3-1.9A1.7 1.7 0 0 0 3 14H2.8v-4H3a1.7 1.7 0 0 0 1.6-1 1.7 1.7 0 0 0-.3-1.9L4.2 7 7 4.2l.1.1a1.7 1.7 0 0 0 1.9.3A1.7 1.7 0 0 0 10 3V2.8h4V3a1.7 1.7 0 0 0 1 1.6 1.7 1.7 0 0 0 1.9-.3l.1-.1L19.8 7l-.1.1a1.7 1.7 0 0 0-.3 1.9 1.7 1.7 0 0 0 1.6 1h.2v4H21a1.7 1.7 0 0 0-1.6 1Z"/>',
    }
    for glyph, paths in icons.items():
        html = html.replace(f'<span class="nx-ico">{glyph}</span>', svg_icon(paths))
    html = re.sub(r"kayi-next\.css' %\}\?v=[^\"]+", "kayi-next.css' %}?v=20260821-tooltime-final", html)
    write(rel, html)


def install_contract_test() -> None:
    test = r'''from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[1]


def test_project_detail_matches_tooltime_information_architecture():
    html = (ROOT / "templates" / "rebuild" / "project_detail.html").read_text(encoding="utf-8")
    for needle in (
        "data-tooltime-project-detail", "tt-project-kpis", "Umsatz (netto)", "Ausgaben (netto)",
        "Offener Betrag (brutto)", ">Übersicht<", ">Aufgaben", ">Dokumente", ">Termine<",
        ">Angebote ", ">Rechnungen<", ">Belege<", ">Zeiteinträge<", "tt-map-frame", "<svg",
    ):
        assert needle in html
    assert "nx-quick-icon" not in html


def test_project_detail_context_has_commercial_and_time_data():
    source = (ROOT / "erp" / "rebuild_views.py").read_text(encoding="utf-8")
    block = source[source.index("def project_detail(request, pk):"):source.index("def appointment_list(request):")]
    for needle in ("quote_rows", "invoice_rows", "turnover_net", "project_expenditure", "open_amount", "time_entries", "receipts"):
        assert needle in block


def test_global_final_surface_is_tooltime_neutral_blue_and_svg_based():
    css = (ROOT / "static" / "css" / "kayi-next.css").read_text(encoding="utf-8")
    base = (ROOT / "templates" / "rebuild" / "base.html").read_text(encoding="utf-8")
    assert "KAYI TOOLTIME FINAL SURFACE 2026-08-21" in css
    assert "--tt-blue:#087ff5" in css
    assert "--tt-sidebar:#12344e" in css
    assert 'class="nx-ico"><svg' in base
    assert "20260821-tooltime-final" in base


def test_kayi_document_defaults_are_present_without_forcing_future_edits():
    payload = json.loads((ROOT / "reference_data" / "tooltime_user_settings.json").read_text(encoding="utf-8"))
    cfg = payload["commercial_profile"]
    assert cfg["quote_defaults"]["intro_text"].startswith("Herzlichen Dank für Ihre Anfrage")
    assert "Widerrufsbelehrung" in cfg["quote_defaults"]["closing_text"]
    assert cfg["invoice_defaults"]["payment_text"] == "Zahlbar sofort ohne Abzug ab Rechnungsdatum."
    importer = (ROOT / "scripts" / "tooltime_user_settings_import.py").read_text(encoding="utf-8")
    assert "merge_missing" in importer
    assert "Any non-empty tenant text" in importer
'''
    write("tests/test_tooltime_final_surface_contract.py", test)


def run() -> None:
    patch_project_view()
    install_project_template()
    patch_css()
    patch_base_icons_and_cache()
    install_contract_test()
    print(f"{MARKER}: project detail, global shell and document defaults are final-layer ToolTime parity.")


if __name__ == "__main__":
    run()
