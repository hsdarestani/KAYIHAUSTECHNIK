from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MARKER = "A+BAU TOOLTIME DOCUMENT WORKSPACE FINAL 2026-09-08"


def read(rel: str) -> str:
    path = ROOT / rel
    if not path.exists():
        raise RuntimeError(f"ToolTime document workspace target missing: {rel}")
    return path.read_text(encoding="utf-8")


def write(rel: str, text: str) -> None:
    path = ROOT / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def patch_views() -> None:
    rel = "erp/tooltime_parity_views.py"
    text = read(rel)

    if "from django.views.decorators.clickjacking import xframe_options_sameorigin" not in text:
        anchor = "from __future__ import annotations\n"
        if anchor not in text:
            raise RuntimeError("ToolTime document workspace future import anchor missing")
        text = text.replace(anchor, anchor + "\nfrom django.views.decorators.clickjacking import xframe_options_sameorigin\n", 1)

    if f"# {MARKER}" not in text:
        text += r'''

# A+BAU TOOLTIME DOCUMENT WORKSPACE FINAL 2026-09-08

def _tt_document_decimal(value):
    try:
        return Decimal(str(value or 0)).quantize(Decimal("0.01"))
    except Exception:
        return Decimal("0.00")


def _tt_customer_label(customer):
    if customer is None:
        return "—"
    display = getattr(customer, "display_name", "")
    if callable(display):
        try:
            display = display()
        except TypeError:
            pass
    display = str(display or "").strip()
    if display:
        return display
    company = str(getattr(customer, "company", "") or "").strip()
    person = " ".join(filter(None, [
        str(getattr(customer, "first_name", "") or "").strip(),
        str(getattr(customer, "last_name", "") or "").strip(),
    ]))
    return company or person or "—"


def _tt_customer_address(customer):
    if customer is None:
        return ""
    street = str(getattr(customer, "street", "") or "").strip()
    city = " ".join(filter(None, [
        str(getattr(customer, "postal_code", "") or "").strip(),
        str(getattr(customer, "city", "") or "").strip(),
    ]))
    return " · ".join(filter(None, [street, city]))


@login_required
@require_GET
@xframe_options_sameorigin
def quote_preview(request, pk):
    """Dedicated same-origin inline preview. The normal PDF route remains a download."""
    org = _org(request)
    quote = get_object_or_404(m.Quote, organization=org, pk=pk)
    try:
        payload = _phase5_quote_pdf_bytes(quote, require_finalized=False)
    except ValueError as exc:
        raise Http404(str(exc)) from exc
    response = HttpResponse(payload, content_type="application/pdf")
    response["Content-Disposition"] = f'inline; filename="angebot-{quote.number or quote.pk}.pdf"'
    response["Cache-Control"] = "private, no-store"
    return response


@login_required
@require_GET
@xframe_options_sameorigin
def invoice_preview(request, pk):
    """Serve the immutable compliance PDF inline without touching the download endpoint."""
    org = _org(request)
    invoice = get_object_or_404(m.Invoice, organization=org, pk=pk)
    compliance = get_compliance(invoice)
    if not compliance or compliance.state == "draft" or not compliance.original_pdf_document_id:
        raise Http404("Für diese Rechnung ist noch kein finalisiertes Original-PDF vorhanden.")
    document = compliance.original_pdf_document
    if not document or not getattr(document, "file", None):
        raise Http404("Das Original-PDF ist nicht verfügbar.")
    try:
        with document.file.open("rb") as handle:
            payload = handle.read()
    except (OSError, ValueError) as exc:
        raise Http404("Das Original-PDF konnte nicht gelesen werden.") from exc
    filename = document.title or f"rechnung-{compliance.final_number or invoice.number or invoice.pk}.pdf"
    response = HttpResponse(payload, content_type="application/pdf")
    response["Content-Disposition"] = f'inline; filename="{filename.replace(chr(34), "")}"'
    response["Cache-Control"] = "private, no-store"
    return response


def _tt_invoice_detail_context(invoice, compliance):
    totals = base._invoice_total(invoice)
    net = _tt_document_decimal(totals.get("net", 0))
    gross = _tt_document_decimal(totals.get("gross", net))
    tax = _tt_document_decimal(totals.get("tax", gross - net))
    paid = _tt_document_decimal(totals.get("paid", 0))
    open_amount = _tt_document_decimal(totals.get("open", gross - paid))
    meta = meta_for(invoice, "invoice", create=False)
    customer = _phase4_customer(invoice, meta)
    project = getattr(invoice, "project", None)
    project_label = _phase4_project_label(invoice)
    if project_label == "Ohne Projekt":
        project = None
    status_label, status_key = _phase4_invoice_display(invoice, totals)

    deliveries = []
    if hasattr(m, "ToolTimeDocumentDelivery"):
        deliveries = list(
            m.ToolTimeDocumentDelivery.objects.filter(organization=invoice.organization, invoice=invoice)
            .select_related("document")
            .order_by("-created_at", "-id")[:8]
        )

    try:
        commercial = invoice.commercial_settings
    except Exception:
        commercial = None

    payments = []
    payment_manager = getattr(invoice, "payments", None)
    if payment_manager is not None:
        try:
            payments = list(payment_manager.all().order_by("-paid_at", "-pk")[:10])
        except Exception:
            payments = []

    return {
        "invoice": invoice,
        "document": invoice,
        "meta": meta,
        "compliance": compliance,
        "customer": customer,
        "customer_name": _tt_customer_label(customer),
        "customer_address": _tt_customer_address(customer),
        "project": project,
        "project_label": project_label,
        "status_label": status_label,
        "status_key": status_key,
        "net": net,
        "tax": tax,
        "gross": gross,
        "paid": paid,
        "open_amount": open_amount,
        "commercial": commercial,
        "payments": payments,
        "deliveries": deliveries,
        "recipient_email": str(getattr(customer, "email", "") or "") if customer else "",
        "today": timezone.localdate(),
    }


@login_required
@require_http_methods(["GET", "POST"])
def invoice_workspace(request, pk):
    """ToolTime lifecycle: only drafts are editable; finalized invoices are documents."""
    org = _org(request)
    invoice = get_object_or_404(
        m.Invoice.objects.select_related("project__customer"),
        organization=org,
        pk=pk,
    )
    compliance = get_compliance(invoice)
    compliance_state = getattr(compliance, "state", "draft") if compliance else "draft"
    if compliance_state == "draft":
        return invoice_editor(request, pk)
    if request.method != "GET":
        messages.info(request, "Finalisierte Rechnungen werden als unveränderliches Dokument angezeigt.")
        return redirect("next-invoice-edit", pk=invoice.pk)
    return render(request, "rebuild/invoice_detail.html", _tt_invoice_detail_context(invoice, compliance))
'''

    write(rel, text)
    compile(text, str(ROOT / rel), "exec")


def patch_urls() -> None:
    rel = "erp/rebuild_urls.py"
    text = read(rel)

    # Final invoice URL must dispatch based on compliance state, while preserving
    # the public route name used by every existing link in the application.
    pattern = re.compile(
        r'path\("invoices/<int:pk>/",\s*(?:tooltime_parity|views)\.invoice_editor,\s*name="next-invoice-edit"\)'
    )
    replacement = 'path("invoices/<int:pk>/", tooltime_parity.invoice_workspace, name="next-invoice-edit")'
    if replacement not in text:
        text, count = pattern.subn(replacement, text, count=1)
        if count != 1:
            raise RuntimeError("ToolTime invoice workspace route anchor missing")

    def insert_route(after_name: str, route: str, route_name: str) -> None:
        nonlocal text
        if f'name="{route_name}"' in text:
            return
        lines = text.splitlines(keepends=True)
        for index, line in enumerate(lines):
            if f'name="{after_name}"' in line:
                indent = line[: len(line) - len(line.lstrip())]
                lines.insert(index + 1, indent + route + "\n")
                text = "".join(lines)
                return
        raise RuntimeError(f"ToolTime route insertion anchor missing: {after_name}")

    insert_route(
        "next-quote-pdf",
        'path("quotes/<int:pk>/preview/", tooltime_parity.quote_preview, name="next-quote-preview"),',
        "next-quote-preview",
    )
    insert_route(
        "next-invoice-edit",
        'path("invoices/<int:pk>/preview/", tooltime_parity.invoice_preview, name="next-invoice-preview"),',
        "next-invoice-preview",
    )

    write(rel, text)


def patch_quote_preview_template() -> None:
    rel = "templates/rebuild/quote_detail.html"
    text = read(rel)
    old = 'src="{% url \'next-quote-pdf\' quote.pk %}?preview=1#toolbar=0&navpanes=0"'
    new = 'src="{% url \'next-quote-preview\' quote.pk %}#toolbar=0&navpanes=0"'
    if new not in text:
        if old not in text:
            raise RuntimeError("ToolTime quote preview iframe anchor missing")
        text = text.replace(old, new, 1)
    write(rel, text)


def patch_draft_editor() -> None:
    rel = "templates/rebuild/document_editor.html"
    text = read(rel)

    css_marker = "tooltime-document-workspace.css"
    if css_marker not in text:
        anchor = "{% block content %}"
        if anchor not in text:
            raise RuntimeError("ToolTime document editor content block anchor missing")
        assets = '''{% block content %}\n{% if kind == 'invoice' %}<link rel="stylesheet" href="/static/css/tooltime-document-workspace.css?v=20260908-1"><script src="/static/js/tooltime-document-workspace.js?v=20260908-1" defer></script>{% endif %}'''
        text = text.replace(anchor, assets, 1)

    old_form = '<form class="tt-document-form"'
    new_form = '<form class="tt-document-form {% if kind == \'invoice\' %}tti-invoice-draft-form{% endif %}" data-document-kind="{{ kind }}"'
    if "tti-invoice-draft-form" not in text:
        if old_form not in text:
            raise RuntimeError("ToolTime document editor form anchor missing")
        text = text.replace(old_form, new_form, 1)

    write(rel, text)


def install_invoice_detail_template() -> None:
    write("templates/rebuild/invoice_detail.html", r'''{% extends 'rebuild/base.html' %}{% load static %}
{% block title %}Rechnung {{ invoice.number }} · A+Bau{% endblock %}
{% block content %}
<link rel="stylesheet" href="{% static 'css/tooltime-document-workspace.css' %}?v=20260908-1">
<div class="ttdw-page" data-tooltime-invoice-detail>
  <header class="ttdw-head">
    <div>
      <a class="ttdw-back" href="{% url 'next-invoices' %}">‹ Rechnungen</a>
      <div class="ttdw-title-line"><div><span class="ttdw-eyebrow">Rechnung</span><h1>{{ invoice.number|default:compliance.final_number }}</h1></div><span class="ttdw-state ttdw-state-{{ status_key }}">{{ status_label }}</span></div>
      <p>{{ customer_name }}{% if project %} · {{ project_label }}{% endif %}</p>
    </div>
    <div class="ttdw-head-actions"><a class="nx-btn" href="{% url 'invoice-compliance-pdf' invoice.pk %}">Original-PDF herunterladen</a>{% if compliance.original_xml_document_id %}<a class="nx-btn" href="{% url 'invoice-compliance-xml' invoice.pk %}">E-Rechnung herunterladen</a>{% endif %}</div>
  </header>

  <div class="ttdw-layout">
    <main class="ttdw-document-column">
      <section class="ttdw-paper-card">
        <div class="ttdw-paper-head"><div><span class="ttdw-eyebrow">Dokument</span><h2>Finale Rechnung</h2></div><a class="ttdw-link" href="{% url 'next-invoice-preview' invoice.pk %}" target="_blank" rel="noopener">In neuem Tab öffnen ↗</a></div>
        <div class="ttdw-preview"><iframe title="PDF-Vorschau Rechnung {{ invoice.number }}" src="{% url 'next-invoice-preview' invoice.pk %}#toolbar=0&navpanes=0" loading="eager"></iframe><div class="ttdw-preview-fallback">Falls die Vorschau im Browser deaktiviert ist: <a href="{% url 'invoice-compliance-pdf' invoice.pk %}">Original-PDF herunterladen</a></div></div>
      </section>
    </main>

    <aside class="ttdw-side">
      <section class="ttdw-card ttdw-amount-card"><span class="ttdw-eyebrow">Offener Betrag</span><h2>{{ open_amount|floatformat:2 }} €</h2><div class="ttdw-mini-total"><span>Gesamt</span><strong>{{ gross|floatformat:2 }} €</strong></div><div class="ttdw-mini-total"><span>Bezahlt</span><strong>{{ paid|floatformat:2 }} €</strong></div></section>

      <section class="ttdw-card"><span class="ttdw-eyebrow">Kunde & Projekt</span><h3>{{ customer_name }}</h3>{% if customer_address %}<p>{{ customer_address }}</p>{% endif %}{% if customer.email %}<p><a class="ttdw-link" href="mailto:{{ customer.email }}">{{ customer.email }}</a></p>{% endif %}{% if customer.phone %}<p>{{ customer.phone }}</p>{% endif %}<hr>{% if project %}<strong>{{ project_label }}</strong>{% else %}<span class="ttdw-muted">Ohne Projekt</span>{% endif %}</section>

      <section class="ttdw-card"><span class="ttdw-eyebrow">Rechnungsdetails</span><dl><div><dt>Status</dt><dd><span class="ttdw-state ttdw-state-{{ status_key }}">{{ status_label }}</span></dd></div><div><dt>Rechnungsdatum</dt><dd>{{ invoice.issue_date|date:'d.m.Y' }}</dd></div>{% if invoice.due_date %}<div><dt>Fällig am</dt><dd>{{ invoice.due_date|date:'d.m.Y' }}</dd></div>{% endif %}<div><dt>Netto</dt><dd>{{ net|floatformat:2 }} €</dd></div><div><dt>MwSt.</dt><dd>{{ tax|floatformat:2 }} €</dd></div><div><dt>Gesamt</dt><dd>{{ gross|floatformat:2 }} €</dd></div>{% if compliance.e_invoice_format %}<div><dt>E-Rechnung</dt><dd>{{ compliance.e_invoice_format }} · {{ compliance.get_e_invoice_status_display }}</dd></div>{% endif %}</dl></section>

      {% if open_amount > 0 %}<section class="ttdw-card"><span class="ttdw-eyebrow">Zahlung</span><h3>Zahlung erfassen</h3><form class="ttdw-pay-form" method="post" action="{% url 'next-invoice-payment' invoice.pk %}">{% csrf_token %}<label>Betrag<input class="nx-control" type="number" min="0.01" step="0.01" max="{{ open_amount }}" name="amount" value="{{ open_amount }}" required></label><div class="ttdw-two"><label>Zahlungsdatum<input class="nx-control" type="date" name="paid_at" value="{{ today|date:'Y-m-d' }}"></label><label>Methode<select class="nx-control" name="method"><option>Überweisung</option><option>Bar</option><option>Karte</option><option>Lastschrift</option><option>Sonstiges</option></select></label></div><label>Referenz<input class="nx-control" name="reference" maxlength="240" placeholder="Optional"></label><button class="nx-btn nx-btn-accent" type="submit">Zahlung speichern</button></form></section>{% endif %}

      <section class="ttdw-card"><span class="ttdw-eyebrow">Kommunikation</span><h3>Rechnung senden</h3><form class="ttdw-mail-form" method="post" action="{% url 'next-invoice-send-email' invoice.pk %}">{% csrf_token %}<label>Empfänger<input class="nx-control" type="email" name="recipient_email" value="{{ recipient_email }}" required></label><label>Betreff<input class="nx-control" name="subject" value="Rechnung {{ invoice.number }} · {{ invoice.organization.name }}" required></label><label>Nachricht<textarea class="nx-control" name="message" rows="4">Sehr geehrte Damen und Herren,

anbei erhalten Sie die Rechnung {{ invoice.number }} als PDF.

Mit freundlichen Grüßen
{{ invoice.organization.name }}</textarea></label><button class="nx-btn" type="submit">PDF per E-Mail senden</button></form>{% if deliveries %}<div class="ttdw-history"><strong>Versandverlauf</strong>{% for delivery in deliveries %}<div><span>{{ delivery.recipient_email }}</span><small>{{ delivery.created_at|date:'d.m.Y H:i' }} · {{ delivery.get_status_display }}</small></div>{% endfor %}</div>{% endif %}</section>

      <section class="ttdw-card ttdw-meta"><span class="ttdw-eyebrow">Dokumenthistorie</span><dl>{% if invoice.created_at %}<div><dt>Erstellt am</dt><dd>{{ invoice.created_at|date:'d.m.Y H:i' }}</dd></div>{% endif %}{% if invoice.created_by %}<div><dt>Erstellt von</dt><dd>{{ invoice.created_by.get_full_name|default:invoice.created_by.username }}</dd></div>{% endif %}{% if invoice.updated_at %}<div><dt>Letzte Änderung</dt><dd>{{ invoice.updated_at|date:'d.m.Y H:i' }}</dd></div>{% endif %}{% if compliance.finalized_at %}<div><dt>Finalisiert</dt><dd>{{ compliance.finalized_at|date:'d.m.Y H:i' }}</dd></div>{% endif %}</dl></section>
    </aside>
  </div>
</div>
{% endblock %}''')


def install_assets() -> None:
    write("static/js/tooltime-document-workspace.js", r'''(() => {
  "use strict";
  const form = document.querySelector("form.tti-invoice-draft-form");
  if (!form) return;
  document.body.classList.add("tti-invoice-draft-page");
  const main = form.closest("main") || document.querySelector("main");
  if (main) main.classList.add("tti-invoice-draft-main");
  form.querySelectorAll("section.tt-card").forEach((card, index) => card.dataset.ttiCardIndex = String(index));
})();
''')

    write("static/css/tooltime-document-workspace.css", r'''/* A+BAU TOOLTIME DOCUMENT WORKSPACE FINAL 2026-09-08 */
:root{--ttdw-blue:#1687e8;--ttdw-ink:#202a34;--ttdw-muted:#74808b;--ttdw-line:#e3e8ed;--ttdw-soft:#f7f9fb;--ttdw-white:#fff}
/* Draft invoice editor: preserve every existing control/handler, change only information architecture and presentation. */
body.tti-invoice-draft-page .content,body.tti-invoice-draft-page main{background:#fff!important}body.tti-invoice-draft-page .tti-invoice-draft-main{max-width:none!important;padding-right:clamp(18px,4vw,54px)!important}.tti-invoice-draft-form{max-width:1450px;margin:0 auto 50px!important;color:var(--ttdw-ink)}.tti-invoice-draft-form .tt-card{border:1px solid var(--ttdw-line)!important;border-radius:8px!important;background:#fff!important;box-shadow:none!important}.tti-invoice-draft-form .tt-document-top{max-width:880px;margin-bottom:28px!important;padding:26px!important}.tti-invoice-draft-form .tt-document-top h2{font-size:18px!important}.tti-invoice-draft-form .tt-document-top .tt-two{gap:12px!important}.tti-invoice-draft-form .nx-control,.tti-invoice-draft-form input,.tti-invoice-draft-form select,.tti-invoice-draft-form textarea{border-color:#d9e0e6!important;border-radius:6px!important;background:#fff!important;box-shadow:none!important}.tti-invoice-draft-form .nx-control:focus,.tti-invoice-draft-form input:focus,.tti-invoice-draft-form select:focus,.tti-invoice-draft-form textarea:focus{border-color:var(--ttdw-blue)!important;box-shadow:0 0 0 2px rgba(22,135,232,.10)!important}.tti-invoice-draft-form label{color:#58636d;font-weight:700}.tti-invoice-draft-form .tt-address-preview{border-radius:6px!important;background:#f7f9fb!important;border:0!important}.tti-invoice-draft-form .tt-inline-help{font-size:12px!important;color:#87919a!important}.tti-invoice-draft-form .tt-link{color:var(--ttdw-blue)!important}.tti-invoice-draft-form .tt-document-heading,.tti-invoice-draft-form .tt-section-title{border:0!important}.tti-invoice-draft-form [data-service-group],.tti-invoice-draft-form .tt-service-group{border:0!important;border-top:1px solid var(--ttdw-line)!important;border-radius:0!important;box-shadow:none!important;background:#fff!important}.tti-invoice-draft-form table{border-collapse:collapse!important}.tti-invoice-draft-form th{background:#fff!important;color:#65717c!important;font-size:11px!important;text-transform:none!important;border-bottom:1px solid var(--ttdw-line)!important}.tti-invoice-draft-form td{border-bottom:1px solid #edf0f3!important}.tti-invoice-draft-form .tt-position-row,.tti-invoice-draft-form [data-position-row]{background:#fff!important}.tti-invoice-draft-form .tt-calculation-card,.tti-invoice-draft-form .tt-summary-card{background:#f8fafc!important;border:0!important;border-radius:6px!important}.tti-invoice-draft-form .nx-btn{border-radius:6px!important}.tti-invoice-draft-form .nx-btn-accent,.tti-invoice-draft-form button[type=submit].ab-primary-action{background:#1687e8!important;border-color:#1687e8!important;color:#fff!important}.tti-invoice-draft-form .nx-form-actions,.tti-invoice-draft-form .tt-form-actions{border-top:1px solid var(--ttdw-line)!important;background:#fff!important;box-shadow:none!important}.tti-invoice-draft-form textarea{min-height:86px}.tti-invoice-draft-form .tt-editor-grid{grid-template-columns:minmax(0,1fr) 300px!important;gap:22px!important}.tti-invoice-draft-form .tt-document-bottom{gap:22px!important}.tti-invoice-draft-form .tt-eyebrow{color:#7b8791!important}.tti-invoice-draft-form [data-group-menu],.tti-invoice-draft-form .tt-menu{border:0!important;background:transparent!important}
/* Final ToolTime-style document workspace. */
.ttdw-page{max-width:1520px;margin:0 auto;padding:0 0 44px;color:var(--ttdw-ink)}.ttdw-head{display:flex;justify-content:space-between;gap:24px;align-items:flex-end;margin:0 0 20px}.ttdw-back,.ttdw-link{color:#64727d;text-decoration:none;font-weight:700}.ttdw-back:hover,.ttdw-link:hover{color:#1687e8}.ttdw-eyebrow{display:block;margin-bottom:5px;color:#7e8a94;font-size:10px;font-weight:850;text-transform:uppercase;letter-spacing:.10em}.ttdw-title-line{display:flex;align-items:center;gap:12px;margin-top:8px}.ttdw-title-line h1{margin:2px 0 0;font-size:clamp(27px,3vw,38px);letter-spacing:-.035em;line-height:1.05}.ttdw-head>div>p{margin:8px 0 0;color:#75818b}.ttdw-head-actions{display:flex;gap:8px;flex-wrap:wrap}.ttdw-layout{display:grid;grid-template-columns:minmax(0,1fr) 310px;gap:28px;align-items:start}.ttdw-document-column{min-width:0}.ttdw-paper-card{background:#f5f7f9;border:1px solid var(--ttdw-line);border-radius:8px;padding:18px}.ttdw-paper-head{display:flex;justify-content:space-between;gap:18px;align-items:end;margin-bottom:14px}.ttdw-paper-head h2{margin:0;font-size:17px}.ttdw-preview{position:relative;height:min(82vh,1120px);min-height:720px;background:#e9edf0;border:1px solid #dfe4e8;border-radius:5px;overflow:hidden}.ttdw-preview iframe{display:block;width:100%;height:100%;border:0;background:#fff}.ttdw-preview-fallback{position:absolute;right:12px;bottom:10px;padding:6px 9px;background:rgba(255,255,255,.94);border:1px solid #e2e7eb;border-radius:5px;font-size:11px;color:#697681}.ttdw-side{display:grid;gap:14px;position:sticky;top:78px}.ttdw-card{background:#fff;border:1px solid var(--ttdw-line);border-radius:8px;padding:18px;box-shadow:none}.ttdw-card h2,.ttdw-card h3{margin:0}.ttdw-card h3{font-size:16px}.ttdw-card p{margin:8px 0;color:#66737e;line-height:1.5}.ttdw-card hr{border:0;border-top:1px solid #edf0f2;margin:14px 0}.ttdw-amount-card h2{margin:0 0 12px;font-size:27px;letter-spacing:-.03em}.ttdw-mini-total{display:flex;justify-content:space-between;gap:14px;padding:7px 0;border-top:1px solid #eef1f3;font-size:13px}.ttdw-card dl{display:grid;margin:9px 0 0}.ttdw-card dl>div{display:flex;justify-content:space-between;gap:14px;padding:8px 0;border-top:1px solid #eef1f3;font-size:13px}.ttdw-card dt{color:#74808a}.ttdw-card dd{margin:0;text-align:right;font-weight:700}.ttdw-state{display:inline-flex;align-items:center;min-height:25px;padding:4px 8px;border-radius:999px;background:#eef1f3;color:#55616b;font-size:11px;font-weight:850;white-space:nowrap}.ttdw-state-unpaid{background:#fff2c8;color:#775b0e}.ttdw-state-overdue{background:#fde8e5;color:#923f35}.ttdw-state-paid{background:#e3f5e9;color:#21643a}.ttdw-state-cancelled,.ttdw-state-credited{background:#eceff1;color:#59636b}.ttdw-muted{color:#84909a;font-size:13px}.ttdw-pay-form,.ttdw-mail-form{display:grid;gap:9px;margin-top:12px}.ttdw-pay-form label,.ttdw-mail-form label{display:grid;gap:5px;color:#68747e;font-size:11px;font-weight:750}.ttdw-two{display:grid;grid-template-columns:1fr 1fr;gap:8px}.ttdw-pay-form .nx-control,.ttdw-mail-form .nx-control{border-radius:6px!important;border-color:#dce2e7!important}.ttdw-history{display:grid;gap:7px;margin-top:14px;padding-top:12px;border-top:1px solid #edf0f2}.ttdw-history>div{display:grid;gap:2px}.ttdw-history small{color:#87929b}.ttdw-meta{font-size:12px}
@media(max-width:1120px){.ttdw-layout{grid-template-columns:1fr}.ttdw-side{position:static;grid-template-columns:repeat(2,minmax(0,1fr))}.ttdw-preview{height:760px}.tti-invoice-draft-form .tt-editor-grid{grid-template-columns:1fr!important}}
@media(max-width:720px){body.tti-invoice-draft-page .tti-invoice-draft-main{padding-right:14px!important}.tti-invoice-draft-form .tt-document-top{padding:15px!important;max-width:none}.ttdw-head{align-items:stretch;flex-direction:column}.ttdw-head-actions{display:grid}.ttdw-head-actions .nx-btn{width:100%}.ttdw-title-line{align-items:flex-start;justify-content:space-between}.ttdw-layout{gap:12px}.ttdw-side{grid-template-columns:1fr}.ttdw-paper-card,.ttdw-card{padding:13px;border-radius:7px}.ttdw-paper-head{align-items:flex-start;flex-direction:column}.ttdw-preview{height:67vh;min-height:480px}.ttdw-preview-fallback{display:none}.ttdw-two{grid-template-columns:1fr}}
''')


def install_tests() -> None:
    write("tests/test_tooltime_document_workspace_final_contract.py", r'''from pathlib import Path
from django.test import SimpleTestCase

ROOT = Path(__file__).resolve().parents[1]


class ToolTimeDocumentWorkspaceFinalContractTests(SimpleTestCase):
    def test_dedicated_inline_preview_routes_exist(self):
        urls = (ROOT / "erp/rebuild_urls.py").read_text(encoding="utf-8")
        views = (ROOT / "erp/tooltime_parity_views.py").read_text(encoding="utf-8")
        self.assertIn('name="next-quote-preview"', urls)
        self.assertIn('name="next-invoice-preview"', urls)
        self.assertIn('def quote_preview(request, pk):', views)
        self.assertIn('def invoice_preview(request, pk):', views)
        self.assertIn('@xframe_options_sameorigin', views)
        self.assertIn('Content-Disposition"] = f\'inline;', views)

    def test_quote_detail_uses_preview_endpoint_not_download_query_hack(self):
        detail = (ROOT / "templates/rebuild/quote_detail.html").read_text(encoding="utf-8")
        self.assertIn("next-quote-preview", detail)
        self.assertNotIn("next-quote-pdf' quote.pk %}?preview=1", detail)

    def test_invoice_route_dispatches_draft_vs_finalized(self):
        urls = (ROOT / "erp/rebuild_urls.py").read_text(encoding="utf-8")
        views = (ROOT / "erp/tooltime_parity_views.py").read_text(encoding="utf-8")
        self.assertIn('tooltime_parity.invoice_workspace, name="next-invoice-edit"', urls)
        self.assertIn('compliance_state == "draft"', views)
        self.assertIn('return invoice_editor(request, pk)', views)
        self.assertIn('rebuild/invoice_detail.html', views)

    def test_final_invoice_is_document_workspace_not_editor(self):
        detail = (ROOT / "templates/rebuild/invoice_detail.html").read_text(encoding="utf-8")
        for phrase in ("Offener Betrag", "Finale Rechnung", "Kunde & Projekt", "Rechnungsdetails", "Zahlung erfassen", "Rechnung senden"):
            self.assertIn(phrase, detail)
        for route in ("next-invoice-preview", "invoice-compliance-pdf", "next-invoice-payment", "next-invoice-send-email"):
            self.assertIn(route, detail)
        self.assertNotIn('name="item_description"', detail)
        self.assertNotIn('tt-document-form', detail)

    def test_invoice_draft_editor_gets_tooltime_presentation_without_replacing_fields(self):
        editor = (ROOT / "templates/rebuild/document_editor.html").read_text(encoding="utf-8")
        css = (ROOT / "static/css/tooltime-document-workspace.css").read_text(encoding="utf-8")
        self.assertIn("tti-invoice-draft-form", editor)
        self.assertIn("tooltime-document-workspace.css", editor)
        self.assertIn(".tti-invoice-draft-form", css)
        self.assertIn(".ttdw-layout", css)
''')


def validate() -> None:
    required = {
        "erp/tooltime_parity_views.py": (
            "def quote_preview(request, pk):",
            "def invoice_preview(request, pk):",
            "def invoice_workspace(request, pk):",
            "xframe_options_sameorigin",
        ),
        "erp/rebuild_urls.py": (
            'name="next-quote-preview"',
            'name="next-invoice-preview"',
            'tooltime_parity.invoice_workspace, name="next-invoice-edit"',
        ),
        "templates/rebuild/quote_detail.html": ("next-quote-preview",),
        "templates/rebuild/invoice_detail.html": ("Offener Betrag", "next-invoice-preview", "Original-PDF herunterladen"),
        "templates/rebuild/document_editor.html": ("tti-invoice-draft-form", "tooltime-document-workspace.css"),
        "static/css/tooltime-document-workspace.css": ("A+BAU TOOLTIME DOCUMENT WORKSPACE FINAL", ".ttdw-layout"),
    }
    for rel, markers in required.items():
        source = read(rel)
        for marker in markers:
            if marker not in source:
                raise RuntimeError(f"ToolTime document workspace validation marker missing in {rel}: {marker}")
    compile(read("erp/tooltime_parity_views.py"), str(ROOT / "erp/tooltime_parity_views.py"), "exec")
    compile(read("tests/test_tooltime_document_workspace_final_contract.py"), str(ROOT / "tests/test_tooltime_document_workspace_final_contract.py"), "exec")


def main() -> None:
    patch_views()
    patch_urls()
    patch_quote_preview_template()
    patch_draft_editor()
    install_invoice_detail_template()
    install_assets()
    install_tests()
    validate()
    print("ToolTime document workspace finalisiert: dedizierte PDF-Vorschauen, ToolTime-artiger Rechnungsentwurf und unveränderliche finale Rechnungsansicht sind verbunden.")


if __name__ == "__main__":
    main()
