from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MARKER = "A+BAU TOOLTIME PHASE 3 EDITOR 2026-08-20"


def read(rel: str) -> str:
    path = ROOT / rel
    if not path.exists():
        raise RuntimeError(f"Phase 3 target missing: {rel}")
    return path.read_text(encoding="utf-8")


def write(rel: str, text: str) -> None:
    path = ROOT / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def patch_models_and_migration() -> None:
    rel = "erp/tooltime_parity_finance.py"
    text = read(rel)
    customer_field = '    customer = models.ForeignKey("erp.Customer", null=True, blank=True, on_delete=models.PROTECT, related_name="tooltime_document_meta")\n'
    if customer_field not in text:
        anchor = '    invoice = models.OneToOneField("erp.Invoice", null=True, blank=True, on_delete=models.CASCADE, related_name="tooltime_meta")\n'
        if anchor not in text:
            raise RuntimeError("Phase 3 ToolTimeDocumentMeta invoice anchor missing")
        text = text.replace(anchor, anchor + customer_field, 1)

    if "class ToolTimeMixedSubitem" not in text:
        text += r'''

class ToolTimeMixedSubitem(models.Model):
    TYPES = [("material", "Material"), ("labour", "Lohn"), ("other", "Sonstiges")]
    organization = models.ForeignKey("erp.Organization", on_delete=models.CASCADE, related_name="tooltime_mixed_subitems")
    quote_item = models.ForeignKey("erp.QuoteItem", null=True, blank=True, on_delete=models.CASCADE, related_name="tooltime_mixed_subitems")
    invoice_item = models.ForeignKey("erp.InvoiceItem", null=True, blank=True, on_delete=models.CASCADE, related_name="tooltime_mixed_subitems")
    item_type = models.CharField(max_length=16, choices=TYPES, default="material")
    description = models.CharField(max_length=300)
    quantity = models.DecimalField(max_digits=12, decimal_places=3, default=1)
    unit = models.CharField(max_length=30, default="Stk.")
    purchase_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    sales_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    sort_order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["sort_order", "id"]
'''
    write(rel, text)

    rel = "erp/ab_bau_commercial.py"
    text = read(rel)
    field = "    show_subitems_in_pdf = models.BooleanField(default=True)\n"
    if field not in text:
        anchor = "    group_title = models.CharField(max_length=220, blank=True)\n"
        if anchor not in text:
            raise RuntimeError("Phase 3 CommercialItemMeta group anchor missing")
        text = text.replace(anchor, anchor + field, 1)
        write(rel, text)

    rel = "erp/models.py"
    text = read(rel)
    if "ToolTimeMixedSubitem" not in text:
        pattern = re.compile(r"from \.tooltime_parity_finance import ([^\n]+)")
        match = pattern.search(text)
        if not match:
            raise RuntimeError("Phase 3 ToolTime models import missing")
        names = match.group(1)
        text = text[:match.start()] + f"from .tooltime_parity_finance import {names}, ToolTimeMixedSubitem" + text[match.end():]
        write(rel, text)

    write("erp/migrations/0016_tooltime_phase3_editor.py", r'''from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("erp", "0015_tooltime_phase2_settings")]
    operations = [
        migrations.AddField(
            model_name="tooltimedocumentmeta",
            name="customer",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="tooltime_document_meta", to="erp.customer"),
        ),
        migrations.AddField(
            model_name="commercialitemmeta",
            name="show_subitems_in_pdf",
            field=models.BooleanField(default=True),
        ),
        migrations.CreateModel(
            name="ToolTimeMixedSubitem",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("item_type", models.CharField(choices=[("material", "Material"), ("labour", "Lohn"), ("other", "Sonstiges")], default="material", max_length=16)),
                ("description", models.CharField(max_length=300)),
                ("quantity", models.DecimalField(decimal_places=3, default=1, max_digits=12)),
                ("unit", models.CharField(default="Stk.", max_length=30)),
                ("purchase_price", models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ("sales_price", models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ("sort_order", models.PositiveIntegerField(default=0)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("invoice_item", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="tooltime_mixed_subitems", to="erp.invoiceitem")),
                ("organization", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="tooltime_mixed_subitems", to="erp.organization")),
                ("quote_item", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="tooltime_mixed_subitems", to="erp.quoteitem")),
            ],
            options={"ordering": ["sort_order", "id"]},
        ),
    ]
''')


def patch_service() -> None:
    rel = "erp/services/tooltime_parity_finance.py"
    text = read(rel)
    anchor = '    profile = profile_for(document.organization).settings\n'
    customer_block = '''    profile = profile_for(document.organization).settings\n    customer_id = (request.POST.get("customer_id") or "").strip()\n    if customer_id.isdigit():\n        meta.customer = m.Customer.objects.filter(organization=document.organization, active=True, pk=int(customer_id)).first()\n    elif getattr(document, "project_id", None):\n        meta.customer = getattr(document.project, "customer", None)\n'''
    if customer_block not in text:
        if anchor not in text:
            raise RuntimeError("Phase 3 save_document_meta settings anchor missing")
        text = text.replace(anchor, customer_block, 1)
    write(rel, text)


def patch_commercial_runtime() -> None:
    rel = "erp/rebuild_views.py"
    text = read(rel)

    groups_anchor = '    groups = request.POST.getlist("item_group")\n'
    groups_new = groups_anchor + '    sales_prices = request.POST.getlist("item_sales_price")\n    mixed_payloads = request.POST.getlist("item_subitems_json")\n    mixed_visibility = request.POST.getlist("item_show_subitems")\n'
    if groups_new not in text:
        if groups_anchor not in text:
            raise RuntimeError("Phase 3 commercial groups anchor missing")
        text = text.replace(groups_anchor, groups_new, 1)

    old_qty = '        quantity = max(Decimal("0"), _money(_posted(quantities, index, "1")))\n'
    new_qty = '        quantity = _money(_posted(quantities, index, "1"))\n'
    if new_qty not in text:
        if old_qty not in text:
            raise RuntimeError("Phase 3 quantity anchor missing")
        text = text.replace(old_qty, new_qty, 1)

    sale_anchor = '        unit_price = (purchase * (Decimal("1") + markup / Decimal("100"))).quantize(Decimal("0.01"))\n'
    sale_new = sale_anchor + '        manual_sales = (_posted(sales_prices, index, "") or "").strip()\n        if manual_sales:\n            unit_price = max(Decimal("0"), _money(manual_sales)).quantize(Decimal("0.01"))\n            if purchase > 0:\n                markup = ((unit_price / purchase) - Decimal("1")) * Decimal("100")\n'
    if sale_new not in text:
        if sale_anchor not in text:
            raise RuntimeError("Phase 3 unit price anchor missing")
        text = text.replace(sale_anchor, sale_new, 1)

    meta_anchor = '            "group_title": (_posted(groups, index, "") or "")[:220],\n'
    meta_new = meta_anchor + '            "show_subitems_in_pdf": (_posted(mixed_visibility, index, "1") or "1") in {"1", "true", "on", "yes"},\n'
    if meta_new not in text:
        if meta_anchor not in text:
            raise RuntimeError("Phase 3 item meta anchor missing")
        text = text.replace(meta_anchor, meta_new, 1)

    create_anchor = '        m.CommercialItemMeta.objects.create(**meta_kwargs)\n'
    create_new = r'''        item_meta = m.CommercialItemMeta.objects.create(**meta_kwargs)
        if position_type == "mixed":
            raw_payload = (_posted(mixed_payloads, index, "") or "").strip()
            try:
                payload = json.loads(raw_payload) if raw_payload else []
            except (TypeError, ValueError, json.JSONDecodeError):
                payload = []
            total_sales = Decimal("0")
            total_purchase = Decimal("0")
            for sub_index, row in enumerate(payload if isinstance(payload, list) else []):
                if not isinstance(row, dict):
                    continue
                sub_description = str(row.get("description") or "").strip()
                if not sub_description:
                    continue
                sub_type = str(row.get("item_type") or "material")
                if sub_type not in {"material", "labour", "other"}:
                    sub_type = "material"
                sub_quantity = _money(row.get("quantity") or 1)
                sub_purchase = max(Decimal("0"), _money(row.get("purchase_price") or 0))
                sub_sales = max(Decimal("0"), _money(row.get("sales_price") or 0))
                sub_kwargs = {
                    "organization": document.organization,
                    "item_type": sub_type,
                    "description": sub_description[:300],
                    "quantity": sub_quantity,
                    "unit": str(row.get("unit") or "Stk.")[:30],
                    "purchase_price": sub_purchase,
                    "sales_price": sub_sales,
                    "sort_order": sub_index,
                }
                sub_kwargs["quote_item" if kind == "quote" else "invoice_item"] = item
                m.ToolTimeMixedSubitem.objects.create(**sub_kwargs)
                total_sales += sub_quantity * sub_sales
                total_purchase += sub_quantity * sub_purchase
            if payload:
                item.unit_price = max(Decimal("0"), total_sales).quantize(Decimal("0.01"))
                item.save(update_fields=["unit_price"])
                item_meta.purchase_price = max(Decimal("0"), total_purchase).quantize(Decimal("0.01"))
                item_meta.markup_percent = (((item.unit_price / item_meta.purchase_price) - Decimal("1")) * Decimal("100")) if item_meta.purchase_price > 0 else Decimal("0")
                item_meta.save(update_fields=["purchase_price", "markup_percent", "updated_at"])
'''
    if create_new not in text:
        if create_anchor not in text:
            raise RuntimeError("Phase 3 CommercialItemMeta create anchor missing")
        text = text.replace(create_anchor, create_new, 1)

    editor_anchor = '        item.ui_catalog_id = item.catalog_item_id or ""\n'
    editor_new = editor_anchor + r'''        item.ui_show_subitems = getattr(meta, "show_subitems_in_pdf", True) if meta else True
        item.ui_mixed_subitems = list(item.tooltime_mixed_subitems.all().order_by("sort_order", "id"))
        item.ui_subitems_json = json.dumps([
            {"item_type": row.item_type, "description": row.description, "quantity": str(row.quantity), "unit": row.unit, "purchase_price": str(row.purchase_price), "sales_price": str(row.sales_price)}
            for row in item.ui_mixed_subitems
        ], ensure_ascii=False)
'''
    if editor_new not in text:
        if editor_anchor not in text:
            raise RuntimeError("Phase 3 item editor context anchor missing")
        text = text.replace(editor_anchor, editor_new, 1)

    write(rel, text)


def patch_template_context() -> None:
    rel = "erp/templatetags/tooltime_parity.py"
    text = read(rel)
    customer_anchor = '    customers = list(m.Customer.objects.filter(organization=org, active=True).order_by("company", "last_name", "first_name")[:300])\n'
    projects_line = '    projects = list(m.Project.objects.filter(organization=org, archived=False).select_related("customer").order_by("-updated_at")[:300])\n'
    if projects_line not in text:
        if customer_anchor not in text:
            raise RuntimeError("Phase 3 template customer context anchor missing")
        text = text.replace(customer_anchor, customer_anchor + projects_line, 1)
    old_return = '    return {"cfg": commercial.settings, "meta": meta, "templates": templates, "customers": customers, "dunning": dunning}\n'
    new_return = '    return {"cfg": commercial.settings, "meta": meta, "templates": templates, "customers": customers, "projects": projects, "dunning": dunning}\n'
    if new_return not in text:
        if old_return not in text:
            raise RuntimeError("Phase 3 template context return anchor missing")
        text = text.replace(old_return, new_return, 1)
    write(rel, text)


def patch_views_and_urls() -> None:
    rel = "erp/tooltime_parity_views.py"
    text = read(rel)

    helper_anchor = '@login_required\n@require_http_methods(["GET", "POST"])\ndef quote_editor(request, pk=None):\n'
    helpers = r'''def _phase3_prepare_direct_customer(request, org):
    if request.method != "POST":
        return None
    data = request.POST.copy()
    project_id = (data.get("project") or "").strip()
    customer_id = (data.get("customer_id") or "").strip()
    if project_id.isdigit():
        project = m.Project.objects.filter(organization=org, pk=int(project_id)).select_related("customer").first()
        if project:
            data["customer_id"] = str(project.customer_id)
            request.POST = data
        return None
    if not customer_id.isdigit():
        request.POST = data
        return None
    customer = m.Customer.objects.filter(organization=org, active=True, pk=int(customer_id)).first()
    if customer is None:
        request.POST = data
        return None
    title = f"Direktdokumente · Kunde {customer.pk}"
    project = m.Project.objects.filter(organization=org, customer=customer, title=title).order_by("id").first()
    if project is None:
        project = m.Project.objects.create(
            organization=org,
            customer=customer,
            number=base._unique_number(m.Project, org, "P"),
            title=title,
            status="inquiry",
            archived=False,
        )
    elif project.archived:
        project.archived = False
        project.save(update_fields=["archived", "updated_at"])
    data["project"] = str(project.pk)
    data["customer_id"] = str(customer.pk)
    request.POST = data
    return project


def _phase3_rearchive_direct_project(project):
    if project is not None and not project.archived:
        project.archived = True
        project.save(update_fields=["archived", "updated_at"])


'''
    if "def _phase3_prepare_direct_customer" not in text:
        if helper_anchor not in text:
            raise RuntimeError("Phase 3 quote editor function anchor missing")
        text = text.replace(helper_anchor, helpers + helper_anchor, 1)

    quote_start = 'def quote_editor(request, pk=None):\n    org = _org(request)\n'
    quote_new = 'def quote_editor(request, pk=None):\n    org = _org(request)\n    direct_project = _phase3_prepare_direct_customer(request, org)\n'
    if quote_new not in text:
        if quote_start not in text:
            raise RuntimeError("Phase 3 quote editor start anchor missing")
        text = text.replace(quote_start, quote_new, 1)
    quote_response = '    response = base.quote_editor(request, pk)\n'
    quote_response_new = '    response = base.quote_editor(request, pk)\n    _phase3_rearchive_direct_project(direct_project)\n'
    if quote_response_new not in text:
        if quote_response not in text:
            raise RuntimeError("Phase 3 quote base response anchor missing")
        text = text.replace(quote_response, quote_response_new, 1)

    invoice_start = 'def invoice_editor(request, pk=None):\n    org = _org(request)\n'
    invoice_new = 'def invoice_editor(request, pk=None):\n    org = _org(request)\n    direct_project = _phase3_prepare_direct_customer(request, org)\n'
    if invoice_new not in text:
        if invoice_start not in text:
            raise RuntimeError("Phase 3 invoice editor start anchor missing")
        text = text.replace(invoice_start, invoice_new, 1)
    invoice_response = '    response = base.invoice_editor(request, pk)\n'
    invoice_response_new = '    response = base.invoice_editor(request, pk)\n    _phase3_rearchive_direct_project(direct_project)\n'
    if invoice_response_new not in text:
        if invoice_response not in text:
            raise RuntimeError("Phase 3 invoice base response anchor missing")
        text = text.replace(invoice_response, invoice_response_new, 1)

    insertion_anchor = '\n\n@login_required\n@require_http_methods(["GET", "POST"])\ndef invoice_editor(request, pk=None):\n'
    quote_actions = r'''

@login_required
@require_POST
def quote_status(request, pk):
    org = _org(request)
    quote = get_object_or_404(m.Quote, pk=pk, organization=org)
    meta = meta_for(quote, "quote")
    action = (request.POST.get("action") or "").strip()
    if meta.finalized_at is None:
        finalize_quote(quote)
        meta = meta_for(quote, "quote")
    if action == "accepted":
        quote.status = "accepted"
        meta.accepted_at = meta.accepted_at or timezone.now()
        meta.rejected_at = None
        meta.save(update_fields=["accepted_at", "rejected_at", "updated_at"])
        quote.save(update_fields=["status", "updated_at"])
        messages.success(request, "Angebot wurde als angenommen markiert.")
    elif action == "rejected":
        quote.status = "rejected"
        meta.rejected_at = timezone.now()
        meta.save(update_fields=["rejected_at", "updated_at"])
        quote.save(update_fields=["status", "updated_at"])
        messages.success(request, "Angebot wurde als abgelehnt markiert.")
    elif action == "pending":
        if meta.accepted_at:
            messages.error(request, "Ein bereits angenommenes Angebot bleibt aus Aufbewahrungsgründen gesperrt. Erstelle bei Änderungen ein neues Angebot.")
        else:
            quote.status = "sent"
            meta.rejected_at = None
            meta.save(update_fields=["rejected_at", "updated_at"])
            quote.save(update_fields=["status", "updated_at"])
            messages.success(request, "Angebotsstatus wurde auf ausstehend zurückgesetzt.")
    return redirect("next-quote-edit", pk=quote.pk)


@login_required
@require_POST
def quote_to_invoice(request, pk):
    org = _org(request)
    quote = get_object_or_404(m.Quote.objects.prefetch_related("items", "items__tooltime_mixed_subitems"), pk=pk, organization=org)
    quote_meta = meta_for(quote, "quote")
    if quote_meta.finalized_at is None:
        quote_meta = finalize_quote(quote)
    today = timezone.localdate()
    try:
        quote_settings = quote.commercial_settings
        due_days = int(quote_settings.payment_due_days or 0)
    except Exception:
        quote_settings = None
        due_days = int(phase2_settings(org).get("payment_terms", {}).get("days") or 0)
    invoice = m.Invoice.objects.create(
        organization=org,
        project=quote.project,
        quote=quote,
        number="",
        status="draft",
        issue_date=today,
        due_date=today + timedelta(days=max(0, due_days)),
        service_date=today,
        intro_text=quote.intro_text,
        outro_text=quote.outro_text,
        notes=quote.notes,
        created_by=request.user,
    )
    invoice_meta = meta_for(invoice, "invoice")
    invoice_meta.customer = quote_meta.customer or getattr(quote.project, "customer", None)
    invoice_meta.document_title = "Rechnung"
    invoice_meta.labour_cost_share_visible = quote_meta.labour_cost_share_visible
    invoice_meta.save(update_fields=["customer", "document_title", "labour_cost_share_visible", "updated_at"])
    if quote_settings is not None:
        m.CommercialDocumentSettings.objects.create(
            organization=org,
            invoice=invoice,
            tax_code=quote_settings.tax_code,
            tax_rate=quote_settings.tax_rate,
            discount_type=quote_settings.discount_type,
            discount_value=quote_settings.discount_value,
            payment_due_days=quote_settings.payment_due_days,
            early_payment_discount_percent=quote_settings.early_payment_discount_percent,
            early_payment_discount_days=quote_settings.early_payment_discount_days,
            closing_text=quote_settings.closing_text,
        )
    for source in quote.items.select_related("catalog_item").order_by("position", "pk"):
        target = m.InvoiceItem.objects.create(
            invoice=invoice,
            position=source.position,
            description=source.description,
            quantity=source.quantity,
            unit=source.unit,
            unit_price=source.unit_price,
            tax_rate=source.tax_rate,
            catalog_item=source.catalog_item,
        )
        try:
            source_meta = source.commercial_meta
        except Exception:
            source_meta = None
        if source_meta is not None:
            m.CommercialItemMeta.objects.create(
                organization=org,
                invoice_item=target,
                position_type=source_meta.position_type,
                purchase_price=source_meta.purchase_price,
                markup_percent=source_meta.markup_percent,
                service_model=source_meta.service_model,
                detail_text=source_meta.detail_text,
                group_title=source_meta.group_title,
                show_subitems_in_pdf=source_meta.show_subitems_in_pdf,
            )
        for sub in source.tooltime_mixed_subitems.all().order_by("sort_order", "id"):
            m.ToolTimeMixedSubitem.objects.create(
                organization=org,
                invoice_item=target,
                item_type=sub.item_type,
                description=sub.description,
                quantity=sub.quantity,
                unit=sub.unit,
                purchase_price=sub.purchase_price,
                sales_price=sub.sales_price,
                sort_order=sub.sort_order,
            )
    links = list(quote_meta.billing_links or [])
    token = {"kind": "invoice", "id": invoice.pk}
    if token not in links:
        links.append(token)
        quote_meta.billing_links = links
        quote_meta.save(update_fields=["billing_links", "updated_at"])
    messages.success(request, "Rechnungsentwurf wurde aus dem Angebot übernommen. Positionen, Gruppen, Kalkulation und Mischpositionen wurden kopiert.")
    return redirect("next-invoice-edit", pk=invoice.pk)
'''
    if "def quote_to_invoice(request, pk):" not in text:
        if insertion_anchor not in text:
            raise RuntimeError("Phase 3 invoice insertion anchor missing")
        text = text.replace(insertion_anchor, quote_actions + insertion_anchor, 1)
    write(rel, text)

    rel = "erp/rebuild_urls.py"
    text = read(rel)
    if "from . import tooltime_parity_views as tooltime_parity" not in text:
        text = text.replace("from . import rebuild_views as views\n", "from . import rebuild_views as views\nfrom . import tooltime_parity_views as tooltime_parity\n", 1)
    route_anchor = '    path("quotes/<int:pk>/", tooltime_parity.quote_editor, name="next-quote-edit"),\n'
    if route_anchor not in text:
        fallback = '    path("quotes/<int:pk>/", views.quote_editor, name="next-quote-edit"),\n'
        if fallback in text:
            text = text.replace(fallback, route_anchor, 1)
        else:
            raise RuntimeError("Phase 3 quote URL anchor missing")
    routes = '    path("quotes/<int:pk>/status/", tooltime_parity.quote_status, name="next-quote-status"),\n    path("quotes/<int:pk>/rechnung/", tooltime_parity.quote_to_invoice, name="next-quote-to-invoice"),\n'
    if "next-quote-to-invoice" not in text:
        text = text.replace(route_anchor, route_anchor + routes, 1)
    write(rel, text)


def patch_editor_template() -> None:
    rel = "templates/rebuild/document_editor.html"
    text = read(rel)
    phase3_script = '<script src="{% static \'js/tooltime-parity-phase3.js\' %}?v=20260820-1" defer></script>'
    if phase3_script not in text:
        anchor = '<script src="{% static \'js/tooltime-parity-finance.js\' %}?v=20260820-1" defer></script>'
        if anchor not in text:
            raise RuntimeError("Phase 3 finance JS anchor missing")
        text = text.replace(anchor, anchor + "\n" + phase3_script, 1)

    top = r'''<section class="tt-card tt-document-top"><h2>Kunde und Projekt</h2>
<div class="tt-two"><label>Kunde auswählen<select class="nx-control" name="customer_id" data-customer-preview data-customer-select><option value="">Kunde auswählen</option>{% for c in tt.customers %}<option value="{{ c.pk }}" data-address="{{ c.street|default:'' }}, {{ c.postal_code|default:'' }} {{ c.city|default:'' }}" {% if tt.meta and tt.meta.customer_id == c.pk %}selected{% elif document and document.project and document.project.customer_id == c.pk %}selected{% endif %}>{{ c.display_name }}</option>{% endfor %}</select></label>
<label>Projekt auswählen<select class="nx-control" name="project" data-project-select><option value="">Kein Projekt · nur Kunde</option>{% for p in tt.projects %}<option value="{{ p.pk }}" data-customer-id="{{ p.customer_id }}" {% if document and document.project_id == p.pk %}selected{% endif %}>{{ p.number }} · {{ p.title }} · {{ p.customer.display_name }}</option>{% endfor %}</select></label></div>
<div class="tt-address-preview" data-address-preview>{% if tt.meta and tt.meta.customer %}<strong>Adresse</strong><span>{{ tt.meta.customer.street }} · {{ tt.meta.customer.postal_code }} {{ tt.meta.customer.city }}</span>{% elif document and document.project %}<strong>Adresse</strong><span>{{ document.project.customer.street }} · {{ document.project.customer.postal_code }} {{ document.project.customer.city }}</span>{% else %}<span>Kunde auswählen. Ein Projekt ist optional.</span>{% endif %}</div>
<div class="tt-inline-help"><a class="tt-link" href="{% url 'next-customer-create' %}" target="_blank" rel="noopener">＋ Neuen Kunden anlegen</a><span>Dokumente ohne Projekt werden intern sauber dem Kunden zugeordnet und erscheinen nicht als normales Projekt.</span></div></section>'''
    text, count = re.subn(r'<section class="tt-card tt-document-top">.*?</section>', lambda _m: top, text, count=1, flags=re.S)
    if count != 1:
        raise RuntimeError("Phase 3 customer/project template block missing")

    menu = '<button type="button" class="tt-menu" data-group-menu>•••</button><div class="tt-group-menu-panel" data-group-menu-panel hidden><button type="button" data-group-action="duplicate">Gruppe duplizieren</button><button type="button" data-group-action="margin">Marge für Gruppe setzen</button><button type="button" data-group-action="delete">Gruppe löschen</button></div>'
    if 'data-group-action="duplicate"' not in text:
        text = text.replace('<button type="button" class="tt-menu" data-group-menu>•••</button>', menu)
    text = text.replace('<input class="tt-group-title" value=', '<input class="tt-group-title" name="group_title" value=')

    toolbar = r'''
{% if kind == 'quote' and document and tt.meta and tt.meta.finalized_at %}
<div class="tt-card tt-quote-statusbar"><div><strong>Status</strong><span>{{ document.get_status_display }} · {{ document.number }}</span></div><div class="tt-head-actions">
  {% if document.status != 'accepted' %}<form method="post" action="{% url 'next-quote-status' document.pk %}">{% csrf_token %}<button class="nx-btn" name="action" value="accepted">Als angenommen markieren</button></form>{% endif %}
  {% if document.status != 'rejected' and document.status != 'accepted' %}<form method="post" action="{% url 'next-quote-status' document.pk %}">{% csrf_token %}<button class="nx-btn" name="action" value="rejected">Als abgelehnt markieren</button></form>{% endif %}
  {% if document.status == 'rejected' %}<form method="post" action="{% url 'next-quote-status' document.pk %}">{% csrf_token %}<button class="nx-btn" name="action" value="pending">Status zurücksetzen</button></form>{% endif %}
  <form method="post" action="{% url 'next-quote-to-invoice' document.pk %}">{% csrf_token %}<button class="nx-btn nx-btn-accent" type="submit">In Rechnung übernehmen</button></form>
</div></div>
{% endif %}
'''
    if "tt-quote-statusbar" not in text:
        anchor = '</form>\n<div class="tt-modal" data-article-modal'
        if anchor not in text:
            raise RuntimeError("Phase 3 main document form closing anchor missing")
        text = text.replace(anchor, '</form>\n' + toolbar + '<div class="tt-modal" data-article-modal', 1)
    write(rel, text)

    write("templates/rebuild/_tooltime_position.html", r'''<div class="tt-position" data-position draggable="true">
<span class="tt-position-grip">⠿</span><span class="tt-position-number" data-position-number>1.1</span>
<select class="nx-control" name="item_type" data-item-type><option value="material" {% if item.ui_type == 'material' %}selected{% endif %}>Material</option><option value="labour" {% if item.ui_type == 'labour' %}selected{% endif %}>Lohn</option><option value="mixed" {% if item.ui_type == 'mixed' %}selected{% endif %}>Mischposition</option><option value="other" {% if item.ui_type == 'other' %}selected{% endif %}>Sonstiges</option></select>
<input class="nx-control tt-qty" name="item_quantity" type="number" step="0.001" value="{{ item.quantity|default:1 }}" title="Negative Menge = Rabattposition; der Einzelpreis bleibt positiv.">
<input class="nx-control tt-unit" name="item_unit" value="{{ item.unit|default:'Stk.' }}">
<div class="tt-description">
  <input type="hidden" name="item_catalog_id" value="{{ item.ui_catalog_id|default:'' }}"><input type="hidden" name="item_group" value="{{ item.ui_group|default:'' }}" data-group-hidden><input type="hidden" name="item_price" value="{{ item.unit_price|default:0 }}" data-hidden-sales-price>
  <input class="nx-control" name="item_description" value="{{ item.description|default:'' }}" placeholder="Bezeichnung" autocomplete="off" data-position-search><button type="button" class="tt-browse" data-browse-articles>Artikel durchsuchen</button>
  <textarea class="nx-control" name="item_detail" rows="2" placeholder="Beschreibung">{{ item.ui_detail|default:'' }}</textarea>
  <div class="tt-mixed-editor" data-mixed-editor {% if item.ui_type != 'mixed' %}hidden{% endif %}>
    <input type="hidden" name="item_subitems_json" value="{{ item.ui_subitems_json|default:'[]'|escape }}" data-subitems-json>
    <input type="hidden" name="item_show_subitems" value="{% if item.ui_show_subitems == False %}0{% else %}1{% endif %}" data-show-subitems-hidden>
    <div class="tt-mixed-head"><strong>Unterpositionen</strong><label class="tt-check"><input type="checkbox" data-show-subitems {% if item.ui_show_subitems != False %}checked{% endif %}> Unterpositionen im PDF anzeigen</label></div>
    <div data-subitem-list>{% for sub in item.ui_mixed_subitems %}<div class="tt-subitem" data-subitem><select class="nx-control" data-sub-type><option value="material" {% if sub.item_type == 'material' %}selected{% endif %}>Material</option><option value="labour" {% if sub.item_type == 'labour' %}selected{% endif %}>Lohn</option><option value="other" {% if sub.item_type == 'other' %}selected{% endif %}>Sonstiges</option></select><input class="nx-control" data-sub-description value="{{ sub.description }}" placeholder="Unterposition"><input class="nx-control" data-sub-qty type="number" step="0.001" value="{{ sub.quantity }}"><input class="nx-control" data-sub-unit value="{{ sub.unit }}"><input class="nx-control" data-sub-purchase type="number" min="0" step="0.01" value="{{ sub.purchase_price }}" placeholder="EK"><input class="nx-control" data-sub-sales type="number" min="0" step="0.01" value="{{ sub.sales_price }}" placeholder="VK"><button type="button" class="tt-delete-position" data-remove-subitem>×</button></div>{% endfor %}</div>
    <button type="button" class="tt-add-position" data-add-subitem>＋ Unterposition hinzufügen</button>
  </div>
  <div class="tt-position-extra"><label class="tt-check"><input type="checkbox" name="item_add_catalog" value="1"> Zum Katalog hinzufügen</label><label class="tt-upload">Bild hinzufügen<input type="file" name="item_image" accept="image/png,image/jpeg,image/webp"></label></div>
</div>
<input class="nx-control tt-money" name="item_purchase_price" type="number" min="0" step="0.01" value="{{ item.ui_purchase_price|default:0 }}" title="Einkaufspreis">
<div class="tt-percent"><input class="nx-control" name="item_markup_percent" type="number" step="0.01" value="{{ item.ui_markup_percent|default:0 }}"><span>%</span></div>
<output data-markup-value>0,00 €</output>
<label class="tt-sales-field"><span>VK</span><input class="nx-control tt-money" name="item_sales_price" type="number" min="0" step="0.01" value="{{ item.unit_price|default:0 }}" data-sales-price></label>
<output data-unit-price>{{ item.unit_price|default:0 }}</output><output data-line-total>0,00 €</output>
<select class="nx-control tt-service-model" name="item_service_model"><option value="normal" {% if item.ui_service_model == 'normal' %}selected{% endif %}>Normalleistung</option><option value="alternative" {% if item.ui_service_model == 'alternative' %}selected{% endif %}>Alternativposition</option><option value="contingent" {% if item.ui_service_model == 'contingent' %}selected{% endif %}>Eventualposition</option></select>
<button type="button" class="tt-delete-position" data-delete-position title="Position löschen">🗑</button>
</div>''')


def install_phase3_js_and_css() -> None:
    write("static/js/tooltime-parity-phase3.js", r'''(() => {
  const num = value => { const n = Number(String(value ?? '').replace(',', '.')); return Number.isFinite(n) ? n : 0; };
  const money = value => `${num(value).toLocaleString('de-DE', {minimumFractionDigits:2, maximumFractionDigits:2})} €`;
  const rowHtml = () => `<div class="tt-subitem" data-subitem><select class="nx-control" data-sub-type><option value="material">Material</option><option value="labour">Lohn</option><option value="other">Sonstiges</option></select><input class="nx-control" data-sub-description placeholder="Unterposition"><input class="nx-control" data-sub-qty type="number" step="0.001" value="1"><input class="nx-control" data-sub-unit value="Stk."><input class="nx-control" data-sub-purchase type="number" min="0" step="0.01" value="0" placeholder="EK"><input class="nx-control" data-sub-sales type="number" min="0" step="0.01" value="0" placeholder="VK"><button type="button" class="tt-delete-position" data-remove-subitem>×</button></div>`;

  function syncGroup(group) {
    const title = group.querySelector('.tt-group-title')?.value || 'Leistungsgruppe';
    group.querySelectorAll('[data-group-hidden]').forEach(input => input.value = title);
  }

  function syncMixed(position) {
    const editor = position.querySelector('[data-mixed-editor]');
    if (!editor) return;
    const mixed = position.querySelector('[data-item-type]')?.value === 'mixed';
    editor.hidden = !mixed;
    const rows = [...editor.querySelectorAll('[data-subitem]')].map((row, index) => ({
      item_type: row.querySelector('[data-sub-type]')?.value || 'material',
      description: row.querySelector('[data-sub-description]')?.value || '',
      quantity: row.querySelector('[data-sub-qty]')?.value || '0',
      unit: row.querySelector('[data-sub-unit]')?.value || 'Stk.',
      purchase_price: row.querySelector('[data-sub-purchase]')?.value || '0',
      sales_price: row.querySelector('[data-sub-sales]')?.value || '0',
      sort_order: index,
    }));
    const json = editor.querySelector('[data-subitems-json]'); if (json) json.value = JSON.stringify(rows);
    const show = editor.querySelector('[data-show-subitems]');
    const hidden = editor.querySelector('[data-show-subitems-hidden]'); if (hidden) hidden.value = show?.checked === false ? '0' : '1';
    if (mixed && rows.length) {
      const sale = rows.reduce((sum, row) => sum + num(row.quantity) * num(row.sales_price), 0);
      const purchase = rows.reduce((sum, row) => sum + num(row.quantity) * num(row.purchase_price), 0);
      const saleInput = position.querySelector('[data-sales-price]'); if (saleInput) saleInput.value = sale.toFixed(2);
      const hiddenSale = position.querySelector('[data-hidden-sales-price]'); if (hiddenSale) hiddenSale.value = sale.toFixed(2);
      const purchaseInput = position.querySelector('[name="item_purchase_price"]'); if (purchaseInput) purchaseInput.value = purchase.toFixed(2);
      const markup = position.querySelector('[name="item_markup_percent"]'); if (markup) markup.value = purchase > 0 ? (((sale / purchase) - 1) * 100).toFixed(2) : '0';
      const output = position.querySelector('[data-unit-price]'); if (output) output.textContent = money(sale);
    }
  }

  document.addEventListener('change', event => {
    const project = event.target.closest('[data-project-select]');
    if (project) {
      const customerId = project.selectedOptions[0]?.dataset.customerId || '';
      const customer = document.querySelector('[data-customer-select]');
      if (customerId && customer) { customer.value = customerId; customer.dispatchEvent(new Event('change', {bubbles:true})); }
    }
    const customer = event.target.closest('[data-customer-select]');
    if (customer) {
      const projectSelect = document.querySelector('[data-project-select]');
      const selected = projectSelect?.selectedOptions[0];
      if (selected?.value && selected.dataset.customerId !== customer.value) projectSelect.value = '';
    }
    const type = event.target.closest('[data-item-type]'); if (type) syncMixed(type.closest('[data-position]'));
    if (event.target.matches('[data-show-subitems]')) syncMixed(event.target.closest('[data-position]'));
  });

  document.addEventListener('input', event => {
    const sales = event.target.closest('[data-sales-price]');
    if (sales) {
      const position = sales.closest('[data-position]');
      const hidden = position?.querySelector('[data-hidden-sales-price]'); if (hidden) hidden.value = num(sales.value).toFixed(2);
      const output = position?.querySelector('[data-unit-price]'); if (output) output.textContent = money(sales.value);
    }
    if (event.target.closest('[data-subitem]')) syncMixed(event.target.closest('[data-position]'));
  });

  document.addEventListener('click', event => {
    const menu = event.target.closest('[data-group-menu]');
    if (menu) { const panel = menu.parentElement.querySelector('[data-group-menu-panel]'); if (panel) panel.hidden = !panel.hidden; return; }
    const action = event.target.closest('[data-group-action]');
    if (action) {
      const group = action.closest('[data-service-group]'); if (!group) return;
      if (action.dataset.groupAction === 'delete') {
        if (confirm('Leistungsgruppe inklusive Positionen löschen?')) group.remove();
      } else if (action.dataset.groupAction === 'duplicate') {
        const clone = group.cloneNode(true);
        clone.querySelectorAll('input[type=file]').forEach(input => input.value = '');
        const title = clone.querySelector('.tt-group-title'); if (title) title.value = `${title.value || 'Leistungsgruppe'} – Kopie`;
        group.after(clone); syncGroup(clone); clone.querySelectorAll('[data-position]').forEach(syncMixed);
      } else if (action.dataset.groupAction === 'margin') {
        const value = prompt('Aufschlag für alle Positionen dieser Gruppe in %:', '20');
        if (value !== null && Number.isFinite(num(value))) group.querySelectorAll('[name="item_markup_percent"]').forEach(input => { input.value = num(value); input.dispatchEvent(new Event('input', {bubbles:true})); });
      }
      const panel = group.querySelector('[data-group-menu-panel]'); if (panel) panel.hidden = true;
      return;
    }
    const add = event.target.closest('[data-add-subitem]');
    if (add) { const list = add.closest('[data-mixed-editor]')?.querySelector('[data-subitem-list]'); if (list) { list.insertAdjacentHTML('beforeend', rowHtml()); syncMixed(add.closest('[data-position]')); } return; }
    const remove = event.target.closest('[data-remove-subitem]');
    if (remove) { const position = remove.closest('[data-position]'); remove.closest('[data-subitem]')?.remove(); if (position) syncMixed(position); }
  });

  document.addEventListener('submit', event => {
    const form = event.target.closest('.tt-document-form'); if (!form) return;
    form.querySelectorAll('[data-service-group]').forEach(syncGroup);
    form.querySelectorAll('[data-position]').forEach(syncMixed);
  });

  window.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('[data-service-group]').forEach(syncGroup);
    document.querySelectorAll('[data-position]').forEach(syncMixed);
  });
})();
''')

    rel = "static/css/tooltime-parity-finance.css"
    text = read(rel)
    if MARKER not in text:
        text += r'''

/* A+BAU TOOLTIME PHASE 3 EDITOR 2026-08-20 */
.tt-inline-help{display:flex;gap:14px;align-items:center;flex-wrap:wrap;margin-top:10px;color:#667085;font-size:12px}.tt-group-menu-panel{position:absolute;right:12px;top:48px;z-index:30;min-width:210px;background:#fff;border:1px solid #e4e7ec;border-radius:12px;box-shadow:0 14px 36px rgba(16,24,40,.14);padding:6px}.tt-group-menu-panel button{display:block;width:100%;border:0;background:transparent;text-align:left;padding:9px 10px;border-radius:8px;cursor:pointer}.tt-group-menu-panel button:hover{background:#f2f4f7}.tt-service-group>header{position:relative}.tt-mixed-editor{grid-column:1/-1;margin-top:10px;padding:12px;border:1px solid #dfe4ea;border-radius:12px;background:#fafbfc}.tt-mixed-head{display:flex;justify-content:space-between;gap:10px;align-items:center;margin-bottom:8px}.tt-subitem{display:grid;grid-template-columns:110px minmax(180px,1fr) 80px 70px 100px 100px 38px;gap:6px;align-items:center;margin:6px 0}.tt-sales-field{display:grid;gap:2px;font-size:10px;color:#667085}.tt-sales-field input{min-width:100px}.tt-quote-statusbar{display:flex;justify-content:space-between;align-items:center;gap:16px;margin-top:12px}.tt-quote-statusbar>div:first-child{display:grid;gap:4px}.tt-quote-statusbar form{margin:0}@media(max-width:900px){.tt-subitem{grid-template-columns:1fr 1fr}.tt-quote-statusbar{align-items:flex-start;flex-direction:column}}
'''
        write(rel, text)


def install_contract_tests() -> None:
    write("tests/test_tooltime_phase3_editor_contract.py", r'''from pathlib import Path
from django.test import SimpleTestCase

ROOT = Path(__file__).resolve().parents[1]


class ToolTimePhase3EditorContractTests(SimpleTestCase):
    def test_phase3_models_and_migration_are_installed(self):
        finance = (ROOT / "erp/tooltime_parity_finance.py").read_text(encoding="utf-8")
        commercial = (ROOT / "erp/ab_bau_commercial.py").read_text(encoding="utf-8")
        migration = (ROOT / "erp/migrations/0016_tooltime_phase3_editor.py").read_text(encoding="utf-8")
        self.assertIn("customer = models.ForeignKey", finance)
        self.assertIn("class ToolTimeMixedSubitem", finance)
        self.assertIn("show_subitems_in_pdf", commercial)
        self.assertIn("ToolTimeMixedSubitem", migration)

    def test_editor_has_real_customer_project_and_mixed_position_controls(self):
        editor = (ROOT / "templates/rebuild/document_editor.html").read_text(encoding="utf-8")
        position = (ROOT / "templates/rebuild/_tooltime_position.html").read_text(encoding="utf-8")
        self.assertIn('name="customer_id"', editor)
        self.assertIn("Kein Projekt · nur Kunde", editor)
        self.assertIn('data-group-action="duplicate"', editor)
        self.assertIn("In Rechnung übernehmen", editor)
        self.assertIn('name="item_subitems_json"', position)
        self.assertIn('name="item_sales_price"', position)
        self.assertNotIn('name="item_quantity" type="number" min="0"', position)

    def test_editor_runtime_routes_and_persistence_exist(self):
        views = (ROOT / "erp/tooltime_parity_views.py").read_text(encoding="utf-8")
        service = (ROOT / "erp/services/tooltime_parity_finance.py").read_text(encoding="utf-8")
        urls = (ROOT / "erp/rebuild_urls.py").read_text(encoding="utf-8")
        rebuild = (ROOT / "erp/rebuild_views.py").read_text(encoding="utf-8")
        self.assertIn("def _phase3_prepare_direct_customer", views)
        self.assertIn("def quote_status", views)
        self.assertIn("def quote_to_invoice", views)
        self.assertIn("next-quote-to-invoice", urls)
        self.assertIn("meta.customer =", service)
        self.assertIn("m.ToolTimeMixedSubitem.objects.create", rebuild)
        self.assertIn("quantity = _money", rebuild)
''')


def validate() -> None:
    for rel in (
        "erp/tooltime_parity_finance.py",
        "erp/ab_bau_commercial.py",
        "erp/services/tooltime_parity_finance.py",
        "erp/rebuild_views.py",
        "erp/tooltime_parity_views.py",
        "erp/templatetags/tooltime_parity.py",
        "erp/rebuild_urls.py",
        "erp/migrations/0016_tooltime_phase3_editor.py",
        "tests/test_tooltime_phase3_editor_contract.py",
    ):
        path = ROOT / rel
        compile(path.read_text(encoding="utf-8"), str(path), "exec")
    editor = read("templates/rebuild/document_editor.html")
    position = read("templates/rebuild/_tooltime_position.html")
    for phrase in ("Kein Projekt · nur Kunde", "Gruppe duplizieren", "In Rechnung übernehmen"):
        if phrase not in editor:
            raise RuntimeError(f"Phase 3 editor contract missing: {phrase}")
    for phrase in ("Unterpositionen", 'name="item_sales_price"', 'name="item_subitems_json"'):
        if phrase not in position:
            raise RuntimeError(f"Phase 3 position contract missing: {phrase}")


def main() -> None:
    patch_models_and_migration()
    patch_service()
    patch_commercial_runtime()
    patch_template_context()
    patch_views_and_urls()
    patch_editor_template()
    install_phase3_js_and_css()
    install_contract_tests()
    validate()
    print("ToolTime Phase 3: Kunde-ohne-Projekt, Gruppenaktionen, Mischpositionen, Rabattmengen, Angebotsstatus und Angebots→Rechnung sind installiert.")


if __name__ == "__main__":
    main()
