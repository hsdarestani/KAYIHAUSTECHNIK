from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MARKER = "KAYI TOOLTIME PROJECT DETAIL SAFE PARITY 2026-08-21"


def read(rel: str) -> str:
    path = ROOT / rel
    if not path.exists():
        raise RuntimeError(f"Project-detail parity target missing: {rel}")
    return path.read_text(encoding="utf-8")


def write(rel: str, text: str) -> None:
    path = ROOT / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def patch_view() -> None:
    rel = "erp/rebuild_views.py"
    text = read(rel)
    start = text.find("@login_required\ndef project_detail(request, pk):")
    if start < 0:
        raise RuntimeError("project_detail view not found")
    end = text.find("\n\n@login_required\ndef appointment_list(request):", start)
    if end < 0:
        raise RuntimeError("project_detail end anchor not found")
    block = text[start:end]

    if "KAYI_TOOLTIME_PROJECT_DETAIL_SAFE_CONTEXT" not in block:
        invoice_line = re.search(r'^    invoice_gross\s*=.*$', block, re.M)
        if not invoice_line:
            raise RuntimeError("invoice_gross anchor not found in project_detail")
        injection = r'''
    # KAYI_TOOLTIME_PROJECT_DETAIL_SAFE_CONTEXT
    quote_rows = [{"quote": quote, "total": _quote_total(quote)} for quote in quotes]
    invoice_rows = [{"invoice": invoice, "total": _invoice_total(invoice)} for invoice in invoices]
    turnover_net = sum((row["total"]["net"] for row in invoice_rows), Decimal("0"))
    open_amount = sum((row["total"]["open"] for row in invoice_rows), Decimal("0"))
    project_expenditure = Decimal("0")
    expense_model = getattr(m, "Expense", None)
    if expense_model is not None:
        try:
            fields = {field.name for field in expense_model._meta.get_fields()}
            if "project" in fields:
                expense_qs = expense_model.objects.filter(project=project)
                if "organization" in fields:
                    expense_qs = expense_qs.filter(organization=org)
                for expense in expense_qs[:500]:
                    raw = None
                    for attr in ("net_amount", "amount_net", "net", "amount"):
                        if hasattr(expense, attr):
                            raw = getattr(expense, attr)
                            if raw is not None:
                                break
                    project_expenditure += Decimal(str(raw or 0))
        except Exception:
            project_expenditure = Decimal("0")
    receipts = [
        document for document in documents
        if str(getattr(document, "category", "")).lower() in {"receipt", "expense", "beleg"}
        or str((getattr(document, "metadata", {}) or {}).get("kind", "")).lower() in {"receipt", "expense", "beleg"}
    ]
    field_user = _is_field_user(request)
'''
        pos = invoice_line.end()
        block = block[:pos] + injection + block[pos:]

    additions = [
        ("quote_rows", '"quote_rows": quote_rows,'),
        ("invoice_rows", '"invoice_rows": invoice_rows,'),
        ("turnover_net", '"turnover_net": turnover_net,'),
        ("project_expenditure", '"project_expenditure": project_expenditure,'),
        ("open_amount", '"open_amount": open_amount,'),
        ("receipts", '"receipts": receipts,'),
        ("field_user", '"field_user": field_user,'),
    ]
    missing = [entry for name, entry in additions if f'"{name}"' not in block]
    if missing:
        match = re.search(r'("invoice_gross"\s*:\s*invoice_gross\s*,?)', block)
        if not match:
            raise RuntimeError("invoice_gross context key not found")
        insert = match.group(1) + "\n        " + "\n        ".join(missing)
        block = block[: match.start()] + insert + block[match.end() :]

    text = text[:start] + block + text[end:]
    write(rel, text)


PROJECT_TEMPLATE = r'''{% extends 'rebuild/base.html' %}
{% block title %}{{ project.title }} · A+Bau{% endblock %}
{% block content %}
<div class="tt-pd-page" data-tooltime-project-detail>
  <div class="tt-pd-header">
    <div class="tt-pd-heading">
      <a class="tt-pd-back" href="{% url 'next-projects' %}" aria-label="Zurück zu Projekte">←</a>
      <div>
        <div class="tt-pd-title-line"><h1>{{ project.title }}</h1><span class="tt-pd-status">{{ project.get_status_display }}</span></div>
        <div class="tt-pd-subline">Projekt {{ project.number }}</div>
      </div>
    </div>
    <div class="tt-pd-actions">
      <a class="nx-btn" href="{% url 'next-appointment-create' %}?project={{ project.pk }}">＋ Termin</a>
      {% if not field_user %}<a class="nx-btn" href="{% url 'next-quote-create' %}?project={{ project.pk }}">＋ Angebot</a><a class="nx-btn nx-btn-primary" href="{% url 'next-invoice-create' %}?project={{ project.pk }}">＋ Rechnung</a>{% endif %}
    </div>
  </div>

  <div class="tt-pd-layout">
    <aside class="tt-pd-rail">
      <section class="tt-pd-identity">
        <div class="tt-pd-identity-top"><h2>{{ project.title }}</h2><span class="tt-pd-edit">✎</span></div>
        <div class="tt-pd-meta-grid">
          <div><span>Projektnummer</span><strong>{{ project.number }}</strong></div>
          <div><span>Erstellt am</span><strong>{{ project.created_at|date:'d.m.Y' }}</strong></div>
        </div>
        <div class="tt-pd-description"><span>Projektbeschreibung</span><p>{{ project.description|default:'–'|linebreaksbr }}</p></div>
      </section>

      <section class="tt-pd-card">
        <a class="tt-pd-customer" href="{% url 'next-customer-detail' project.customer.pk %}"><span class="tt-pd-home">⌂</span><strong>{{ project.customer.display_name }}</strong></a>
        <div class="tt-pd-divider"></div>
        <span class="tt-pd-label">Kundendaten</span>
        <div class="tt-pd-contact">⌖ <span>{{ project.customer.street|default:'Keine Straße' }}, {{ project.customer.postal_code }} {{ project.customer.city }}</span></div>
        {% if project.customer.mobile or project.customer.phone %}<div class="tt-pd-contact">☎ <a href="tel:{{ project.customer.mobile|default:project.customer.phone }}">{{ project.customer.mobile|default:project.customer.phone }}</a></div>{% endif %}
        {% if project.customer.email %}<div class="tt-pd-contact">✉ <a href="mailto:{{ project.customer.email }}">{{ project.customer.email }}</a></div>{% endif %}
      </section>

      <section class="tt-pd-card tt-pd-site">
        <span class="tt-pd-label">Einsatzort</span>
        {% if project.object_location %}
          {% if project.object_location.name %}<div class="tt-pd-contact">☺ <span>{{ project.object_location.name }}</span></div>{% endif %}
          <div class="tt-pd-contact">⌖ <a target="_blank" rel="noopener" href="https://www.google.com/maps/search/?api=1&query={{ project.object_location.street|urlencode }}%20{{ project.object_location.postal_code|urlencode }}%20{{ project.object_location.city|urlencode }}">{{ project.object_location.street }}, {{ project.object_location.postal_code }} {{ project.object_location.city }}</a></div>
          <div class="tt-pd-map"><iframe title="Karte Einsatzort" loading="lazy" referrerpolicy="no-referrer-when-downgrade" src="https://www.google.com/maps?q={{ project.object_location.street|urlencode }}%20{{ project.object_location.postal_code|urlencode }}%20{{ project.object_location.city|urlencode }}&output=embed"></iframe></div>
        {% else %}
          <div class="tt-pd-contact">⌖ <a target="_blank" rel="noopener" href="https://www.google.com/maps/search/?api=1&query={{ project.customer.street|urlencode }}%20{{ project.customer.postal_code|urlencode }}%20{{ project.customer.city|urlencode }}">{{ project.customer.street }}, {{ project.customer.postal_code }} {{ project.customer.city }}</a></div>
          <div class="tt-pd-map"><iframe title="Karte Einsatzort" loading="lazy" referrerpolicy="no-referrer-when-downgrade" src="https://www.google.com/maps?q={{ project.customer.street|urlencode }}%20{{ project.customer.postal_code|urlencode }}%20{{ project.customer.city|urlencode }}&output=embed"></iframe></div>
        {% endif %}
      </section>

      <section class="tt-pd-tools">
        <span class="tt-pd-label">Projektwerkzeuge</span>
        <div class="tt-pd-tool-grid">
          <a href="{% url 'next-appointment-create' %}?project={{ project.pk }}">◫ Termin</a>
          <a href="{% url 'configurator' %}?project={{ project.pk }}">▱ Aufmaß & 3D</a>
          {% if field_user %}<a href="{% url 'next-field' %}">✎ Dokumentieren</a>{% else %}<a href="{% url 'next-quote-create' %}?project={{ project.pk }}">◇ Angebot</a><a href="{% url 'next-invoice-create' %}?project={{ project.pk }}">€ Rechnung</a>{% endif %}
        </div>
      </section>
    </aside>

    <main class="tt-pd-main">
      <div class="tt-pd-kpis">
        <section><span>Umsatz (netto)</span><strong>€{{ turnover_net|floatformat:2 }}</strong></section>
        <section><span>Ausgaben (netto)</span><strong>€{{ project_expenditure|floatformat:2 }}</strong></section>
        <section class="tt-pd-kpi-open"><span>Offener Betrag (brutto)</span><strong>€{{ open_amount|floatformat:2 }}</strong></section>
      </div>

      {% if project.job_type == 'insurance' %}
      <section class="tt-pd-insurance">
        <div><span>B&O / Versicherung</span><strong>Leistungsnachweis / Regiebericht</strong></div>
        <div class="tt-pd-actions">{% if bando_report %}<a class="nx-btn" target="_blank" href="{% url 'site-report-pdf' bando_report.pk %}">PDF öffnen</a><a class="nx-btn nx-btn-primary" href="{% url 'site-report-edit' bando_report.pk %}">Bearbeiten</a>{% else %}<a class="nx-btn nx-btn-primary" href="{% url 'site-report-create' project.pk %}">Leistungsnachweis erstellen</a>{% endif %}</div>
      </section>
      {% endif %}

      <div class="tt-pd-workspace" data-tabs>
        <div class="tt-pd-tabs"><button type="button" class="is-active" data-tab="overview">Übersicht</button><button type="button" data-tab="tasks">Aufgaben</button><button type="button" data-tab="documents">Dokumente</button></div>

        <div class="tt-pd-panel is-active" data-tab-panel="overview">
          <section class="tt-pd-section">
            <h3>Termine</h3>
            {% for event in appointments %}<a class="tt-pd-row" href="{% url 'next-appointment-detail' event.pk %}"><div><strong>{{ event.title }}</strong><small>{{ event.starts_at|date:'d.m.Y H:i' }} · {{ event.location|default:'Kein Ort angegeben' }}</small></div><span>{{ event.get_type_display }}</span></a>{% empty %}<div class="tt-pd-empty">Noch keine Termine angelegt.</div>{% endfor %}
          </section>

          {% if not field_user %}<section class="tt-pd-section">
            <h3>Angebote</h3>
            {% for row in quote_rows %}<a class="tt-pd-row" href="{% url 'next-quote-edit' row.quote.pk %}"><div><strong>{{ row.quote.number }}</strong><small>{{ row.quote.issue_date|date:'d.m.Y' }}</small></div><div class="tt-pd-row-end"><span>{{ row.quote.get_status_display }}</span><strong>€{{ row.total.gross|floatformat:2 }}</strong></div></a>{% empty %}<div class="tt-pd-empty">Noch keine Angebote angelegt.</div>{% endfor %}
          </section>

          <section class="tt-pd-section">
            <h3>Rechnungen</h3>
            {% for row in invoice_rows %}<a class="tt-pd-row" href="{% url 'next-invoice-edit' row.invoice.pk %}"><div><strong>{{ row.invoice.number }}</strong><small>{{ row.invoice.issue_date|date:'d.m.Y' }} · fällig {{ row.invoice.due_date|date:'d.m.Y' }}</small></div><div class="tt-pd-row-end"><span>{{ row.invoice.get_status_display }}</span><strong>€{{ row.total.gross|floatformat:2 }}</strong></div></a>{% empty %}<div class="tt-pd-empty">Noch keine Rechnungen angelegt.</div>{% endfor %}
          </section>{% endif %}

          <section class="tt-pd-section">
            <h3>Belege</h3>
            {% for document in receipts %}<div class="tt-pd-row"><div><strong>{{ document.title }}</strong><small>{{ document.created_at|date:'d.m.Y H:i' }}</small></div>{% if document.file %}<a class="nx-btn nx-btn-ghost" href="{{ document.file.url }}" target="_blank">Öffnen</a>{% endif %}</div>{% empty %}<div class="tt-pd-empty">Noch keine Belege angelegt.</div>{% endfor %}
          </section>
        </div>

        <div class="tt-pd-panel" data-tab-panel="tasks">
          <section class="tt-pd-section"><h3>Aufgaben</h3>{% for task in tasks %}<div class="tt-pd-row"><div><strong>{{ task.title }}</strong><small>{{ task.description|truncatechars:120 }}</small></div><span>{{ task.get_status_display }}</span></div>{% empty %}<div class="tt-pd-empty">Keine offenen Aufgaben.</div>{% endfor %}</section>
        </div>

        <div class="tt-pd-panel" data-tab-panel="documents">
          <section class="tt-pd-section"><h3>Dokumente</h3>{% for document in documents %}<div class="tt-pd-row"><div><strong>{{ document.title }}</strong><small>{{ document.get_category_display }} · {{ document.created_at|date:'d.m.Y H:i' }}</small></div>{% if document.file %}<a class="nx-btn nx-btn-ghost" href="{{ document.file.url }}" target="_blank">Öffnen</a>{% endif %}</div>{% empty %}<div class="tt-pd-empty">Noch keine Dokumente angelegt.</div>{% endfor %}</section>
        </div>
      </div>
    </main>
  </div>
</div>
{% endblock %}
'''


def install_template() -> None:
    write("templates/rebuild/project_detail.html", PROJECT_TEMPLATE)


CSS = r'''/* KAYI TOOLTIME PROJECT DETAIL SAFE PARITY 2026-08-21 */
.tt-pd-page{max-width:1540px;margin:0 auto;color:#283443}.tt-pd-header{display:flex;align-items:center;justify-content:space-between;gap:24px;margin:0 0 22px}.tt-pd-heading{display:flex;align-items:center;gap:16px}.tt-pd-back{font-size:27px;line-height:1;text-decoration:none;color:#27445c}.tt-pd-title-line{display:flex;align-items:center;gap:12px}.tt-pd-title-line h1{font-size:21px;margin:0;font-weight:800}.tt-pd-status{font-size:11px;font-weight:750;background:#7fc49a;color:#fff;padding:5px 10px;border-radius:999px}.tt-pd-subline{font-size:11px;color:#8b98a7;margin-top:5px}.tt-pd-actions{display:flex;gap:8px;align-items:center;flex-wrap:wrap}.tt-pd-layout{display:grid;grid-template-columns:minmax(300px,360px) minmax(0,1fr);gap:34px;align-items:start}.tt-pd-rail{display:flex;flex-direction:column;gap:18px}.tt-pd-identity{padding:0 0 8px}.tt-pd-identity-top{display:flex;align-items:center;justify-content:space-between}.tt-pd-identity h2{font-size:22px;margin:0 0 18px}.tt-pd-edit{color:#7590aa;font-size:18px}.tt-pd-meta-grid{display:grid;grid-template-columns:1fr 1fr;gap:28px;margin-bottom:28px}.tt-pd-meta-grid span,.tt-pd-description>span,.tt-pd-label{display:block;color:#8c9aaa;font-size:11px;margin-bottom:7px}.tt-pd-meta-grid strong{font-size:12px}.tt-pd-description p{font-size:12px;line-height:1.55;margin:0}.tt-pd-card{background:#fff;border:1px solid #dfe5ec;border-radius:8px;padding:20px;overflow:hidden}.tt-pd-customer{display:flex;gap:9px;align-items:center;color:#087ff5;text-decoration:none;font-size:12px}.tt-pd-home{font-size:18px}.tt-pd-divider{height:1px;background:#e7ebf0;margin:16px 0}.tt-pd-contact{display:flex;gap:10px;align-items:flex-start;font-size:12px;color:#4f6173;margin:9px 0;line-height:1.4}.tt-pd-contact a{color:#087ff5;text-decoration:none}.tt-pd-site{padding-bottom:0}.tt-pd-map{height:150px;margin:16px -20px 0}.tt-pd-map iframe{width:100%;height:100%;border:0}.tt-pd-tools{padding:2px 0 0}.tt-pd-tool-grid{display:grid;grid-template-columns:1fr 1fr;gap:8px}.tt-pd-tool-grid a{font-size:11px;text-decoration:none;color:#087ff5;background:#fff;border:1px solid #dfe5ec;border-radius:7px;padding:10px 11px}.tt-pd-main{min-width:0}.tt-pd-kpis{display:grid;grid-template-columns:repeat(3,1fr);gap:14px;margin-bottom:14px}.tt-pd-kpis section{background:#fff;border:1px solid #eef1f5;border-radius:8px;padding:14px 16px;min-height:70px}.tt-pd-kpis span{display:block;font-size:10px;color:#6f8295;margin-bottom:8px}.tt-pd-kpis strong{font-size:16px}.tt-pd-kpi-open strong{color:#ef4444}.tt-pd-insurance{display:flex;justify-content:space-between;gap:18px;align-items:center;background:#fff;border:1px solid #dfe5ec;border-radius:8px;padding:14px 16px;margin-bottom:14px}.tt-pd-insurance span{font-size:10px;color:#8a97a5;display:block}.tt-pd-insurance strong{font-size:13px;display:block;margin-top:4px}.tt-pd-workspace{background:#fff;border:1px solid #eef1f5;border-radius:8px;overflow:hidden}.tt-pd-tabs{display:flex;gap:28px;border-bottom:1px solid #dfe5ec;padding:0 20px}.tt-pd-tabs button{appearance:none;border:0;background:none;padding:16px 0 13px;font-size:12px;color:#7b8998;font-weight:700;cursor:pointer;border-bottom:2px solid transparent}.tt-pd-tabs button.is-active{color:#34485c;border-bottom-color:#087ff5}.tt-pd-panel{display:none;padding:0 20px 18px}.tt-pd-panel.is-active{display:block}.tt-pd-section{padding:20px 0 6px;border-bottom:1px solid #edf0f4}.tt-pd-section:last-child{border-bottom:0}.tt-pd-section h3{font-size:13px;margin:0 0 15px}.tt-pd-empty{text-align:center;color:#8b98a7;font-size:11px;padding:24px 12px}.tt-pd-row{display:flex;align-items:center;justify-content:space-between;gap:16px;text-decoration:none;color:inherit;border-top:1px solid #edf0f4;padding:12px 10px;font-size:11px}.tt-pd-row:first-of-type{border-top:0}.tt-pd-row strong{font-size:11px}.tt-pd-row small{display:block;color:#8a98a6;margin-top:4px}.tt-pd-row>span,.tt-pd-row-end>span{color:#6f8295}.tt-pd-row-end{display:flex;align-items:center;gap:22px}.tt-pd-row-end strong{min-width:78px;text-align:right}.tt-pd-row:hover{background:#f8fafc}.tt-pd-page .nx-btn{font-size:11px;padding:9px 12px}
@media(max-width:1100px){.tt-pd-layout{grid-template-columns:300px minmax(0,1fr);gap:20px}.tt-pd-kpis{grid-template-columns:1fr}.tt-pd-kpis section{min-height:auto}}
@media(max-width:820px){.tt-pd-header{align-items:flex-start;flex-direction:column}.tt-pd-layout{grid-template-columns:1fr}.tt-pd-rail{order:1}.tt-pd-main{order:0}.tt-pd-kpis{grid-template-columns:repeat(3,1fr)}.tt-pd-map{height:190px}}
@media(max-width:620px){.tt-pd-kpis{grid-template-columns:1fr}.tt-pd-meta-grid{gap:14px}.tt-pd-tabs{gap:18px;overflow:auto}.tt-pd-row{align-items:flex-start;flex-direction:column}.tt-pd-row-end{width:100%;justify-content:space-between}.tt-pd-actions{width:100%}.tt-pd-actions .nx-btn{flex:1;text-align:center}.tt-pd-tool-grid{grid-template-columns:1fr 1fr}}
/* END KAYI TOOLTIME PROJECT DETAIL SAFE PARITY */'''


def patch_css() -> None:
    rel = "static/css/kayi-next.css"
    text = read(rel)
    pattern = re.compile(r'/\* KAYI TOOLTIME PROJECT DETAIL SAFE PARITY 2026-08-21 \*/.*?/\* END KAYI TOOLTIME PROJECT DETAIL SAFE PARITY \*/', re.S)
    if pattern.search(text):
        text = pattern.sub(CSS, text, count=1)
    else:
        text = text.rstrip() + "\n\n" + CSS + "\n"
    write(rel, text)


def guard() -> None:
    view = read("erp/rebuild_views.py")
    template = read("templates/rebuild/project_detail.html")
    css = read("static/css/kayi-next.css")
    for needle in ("turnover_net", "project_expenditure", "open_amount", "quote_rows", "invoice_rows", "field_user"):
        if needle not in view:
            raise RuntimeError(f"Project-detail context missing: {needle}")
    for needle in ("data-tooltime-project-detail", "Umsatz (netto)", "Ausgaben (netto)", "Offener Betrag (brutto)", "configurator", "site-report-create", "next-field", "Belege"):
        if needle not in template:
            raise RuntimeError(f"Project-detail ToolTime surface missing: {needle}")
    if MARKER not in css:
        raise RuntimeError("Project-detail safe parity CSS missing")


def run() -> None:
    patch_view()
    install_template()
    patch_css()
    guard()
    print(f"{MARKER}: ToolTime project detail restored while B&O, Room Planner, finance and field hooks stay intact.")


if __name__ == "__main__":
    run()
