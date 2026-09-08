from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MARKER = "A+BAU TOOLTIME QUOTE POST-DRAFT DETAIL 2026-09-07"


def read(rel: str) -> str:
    path = ROOT / rel
    if not path.exists():
        raise RuntimeError(f"Post-draft quote detail target missing: {rel}")
    return path.read_text(encoding="utf-8")


def write(rel: str, text: str) -> None:
    path = ROOT / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def patch_views() -> None:
    rel = "erp/tooltime_parity_views.py"
    text = read(rel)
    if f"# {MARKER}" not in text:
        text += r'''

# A+BAU TOOLTIME QUOTE POST-DRAFT DETAIL 2026-09-07

def _quote_detail_decimal(value):
    try:
        return Decimal(str(value or 0)).quantize(Decimal("0.01"))
    except Exception:
        return Decimal("0.00")


def _quote_detail_status(quote):
    raw = str(getattr(quote, "status", "") or "draft").lower()
    labels = {
        "draft": ("Entwurf", "draft"),
        "sent": ("Ausstehend", "pending"),
        "pending": ("Ausstehend", "pending"),
        "accepted": ("Angenommen", "accepted"),
        "rejected": ("Abgelehnt", "rejected"),
        "declined": ("Abgelehnt", "rejected"),
        "expired": ("Abgelaufen", "rejected"),
    }
    return labels.get(raw, (raw.replace("_", " ").title(), raw))


def _quote_detail_customer_name(customer):
    if customer is None:
        return "—"
    display = getattr(customer, "display_name", "")
    if callable(display):
        try:
            display = display()
        except TypeError:
            pass
    if str(display or "").strip():
        return str(display).strip()
    company = str(getattr(customer, "company", "") or "").strip()
    person = " ".join(filter(None, [str(getattr(customer, "first_name", "") or "").strip(), str(getattr(customer, "last_name", "") or "").strip()]))
    return company or person or "—"


def _quote_detail_context(quote, meta):
    totals = base._quote_total(quote)
    net = _quote_detail_decimal(totals.get("net", 0))
    gross = _quote_detail_decimal(totals.get("gross", net))
    tax = _quote_detail_decimal(totals.get("tax", gross - net))
    customer = _phase4_customer(quote, meta)
    project = getattr(quote, "project", None)
    status_label, status_key = _quote_detail_status(quote)

    rows = []
    for item in quote.items.all().order_by("position", "pk"):
        quantity = getattr(item, "quantity", 0) or 0
        unit_price = _quote_detail_decimal(getattr(item, "unit_price", 0))
        try:
            line_total = _quote_detail_decimal(quantity * unit_price)
        except Exception:
            line_total = Decimal("0.00")
        rows.append({
            "item": item,
            "quantity": quantity,
            "unit_price": unit_price,
            "line_total": line_total,
            "tax_rate": getattr(item, "tax_rate", 0) or 0,
        })

    try:
        commercial = quote.commercial_settings
    except Exception:
        commercial = None
    payment_due_days = getattr(commercial, "payment_due_days", None) if commercial else None
    early_percent = getattr(commercial, "early_payment_discount_percent", None) if commercial else None
    early_days = getattr(commercial, "early_payment_discount_days", None) if commercial else None
    discount_type = str(getattr(commercial, "discount_type", "") or "") if commercial else ""
    discount_value = getattr(commercial, "discount_value", None) if commercial else None

    deliveries = []
    if hasattr(m, "ToolTimeDocumentDelivery"):
        deliveries = list(
            m.ToolTimeDocumentDelivery.objects.filter(organization=quote.organization, quote=quote)
            .select_related("document")
            .order_by("-created_at", "-id")[:8]
        )

    customer_address = " · ".join(filter(None, [
        str(getattr(customer, "street", "") or "").strip() if customer else "",
        " ".join(filter(None, [
            str(getattr(customer, "postal_code", "") or "").strip() if customer else "",
            str(getattr(customer, "city", "") or "").strip() if customer else "",
        ])),
    ]))
    project_label = _phase4_project_label(quote)
    if project_label == "Ohne Projekt":
        project = None

    return {
        "quote": quote,
        "document": quote,
        "meta": meta,
        "items": rows,
        "net": net,
        "tax": tax,
        "gross": gross,
        "customer": customer,
        "customer_name": _quote_detail_customer_name(customer),
        "customer_address": customer_address,
        "project": project,
        "project_label": project_label,
        "status_label": status_label,
        "status_key": status_key,
        "commercial": commercial,
        "payment_due_days": payment_due_days,
        "early_percent": early_percent,
        "early_days": early_days,
        "discount_type": discount_type,
        "discount_value": discount_value,
        "deliveries": deliveries,
        "recipient_email": str(getattr(customer, "email", "") or "") if customer else "",
        "document_title": str(getattr(meta, "document_title", "") or "Angebot") if meta else "Angebot",
        "finalized_at": getattr(meta, "finalized_at", None) if meta else None,
    }


@login_required
@require_http_methods(["GET", "POST"])
def quote_workspace(request, pk):
    """Keep drafts in the ToolTime editor and render every post-draft quote as a document."""
    org = _org(request)
    quote = get_object_or_404(
        m.Quote.objects.select_related("project__customer").prefetch_related("items"),
        organization=org,
        pk=pk,
    )
    meta = meta_for(quote, "quote", create=False)
    is_editable_draft = str(getattr(quote, "status", "") or "draft").lower() == "draft" and not bool(meta and meta.finalized_at)
    if is_editable_draft:
        return quote_editor(request, pk)
    if request.method != "GET":
        messages.info(request, "Fertiggestellte Angebote werden als Dokument angezeigt und nicht mehr im Entwurfseditor bearbeitet.")
        return redirect("next-quote-edit", pk=quote.pk)
    return render(request, "rebuild/quote_detail.html", _quote_detail_context(quote, meta))
'''

    # The PDF route is also used by the inline document preview. Downloads remain
    # attachments; only the explicit same-origin preview query switches disposition.
    inline_marker = 'request.GET.get("preview") == "1"'
    if inline_marker not in text:
        old_header = '    response["Content-Disposition"] = f\'attachment; filename="angebot-{quote.number or quote.pk}.pdf"\'\n'
        new_header = '    disposition = "inline" if request.GET.get("preview") == "1" else "attachment"\n    response["Content-Disposition"] = f\'{disposition}; filename="angebot-{quote.number or quote.pk}.pdf"\'\n'
        if old_header in text:
            text = text.replace(old_header, new_header, 1)
        else:
            old_stream = 'return FileResponse(io.BytesIO(payload), as_attachment=True, content_type="application/pdf", filename=f"angebot-{quote.number or quote.pk}.pdf")'
            new_stream = 'return FileResponse(io.BytesIO(payload), as_attachment=request.GET.get("preview") != "1", content_type="application/pdf", filename=f"angebot-{quote.number or quote.pk}.pdf")'
            if old_stream in text:
                text = text.replace(old_stream, new_stream, 1)
            elif 'as_attachment=request.GET.get("preview") != "1"' not in text:
                raise RuntimeError("Post-draft quote PDF disposition anchor missing")

    write(rel, text)
    compile(text, str(ROOT / rel), "exec")


def patch_urls() -> None:
    rel = "erp/rebuild_urls.py"
    text = read(rel)
    old = '    path("quotes/<int:pk>/", tooltime_parity.quote_editor, name="next-quote-edit"),\n'
    new = '    path("quotes/<int:pk>/", tooltime_parity.quote_workspace, name="next-quote-edit"),\n'
    if new not in text:
        if old not in text:
            raise RuntimeError("Post-draft quote workspace route anchor missing")
        text = text.replace(old, new, 1)
    write(rel, text)


def install_template() -> None:
    write("templates/rebuild/quote_detail.html", r'''{% extends 'rebuild/base.html' %}{% load static %}
{% block title %}{{ document_title }} {{ quote.number }} · A+Bau{% endblock %}
{% block content %}
<link rel="stylesheet" href="{% static 'css/tooltime-quote-detail.css' %}?v=20260907-1">
<div class="ttqd-page" data-tooltime-quote-detail>
  <header class="ttqd-head">
    <div class="ttqd-head-main">
      <a class="ttqd-back" href="{% url 'next-quotes' %}">‹ Angebote</a>
      <div class="ttqd-title-row"><div><span class="ttqd-eyebrow">Dokument</span><h1>{{ document_title }} {% if quote.number %}{{ quote.number }}{% endif %}</h1></div><span class="ttqd-status ttqd-status-{{ status_key }}">{{ status_label }}</span></div>
      <p>{% if customer %}{{ customer_name }}{% else %}Kein Kunde zugeordnet{% endif %}{% if project %} · {{ project_label }}{% endif %}</p>
    </div>
    <div class="ttqd-head-actions"><a class="nx-btn" href="{% url 'next-quote-pdf' quote.pk %}">PDF herunterladen</a>{% if quote.status != 'accepted' %}<form method="post" action="{% url 'next-quote-status' quote.pk %}">{% csrf_token %}<button class="nx-btn nx-btn-accent" name="action" value="accepted">Als angenommen markieren</button></form>{% endif %}</div>
  </header>

  <div class="ttqd-grid">
    <main class="ttqd-main">
      <section class="ttqd-card ttqd-preview-card">
        <div class="ttqd-card-head"><div><span class="ttqd-eyebrow">PDF-Vorschau</span><h2>Finales Angebotsdokument</h2></div><a class="ttqd-link" href="{% url 'next-quote-pdf' quote.pk %}" target="_blank" rel="noopener">In neuem Tab öffnen ↗</a></div>
        <div class="ttqd-pdf-wrap"><iframe title="PDF-Vorschau {{ quote.number }}" src="{% url 'next-quote-pdf' quote.pk %}?preview=1#toolbar=0&navpanes=0" loading="eager"></iframe><div class="ttqd-pdf-fallback">PDF-Vorschau nicht verfügbar? <a href="{% url 'next-quote-pdf' quote.pk %}">PDF herunterladen</a></div></div>
      </section>

      <section class="ttqd-card">
        <div class="ttqd-card-head"><div><span class="ttqd-eyebrow">Leistungen</span><h2>Positionen</h2></div><strong>{{ gross|floatformat:2 }} €</strong></div>
        <div class="ttqd-table-wrap"><table class="ttqd-table"><thead><tr><th>Pos.</th><th>Beschreibung</th><th class="num">Menge</th><th class="num">Einzelpreis</th><th class="num">MwSt.</th><th class="num">Gesamt</th></tr></thead><tbody>{% for row in items %}<tr><td>{{ row.item.position|default:'—' }}</td><td><strong>{{ row.item.description|default:'—' }}</strong><small>{{ row.item.unit|default:'' }}</small></td><td class="num">{{ row.quantity|floatformat:-3 }} {{ row.item.unit }}</td><td class="num">{{ row.unit_price|floatformat:2 }} €</td><td class="num">{{ row.tax_rate|floatformat:-2 }} %</td><td class="num"><strong>{{ row.line_total|floatformat:2 }} €</strong></td></tr>{% empty %}<tr><td colspan="6" class="ttqd-empty">Keine Positionen vorhanden.</td></tr>{% endfor %}</tbody></table></div>
        <div class="ttqd-totals"><div><span>Nettobetrag</span><strong>{{ net|floatformat:2 }} €</strong></div><div><span>Umsatzsteuer</span><strong>{{ tax|floatformat:2 }} €</strong></div><div class="ttqd-total-final"><span>Gesamtbetrag</span><strong>{{ gross|floatformat:2 }} €</strong></div></div>
      </section>

      {% if quote.intro_text or quote.outro_text %}<section class="ttqd-card"><div class="ttqd-card-head"><div><span class="ttqd-eyebrow">Dokumenttexte</span><h2>Texte & Hinweise</h2></div></div>{% if quote.intro_text %}<div class="ttqd-copy"><strong>Einleitung</strong><p>{{ quote.intro_text|linebreaksbr }}</p></div>{% endif %}{% if quote.outro_text %}<div class="ttqd-copy"><strong>Schlusstext</strong><p>{{ quote.outro_text|linebreaksbr }}</p></div>{% endif %}</section>{% endif %}
    </main>

    <aside class="ttqd-side">
      <section class="ttqd-card ttqd-summary">
        <span class="ttqd-eyebrow">Zusammenfassung</span><h2>{{ gross|floatformat:2 }} €</h2>
        <dl><div><dt>Status</dt><dd><span class="ttqd-status ttqd-status-{{ status_key }}">{{ status_label }}</span></dd></div><div><dt>Angebotsdatum</dt><dd>{{ quote.issue_date|date:'d.m.Y' }}</dd></div><div><dt>Nummer</dt><dd>{{ quote.number|default:'—' }}</dd></div>{% if finalized_at %}<div><dt>Fertiggestellt</dt><dd>{{ finalized_at|date:'d.m.Y H:i' }}</dd></div>{% endif %}</dl>
      </section>

      <section class="ttqd-card"><span class="ttqd-eyebrow">Kunde & Projekt</span><h3>{{ customer_name }}</h3>{% if customer_address %}<p>{{ customer_address }}</p>{% endif %}{% if customer.email %}<p><a class="ttqd-link" href="mailto:{{ customer.email }}">{{ customer.email }}</a></p>{% endif %}{% if customer.phone %}<p>{{ customer.phone }}</p>{% endif %}<hr>{% if project %}<strong>{{ project_label }}</strong>{% else %}<span class="ttqd-muted">Ohne Projekt</span>{% endif %}</section>

      <section class="ttqd-card"><span class="ttqd-eyebrow">Zahlungsbedingungen</span><dl>{% if payment_due_days != None %}<div><dt>Zahlungsziel</dt><dd>{{ payment_due_days }} Tage</dd></div>{% endif %}{% if early_percent %}<div><dt>Skonto</dt><dd>{{ early_percent|floatformat:-2 }} %{% if early_days %} bei Zahlung in {{ early_days }} Tagen{% endif %}</dd></div>{% endif %}{% if discount_value %}<div><dt>Rabatt</dt><dd>{{ discount_value|floatformat:-2 }}{% if discount_type == 'percent' %} %{% else %} €{% endif %}</dd></div>{% endif %}</dl>{% if commercial.closing_text %}<p class="ttqd-muted">{{ commercial.closing_text|linebreaksbr }}</p>{% endif %}</section>

      <section class="ttqd-card"><span class="ttqd-eyebrow">Aktionen</span><div class="ttqd-action-stack">{% if quote.status != 'accepted' and quote.status != 'rejected' %}<form method="post" action="{% url 'next-quote-status' quote.pk %}">{% csrf_token %}<button class="nx-btn" name="action" value="rejected">Als abgelehnt markieren</button></form>{% endif %}{% if quote.status == 'rejected' %}<form method="post" action="{% url 'next-quote-status' quote.pk %}">{% csrf_token %}<button class="nx-btn" name="action" value="pending">Status zurücksetzen</button></form>{% endif %}<form method="post" action="{% url 'next-quote-to-invoice' quote.pk %}">{% csrf_token %}<button class="nx-btn nx-btn-accent" type="submit">In Rechnung übernehmen</button></form></div></section>

      <section class="ttqd-card"><span class="ttqd-eyebrow">Kommunikation</span><h3>Per E-Mail senden</h3><form class="ttqd-email" method="post" action="{% url 'next-quote-send-email' quote.pk %}">{% csrf_token %}<label>Empfänger<input class="nx-control" type="email" name="recipient_email" value="{{ recipient_email }}" required></label><label>Betreff<input class="nx-control" name="subject" value="Angebot {{ quote.number }} · {{ quote.organization.name }}" required></label><label>Nachricht<textarea class="nx-control" name="message" rows="4">Sehr geehrte Damen und Herren,

anbei erhalten Sie das Angebot {{ quote.number }} als PDF.

Mit freundlichen Grüßen
{{ quote.organization.name }}</textarea></label><button class="nx-btn" type="submit">PDF per E-Mail senden</button></form>{% if deliveries %}<div class="ttqd-history"><strong>Versandverlauf</strong>{% for delivery in deliveries %}<div><span>{{ delivery.recipient_email }}</span><small>{{ delivery.created_at|date:'d.m.Y H:i' }} · {{ delivery.get_status_display }}</small></div>{% endfor %}</div>{% endif %}</section>
    </aside>
  </div>
</div>
{% endblock %}''')

    write("static/css/tooltime-quote-detail.css", r'''/* A+BAU TOOLTIME QUOTE POST-DRAFT DETAIL 2026-09-07 */
.ttqd-page{max-width:1540px;margin:0 auto;padding:4px 0 44px;color:#1d2329}.ttqd-head{display:flex;justify-content:space-between;gap:24px;align-items:flex-end;margin:0 0 22px}.ttqd-head-main{min-width:0}.ttqd-back,.ttqd-link{color:#5e6872;text-decoration:none;font-weight:700}.ttqd-back:hover,.ttqd-link:hover{color:#111}.ttqd-title-row{display:flex;align-items:center;gap:13px;margin-top:9px}.ttqd-title-row h1{margin:2px 0 0;font-size:clamp(28px,3vw,42px);line-height:1.06;letter-spacing:-.035em}.ttqd-head-main>p{margin:8px 0 0;color:#727b84}.ttqd-eyebrow{display:block;margin-bottom:5px;color:#8b7450;font-size:11px;font-weight:850;text-transform:uppercase;letter-spacing:.11em}.ttqd-head-actions{display:flex;gap:8px;align-items:center;flex-wrap:wrap}.ttqd-head-actions form{margin:0}.ttqd-status{display:inline-flex;align-items:center;min-height:27px;padding:4px 9px;border-radius:999px;font-size:12px;font-weight:800;white-space:nowrap;background:#eef1f3;color:#44505a}.ttqd-status-pending{background:#fff3cf;color:#775a0b}.ttqd-status-accepted{background:#e3f4e8;color:#21663b}.ttqd-status-rejected{background:#fbe7e4;color:#8e3d33}.ttqd-status-draft{background:#eceff2;color:#5a626a}.ttqd-grid{display:grid;grid-template-columns:minmax(0,1fr) 350px;gap:20px;align-items:start}.ttqd-main,.ttqd-side{display:grid;gap:18px}.ttqd-side{position:sticky;top:82px}.ttqd-card{background:#fff;border:1px solid #e5e2dc;border-radius:14px;padding:20px;box-shadow:0 7px 24px rgba(25,29,33,.035)}.ttqd-card h2,.ttqd-card h3{margin:0}.ttqd-card h3{font-size:17px}.ttqd-card p{color:#5f6871;line-height:1.55}.ttqd-card hr{border:0;border-top:1px solid #ece9e2;margin:16px 0}.ttqd-card-head{display:flex;justify-content:space-between;align-items:flex-end;gap:15px;margin-bottom:16px}.ttqd-card-head h2{font-size:20px}.ttqd-preview-card{padding-bottom:16px}.ttqd-pdf-wrap{height:min(76vh,880px);min-height:620px;border:1px solid #dfddd8;border-radius:10px;overflow:hidden;background:#f2f1ee;position:relative}.ttqd-pdf-wrap iframe{display:block;width:100%;height:100%;border:0;background:#fff}.ttqd-pdf-fallback{position:absolute;right:12px;bottom:10px;padding:5px 8px;border-radius:7px;background:rgba(255,255,255,.92);font-size:11px;color:#68717a}.ttqd-pdf-fallback a{color:inherit;font-weight:800}.ttqd-table-wrap{overflow:auto}.ttqd-table{width:100%;border-collapse:collapse;min-width:720px}.ttqd-table th{padding:9px 10px;border-bottom:1px solid #dedbd5;color:#737b83;font-size:11px;text-align:left;text-transform:uppercase;letter-spacing:.04em}.ttqd-table td{padding:13px 10px;border-bottom:1px solid #eeece8;vertical-align:top}.ttqd-table td small{display:block;margin-top:4px;color:#90969c}.ttqd-table .num{text-align:right;white-space:nowrap}.ttqd-empty{text-align:center!important;color:#7c858d}.ttqd-totals{width:min(410px,100%);margin:18px 0 0 auto;display:grid;gap:8px}.ttqd-totals>div{display:flex;justify-content:space-between;gap:20px;padding:3px 0}.ttqd-total-final{border-top:1px solid #d8d4cc;margin-top:5px;padding-top:11px!important;font-size:17px}.ttqd-copy+.ttqd-copy{border-top:1px solid #ece9e2;margin-top:16px;padding-top:16px}.ttqd-summary h2{font-size:28px;margin:0 0 12px;letter-spacing:-.03em}.ttqd-card dl{display:grid;gap:0;margin:10px 0 0}.ttqd-card dl>div{display:flex;justify-content:space-between;gap:12px;padding:9px 0;border-top:1px solid #efede8}.ttqd-card dt{color:#737b83}.ttqd-card dd{margin:0;text-align:right;font-weight:700}.ttqd-muted{color:#808890;font-size:13px;line-height:1.5}.ttqd-action-stack{display:grid;gap:8px}.ttqd-action-stack form,.ttqd-action-stack button{width:100%}.ttqd-email{display:grid;gap:10px;margin-top:13px}.ttqd-email label{display:grid;gap:5px;color:#6e7780;font-size:12px;font-weight:700}.ttqd-email textarea{resize:vertical}.ttqd-history{display:grid;gap:7px;margin-top:16px;padding-top:14px;border-top:1px solid #ece9e2}.ttqd-history>div{display:grid;gap:2px;padding:5px 0}.ttqd-history small{color:#858d94}
@media(max-width:1100px){.ttqd-grid{grid-template-columns:1fr}.ttqd-side{position:static;grid-template-columns:repeat(2,minmax(0,1fr))}.ttqd-side .ttqd-card:last-child{grid-column:1/-1}.ttqd-pdf-wrap{height:700px}}
@media(max-width:720px){.ttqd-page{padding-bottom:24px}.ttqd-head{align-items:stretch;flex-direction:column}.ttqd-head-actions{display:grid;grid-template-columns:1fr}.ttqd-head-actions a,.ttqd-head-actions button{width:100%}.ttqd-title-row{align-items:flex-start;justify-content:space-between}.ttqd-title-row h1{font-size:29px}.ttqd-grid,.ttqd-main,.ttqd-side{gap:12px}.ttqd-side{grid-template-columns:1fr}.ttqd-side .ttqd-card:last-child{grid-column:auto}.ttqd-card{padding:15px;border-radius:11px}.ttqd-card-head{align-items:flex-start;flex-direction:column}.ttqd-pdf-wrap{min-height:0;height:66vh}.ttqd-pdf-fallback{display:none}.ttqd-table{min-width:650px}}
''')


def install_tests() -> None:
    write("tests/test_tooltime_quote_postdraft_detail_contract.py", r'''from pathlib import Path
from django.test import SimpleTestCase

ROOT = Path(__file__).resolve().parents[1]


class ToolTimeQuotePostDraftDetailContractTests(SimpleTestCase):
    def test_quote_route_uses_workspace_dispatcher(self):
        urls = (ROOT / "erp/rebuild_urls.py").read_text(encoding="utf-8")
        views = (ROOT / "erp/tooltime_parity_views.py").read_text(encoding="utf-8")
        self.assertIn('tooltime_parity.quote_workspace, name="next-quote-edit"', urls)
        self.assertIn('def quote_workspace(request, pk):', views)
        self.assertIn('is_editable_draft', views)
        self.assertIn('return quote_editor(request, pk)', views)
        self.assertIn('rebuild/quote_detail.html', views)

    def test_postdraft_surface_is_document_not_editor(self):
        detail = (ROOT / "templates/rebuild/quote_detail.html").read_text(encoding="utf-8")
        for marker in ("PDF-Vorschau", "Positionen", "Zahlungsbedingungen", "Kunde & Projekt", "In Rechnung übernehmen", "Per E-Mail senden"):
            self.assertIn(marker, detail)
        self.assertNotIn('name="item_description"', detail)
        self.assertNotIn('tt-document-form', detail)

    def test_pdf_supports_inline_preview_without_changing_download_contract(self):
        views = (ROOT / "erp/tooltime_parity_views.py").read_text(encoding="utf-8")
        detail = (ROOT / "templates/rebuild/quote_detail.html").read_text(encoding="utf-8")
        self.assertIn('request.GET.get("preview")', views)
        self.assertIn('?preview=1', detail)
        self.assertIn('PDF herunterladen', detail)

    def test_financial_and_lifecycle_actions_remain_server_backed(self):
        detail = (ROOT / "templates/rebuild/quote_detail.html").read_text(encoding="utf-8")
        for route in ("next-quote-status", "next-quote-to-invoice", "next-quote-send-email", "next-quote-pdf"):
            self.assertIn(route, detail)
        for value in ("net", "tax", "gross", "payment_due_days", "early_percent"):
            self.assertIn(f'"{value}"', (ROOT / "erp/tooltime_parity_views.py").read_text(encoding="utf-8"))
''')


def validate() -> None:
    required = {
        "erp/tooltime_parity_views.py": ("def quote_workspace", "is_editable_draft", "rebuild/quote_detail.html", 'request.GET.get("preview")'),
        "erp/rebuild_urls.py": ('tooltime_parity.quote_workspace, name="next-quote-edit"',),
        "templates/rebuild/quote_detail.html": ("PDF-Vorschau", "Positionen", "Zahlungsbedingungen", "In Rechnung übernehmen"),
        "static/css/tooltime-quote-detail.css": ("A+BAU TOOLTIME QUOTE POST-DRAFT DETAIL", ".ttqd-grid"),
    }
    for rel, markers in required.items():
        source = read(rel)
        for marker in markers:
            if marker not in source:
                raise RuntimeError(f"Post-draft quote detail validation marker missing in {rel}: {marker}")


def main() -> None:
    patch_views()
    patch_urls()
    install_template()
    install_tests()
    validate()
    print("ToolTime Angebot workflow: Entwürfe bleiben im Editor; fertiggestellte/versendete Angebote öffnen als dokumentorientierte Detailansicht mit PDF-Vorschau, Kalkulation, Kunde/Projekt, Zahlungsbedingungen und Lifecycle-Aktionen.")


if __name__ == "__main__":
    main()
