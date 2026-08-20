from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MARKER = "A+BAU TOOLTIME PHASE 7 E2E FLOW 2026-08-20"


def read(rel: str) -> str:
    path = ROOT / rel
    if not path.exists():
        raise RuntimeError(f"Phase 7 target missing: {rel}")
    return path.read_text(encoding="utf-8")


def write(rel: str, text: str) -> None:
    path = ROOT / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def patch_views() -> None:
    rel = "erp/tooltime_parity_views.py"
    text = read(rel)

    helper_anchor = 'def _phase4_customer(document, meta=None):\n'
    helper = r'''def _phase7_can_commercially_mutate(request):
    if getattr(request.user, "is_superuser", False):
        return True
    role = str(getattr(getattr(request.user, "profile", None), "role", "") or "")
    return role in {"admin", "office", "project_manager", "accounting"}


def _phase7_commercial_guard(request, redirect_name="next-quotes"):
    if _phase7_can_commercially_mutate(request):
        return None
    messages.error(request, "Diese kaufmännische Aktion ist nur für Büro, Projektleitung oder Buchhaltung freigegeben.")
    return redirect(redirect_name)


def _phase7_order_confirmation_document(quote, user):
    for existing in m.Document.objects.filter(
        organization=quote.organization,
        project=quote.project,
        category="contract",
    ).order_by("-pk")[:50]:
        metadata = existing.metadata or {}
        if metadata.get("kind") == "order_confirmation" and str(metadata.get("quote_id")) == str(quote.pk):
            return existing, False

    customer = _phase5_customer(quote, "quote")
    totals = base._quote_total(quote)
    gross = money(totals.get("gross", totals.get("net", 0)) or 0)
    rows = []
    for item in quote.items.all().order_by("position", "pk"):
        quantity = getattr(item, "quantity", 0) or 0
        unit_price = money(getattr(item, "unit_price", 0) or 0)
        line_total = money(quantity * unit_price)
        rows.append(
            "<tr>"
            f"<td>{html.escape(str(getattr(item, 'position', '') or ''))}</td>"
            f"<td>{html.escape(str(getattr(item, 'description', '') or ''))}</td>"
            f"<td style='text-align:right'>{html.escape(str(quantity))} {html.escape(str(getattr(item, 'unit', '') or ''))}</td>"
            f"<td style='text-align:right'>{line_total:.2f} €</td>"
            "</tr>"
        )
    customer_name = getattr(customer, "display_name", "") if customer else ""
    project_label = f"{quote.project.number} · {quote.project.title}" if quote.project_id else ""
    accepted_at = meta_for(quote, "quote").accepted_at
    accepted_label = timezone.localtime(accepted_at).strftime("%d.%m.%Y %H:%M") if accepted_at else timezone.localtime().strftime("%d.%m.%Y %H:%M")
    body = f'''<html><body style="font-family:Arial,sans-serif;font-size:11px;color:#202428">
<h1>Auftragsbestätigung</h1>
<p>Angebot: <strong>{html.escape(quote.number or '')}</strong></p>
<p>Kunde: <strong>{html.escape(str(customer_name))}</strong></p>
<p>Projekt: {html.escape(project_label)}</p>
<p>Wir bestätigen die Beauftragung auf Grundlage des angenommenen Angebots. Annahme: {html.escape(accepted_label)}.</p>
<table style="width:100%;border-collapse:collapse" cellpadding="6"><thead><tr style="border-bottom:1px solid #bbb"><th>Pos.</th><th style="text-align:left">Leistung</th><th style="text-align:right">Menge</th><th style="text-align:right">Gesamt</th></tr></thead><tbody>{''.join(rows)}</tbody></table>
<p style="font-size:13px;margin-top:18px">Auftragssumme <strong style="float:right">{gross:.2f} €</strong></p>
<p style="margin-top:36px">Mit freundlichen Grüßen<br>{html.escape(quote.organization.name)}</p>
</body></html>'''
    payload = html_to_pdf_bytes(inject_business_pdf_identity(body, org=quote.organization, document_kind="Auftragsbestätigung"))
    filename = f"auftragsbestaetigung-{quote.number or quote.pk}.pdf"
    document = m.Document(
        organization=quote.organization,
        project=quote.project,
        customer=customer,
        title=f"Auftragsbestätigung · {quote.number or quote.pk}",
        category="contract",
        mime_type="application/pdf",
        size=len(payload),
        sha256=hashlib.sha256(payload).hexdigest(),
        metadata={
            "kind": "order_confirmation",
            "quote_id": quote.pk,
            "quote_number": quote.number or "",
            "immutable": True,
            "accepted_at": accepted_at.isoformat() if accepted_at else "",
        },
        uploaded_by=user,
    )
    document.file.save(filename, ContentFile(payload), save=False)
    document.save()
    project = quote.project
    if project and project.status not in {"cancelled", "completed", "invoiced"}:
        project.status = "confirmed"
        project.save(update_fields=["status", "updated_at"])
    m.ActivityLog.objects.create(
        organization=quote.organization,
        user=user,
        verb="quote.order_confirmation.created",
        entity_type="quote",
        entity_id=str(quote.pk),
        description=f"Auftragsbestätigung für Angebot {quote.number or quote.pk} erstellt.",
        metadata={"document_id": document.pk, "project_id": quote.project_id},
    )
    return document, True


'''
    if "def _phase7_order_confirmation_document(" not in text:
        if helper_anchor not in text:
            raise RuntimeError("Phase 7 helper anchor missing")
        text = text.replace(helper_anchor, helper + helper_anchor, 1)

    # Commercial mutations are office-side actions. Außendienst/Monteur may still
    # read assigned work, but crafted POST requests must not mutate finance data.
    required_mutations = {
        "quote_status": "next-quotes",
        "quote_to_invoice": "next-quotes",
        "invoice_payment": "next-invoices",
    }
    for function_name, redirect_name in required_mutations.items():
        pattern = re.compile(
            rf"(def {function_name}\([^\n]+\):\n    org = _org\(request\)\n)(?!    phase7_guard =)",
        )
        replacement = (
            rf"\1    phase7_guard = _phase7_commercial_guard(request, \"{redirect_name}\")\n"
            "    if phase7_guard is not None:\n"
            "        return phase7_guard\n"
        )
        text, count = pattern.subn(replacement, text, count=1)
        if count != 1 and f"def {function_name}" in text and "phase7_guard = _phase7_commercial_guard" not in text[text.find(f"def {function_name}"):text.find(f"def {function_name}") + 500]:
            raise RuntimeError(f"Phase 7 role guard anchor missing for {function_name}")

    # Editing a commercial document is allowed for field staff as read-only, but
    # POSTing changes is not. This closes the direct-form bypass as well.
    for function_name, redirect_name in (("quote_editor", "next-quotes"), ("invoice_editor", "next-invoices")):
        marker = f"def {function_name}(request, pk=None):\n    org = _org(request)\n"
        guarded = marker + f"    if request.method == \"POST\":\n        phase7_guard = _phase7_commercial_guard(request, \"{redirect_name}\")\n        if phase7_guard is not None:\n            return phase7_guard\n"
        if guarded not in text:
            if marker not in text:
                raise RuntimeError(f"Phase 7 editor guard anchor missing: {function_name}")
            text = text.replace(marker, guarded, 1)

    # Enforce Annahme -> Auftragsbestätigung -> Rechnung, and make invoice
    # conversion idempotent even if a form is submitted twice.
    invoice_anchor = '    quote_meta = meta_for(quote, "quote")\n'
    invoice_guard = invoice_anchor + r'''    if quote.status != "accepted":
        messages.error(request, "Eine Rechnung kann erst nach Annahme des Angebots erstellt werden.")
        return redirect("next-quote-edit", pk=quote.pk)
    order_confirmation = None
    for candidate in m.Document.objects.filter(organization=org, project=quote.project, category="contract").order_by("-pk")[:50]:
        metadata = candidate.metadata or {}
        if metadata.get("kind") == "order_confirmation" and str(metadata.get("quote_id")) == str(quote.pk):
            order_confirmation = candidate
            break
    if order_confirmation is None:
        messages.error(request, "Bitte zuerst die Auftragsbestätigung erstellen.")
        return redirect("next-quote-edit", pk=quote.pk)
    existing_invoice = m.Invoice.objects.filter(organization=org, quote=quote).order_by("pk").first()
    if existing_invoice is not None:
        messages.info(request, "Für dieses Angebot existiert bereits eine Rechnung. Sie wurde geöffnet.")
        return redirect("next-invoice-edit", pk=existing_invoice.pk)
'''
    quote_to_invoice_pos = text.find("def quote_to_invoice(request, pk):")
    if quote_to_invoice_pos < 0:
        raise RuntimeError("Phase 7 quote_to_invoice missing")
    segment_end = text.find("\n\n@login_required", quote_to_invoice_pos + 10)
    if segment_end < 0:
        segment_end = min(len(text), quote_to_invoice_pos + 12000)
    segment = text[quote_to_invoice_pos:segment_end]
    if "Bitte zuerst die Auftragsbestätigung erstellen." not in segment:
        anchor_pos = text.find(invoice_anchor, quote_to_invoice_pos, segment_end)
        if anchor_pos < 0:
            raise RuntimeError("Phase 7 invoice flow anchor missing")
        text = text[:anchor_pos] + invoice_guard + text[anchor_pos + len(invoice_anchor):]

    billing_anchor = '    messages.success(request, "Rechnungsentwurf wurde aus dem Angebot übernommen. Positionen, Gruppen, Kalkulation und Mischpositionen wurden kopiert.")\n'
    billing_update = r'''    if quote.project and quote.project.status not in {"cancelled", "completed"}:
        quote.project.status = "invoiced"
        quote.project.save(update_fields=["status", "updated_at"])
''' + billing_anchor
    if "quote.project.status = \"invoiced\"" not in text:
        if billing_anchor not in text:
            raise RuntimeError("Phase 7 project invoiced anchor missing")
        text = text.replace(billing_anchor, billing_update, 1)

    payment_anchor = '    invoice.save(update_fields=["status", "updated_at"])\n'
    payment_update = payment_anchor + r'''    if invoice.status == "paid" and invoice.project and invoice.project.status not in {"cancelled", "completed"}:
        invoice.project.status = "completed"
        invoice.project.progress = 100
        invoice.project.save(update_fields=["status", "progress", "updated_at"])
'''
    payment_pos = text.find("def invoice_payment(request, pk):")
    if payment_pos < 0:
        raise RuntimeError("Phase 7 invoice_payment missing")
    if "invoice.project.status = \"completed\"" not in text[payment_pos:payment_pos + 5000]:
        anchor_pos = text.find(payment_anchor, payment_pos, payment_pos + 5000)
        if anchor_pos < 0:
            raise RuntimeError("Phase 7 payment completion anchor missing")
        text = text[:anchor_pos] + payment_update + text[anchor_pos + len(payment_anchor):]

    endpoint_anchor = '\n\n@login_required\n@require_http_methods(["GET", "POST"])\ndef invoice_editor(request, pk=None):\n'
    endpoint = r'''

@login_required
@require_http_methods(["GET", "POST"])
def quote_order_confirmation(request, pk):
    org = _org(request)
    phase7_guard = _phase7_commercial_guard(request, "next-quotes")
    if phase7_guard is not None:
        return phase7_guard
    quote = get_object_or_404(m.Quote.objects.select_related("project__customer"), organization=org, pk=pk)
    meta = meta_for(quote, "quote")
    if quote.status != "accepted" or not meta.finalized_at:
        messages.error(request, "Eine Auftragsbestätigung ist erst für ein fertiggestelltes und angenommenes Angebot verfügbar.")
        return redirect("next-quote-edit", pk=quote.pk)
    document = None
    for candidate in m.Document.objects.filter(organization=org, project=quote.project, category="contract").order_by("-pk")[:50]:
        metadata = candidate.metadata or {}
        if metadata.get("kind") == "order_confirmation" and str(metadata.get("quote_id")) == str(quote.pk):
            document = candidate
            break
    if request.method == "POST" and document is None:
        document, created = _phase7_order_confirmation_document(quote, request.user)
        if created:
            messages.success(request, "Auftragsbestätigung wurde erstellt und revisionssicher im Projekt gespeichert.")
    if document is None:
        messages.info(request, "Für dieses Angebot wurde noch keine Auftragsbestätigung erstellt.")
        return redirect("next-quote-edit", pk=quote.pk)
    if not document.file:
        raise Http404("Auftragsbestätigung nicht verfügbar")
    response = FileResponse(document.file.open("rb"), content_type="application/pdf", as_attachment=True, filename=f"auftragsbestaetigung-{quote.number or quote.pk}.pdf")
    response["X-Content-Type-Options"] = "nosniff"
    return response
'''
    if "def quote_order_confirmation(request, pk):" not in text:
        if endpoint_anchor not in text:
            raise RuntimeError("Phase 7 order confirmation insertion anchor missing")
        text = text.replace(endpoint_anchor, endpoint + endpoint_anchor, 1)

    write(rel, text)


def patch_dunning_role() -> None:
    rel = "erp/tooltime_parity_finance.py"
    text = read(rel)
    old = '''def invoice_dunning(request, pk):
    org = _org(request); invoice = get_object_or_404(m.Invoice, organization=org, pk=pk)
'''
    new = '''def invoice_dunning(request, pk):
    org = _org(request)
    role = str(getattr(getattr(request.user, "profile", None), "role", "") or "")
    if not (getattr(request.user, "is_superuser", False) or role in {"admin", "office", "project_manager", "accounting"}):
        messages.error(request, "Mahnungen sind nur für Büro, Projektleitung oder Buchhaltung freigegeben.")
        return redirect("next-invoices")
    invoice = get_object_or_404(m.Invoice, organization=org, pk=pk)
'''
    if "Mahnungen sind nur für Büro" not in text:
        if old not in text:
            raise RuntimeError("Phase 7 invoice_dunning role anchor missing")
        text = text.replace(old, new, 1)
    write(rel, text)


def patch_urls() -> None:
    rel = "erp/rebuild_urls.py"
    text = read(rel)
    anchor = '    path("quotes/<int:pk>/rechnung/", tooltime_parity.quote_to_invoice, name="next-quote-to-invoice"),\n'
    route = '    path("quotes/<int:pk>/auftragsbestaetigung/", tooltime_parity.quote_order_confirmation, name="next-quote-order-confirmation"),\n'
    if route not in text:
        if anchor not in text:
            raise RuntimeError("Phase 7 quote-to-invoice route anchor missing")
        text = text.replace(anchor, route + anchor, 1)
    write(rel, text)


def patch_template_context() -> None:
    rel = "erp/templatetags/tooltime_parity.py"
    text = read(rel)
    dunning_anchor = '    dunning = list(document.tooltime_dunning_records.select_related("document").all()) if kind == "invoice" and document is not None else []\n'
    extra = dunning_anchor + r'''    phase7_appointment = None
    phase7_order_confirmation = None
    phase7_invoice = None
    if kind == "quote" and document is not None and getattr(document, "project_id", None):
        phase7_appointment = m.CalendarEvent.objects.filter(organization=org, project_id=document.project_id).order_by("-starts_at", "-pk").first()
        phase7_invoice = m.Invoice.objects.filter(organization=org, quote=document).order_by("pk").first()
        for candidate in m.Document.objects.filter(organization=org, project_id=document.project_id, category="contract").order_by("-pk")[:50]:
            metadata = candidate.metadata or {}
            if metadata.get("kind") == "order_confirmation" and str(metadata.get("quote_id")) == str(document.pk):
                phase7_order_confirmation = candidate
                break
'''
    if "phase7_order_confirmation = None" not in text:
        if dunning_anchor not in text:
            raise RuntimeError("Phase 7 template context dunning anchor missing")
        text = text.replace(dunning_anchor, extra, 1)
    return_pattern = re.compile(r'    return \{([^\n]+)\}\n')
    match = return_pattern.search(text)
    if not match:
        raise RuntimeError("Phase 7 template context return dictionary missing")
    if '"phase7_appointment"' not in match.group(0):
        inside = match.group(1).rstrip()
        replacement = '    return {' + inside + ', "phase7_appointment": phase7_appointment, "phase7_order_confirmation": phase7_order_confirmation, "phase7_invoice": phase7_invoice}\n'
        text = text[:match.start()] + replacement + text[match.end():]
    write(rel, text)


def patch_templates() -> None:
    rel = "templates/rebuild/document_editor.html"
    text = read(rel)
    flow = r'''
{% if kind == 'quote' and document and tt.meta and tt.meta.finalized_at %}
<section class="tt-card tt-phase7-flow" data-phase7-flow>
  <div class="tt-section-title"><div><span class="tt-eyebrow">Auftragsablauf</span><h2>Vom Kunden bis zur Zahlung</h2></div><span class="nx-badge">{{ document.get_status_display }}</span></div>
  <div class="tt-phase7-steps">
    <span class="is-done">✓ Kunde</span>
    <span class="is-done">✓ Projekt</span>
    <span class="{% if tt.phase7_appointment %}is-done{% endif %}">{% if tt.phase7_appointment %}✓{% else %}○{% endif %} Termin</span>
    <span class="is-done">✓ Angebot</span>
    <span class="{% if document.status == 'accepted' %}is-done{% endif %}">{% if document.status == 'accepted' %}✓{% else %}○{% endif %} Annahme</span>
    <span class="{% if tt.phase7_order_confirmation %}is-done{% endif %}">{% if tt.phase7_order_confirmation %}✓{% else %}○{% endif %} Auftragsbestätigung</span>
    <span class="{% if tt.phase7_invoice %}is-done{% endif %}">{% if tt.phase7_invoice %}✓{% else %}○{% endif %} Rechnung</span>
  </div>
  {% if tt.phase7_appointment %}<p class="tt-modal-note">Termin: {{ tt.phase7_appointment.starts_at|date:'d.m.Y H:i' }} · {{ tt.phase7_appointment.title }}</p>{% else %}<p class="tt-modal-note">Noch kein Termin mit diesem Projekt verknüpft.</p>{% endif %}
</section>
{% endif %}
'''
    toolbar_anchor = '<div class="tt-card tt-quote-statusbar">'
    if "data-phase7-flow" not in text:
        if toolbar_anchor not in text:
            raise RuntimeError("Phase 7 quote statusbar anchor missing")
        text = text.replace(toolbar_anchor, flow + toolbar_anchor, 1)

    invoice_form = '''  <form method="post" action="{% url 'next-quote-to-invoice' document.pk %}">{% csrf_token %}<button class="nx-btn nx-btn-accent" type="submit">In Rechnung übernehmen</button></form>'''
    flow_actions = r'''  {% if document.status == 'accepted' %}<form method="post" action="{% url 'next-quote-order-confirmation' document.pk %}" data-phase7-order-confirmation>{% csrf_token %}<button class="nx-btn" type="submit">{% if tt.phase7_order_confirmation %}Auftragsbestätigung herunterladen{% else %}Auftragsbestätigung erstellen{% endif %}</button></form>{% endif %}
  {% if document.status == 'accepted' and tt.phase7_order_confirmation %}<form method="post" action="{% url 'next-quote-to-invoice' document.pk %}">{% csrf_token %}<button class="nx-btn nx-btn-accent" type="submit">{% if tt.phase7_invoice %}Rechnung öffnen{% else %}In Rechnung übernehmen{% endif %}</button></form>{% endif %}'''
    if "data-phase7-order-confirmation" not in text:
        if invoice_form not in text:
            raise RuntimeError("Phase 7 editor invoice action anchor missing")
        text = text.replace(invoice_form, flow_actions, 1)
    write(rel, text)

    rel = "templates/rebuild/quotes.html"
    text = read(rel)
    list_invoice = '''<form method="post" action="{% url 'next-quote-to-invoice' row.quote.pk %}">{% csrf_token %}<button class="nx-btn nx-btn-small nx-btn-accent" type="submit">In Rechnung</button></form>'''
    list_actions = r'''{% if row.quote.status == 'accepted' %}<form method="post" action="{% url 'next-quote-order-confirmation' row.quote.pk %}">{% csrf_token %}<button class="nx-btn nx-btn-small" type="submit">Auftragsbestätigung</button></form>{% endif %}<form method="post" action="{% url 'next-quote-to-invoice' row.quote.pk %}">{% csrf_token %}<button class="nx-btn nx-btn-small nx-btn-accent" type="submit">In Rechnung</button></form>'''
    if "next-quote-order-confirmation" not in text:
        if list_invoice not in text:
            raise RuntimeError("Phase 7 quote list invoice anchor missing")
        text = text.replace(list_invoice, list_actions, 1)
    write(rel, text)

    rel = "static/css/tooltime-parity-finance.css"
    css = read(rel)
    if "/* A+BAU PHASE 7 E2E FLOW */" not in css:
        css += r'''

/* A+BAU PHASE 7 E2E FLOW */
.tt-phase7-flow{margin-bottom:14px}.tt-phase7-steps{display:flex;gap:8px;flex-wrap:wrap;margin:12px 0}.tt-phase7-steps span{display:inline-flex;align-items:center;min-height:32px;padding:6px 10px;border-radius:999px;background:#f1f4f7;color:#667085;font-size:12px;font-weight:800}.tt-phase7-steps span.is-done{background:#e9f7ef;color:#11733c}
'''
        write(rel, css)


def patch_browser_smoke() -> None:
    rel = "scripts/production_browser_smoke.py"
    text = read(rel)
    marker = "# A+BAU PHASE 7 E2E FLOW BROWSER SMOKE"
    if marker not in text:
        anchor = "            context.close()\n"
        pos = text.rfind(anchor)
        if pos < 0:
            raise RuntimeError("Phase 7 browser-smoke final context anchor missing")
        block = r'''            # A+BAU PHASE 7 E2E FLOW BROWSER SMOKE
            response = page.goto(urljoin(base_url, "quotes/"), wait_until="domcontentloaded", timeout=30_000)
            if response is None or response.status >= 500:
                fail(f"Phase-7-Angebotsliste returned {response.status if response else 'no response'}")
            hrefs = page.locator('a[href]').evaluate_all("els => els.map(el => el.getAttribute('href') || '').filter(Boolean)")
            quote_paths = []
            for href in hrefs:
                candidate = urlparse(urljoin(base_url, href)).path
                if re.match(r"^/quotes/\d+/$", candidate) and candidate not in quote_paths:
                    quote_paths.append(candidate)
            for quote_path in quote_paths[:20]:
                detail_response = page.goto(urljoin(base_url, quote_path.lstrip('/')), wait_until="domcontentloaded", timeout=30_000)
                if detail_response is None or detail_response.status >= 500:
                    fail(f"{quote_path} returned {detail_response.status if detail_response else 'no response'}")
                statusbar = page.locator('.tt-quote-statusbar')
                if statusbar.count() != 1:
                    continue
                if page.locator('[data-phase7-flow]').count() != 1:
                    fail("Finalisiertes Angebot zeigt keinen Ende-zu-Ende-Auftragsablauf")
                if "Angenommen" in statusbar.inner_text() and page.locator('[data-phase7-order-confirmation]').count() != 1:
                    fail("Angenommenes Angebot bietet keine Auftragsbestätigung an")
                break

'''
        text = text[:pos] + block + text[pos:]
    write(rel, text)
    compile(text, str(ROOT / rel), "exec")


def install_tests() -> None:
    write("tests/test_tooltime_phase7_e2e_flow_contract.py", r'''from pathlib import Path
from django.test import SimpleTestCase

ROOT = Path(__file__).resolve().parents[1]


class ToolTimePhase7E2EFlowContractTests(SimpleTestCase):
    def test_order_confirmation_is_real_immutable_project_document(self):
        views = (ROOT / "erp/tooltime_parity_views.py").read_text(encoding="utf-8")
        urls = (ROOT / "erp/rebuild_urls.py").read_text(encoding="utf-8")
        self.assertIn("def quote_order_confirmation(request, pk):", views)
        self.assertIn('"kind": "order_confirmation"', views)
        self.assertIn('"immutable": True', views)
        self.assertIn('hashlib.sha256(payload).hexdigest()', views)
        self.assertIn('project.status = "confirmed"', views)
        self.assertIn('name="next-quote-order-confirmation"', urls)

    def test_invoice_conversion_requires_acceptance_and_order_confirmation_and_is_idempotent(self):
        views = (ROOT / "erp/tooltime_parity_views.py").read_text(encoding="utf-8")
        self.assertIn('if quote.status != "accepted":', views)
        self.assertIn('Bitte zuerst die Auftragsbestätigung erstellen.', views)
        self.assertIn('existing_invoice = m.Invoice.objects.filter(organization=org, quote=quote)', views)
        self.assertIn('quote.project.status = "invoiced"', views)
        self.assertIn('invoice.project.status = "completed"', views)

    def test_field_role_cannot_mutate_commercial_endpoints(self):
        views = (ROOT / "erp/tooltime_parity_views.py").read_text(encoding="utf-8")
        finance = (ROOT / "erp/tooltime_parity_finance.py").read_text(encoding="utf-8")
        self.assertIn('role in {"admin", "office", "project_manager", "accounting"}', views)
        self.assertIn('Diese kaufmännische Aktion ist nur für Büro', views)
        self.assertIn('Mahnungen sind nur für Büro', finance)
        for function_name in ("quote_status", "quote_to_invoice", "invoice_payment"):
            start = views.index(f"def {function_name}")
            self.assertIn("_phase7_commercial_guard", views[start:start + 900])

    def test_flow_ui_connects_appointment_acceptance_confirmation_and_invoice(self):
        tags = (ROOT / "erp/templatetags/tooltime_parity.py").read_text(encoding="utf-8")
        template = (ROOT / "templates/rebuild/document_editor.html").read_text(encoding="utf-8")
        self.assertIn("m.CalendarEvent.objects.filter", tags)
        self.assertIn('data-phase7-flow', template)
        self.assertIn('data-phase7-order-confirmation', template)
        for label in ("Kunde", "Projekt", "Termin", "Annahme", "Auftragsbestätigung", "Rechnung"):
            self.assertIn(label, template)
''')


def run() -> None:
    patch_views()
    patch_dunning_role()
    patch_urls()
    patch_template_context()
    patch_templates()
    patch_browser_smoke()
    install_tests()
    for rel in (
        "erp/tooltime_parity_views.py",
        "erp/tooltime_parity_finance.py",
        "erp/templatetags/tooltime_parity.py",
        "scripts/production_browser_smoke.py",
    ):
        path = ROOT / rel
        compile(path.read_text(encoding="utf-8"), str(path), "exec")
    print("ToolTime Phase 7 installiert: Kunde→Projekt→Termin→Angebot→Annahme→Auftragsbestätigung→Rechnung→Zahlung/Mahnung ist verbunden und kaufmännisch rollenbeschränkt.")


if __name__ == "__main__":
    run()
