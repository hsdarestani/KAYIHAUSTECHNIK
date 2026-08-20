from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(rel):
    path = ROOT / rel
    if not path.exists():
        raise RuntimeError(f"Rechnungsassistent: Datei fehlt: {rel}")
    return path.read_text(encoding="utf-8")


def write(rel, text):
    (ROOT / rel).write_text(text, encoding="utf-8")


def patch_views():
    rel = "erp/tooltime_parity_views.py"
    text = read(rel)
    insertion = r'''

def _quote_item_billed_quantities(quote):
    billed = {}
    metas = m.ToolTimeDocumentMeta.objects.filter(
        organization=quote.organization,
        invoice__project=quote.project,
        invoice__quote=quote,
        invoice_type="partial",
    ).exclude(invoice__status="cancelled")
    for meta in metas:
        for link in meta.billing_links or []:
            try:
                item_id = int(link.get("quote_item_id") or 0)
                quantity = Decimal(str(link.get("quantity") or "0"))
            except Exception:
                continue
            billed[item_id] = billed.get(item_id, Decimal("0")) + quantity
    return billed


def _available_invoice_types(quote):
    existing = set(m.ToolTimeDocumentMeta.objects.filter(
        organization=quote.organization,
        invoice__project=quote.project,
        invoice__quote=quote,
    ).exclude(invoice__status="cancelled").values_list("invoice_type", flat=True))
    result = []
    if "partial" not in existing:
        result.append(("advance", "Abschlagsrechnung", "Anzahlung oder Vorschuss ohne konkrete Leistungszuordnung."))
    if "advance" not in existing:
        result.append(("partial", "Teilrechnung", "Bereits vollständig oder teilweise erbrachte, klar abgegrenzte Leistungen abrechnen."))
    result.append(("final", "Schlussrechnung", "Gesamtabrechnung unter Berücksichtigung bereits erstellter Abschlags- oder Teilrechnungen."))
    return result


def _copy_quote_item_to_invoice(invoice, quote_item, quantity, position):
    item = m.InvoiceItem.objects.create(
        invoice=invoice,
        position=position,
        code=quote_item.code,
        description=quote_item.description,
        quantity=quantity,
        unit=quote_item.unit,
        unit_price=quote_item.unit_price,
        tax_rate=quote_item.tax_rate,
        catalog_item=quote_item.catalog_item,
        ai_generated=False,
        approved=True,
    )
    try:
        src = quote_item.commercial_meta
        m.CommercialItemMeta.objects.create(
            organization=invoice.organization,
            invoice_item=item,
            position_type=src.position_type,
            purchase_price=src.purchase_price,
            markup_percent=src.markup_percent,
            service_model=src.service_model,
            detail_text=src.detail_text,
            group_title=src.group_title,
        )
    except Exception:
        pass
    return item


@login_required
@require_http_methods(["GET", "POST"])
def quote_invoice_wizard(request, pk):
    org = _org(request)
    quote = get_object_or_404(m.Quote.objects.select_related("project", "project__customer"), organization=org, pk=pk)
    quote_meta = meta_for(quote, "quote")
    if not quote_meta.finalized_at:
        messages.error(request, "Bitte das Angebot zuerst fertigstellen.")
        return redirect("next-quote-edit", pk=quote.pk)
    available_types = _available_invoice_types(quote)
    allowed = {row[0] for row in available_types}
    billed = _quote_item_billed_quantities(quote)
    item_rows = []
    for item in quote.items.select_related("catalog_item").order_by("position", "pk"):
        already = billed.get(item.pk, Decimal("0"))
        remaining = max(Decimal("0"), Decimal(str(item.quantity)) - already)
        item.ui_billed_quantity = already
        item.ui_remaining_quantity = remaining
        item_rows.append(item)
    previous = []
    for meta in m.ToolTimeDocumentMeta.objects.filter(organization=org, invoice__project=quote.project, invoice__quote=quote).exclude(invoice__status="cancelled").select_related("invoice").order_by("invoice__issue_date", "invoice__pk"):
        previous.append({"meta": meta, "invoice": meta.invoice, "total": base._invoice_total(meta.invoice)})

    if request.method == "POST":
        invoice_type = (request.POST.get("invoice_type") or "").strip()
        if invoice_type not in allowed:
            messages.error(request, "Diese Rechnungsart ist für den aktuellen Projektstand nicht verfügbar.")
            return redirect("next-quote-invoice-wizard", pk=quote.pk)
        issue_date = timezone.localdate()
        due_days = int(profile_for(org).settings.get("payment_terms", {}).get("days") or 0)
        invoice = m.Invoice.objects.create(
            organization=org,
            project=quote.project,
            quote=quote,
            number="",
            status="draft",
            issue_date=issue_date,
            due_date=issue_date + timedelta(days=due_days),
            service_date=issue_date,
            intro_text="",
            outro_text="",
            notes="",
            created_by=request.user,
        )
        try:
            qsettings = quote.commercial_settings
            settings = m.CommercialDocumentSettings.objects.create(
                organization=org,
                invoice=invoice,
                tax_code=qsettings.tax_code,
                tax_rate=qsettings.tax_rate,
                discount_type="percent",
                discount_value=0,
                payment_due_days=due_days,
                early_payment_discount_percent=qsettings.early_payment_discount_percent,
                early_payment_discount_days=qsettings.early_payment_discount_days,
                closing_text=qsettings.closing_text,
            )
        except Exception:
            settings = m.CommercialDocumentSettings.objects.create(organization=org, invoice=invoice, payment_due_days=due_days)
        meta = m.ToolTimeDocumentMeta.objects.create(
            organization=org,
            invoice=invoice,
            document_title={"advance":"Abschlagsrechnung", "partial":"Teilrechnung", "final":"Schlussrechnung"}[invoice_type],
            salutation="Sehr geehrte Damen und Herren,",
            invoice_type=invoice_type,
            title_suffix=(request.POST.get("title_suffix") or "")[:120],
            web_view_enabled=False,
            labour_cost_share_visible=True,
        )
        links = []
        position = 1
        if invoice_type == "advance":
            quote_total = base._quote_total(quote)["net"]
            mode = request.POST.get("advance_mode") or "percent"
            value = money(request.POST.get("advance_value"))
            amount = quote_total * value / Decimal("100") if mode == "percent" else value
            amount = max(Decimal("0"), min(quote_total, amount)).quantize(Decimal("0.01"))
            if amount <= 0:
                invoice.delete()
                messages.error(request, "Bitte einen gültigen Abschlagsbetrag eingeben.")
                return redirect("next-quote-invoice-wizard", pk=quote.pk)
            m.InvoiceItem.objects.create(invoice=invoice, position=1, code="", description=f"Abschlagszahlung zu Angebot {quote.number}", quantity=1, unit="Pauschal", unit_price=amount, tax_rate=settings.tax_rate, ai_generated=False, approved=True)
            links = [{"kind": "advance", "amount": str(amount), "quote_id": quote.pk}]
        elif invoice_type == "partial":
            selected_any = False
            for row in item_rows:
                raw = request.POST.get(f"quantity_{row.pk}") or "0"
                qty = max(Decimal("0"), Decimal(str(raw).replace(",", ".")))
                if qty <= 0:
                    continue
                remaining = row.ui_remaining_quantity
                if qty > remaining:
                    invoice.delete()
                    messages.error(request, f"Position {row.position}: maximal {remaining} {row.unit} sind noch abrechenbar.")
                    return redirect("next-quote-invoice-wizard", pk=quote.pk)
                _copy_quote_item_to_invoice(invoice, row, qty, position)
                links.append({"kind":"partial", "quote_item_id": row.pk, "quantity": str(qty)})
                position += 1; selected_any = True
            if not selected_any:
                invoice.delete()
                messages.error(request, "Bitte mindestens eine noch offene Leistung auswählen.")
                return redirect("next-quote-invoice-wizard", pk=quote.pk)
        else:
            for row in item_rows:
                _copy_quote_item_to_invoice(invoice, row, row.quantity, position); position += 1
            deductions = []
            for prev in previous:
                if prev["meta"].invoice_type not in {"advance", "partial"}:
                    continue
                net = prev["total"]["net"]
                if net <= 0:
                    continue
                label = "Abschlag" if prev["meta"].invoice_type == "advance" else "Bereits abgerechnete Teilleistung"
                m.InvoiceItem.objects.create(invoice=invoice, position=position, code="", description=f"{label} · {prev['invoice'].number or 'Entwurf'}", quantity=1, unit="Pauschal", unit_price=-net, tax_rate=settings.tax_rate, ai_generated=False, approved=True)
                deductions.append({"invoice_id": prev["invoice"].pk, "amount": str(net), "type": prev["meta"].invoice_type})
                position += 1
            links = [{"kind": "final", "quote_id": quote.pk, "deductions": deductions}]
        meta.billing_links = links; meta.save(update_fields=["billing_links", "updated_at"])
        messages.success(request, f"{meta.get_invoice_type_display()} wurde als Entwurf erstellt. Es wurde noch keine Rechnungsnummer vergeben.")
        return redirect("next-invoice-edit", pk=invoice.pk)

    return render(request, "rebuild/invoice_wizard.html", {"quote": quote, "available_types": available_types, "items": item_rows, "previous": previous, "quote_total": base._quote_total(quote)})
'''
    anchor = '\n\n@login_required\n@require_http_methods(["GET", "POST"])\ndef settings_page(request):\n'
    if insertion not in text:
        if anchor not in text:
            raise RuntimeError("Rechnungsassistent: View-Anker fehlt.")
        text = text.replace(anchor, insertion + anchor, 1)
    write(rel, text)


def patch_urls():
    rel = "erp/rebuild_urls.py"
    text = read(rel)
    anchor = '    path("quotes/<int:pk>/", tooltime_parity.quote_editor, name="next-quote-edit"),\n'
    route = '    path("quotes/<int:pk>/rechnung-erstellen/", tooltime_parity.quote_invoice_wizard, name="next-quote-invoice-wizard"),\n'
    if route not in text:
        if anchor not in text:
            raise RuntimeError("Rechnungsassistent: URL-Anker fehlt.")
        text = text.replace(anchor, anchor + route, 1)
    write(rel, text)


def patch_editor():
    rel = "templates/rebuild/document_editor.html"
    text = read(rel)
    old = '{% if kind == \'quote\' and document and tt.meta.finalized_at and tt.meta.web_view_enabled %}<button type="button" class="nx-btn" data-copy-link data-link="{{ request.scheme }}://{{ request.get_host }}{% url \'next-public-quote\' tt.meta.web_token %}">Webansicht kopieren</button>{% endif %}{% if document %}<span class="nx-badge">{{ document.get_status_display }}</span>{% endif %}'
    new = '{% if kind == \'quote\' and document and tt.meta.finalized_at %}<a class="nx-btn nx-btn-accent" href="{% url \'next-quote-invoice-wizard\' document.pk %}">Rechnung erstellen</a>{% if tt.meta.web_view_enabled %}<button type="button" class="nx-btn" data-copy-link data-link="{{ request.scheme }}://{{ request.get_host }}{% url \'next-public-quote\' tt.meta.web_token %}">Webansicht kopieren</button>{% endif %}{% endif %}{% if document %}<span class="nx-badge">{{ document.get_status_display }}</span>{% endif %}'
    if old not in text:
        raise RuntimeError("Rechnungsassistent: Editor-Kopf-Anker fehlt.")
    write(rel, text.replace(old, new, 1))


def install_template():
    write("templates/rebuild/invoice_wizard.html", r'''{% extends 'rebuild/base.html' %}{% load static %}{% block title %}Rechnung erstellen · A+Bau{% endblock %}{% block content %}<link rel="stylesheet" href="{% static 'css/tooltime-parity-finance.css' %}?v=20260820-2"><div class="nx-pagehead"><div><div class="nx-kicker">{{ quote.number }} · {{ quote.project.customer.display_name }}</div><h1>Rechnung erstellen</h1><p>Wähle die passende Rechnungsart. Bereits abgerechnete Leistungen werden berücksichtigt.</p></div><a class="nx-btn" href="{% url 'next-quote-edit' quote.pk %}">Zum Angebot</a></div><form method="post" class="tt-document-form" data-invoice-wizard>{% csrf_token %}<section class="tt-card"><h2>1. Rechnungsart auswählen</h2><div class="tt-invoice-types">{% for value,title,description in available_types %}<label class="tt-type-card"><input type="radio" name="invoice_type" value="{{ value }}" {% if forloop.first %}checked{% endif %}><span><strong>{{ title }}</strong><small>{{ description }}</small></span></label>{% endfor %}</div><label>Titelsuffix (optional)<input class="nx-control" name="title_suffix" placeholder="z. B. 1. Abschlag"></label></section><section class="tt-card" data-advance-panel><h2>2. Abschlagsbetrag</h2><div class="tt-two"><label>Berechnung<select class="nx-control" name="advance_mode"><option value="percent">Prozent vom Angebotsnetto</option><option value="fixed">Fester Nettobetrag</option></select></label><label>Wert<input class="nx-control" type="number" step="0.01" min="0" name="advance_value" value="30"></label></div><p>Angebotsnetto: <strong>{{ quote_total.net|floatformat:2 }} €</strong></p></section><section class="tt-card" data-partial-panel hidden><h2>2. Leistungen auswählen</h2><p>Es können nur noch nicht abgerechnete Restmengen ausgewählt werden.</p><div class="nx-table-wrap"><table class="nx-table"><thead><tr><th>Pos.</th><th>Leistung</th><th>Angebot</th><th>Bereits abgerechnet</th><th>Restmenge</th><th>Jetzt abrechnen</th></tr></thead><tbody>{% for item in items %}<tr><td>{{ item.position }}</td><td>{{ item.description }}</td><td>{{ item.quantity }} {{ item.unit }}</td><td>{{ item.ui_billed_quantity }} {{ item.unit }}</td><td><strong>{{ item.ui_remaining_quantity }} {{ item.unit }}</strong></td><td><input class="nx-control" type="number" step="0.001" min="0" max="{{ item.ui_remaining_quantity }}" name="quantity_{{ item.pk }}" value="0" {% if item.ui_remaining_quantity <= 0 %}disabled{% endif %}></td></tr>{% endfor %}</tbody></table></div></section><section class="tt-card" data-final-panel hidden><h2>2. Schlussrechnung prüfen</h2><p>Alle Positionen des ursprünglichen Angebots werden übernommen. Vorherige Abschlags- oder Teilrechnungen werden als Abzug berücksichtigt.</p>{% for row in previous %}<div class="tt-summary-line"><span>{{ row.meta.get_invoice_type_display }} · {{ row.invoice.number|default:'Entwurf' }}</span><strong>{{ row.total.gross|floatformat:2 }} €</strong></div>{% empty %}<p>Noch keine vorherige Rechnung vorhanden.</p>{% endfor %}</section><div class="tt-actions"><a class="nx-btn" href="{% url 'next-quote-edit' quote.pk %}">Abbrechen</a><button class="nx-btn nx-btn-accent" type="submit">Rechnungsentwurf erstellen</button></div></form><script>document.addEventListener('DOMContentLoaded',()=>{const form=document.querySelector('[data-invoice-wizard]');if(!form)return;const update=()=>{const type=form.querySelector('[name=invoice_type]:checked')?.value;form.querySelector('[data-advance-panel]').hidden=type!=='advance';form.querySelector('[data-partial-panel]').hidden=type!=='partial';form.querySelector('[data-final-panel]').hidden=type!=='final'};form.addEventListener('change',e=>{if(e.target.name==='invoice_type')update()});update()});</script>{% endblock %}''')


def patch_css():
    rel = "static/css/tooltime-parity-finance.css"
    css = read(rel)
    css += r'''
.tt-invoice-types{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px;margin-bottom:18px}.tt-type-card{display:block!important;position:relative}.tt-type-card input{position:absolute;opacity:0}.tt-type-card span{display:grid;gap:6px;border:1px solid #dfe5ec;border-radius:12px;padding:16px;cursor:pointer;min-height:92px}.tt-type-card input:checked+span{border-color:#1268e8;box-shadow:0 0 0 2px rgba(18,104,232,.12)}.tt-type-card small{font-weight:400;color:#6f7b88}@media(max-width:760px){.tt-invoice-types{grid-template-columns:1fr}}
'''
    write(rel, css)


def patch_tests():
    rel = "tests/test_tooltime_finance_parity_batch.py"
    text = read(rel)
    anchor = "    def test_group_actions_are_real_controls(self):\n"
    test = '''    def test_guided_invoice_wizard_exists(self):
        views = (ROOT / "erp/tooltime_parity_views.py").read_text()
        template = (ROOT / "templates/rebuild/invoice_wizard.html").read_text()
        self.assertIn("def quote_invoice_wizard", views)
        self.assertIn("_quote_item_billed_quantities", views)
        self.assertIn("Restmengen", template)
        self.assertIn("Abschlagsrechnung", template)
        self.assertIn("Teilrechnung", template)
        self.assertIn("Schlussrechnung", template)
        self.assertIn("maximal", views)

'''
    if test not in text:
        if anchor not in text:
            raise RuntimeError("Rechnungsassistent: Test-Anker fehlt.")
        text = text.replace(anchor, test + anchor, 1)
    write(rel, text)


def run():
    patch_views(); patch_urls(); patch_editor(); install_template(); patch_css(); patch_tests()
    print("Geführter Rechnungsassistent installiert: Abschlag, Teil, Schluss, Restmengen und Doppelabrechnungsschutz.")


if __name__ == "__main__":
    run()
