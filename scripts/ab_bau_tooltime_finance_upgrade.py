from __future__ import annotations

import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MARKER = "A+BAU TOOLTIME COMMERCIAL + FINANCE UPGRADE 2026-08-12"
VERSION = "20260812-ab-bau-1"


def read(rel: str) -> str:
    path = ROOT / rel
    if not path.exists():
        raise RuntimeError(f"A+Bau upgrade target missing: {rel}")
    return path.read_text(encoding="utf-8")


def write(rel: str, text: str) -> None:
    path = ROOT / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def install_commercial_models() -> None:
    write("erp/ab_bau_commercial.py", '''from __future__ import annotations

from django.db import models


class CommercialDocumentSettings(models.Model):
    TAX_CHOICES = [
        ("19", "19 % Umsatzsteuer"),
        ("7", "7 % Umsatzsteuer"),
        ("0_19", "0 % gemäß § 19 UStG"),
        ("0_13b", "0 % gemäß § 13b UStG"),
        ("0_4", "0 % gemäß § 4 UStG"),
        ("0", "0 % Umsatzsteuer"),
    ]
    DISCOUNT_CHOICES = [("percent", "Prozent"), ("fixed", "Fester Betrag")]

    organization = models.ForeignKey("erp.Organization", on_delete=models.CASCADE, related_name="commercial_document_settings")
    quote = models.OneToOneField("erp.Quote", null=True, blank=True, on_delete=models.CASCADE, related_name="commercial_settings")
    invoice = models.OneToOneField("erp.Invoice", null=True, blank=True, on_delete=models.CASCADE, related_name="commercial_settings")
    tax_code = models.CharField(max_length=20, choices=TAX_CHOICES, default="19")
    tax_rate = models.DecimalField(max_digits=5, decimal_places=2, default=19)
    discount_type = models.CharField(max_length=16, choices=DISCOUNT_CHOICES, default="percent")
    discount_value = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    payment_due_days = models.PositiveIntegerField(default=14)
    early_payment_discount_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    early_payment_discount_days = models.PositiveIntegerField(default=0)
    closing_text = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]


class CommercialItemMeta(models.Model):
    TYPE_CHOICES = [
        ("material", "Material"),
        ("labour", "Arbeitsleistung"),
        ("mixed", "Gemischte Leistung"),
        ("other", "Sonstiges"),
    ]
    SERVICE_CHOICES = [
        ("normal", "Normalleistung"),
        ("alternative", "Alternativposition"),
        ("contingent", "Eventualposition"),
    ]

    organization = models.ForeignKey("erp.Organization", on_delete=models.CASCADE, related_name="commercial_item_meta")
    quote_item = models.OneToOneField("erp.QuoteItem", null=True, blank=True, on_delete=models.CASCADE, related_name="commercial_meta")
    invoice_item = models.OneToOneField("erp.InvoiceItem", null=True, blank=True, on_delete=models.CASCADE, related_name="commercial_meta")
    position_type = models.CharField(max_length=16, choices=TYPE_CHOICES, default="material")
    purchase_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    markup_percent = models.DecimalField(max_digits=7, decimal_places=2, default=0)
    service_model = models.CharField(max_length=16, choices=SERVICE_CHOICES, default="normal")
    detail_text = models.TextField(blank=True)
    group_title = models.CharField(max_length=220, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["id"]
''')

    models_rel = "erp/models.py"
    models_text = read(models_rel)
    import_line = "from .ab_bau_commercial import CommercialDocumentSettings, CommercialItemMeta"
    if import_line not in models_text:
        models_text = models_text.rstrip() + "\n\n# A+Bau commercial extension; kept separate to avoid rewriting the stable ERP schema.\n" + import_line + "\n"
        write(models_rel, models_text)

    migration = '''from django.db import migrations, models
import django.db.models.deletion


def rename_brand(apps, schema_editor):
    Organization = apps.get_model("erp", "Organization")
    Organization.objects.filter(name__iexact="KAYI Haustechnik").update(name="A+Bau")


class Migration(migrations.Migration):
    dependencies = [("erp", "0008_rename_erp_nativ_organiz_1f223e_idx_erp_nativer_organiz_1823cd_idx_and_more")]
    operations = [
        migrations.CreateModel(
            name="CommercialDocumentSettings",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("tax_code", models.CharField(choices=[("19", "19 % Umsatzsteuer"), ("7", "7 % Umsatzsteuer"), ("0_19", "0 % gemäß § 19 UStG"), ("0_13b", "0 % gemäß § 13b UStG"), ("0_4", "0 % gemäß § 4 UStG"), ("0", "0 % Umsatzsteuer")], default="19", max_length=20)),
                ("tax_rate", models.DecimalField(decimal_places=2, default=19, max_digits=5)),
                ("discount_type", models.CharField(choices=[("percent", "Prozent"), ("fixed", "Fester Betrag")], default="percent", max_length=16)),
                ("discount_value", models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ("payment_due_days", models.PositiveIntegerField(default=14)),
                ("early_payment_discount_percent", models.DecimalField(decimal_places=2, default=0, max_digits=5)),
                ("early_payment_discount_days", models.PositiveIntegerField(default=0)),
                ("closing_text", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("invoice", models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="commercial_settings", to="erp.invoice")),
                ("organization", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="commercial_document_settings", to="erp.organization")),
                ("quote", models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="commercial_settings", to="erp.quote")),
            ],
            options={"ordering": ["-updated_at"]},
        ),
        migrations.CreateModel(
            name="CommercialItemMeta",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("position_type", models.CharField(choices=[("material", "Material"), ("labour", "Arbeitsleistung"), ("mixed", "Gemischte Leistung"), ("other", "Sonstiges")], default="material", max_length=16)),
                ("purchase_price", models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ("markup_percent", models.DecimalField(decimal_places=2, default=0, max_digits=7)),
                ("service_model", models.CharField(choices=[("normal", "Normalleistung"), ("alternative", "Alternativposition"), ("contingent", "Eventualposition")], default="normal", max_length=16)),
                ("detail_text", models.TextField(blank=True)),
                ("group_title", models.CharField(blank=True, max_length=220)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("invoice_item", models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="commercial_meta", to="erp.invoiceitem")),
                ("organization", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="commercial_item_meta", to="erp.organization")),
                ("quote_item", models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="commercial_meta", to="erp.quoteitem")),
            ],
            options={"ordering": ["id"]},
        ),
        migrations.RunPython(rename_brand, migrations.RunPython.noop),
    ]
'''
    write("erp/migrations/0009_ab_bau_commercial.py", migration)


def patch_commercial_views() -> None:
    rel = "erp/rebuild_views.py"
    text = read(rel)

    text = text.replace(
        'fields = ["project", "issue_date", "valid_until", "intro_text", "outro_text", "discount_percent", "notes"]',
        'fields = ["project", "issue_date", "valid_until", "intro_text", "notes"]',
    )
    text = text.replace(
        'fields = ["project", "quote", "issue_date", "due_date", "service_date", "intro_text", "outro_text", "notes"]',
        'fields = ["project", "quote", "issue_date", "service_date", "intro_text", "notes"]',
    )

    totals_pattern = re.compile(r"def _project_total\(project\):.*?\n\nclass StyledModelForm", re.S)
    totals_new = r'''def _commercial_settings(document):
    if document is None:
        return None
    try:
        return document.commercial_settings
    except (m.CommercialDocumentSettings.DoesNotExist, AttributeError):
        return None


def _item_commercial_meta(item):
    try:
        return item.commercial_meta
    except (m.CommercialItemMeta.DoesNotExist, AttributeError):
        return None


def _discount_amount(net, settings, legacy_percent=Decimal("0")):
    if settings is None:
        value = net * _money(legacy_percent) / Decimal("100")
        return min(net, max(Decimal("0"), value))
    value = max(Decimal("0"), _money(settings.discount_value))
    if settings.discount_type == "fixed":
        return min(net, value)
    return min(net, net * value / Decimal("100"))


def _document_totals(document, *, include_payments=False):
    if document is None:
        base = {"net": Decimal("0"), "tax": Decimal("0"), "gross": Decimal("0"), "cost": Decimal("0"), "margin": Decimal("0"), "margin_percent": Decimal("0"), "discount": Decimal("0"), "alternative": Decimal("0"), "contingent": Decimal("0")}
        if include_payments:
            base.update({"paid": Decimal("0"), "open": Decimal("0")})
        return base
    settings = _commercial_settings(document)
    normal = alternative = contingent = cost = Decimal("0")
    for item in document.items.all():
        line = _money(item.quantity) * _money(item.unit_price)
        meta = _item_commercial_meta(item)
        model = getattr(meta, "service_model", "normal") if meta else "normal"
        if model == "alternative":
            alternative += line
            continue
        if model == "contingent":
            contingent += line
            continue
        normal += line
        purchase = _money(getattr(meta, "purchase_price", 0)) if meta else Decimal("0")
        if purchase <= 0 and getattr(item, "catalog_item_id", None):
            purchase = _money(getattr(item.catalog_item, "purchase_price", 0))
        cost += _money(item.quantity) * purchase
    legacy_discount = getattr(document, "discount_percent", Decimal("0"))
    discount = _discount_amount(normal, settings, legacy_discount)
    net = max(Decimal("0"), normal - discount)
    tax_rate = _money(getattr(settings, "tax_rate", 19) if settings else 19)
    tax = net * tax_rate / Decimal("100")
    gross = net + tax
    margin = net - cost
    margin_percent = (margin / net * Decimal("100")) if net else Decimal("0")
    result = {"net": net, "tax": tax, "gross": gross, "cost": cost, "margin": margin, "margin_percent": margin_percent, "discount": discount, "alternative": alternative, "contingent": contingent}
    if include_payments:
        paid = document.payments.aggregate(total=Sum("amount"))["total"] or Decimal("0")
        result.update({"paid": paid, "open": max(Decimal("0"), gross - paid)})
    return result


def _project_total(project):
    return sum((_invoice_total(invoice)["gross"] for invoice in project.invoices.exclude(status="cancelled").prefetch_related("items", "items__catalog_item", "items__commercial_meta", "payments")), Decimal("0"))


def _quote_total(quote):
    return _document_totals(quote, include_payments=False)


def _invoice_total(invoice):
    return _document_totals(invoice, include_payments=True)


def _project_financials(project):
    invoices = list(project.invoices.exclude(status="cancelled").prefetch_related("items", "items__catalog_item", "items__commercial_meta", "payments"))
    quotes = list(project.quotes.exclude(status="rejected").prefetch_related("items", "items__catalog_item", "items__commercial_meta"))
    invoice_totals = [_invoice_total(invoice) for invoice in invoices]
    quote_totals = [_quote_total(quote) for quote in quotes]
    revenue = sum((row["net"] for row in invoice_totals), Decimal("0"))
    costs = sum((row["cost"] for row in invoice_totals), Decimal("0"))
    margin = revenue - costs
    return {
        "revenue": revenue,
        "cost": costs,
        "margin": margin,
        "margin_percent": (margin / revenue * Decimal("100")) if revenue else Decimal("0"),
        "gross": sum((row["gross"] for row in invoice_totals), Decimal("0")),
        "paid": sum((row["paid"] for row in invoice_totals), Decimal("0")),
        "open": sum((row["open"] for row in invoice_totals), Decimal("0")),
        "quote_volume": sum((row["net"] for row in quote_totals), Decimal("0")),
    }


class StyledModelForm'''
    text, count = totals_pattern.subn(totals_new, text, count=1)
    if count != 1:
        raise RuntimeError("A+Bau totals anchor changed")

    save_quote_pattern = re.compile(r"def _save_quote_items\(quote, request\):.*?\n\n@login_required\n@require_http_methods\(\[\"GET\", \"POST\"\]\)\ndef quote_editor", re.S)
    save_quote_new = r'''def _tax_from_code(code):
    return {"19": Decimal("19"), "7": Decimal("7"), "0_19": Decimal("0"), "0_13b": Decimal("0"), "0_4": Decimal("0"), "0": Decimal("0")}.get(code, Decimal("19"))


def _save_document_settings(document, request, kind):
    lookup = {"quote": document} if kind == "quote" else {"invoice": document}
    settings, _ = m.CommercialDocumentSettings.objects.get_or_create(organization=document.organization, **lookup)
    settings.tax_code = (request.POST.get("document_tax_code") or "19")[:20]
    settings.tax_rate = _tax_from_code(settings.tax_code)
    settings.discount_type = "fixed" if request.POST.get("discount_type") == "fixed" else "percent"
    settings.discount_value = max(Decimal("0"), _money(request.POST.get("discount_value")))
    settings.payment_due_days = max(0, min(365, int(_money(request.POST.get("payment_due_days") or 14))))
    settings.early_payment_discount_percent = max(Decimal("0"), min(Decimal("100"), _money(request.POST.get("early_discount_percent"))))
    settings.early_payment_discount_days = max(0, min(365, int(_money(request.POST.get("early_discount_days") or 0))))
    settings.closing_text = (request.POST.get("closing_text") or "").strip()
    settings.save()
    return settings


def _posted(values, index, default=""):
    return values[index] if index < len(values) else default


def _save_commercial_items(document, request, kind, settings):
    parent_field = "quote" if kind == "quote" else "invoice"
    model = m.QuoteItem if kind == "quote" else m.InvoiceItem
    descriptions = request.POST.getlist("item_description")
    detail_texts = request.POST.getlist("item_detail")
    quantities = request.POST.getlist("item_quantity")
    units = request.POST.getlist("item_unit")
    purchases = request.POST.getlist("item_purchase_price")
    markups = request.POST.getlist("item_markup_percent")
    item_types = request.POST.getlist("item_type")
    service_models = request.POST.getlist("item_service_model")
    catalog_ids = request.POST.getlist("item_catalog_id")
    groups = request.POST.getlist("item_group")
    document.items.all().delete()
    position = 1
    for index, raw_description in enumerate(descriptions):
        description = (raw_description or "").strip()
        if not description:
            continue
        quantity = max(Decimal("0"), _money(_posted(quantities, index, "1")))
        purchase_raw = (_posted(purchases, index, "") or "").strip()
        markup = max(Decimal("-100"), _money(_posted(markups, index, "0")))
        catalog = None
        catalog_id = (_posted(catalog_ids, index, "") or "").strip()
        if catalog_id.isdigit():
            catalog = m.CatalogItem.objects.filter(organization=document.organization, active=True, pk=int(catalog_id)).first()
        if purchase_raw:
            purchase = max(Decimal("0"), _money(purchase_raw))
        elif catalog is not None:
            purchase = max(Decimal("0"), _money(catalog.purchase_price))
            if purchase <= 0:
                purchase = max(Decimal("0"), _money(catalog.sales_price))
        else:
            purchase = Decimal("0")
        unit_price = (purchase * (Decimal("1") + markup / Decimal("100"))).quantize(Decimal("0.01"))
        if unit_price <= 0 and catalog is not None and _money(catalog.sales_price) > 0:
            unit_price = _money(catalog.sales_price).quantize(Decimal("0.01"))
            if purchase <= 0:
                purchase = unit_price
                markup = Decimal("0")
        kwargs = {
            parent_field: document,
            "position": position,
            "description": description,
            "quantity": quantity,
            "unit": (_posted(units, index, "Stk.") or "Stk.")[:30],
            "unit_price": unit_price,
            "tax_rate": settings.tax_rate,
            "catalog_item": catalog,
        }
        item = model.objects.create(**kwargs)
        detail = (_posted(detail_texts, index, "") or "").strip()
        position_type = (_posted(item_types, index, "material") or "material")
        if position_type not in {"material", "labour", "mixed", "other"}:
            position_type = "material"
        service_model = (_posted(service_models, index, "normal") or "normal")
        if service_model not in {"normal", "alternative", "contingent"}:
            service_model = "normal"
        meta_kwargs = {
            "organization": document.organization,
            "position_type": position_type,
            "purchase_price": purchase,
            "markup_percent": markup,
            "service_model": service_model,
            "detail_text": detail,
            "group_title": (_posted(groups, index, "") or "")[:220],
        }
        meta_kwargs["quote_item" if kind == "quote" else "invoice_item"] = item
        m.CommercialItemMeta.objects.create(**meta_kwargs)
        if catalog is not None and detail and not (catalog.description or "").strip():
            catalog.description = detail
            catalog.save(update_fields=["description", "updated_at"])
        position += 1


def _items_for_editor(document):
    if document is None:
        return []
    rows = list(document.items.select_related("catalog_item").order_by("position"))
    for item in rows:
        meta = _item_commercial_meta(item)
        purchase = _money(getattr(meta, "purchase_price", 0)) if meta else Decimal("0")
        if purchase <= 0 and item.catalog_item_id:
            purchase = _money(item.catalog_item.purchase_price)
        if purchase <= 0:
            purchase = _money(item.unit_price)
        item.ui_purchase_price = purchase
        item.ui_markup_percent = _money(getattr(meta, "markup_percent", 0)) if meta else Decimal("0")
        item.ui_type = getattr(meta, "position_type", "material") if meta else ("material" if item.catalog_item_id else "other")
        item.ui_service_model = getattr(meta, "service_model", "normal") if meta else "normal"
        item.ui_detail = getattr(meta, "detail_text", "") if meta else (item.catalog_item.description if item.catalog_item_id else "")
        item.ui_group = getattr(meta, "group_title", "") if meta else ""
        item.ui_catalog_id = item.catalog_item_id or ""
    return rows


@login_required
@require_http_methods(["GET", "POST"])
def quote_editor'''
    text, count = save_quote_pattern.subn(save_quote_new, text, count=1)
    if count != 1:
        raise RuntimeError("A+Bau quote item anchor changed")

    quote_editor_pattern = re.compile(r"@login_required\n@require_http_methods\(\[\"GET\", \"POST\"\]\)\ndef quote_editor\(request, pk=None\):.*?\n\n@login_required\ndef invoice_list", re.S)
    quote_editor_new = r'''@login_required
@require_http_methods(["GET", "POST"])
def quote_editor(request, pk=None):
    org = _org(request)
    quote = get_object_or_404(m.Quote, pk=pk, organization=org) if pk else None
    initial = {}
    if request.GET.get("project"):
        initial["project"] = request.GET.get("project")
    form = QuoteForm(request.POST or None, instance=quote, organization=org, initial=initial)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            obj = form.save(commit=False)
            obj.organization = org
            obj.created_by = obj.created_by or request.user
            if not obj.number:
                obj.number = _unique_number(m.Quote, org, "A")
            if request.POST.get("action") == "send":
                obj.status = "sent"
                obj.sent_at = timezone.now()
            obj.outro_text = (request.POST.get("closing_text") or "").strip()
            obj.save()
            settings = _save_document_settings(obj, request, "quote")
            obj.discount_percent = settings.discount_value if settings.discount_type == "percent" else Decimal("0")
            obj.save(update_fields=["discount_percent", "outro_text", "updated_at"])
            _save_commercial_items(obj, request, "quote", settings)
        messages.success(request, "Angebot gespeichert.")
        return redirect("next-quote-edit", pk=obj.pk)
    settings = _commercial_settings(quote)
    catalog = m.CatalogItem.objects.filter(organization=org, active=True).order_by("name")[:500]
    return render(request, "rebuild/document_editor.html", {
        "form": form, "document": quote, "items": _items_for_editor(quote), "catalog": catalog,
        "kind": "quote", "totals": _quote_total(quote) if quote else None, "commercial": settings,
    })


@login_required
def invoice_list'''
    text, count = quote_editor_pattern.subn(quote_editor_new, text, count=1)
    if count != 1:
        raise RuntimeError("A+Bau quote editor anchor changed")

    save_invoice_pattern = re.compile(r"def _save_invoice_items\(invoice, request\):.*?\n\n@login_required\n@require_http_methods\(\[\"GET\", \"POST\"\]\)\ndef invoice_editor", re.S)
    save_invoice_new = r'''def _save_invoice_items(invoice, request):
    settings = _commercial_settings(invoice)
    if settings is None:
        settings = m.CommercialDocumentSettings.objects.create(organization=invoice.organization, invoice=invoice)
    _save_commercial_items(invoice, request, "invoice", settings)


@login_required
@require_http_methods(["GET", "POST"])
def invoice_editor'''
    text, count = save_invoice_pattern.subn(save_invoice_new, text, count=1)
    if count != 1:
        raise RuntimeError("A+Bau invoice item anchor changed")

    invoice_editor_pattern = re.compile(r"@login_required\n@require_http_methods\(\[\"GET\", \"POST\"\]\)\ndef invoice_editor\(request, pk=None\):.*?\n\n@login_required\n@require_POST\ndef invoice_payment", re.S)
    invoice_editor_new = r'''@login_required
@require_http_methods(["GET", "POST"])
def invoice_editor(request, pk=None):
    org = _org(request)
    invoice = get_object_or_404(m.Invoice, pk=pk, organization=org) if pk else None
    initial = {}
    if request.GET.get("project"):
        initial["project"] = request.GET.get("project")
    if request.GET.get("quote"):
        initial["quote"] = request.GET.get("quote")
    form = InvoiceForm(request.POST or None, instance=invoice, organization=org, initial=initial)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            obj = form.save(commit=False)
            obj.organization = org
            obj.created_by = obj.created_by or request.user
            if not obj.number:
                obj.number = _unique_number(m.Invoice, org, "R")
            due_days = max(0, min(365, int(_money(request.POST.get("payment_due_days") or 14))))
            obj.due_date = obj.issue_date + timedelta(days=due_days)
            obj.outro_text = (request.POST.get("closing_text") or "").strip()
            if request.POST.get("action") == "send":
                obj.status = "sent"
                obj.sent_at = timezone.now()
            obj.save()
            settings = _save_document_settings(obj, request, "invoice")
            _save_commercial_items(obj, request, "invoice", settings)
        messages.success(request, "Rechnung gespeichert.")
        return redirect("next-invoice-edit", pk=obj.pk)
    settings = _commercial_settings(invoice)
    return render(request, "rebuild/document_editor.html", {
        "form": form, "document": invoice, "items": _items_for_editor(invoice),
        "catalog": m.CatalogItem.objects.filter(organization=org, active=True).order_by("name")[:500],
        "kind": "invoice", "totals": _invoice_total(invoice) if invoice else None, "commercial": settings,
    })


@login_required
@require_POST
def invoice_payment'''
    text, count = invoice_editor_pattern.subn(invoice_editor_new, text, count=1)
    if count != 1:
        raise RuntimeError("A+Bau invoice editor anchor changed")

    finance_marker = "def finance_dashboard(request):"
    if finance_marker not in text:
        anchor = "\n\n@login_required\ndef time_overview(request):\n"
        if anchor not in text:
            raise RuntimeError("A+Bau finance insertion anchor changed")
        finance_view = r'''

@login_required
def finance_dashboard(request):
    if _is_field_user(request):
        messages.error(request, "Die Finanzübersicht ist nur für Büro, Projektleitung und Buchhaltung verfügbar.")
        return redirect("next-dashboard")
    org = _org(request)
    invoices = m.Invoice.objects.filter(organization=org).exclude(status="cancelled").select_related("project", "project__customer").prefetch_related("items", "items__catalog_item", "items__commercial_meta", "payments")
    quotes = m.Quote.objects.filter(organization=org).exclude(status="rejected").prefetch_related("items", "items__catalog_item", "items__commercial_meta")
    date_from = (request.GET.get("date_from") or "").strip()
    date_to = (request.GET.get("date_to") or "").strip()
    project_filter = (request.GET.get("project") or "").strip()
    try:
        if date_from:
            invoices = invoices.filter(issue_date__gte=timezone.datetime.strptime(date_from, "%Y-%m-%d").date())
            quotes = quotes.filter(issue_date__gte=timezone.datetime.strptime(date_from, "%Y-%m-%d").date())
    except ValueError:
        date_from = ""
    try:
        if date_to:
            invoices = invoices.filter(issue_date__lte=timezone.datetime.strptime(date_to, "%Y-%m-%d").date())
            quotes = quotes.filter(issue_date__lte=timezone.datetime.strptime(date_to, "%Y-%m-%d").date())
    except ValueError:
        date_to = ""
    if project_filter.isdigit():
        invoices = invoices.filter(project_id=int(project_filter))
        quotes = quotes.filter(project_id=int(project_filter))
    invoice_rows = []
    revenue = cost = gross = paid = open_amount = Decimal("0")
    by_project = {}
    for invoice in invoices.order_by("-issue_date", "-created_at"):
        totals = _invoice_total(invoice)
        revenue += totals["net"]; cost += totals["cost"]; gross += totals["gross"]; paid += totals["paid"]; open_amount += totals["open"]
        invoice_rows.append({"invoice": invoice, "total": totals})
        bucket = by_project.setdefault(invoice.project_id, {"project": invoice.project, "revenue": Decimal("0"), "cost": Decimal("0"), "margin": Decimal("0"), "gross": Decimal("0"), "open": Decimal("0")})
        bucket["revenue"] += totals["net"]; bucket["cost"] += totals["cost"]; bucket["gross"] += totals["gross"]; bucket["open"] += totals["open"]
    project_rows = []
    for bucket in by_project.values():
        bucket["margin"] = bucket["revenue"] - bucket["cost"]
        bucket["margin_percent"] = (bucket["margin"] / bucket["revenue"] * Decimal("100")) if bucket["revenue"] else Decimal("0")
        project_rows.append(bucket)
    project_rows.sort(key=lambda row: row["revenue"], reverse=True)
    margin = revenue - cost
    quote_volume = sum((_quote_total(q)["net"] for q in quotes), Decimal("0"))
    projects = m.Project.objects.filter(organization=org, archived=False).order_by("-updated_at")[:300]
    return render(request, "rebuild/finance_dashboard.html", {
        "revenue": revenue, "cost": cost, "margin": margin,
        "margin_percent": (margin / revenue * Decimal("100")) if revenue else Decimal("0"),
        "gross": gross, "paid": paid, "open_amount": open_amount, "quote_volume": quote_volume,
        "invoice_rows": invoice_rows[:100], "project_rows": project_rows[:100], "projects": projects,
        "date_from": date_from, "date_to": date_to, "project_filter": project_filter,
    })
'''
        text = text.replace(anchor, finance_view + anchor, 1)

    text = text.replace('m.Organization.objects.create(name="KAYI Haustechnik")', 'm.Organization.objects.create(name="A+Bau")')
    write(rel, text)


def patch_project_finance() -> None:
    rel = "erp/rebuild_projects.py"
    text = read(rel)
    text = text.replace(
        "from .rebuild_views import _employee, _invoice_total, _is_field_user, _org",
        "from .rebuild_views import _employee, _invoice_total, _is_field_user, _org, _project_financials",
    )
    if '"finance": finance,' not in text:
        anchor = '    invoice_gross = sum((_invoice_total(invoice)["gross"] for invoice in invoices), Decimal("0"))\n'
        if anchor not in text:
            raise RuntimeError("A+Bau project finance anchor changed")
        text = text.replace(anchor, anchor + "    finance = _project_financials(project)\n", 1)
        context_anchor = '        "invoice_gross": invoice_gross,\n'
        if context_anchor not in text:
            raise RuntimeError("A+Bau project finance context anchor changed")
        text = text.replace(context_anchor, context_anchor + '        "finance": finance,\n', 1)
    write(rel, text)


def patch_urls() -> None:
    rel = "erp/rebuild_urls.py"
    text = read(rel)
    route = '    path("finanzen/", views.finance_dashboard, name="next-finance"),\n'
    if route not in text:
        anchor = '    path("invoices/<int:pk>/payment/", views.invoice_payment, name="next-invoice-payment"),\n'
        if anchor not in text:
            raise RuntimeError("A+Bau finance URL anchor changed")
        text = text.replace(anchor, anchor + route, 1)
    write(rel, text)


def document_editor_template() -> str:
    return r'''{% extends 'rebuild/base.html' %}
{% block title %}{% if kind == 'quote' %}Angebot{% else %}Rechnung{% endif %} · A+Bau{% endblock %}
{% block content %}
<div class="nx-pagehead ab-doc-head">
  <div><div class="nx-kicker">{% if kind == 'quote' %}Angebot{% else %}Rechnung{% endif %}{% if document %} · {{ document.number }}{% endif %}</div><h1>{% if document %}{{ document.number }} bearbeiten{% elif kind == 'quote' %}Neues Angebot{% else %}Neue Rechnung{% endif %}</h1><p>Kalkulation mit Einkaufspreisen, Aufschlägen und sauberer Dokumentsteuer.</p></div>
  <div class="nx-actions">{% if document %}<span class="nx-badge">{{ document.get_status_display }}</span>{% endif %}</div>
</div>
<form class="nx-form ab-document-form" method="post" data-ab-commercial-form>{% csrf_token %}
  <section class="nx-card nx-card-pad ab-document-meta">
    <div class="nx-card-head" style="padding:0 0 15px"><div><h2>Dokument</h2><p>Projekt, Datum und optionale Einleitung.</p></div></div>
    <div class="nx-form-grid">{% for field in form %}<div class="nx-field {% if field.name == 'intro_text' or field.name == 'notes' %}nx-field-full{% endif %}"><label for="{{ field.id_for_label }}">{{ field.label }}</label>{{ field }}{{ field.errors }}</div>{% endfor %}</div>
  </section>

  <section class="nx-card ab-services-card">
    <div class="nx-card-head"><div><div class="nx-kicker">Leistungen</div><h2>Positionen</h2><p>Positionen können per Drag & Drop sortiert werden. Steuer wird erst in der Gesamtsumme festgelegt.</p></div><button class="nx-btn nx-btn-primary" type="button" data-ab-add-item>＋ Position</button></div>
    <div class="nx-table-wrap ab-item-table-wrap">
      <table class="ab-item-table" data-document-items data-ab-items>
        <thead><tr><th></th><th>Nr.</th><th>Art</th><th>Menge</th><th>Einheit</th><th>Bezeichnung</th><th>Einkauf</th><th>Aufschlag</th><th>Aufschlag €</th><th>Einzelpreis</th><th>Gesamt</th><th></th></tr></thead>
        <tbody>
        {% for item in items %}
          <tr class="ab-item-row" draggable="true">
            <td class="ab-drag-cell"><button type="button" class="ab-drag" title="Position verschieben" aria-label="Position verschieben">⋮⋮</button></td>
            <td class="ab-pos">{{ forloop.counter }}</td>
            <td><select class="nx-control" name="item_type"><option value="material" {% if item.ui_type == 'material' %}selected{% endif %}>Material</option><option value="labour" {% if item.ui_type == 'labour' %}selected{% endif %}>Arbeitsleistung</option><option value="mixed" {% if item.ui_type == 'mixed' %}selected{% endif %}>Gemischte Leistung</option><option value="other" {% if item.ui_type == 'other' %}selected{% endif %}>Sonstiges</option></select></td>
            <td><input class="nx-control ab-num" name="item_quantity" type="number" min="0" step="0.001" value="{{ item.quantity|stringformat:'s' }}"></td>
            <td><select class="nx-control" name="item_unit" data-unit-select><option {% if item.unit == 'Stk.' %}selected{% endif %}>Stk.</option><option {% if item.unit == 'm' %}selected{% endif %}>m</option><option {% if item.unit == 'm²' %}selected{% endif %}>m²</option><option {% if item.unit == 'm³' %}selected{% endif %}>m³</option><option {% if item.unit == 'kg' %}selected{% endif %}>kg</option><option {% if item.unit == 't' %}selected{% endif %}>t</option><option {% if item.unit == 'l' %}selected{% endif %}>l</option><option {% if item.unit == 'Std.' %}selected{% endif %}>Std.</option><option {% if item.unit == 'Tag' %}selected{% endif %}>Tag</option><option {% if item.unit == 'Woche' %}selected{% endif %}>Woche</option><option {% if item.unit == 'Pauschal' %}selected{% endif %}>Pauschal</option><option {% if item.unit == 'Satz' %}selected{% endif %}>Satz</option><option {% if item.unit == 'Rolle' %}selected{% endif %}>Rolle</option><option {% if item.unit == 'Packung' %}selected{% endif %}>Packung</option><option {% if item.unit == 'Rohr' %}selected{% endif %}>Rohr</option></select></td>
            <td class="ab-title-cell"><input type="hidden" name="item_catalog_id" value="{{ item.ui_catalog_id }}"><input type="hidden" name="item_group" value="{{ item.ui_group }}"><input type="hidden" name="item_price" value="{{ item.unit_price|stringformat:'s' }}"><input class="nx-control" name="item_description" value="{{ item.description }}" placeholder="Bezeichnung"><textarea class="nx-control ab-detail" name="item_detail" rows="2" placeholder="Beschreibung (optional)">{{ item.ui_detail }}</textarea></td>
            <td><input class="nx-control ab-num" name="item_purchase_price" type="number" min="0" step="0.01" value="{{ item.ui_purchase_price|stringformat:'s' }}"></td>
            <td><div class="ab-suffix"><input class="nx-control ab-num" name="item_markup_percent" type="number" step="0.01" value="{{ item.ui_markup_percent|stringformat:'s' }}"><span>%</span></div></td>
            <td><output data-line-markup>0,00 €</output></td><td><output data-line-unit-price>0,00 €</output></td><td><output data-line-total>0,00 €</output></td>
            <td><button type="button" class="nx-item-remove" aria-label="Position entfernen">×</button></td>
          </tr>
          <tr class="ab-item-subrow"><td></td><td></td><td colspan="10"><label>Preismodell <select class="nx-control ab-service-model" name="item_service_model"><option value="normal" {% if item.ui_service_model == 'normal' %}selected{% endif %}>Normalleistung</option><option value="alternative" {% if item.ui_service_model == 'alternative' %}selected{% endif %}>Alternativposition</option><option value="contingent" {% if item.ui_service_model == 'contingent' %}selected{% endif %}>Eventualposition</option></select></label></td></tr>
        {% empty %}{% endfor %}
        </tbody>
      </table>
    </div>
    <div class="ab-add-bar"><button class="nx-btn" type="button" data-ab-add-item>＋ Position hinzufügen</button><span class="nx-muted">Tipp: Am Griff links ziehen, um die Reihenfolge zu ändern.</span></div>
  </section>

  <div class="ab-document-bottom">
    <section class="nx-card ab-catalog-card">
      <div class="nx-card-head"><div><h2>Katalog</h2><p>Auswahl übernimmt Einheit, Beschreibung und hinterlegten Einkaufspreis.</p></div></div>
      <div class="ab-catalog-search"><input class="nx-control" type="search" placeholder="Katalog durchsuchen …" data-ab-catalog-search></div>
      <div class="ab-catalog-list" data-ab-catalog-list>{% for item in catalog %}<button type="button" class="ab-catalog-item" data-ab-catalog data-name="{{ item.name|escape }}" data-description="{{ item.description|escape }}" data-unit="{{ item.unit|escape }}" data-purchase="{{ item.purchase_price|stringformat:'s' }}" data-sales="{{ item.sales_price|stringformat:'s' }}" data-kind="{{ item.kind|escape }}" data-id="{{ item.pk }}"><span><b>{{ item.name }}</b><small>{{ item.code }} · {{ item.unit }}</small></span><strong>{{ item.sales_price|floatformat:2 }} €</strong></button>{% empty %}<div class="nx-empty">Noch keine Katalogpositionen.</div>{% endfor %}</div>
    </section>

    <aside class="nx-card nx-card-pad ab-summary-card">
      <div class="nx-kicker">Kalkulation</div>
      <div class="ab-summary-lines">
        <div><span>Nettobetrag</span><strong data-total="net">0,00 €</strong></div>
        <div><span>Gesamte Einkaufskosten</span><strong data-total="cost">0,00 €</strong></div>
        <div><span>Marge</span><strong data-total="margin">0,00 €</strong></div>
        <div><span>Marge %</span><strong data-total="margin-percent">0,00 %</strong></div>
        <div class="ab-muted-total"><span>Alternativpositionen</span><strong data-total="alternative">0,00 €</strong></div>
        <div class="ab-muted-total"><span>Eventualpositionen</span><strong data-total="contingent">0,00 €</strong></div>
        <div><span>Rabatt</span><strong data-total="discount">0,00 €</strong></div>
        <div><span>Umsatzsteuer</span><strong data-total="tax">0,00 €</strong></div>
        <div class="ab-grand-total"><span>Gesamtbetrag</span><strong data-total="gross">0,00 €</strong></div>
        {% if kind == 'invoice' and totals %}<div><span>Bezahlt</span><strong>{{ totals.paid|floatformat:2 }} €</strong></div><div><span>Offen</span><strong>{{ totals.open|floatformat:2 }} €</strong></div>{% endif %}
      </div>
      <div class="ab-summary-controls">
        <label><span>Rabatt</span><div class="ab-inline"><select class="nx-control" name="discount_type"><option value="percent" {% if not commercial or commercial.discount_type == 'percent' %}selected{% endif %}>Prozent</option><option value="fixed" {% if commercial.discount_type == 'fixed' %}selected{% endif %}>Fester Betrag</option></select><input class="nx-control" name="discount_value" type="number" min="0" step="0.01" value="{% if commercial %}{{ commercial.discount_value|stringformat:'s' }}{% elif kind == 'quote' and document %}{{ document.discount_percent|stringformat:'s' }}{% else %}0{% endif %}"></div></label>
        <label><span>Umsatzsteuer für das Dokument</span><select class="nx-control" name="document_tax_code"><option value="19" {% if not commercial or commercial.tax_code == '19' %}selected{% endif %}>19 % Umsatzsteuer</option><option value="7" {% if commercial.tax_code == '7' %}selected{% endif %}>7 % Umsatzsteuer</option><option value="0_19" {% if commercial.tax_code == '0_19' %}selected{% endif %}>0 % gemäß § 19 UStG</option><option value="0_13b" {% if commercial.tax_code == '0_13b' %}selected{% endif %}>0 % gemäß § 13b UStG</option><option value="0_4" {% if commercial.tax_code == '0_4' %}selected{% endif %}>0 % gemäß § 4 UStG</option><option value="0" {% if commercial.tax_code == '0' %}selected{% endif %}>0 % Umsatzsteuer</option></select></label>
        {% if kind == 'invoice' %}<label><span>Zahlungsziel</span><select class="nx-control" name="payment_due_days"><option value="0" {% if commercial.payment_due_days == 0 %}selected{% endif %}>Sofort</option><option value="7" {% if commercial.payment_due_days == 7 %}selected{% endif %}>7 Tage</option><option value="14" {% if not commercial or commercial.payment_due_days == 14 %}selected{% endif %}>14 Tage</option><option value="30" {% if commercial.payment_due_days == 30 %}selected{% endif %}>30 Tage</option><option value="60" {% if commercial.payment_due_days == 60 %}selected{% endif %}>60 Tage</option></select></label><label><span>Skonto</span><div class="ab-inline"><input class="nx-control" name="early_discount_percent" type="number" min="0" max="100" step="0.01" value="{% if commercial %}{{ commercial.early_payment_discount_percent|stringformat:'s' }}{% else %}0{% endif %}" placeholder="%"><input class="nx-control" name="early_discount_days" type="number" min="0" step="1" value="{% if commercial %}{{ commercial.early_payment_discount_days }}{% else %}0{% endif %}" placeholder="Tage"></div></label>{% else %}<input type="hidden" name="payment_due_days" value="14"><input type="hidden" name="early_discount_percent" value="0"><input type="hidden" name="early_discount_days" value="0">{% endif %}
      </div>
    </aside>
  </div>

  <section class="nx-card nx-card-pad ab-closing-card">
    <div class="nx-card-head" style="padding:0 0 14px"><div><h2>Abschluss- und Rechtstext</h2><p>Vorlagen sind editierbar. Rechtliche Texte sollten vor produktiver Nutzung betrieblich geprüft werden.</p></div><select class="nx-control ab-template-select" data-legal-template><option value="">Vorlage auswählen …</option><option value="standard">Standardabschluss</option><option value="widerruf">Widerruf & vorzeitiger Arbeitsbeginn</option><option value="zahlung">Zahlungsbedingungen</option><option value="ausfuehrung">Ausführungsbedingungen</option></select></div>
    <textarea class="nx-control" rows="10" name="closing_text" data-closing-text placeholder="Abschluss- und Rechtstext …">{% if commercial and commercial.closing_text %}{{ commercial.closing_text }}{% elif document %}{{ document.outro_text }}{% endif %}</textarea>
  </section>

  <div class="nx-form-actions"><a class="nx-btn" href="{% if kind == 'quote' %}{% url 'next-quotes' %}{% else %}{% url 'next-invoices' %}{% endif %}">Zurück</a><button class="nx-btn" type="submit" name="action" value="save">Entwurf speichern</button><button class="nx-btn nx-btn-primary" type="submit" name="action" value="send">Speichern & als gesendet markieren</button></div>
</form>
{% endblock %}'''


def patch_templates_and_brand() -> None:
    write("templates/rebuild/document_editor.html", document_editor_template())

    base_rel = "templates/rebuild/base.html"
    base = read(base_rel)
    base = base.replace("{% block title %}KAYI{% endblock %}", "{% block title %}A+Bau{% endblock %}")
    brand_pattern = re.compile(r'<a class="nx-brand" href="(?P<href>.*?)"><span class="nx-brandmark">K</span><span><strong>KAYI</strong><small>(?P<small>.*?)</small></span></a>', re.S)
    brand_new = r'''<a class="nx-brand ab-brand" href="\g<href>"><img src="{% static 'brand/ab-bau-logo.webp' %}" alt="A+Bau"><span><strong>A+Bau</strong><small>Alles organisiert. Alles im Griff.</small></span></a>'''
    base, count = brand_pattern.subn(brand_new, base, count=1)
    if count != 1 and "ab-brand" not in base:
        raise RuntimeError("A+Bau base brand anchor changed")
    finance_link = '''      <a class="{% if request.resolver_match.url_name == 'next-finance' %}is-active{% endif %}" href="{% url 'next-finance' %}"><span class="nx-ico">↗</span>Finanzen</a>\n'''
    if "next-finance" not in base:
        anchor = '''      <a class="{% if 'invoice' in request.resolver_match.url_name %}is-active{% endif %}" href="{% url 'next-invoices' %}"><span class="nx-ico">€</span>Rechnungen</a>\n'''
        if anchor not in base:
            raise RuntimeError("A+Bau finance navigation anchor changed")
        base = base.replace(anchor, anchor + finance_link, 1)
    base = base.replace("KAYI Next", "A+Bau").replace("KAYI", "A+Bau")
    base = base.replace("Bestehende Daten bleiben erhalten.", "Von der Baustelle bis zur Rechnung.")
    base = re.sub(r"kayi-next\.css' %\}\?v=[^\"']+", f"kayi-next.css' %}}?v={VERSION}", base)
    base = re.sub(r"kayi-next\.js' %\}\?v=[^\"']+", f"kayi-next.js' %}}?v={VERSION}", base)
    write(base_rel, base)

    for path in (ROOT / "templates" / "rebuild").glob("*.html"):
        content = path.read_text(encoding="utf-8")
        content = content.replace("KAYI Next", "A+Bau").replace("KAYI Haustechnik", "A+Bau").replace(" · KAYI", " · A+Bau")
        path.write_text(content, encoding="utf-8")

    project_rel = "templates/rebuild/project_detail.html"
    project = read(project_rel)
    if 'data-tab="finance"' not in project:
        tab_anchor = '''{% if not field_user %}<button type="button" data-tab="commercial">Angebote & Rechnungen</button>{% endif %}<button type="button" data-tab="tasks">Aufgaben</button>'''
        tab_new = '''{% if not field_user %}<button type="button" data-tab="commercial">Angebote & Rechnungen</button><button type="button" data-tab="finance">Finanzen</button>{% endif %}<button type="button" data-tab="tasks">Aufgaben</button>'''
        if tab_anchor not in project:
            raise RuntimeError("A+Bau project finance tab anchor changed")
        project = project.replace(tab_anchor, tab_new, 1)
        tasks_anchor = '''  <div class="nx-tab-panel" data-tab-panel="tasks" style="margin-top:14px">'''
        finance_panel = '''  {% if not field_user %}<div class="nx-tab-panel" data-tab-panel="finance" style="margin-top:14px"><section class="nx-finance-kpis"><div><small>Umsatz netto</small><b>{{ finance.revenue|floatformat:2 }} €</b></div><div><small>Einkaufskosten</small><b>{{ finance.cost|floatformat:2 }} €</b></div><div><small>Marge</small><b>{{ finance.margin|floatformat:2 }} €</b><span>{{ finance.margin_percent|floatformat:1 }} %</span></div><div><small>Offen</small><b>{{ finance.open|floatformat:2 }} €</b></div></section><section class="nx-card nx-card-pad" style="margin-top:14px"><div class="nx-card-head" style="padding:0"><div><h2>Projektfinanzen</h2><p>Angebotsvolumen {{ finance.quote_volume|floatformat:2 }} € · fakturiert brutto {{ finance.gross|floatformat:2 }} € · bezahlt {{ finance.paid|floatformat:2 }} €.</p></div><a class="nx-btn" href="{% url 'next-finance' %}?project={{ project.pk }}">In Finanzübersicht öffnen →</a></div></section></div>{% endif %}\n'''
        if tasks_anchor not in project:
            raise RuntimeError("A+Bau project finance panel anchor changed")
        project = project.replace(tasks_anchor, finance_panel + tasks_anchor, 1)
    write(project_rel, project)

    finance = r'''{% extends 'rebuild/base.html' %}{% block title %}Finanzen · A+Bau{% endblock %}{% block content %}
<div class="nx-pagehead"><div><div class="nx-kicker">Finanzen</div><h1>Finanzübersicht</h1><p>Umsatz, Einkaufskosten und Marge über alle Projekte.</p></div></div>
<section class="nx-finance-kpis"><div><small>Umsatz netto</small><b>{{ revenue|floatformat:2 }} €</b><span>Rechnungen im Filter</span></div><div><small>Einkaufskosten</small><b>{{ cost|floatformat:2 }} €</b><span>aus den Positionen</span></div><div><small>Marge</small><b>{{ margin|floatformat:2 }} €</b><span>{{ margin_percent|floatformat:1 }} %</span></div><div><small>Offene Beträge</small><b>{{ open_amount|floatformat:2 }} €</b><span>brutto</span></div><div><small>Bezahlt</small><b>{{ paid|floatformat:2 }} €</b><span>erfasste Zahlungen</span></div><div><small>Angebotsvolumen</small><b>{{ quote_volume|floatformat:2 }} €</b><span>netto</span></div></section>
<section class="nx-card nx-card-pad nx-finance-filter"><form method="get" class="nx-time-filters"><label><span>Projekt</span><select class="nx-control" name="project"><option value="">Alle Projekte</option>{% for p in projects %}<option value="{{ p.pk }}" {% if project_filter == p.pk|stringformat:'s' %}selected{% endif %}>{{ p.number }} · {{ p.title }}</option>{% endfor %}</select></label><label><span>Von</span><input class="nx-control" type="date" name="date_from" value="{{ date_from }}"></label><label><span>Bis</span><input class="nx-control" type="date" name="date_to" value="{{ date_to }}"></label><div class="nx-time-filter-actions"><button class="nx-btn nx-btn-primary">Filtern</button><a class="nx-btn" href="{% url 'next-finance' %}">Zurücksetzen</a></div></form></section>
<div class="nx-grid nx-grid-2" style="margin-top:16px"><section class="nx-card"><div class="nx-card-head"><div><h2>Nach Projekt</h2><p>Marge je Projekt.</p></div></div><div class="nx-table-wrap"><table class="nx-table"><thead><tr><th>Projekt</th><th>Umsatz</th><th>Einkauf</th><th>Marge</th><th>Marge %</th><th>Offen</th></tr></thead><tbody>{% for row in project_rows %}<tr><td><a href="{% url 'next-project-detail' row.project.pk %}"><strong>{{ row.project.number }}</strong><br>{{ row.project.title }}</a></td><td>{{ row.revenue|floatformat:2 }} €</td><td>{{ row.cost|floatformat:2 }} €</td><td><strong>{{ row.margin|floatformat:2 }} €</strong></td><td>{{ row.margin_percent|floatformat:1 }} %</td><td>{{ row.open|floatformat:2 }} €</td></tr>{% empty %}<tr><td colspan="6"><div class="nx-empty">Noch keine Finanzdaten im gewählten Zeitraum.</div></td></tr>{% endfor %}</tbody></table></div></section><section class="nx-card"><div class="nx-card-head"><div><h2>Rechnungen</h2><p>Letzte Rechnungen im Filter.</p></div></div><div class="nx-table-wrap"><table class="nx-table"><thead><tr><th>Rechnung</th><th>Projekt</th><th>Netto</th><th>Marge</th><th>Offen</th></tr></thead><tbody>{% for row in invoice_rows %}<tr><td><a href="{% url 'next-invoice-edit' row.invoice.pk %}"><strong>{{ row.invoice.number }}</strong></a><br>{{ row.invoice.issue_date|date:'d.m.Y' }}</td><td>{{ row.invoice.project.number }}</td><td>{{ row.total.net|floatformat:2 }} €</td><td>{{ row.total.margin|floatformat:2 }} €</td><td>{{ row.total.open|floatformat:2 }} €</td></tr>{% empty %}<tr><td colspan="5"><div class="nx-empty">Noch keine Rechnungen.</div></td></tr>{% endfor %}</tbody></table></div></section></div>
{% endblock %}'''
    write("templates/rebuild/finance_dashboard.html", finance)


def patch_javascript() -> None:
    rel = "static/js/kayi-next.js"
    text = read(rel)
    time_pattern = re.compile(r"  \$\$\('\[data-time-toggle\]'\)\.forEach\(\(button\) => \{.*?\n  \}\);\n\n  const addItemRow", re.S)
    time_new = r'''  $$('[data-time-toggle]').forEach((button) => {
    button.addEventListener('click', async () => {
      if (button.disabled) return;
      button.disabled = true;
      const old = button.textContent;
      button.textContent = 'Wird gespeichert …';
      try {
        const response = await fetch(button.dataset.timeToggle, {method:'POST',credentials:'same-origin',headers:{'Accept':'application/json','X-CSRFToken':csrf(),'X-Requested-With':'XMLHttpRequest'}});
        const raw = await response.text();
        let data = null;
        try { data = raw ? JSON.parse(raw) : {}; } catch (_) {
          if (response.redirected || response.status === 401 || response.status === 403 || /text\/html/i.test(response.headers.get('content-type') || '')) throw new Error('Die Sitzung oder Berechtigung ist abgelaufen. Bitte Seite neu laden und erneut versuchen.');
          throw new Error('Die Zeiterfassung hat keine gültige Serverantwort erhalten.');
        }
        if (!response.ok || !data.ok) throw new Error(data?.error || `Zeiterfassung fehlgeschlagen (${response.status}).`);
        button.textContent = data.state === 'running' ? '■ Arbeit stoppen' : '▶ Arbeit starten';
        button.classList.toggle('nx-btn-danger', data.state === 'running');
        button.classList.toggle('nx-btn-accent', data.state !== 'running');
      } catch (error) {
        button.textContent = old;
        alert(error.message || 'Zeiterfassung konnte nicht geändert werden.');
      } finally { button.disabled = false; }
    });
  });

  const addItemRow'''
    text, count = time_pattern.subn(time_new, text, count=1)
    if count != 1:
        raise RuntimeError("A+Bau time JSON anchor changed")

    doc_pattern = re.compile(r"  const addItemRow = \(table, values = \{\}\) => \{.*?\n  \$\$\('\[data-catalog-item\]'\)\.forEach\(\(button\) => \{.*?\n  \}\);\n\n  const setupVoice", re.S)
    doc_new = r'''  const abMoney = new Intl.NumberFormat('de-DE',{style:'currency',currency:'EUR'});
  const abNum = (value) => { const n = Number(String(value ?? '').replace(',','.')); return Number.isFinite(n) ? n : 0; };
  const abEscape = (value) => String(value ?? '').replace(/[&<>"']/g,(c)=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const abUnits = ['Stk.','m','m²','m³','kg','t','l','Std.','Tag','Woche','Pauschal','Satz','Rolle','Packung','Rohr'];
  const abUnitOptions = (selected='Stk.') => abUnits.map((u)=>`<option ${u===selected?'selected':''}>${u}</option>`).join('');

  const abRenumber = (table) => $$('.ab-item-row', table).forEach((row,index)=>{ const pos=$('.ab-pos',row); if(pos)pos.textContent=String(index+1); });
  const abRowPair = (row) => { const next=row.nextElementSibling; return next?.classList.contains('ab-item-subrow') ? next : null; };
  const abRemoveRow = (row, table) => { abRowPair(row)?.remove(); row.remove(); abRenumber(table); abRecalc(table); };
  const abRowHtml = (v={}) => `<tr class="ab-item-row" draggable="true"><td class="ab-drag-cell"><button type="button" class="ab-drag" title="Position verschieben">⋮⋮</button></td><td class="ab-pos"></td><td><select class="nx-control" name="item_type"><option value="material" ${v.type==='material'||!v.type?'selected':''}>Material</option><option value="labour" ${v.type==='labour'?'selected':''}>Arbeitsleistung</option><option value="mixed" ${v.type==='mixed'?'selected':''}>Gemischte Leistung</option><option value="other" ${v.type==='other'?'selected':''}>Sonstiges</option></select></td><td><input class="nx-control ab-num" name="item_quantity" type="number" min="0" step="0.001" value="${abEscape(v.quantity ?? 1)}"></td><td><select class="nx-control" name="item_unit">${abUnitOptions(v.unit||'Stk.')}</select></td><td class="ab-title-cell"><input type="hidden" name="item_catalog_id" value="${abEscape(v.catalogId||'')}"><input type="hidden" name="item_group" value=""><input type="hidden" name="item_price" value="0"><input class="nx-control" name="item_description" value="${abEscape(v.description||'')}" placeholder="Bezeichnung"><textarea class="nx-control ab-detail" name="item_detail" rows="2" placeholder="Beschreibung (optional)">${abEscape(v.detail||'')}</textarea></td><td><input class="nx-control ab-num" name="item_purchase_price" type="number" min="0" step="0.01" value="${abEscape(v.purchase ?? 0)}"></td><td><div class="ab-suffix"><input class="nx-control ab-num" name="item_markup_percent" type="number" step="0.01" value="${abEscape(v.markup ?? 0)}"><span>%</span></div></td><td><output data-line-markup>0,00 €</output></td><td><output data-line-unit-price>0,00 €</output></td><td><output data-line-total>0,00 €</output></td><td><button type="button" class="nx-item-remove" aria-label="Position entfernen">×</button></td></tr><tr class="ab-item-subrow"><td></td><td></td><td colspan="10"><label>Preismodell <select class="nx-control ab-service-model" name="item_service_model"><option value="normal">Normalleistung</option><option value="alternative">Alternativposition</option><option value="contingent">Eventualposition</option></select></label></td></tr>`;

  const abBindRow = (row, table) => {
    row.querySelector('.nx-item-remove')?.addEventListener('click',()=>abRemoveRow(row,table));
    $$('input,select,textarea',row).forEach((el)=>el.addEventListener('input',()=>abRecalc(table)));
    const sub=abRowPair(row); $$('select',sub||document.createElement('div')).forEach((el)=>el.addEventListener('change',()=>abRecalc(table)));
    row.addEventListener('dragstart',(e)=>{ row.classList.add('is-dragging'); e.dataTransfer.effectAllowed='move'; e.dataTransfer.setData('text/plain','position'); });
    row.addEventListener('dragend',()=>{row.classList.remove('is-dragging');abRenumber(table);abRecalc(table);});
  };
  const abInsertRow = (table, values={}) => { const body=$('tbody',table); const temp=document.createElement('tbody'); temp.innerHTML=abRowHtml(values); const row=temp.children[0], sub=temp.children[1]; body.append(row,sub); abBindRow(row,table); abRenumber(table); abRecalc(table); row.querySelector('[name=item_description]')?.focus(); return row; };

  const abRecalc = (table) => {
    let net=0,cost=0,alternative=0,contingent=0;
    $$('.ab-item-row',table).forEach((row)=>{
      const qty=Math.max(0,abNum($('[name=item_quantity]',row)?.value)); const purchase=Math.max(0,abNum($('[name=item_purchase_price]',row)?.value)); const markup=abNum($('[name=item_markup_percent]',row)?.value); const unit=Math.max(0,purchase*(1+markup/100)); const line=qty*unit; const markupValue=Math.max(0,unit-purchase); const model=abRowPair(row)?.querySelector('[name=item_service_model]')?.value || 'normal';
      $('[name=item_price]',row).value=unit.toFixed(2); $('[data-line-markup]',row).textContent=abMoney.format(markupValue); $('[data-line-unit-price]',row).textContent=abMoney.format(unit); $('[data-line-total]',row).textContent=abMoney.format(line);
      if(model==='alternative') alternative+=line; else if(model==='contingent') contingent+=line; else {net+=line; cost+=qty*purchase;}
    });
    const type=document.querySelector('[name=discount_type]')?.value||'percent'; const dval=Math.max(0,abNum(document.querySelector('[name=discount_value]')?.value)); const discount=Math.min(net,type==='fixed'?dval:net*dval/100); const after=Math.max(0,net-discount); const code=document.querySelector('[name=document_tax_code]')?.value||'19'; const rate=code==='7'?7:(code==='19'?19:0); const tax=after*rate/100; const margin=after-cost; const marginPct=after?margin/after*100:0;
    const set=(key,val,percent=false)=>{const el=document.querySelector(`[data-total="${key}"]`);if(el)el.textContent=percent?`${val.toLocaleString('de-DE',{minimumFractionDigits:2,maximumFractionDigits:2})} %`:abMoney.format(val);};
    set('net',after);set('cost',cost);set('margin',margin);set('margin-percent',marginPct,true);set('alternative',alternative);set('contingent',contingent);set('discount',discount);set('tax',tax);set('gross',after+tax);
  };

  $$('[data-ab-items]').forEach((table)=>{
    $$('.ab-item-row',table).forEach((row)=>abBindRow(row,table));
    if(!$('.ab-item-row',table)) abInsertRow(table,{});
    $$('[data-ab-add-item]').forEach((button)=>button.addEventListener('click',()=>abInsertRow(table,{})));
    table.addEventListener('dragover',(e)=>{e.preventDefault();const dragging=$('.ab-item-row.is-dragging',table);if(!dragging)return;const target=e.target.closest('.ab-item-row');if(!target||target===dragging)return;const pair=abRowPair(dragging);const rect=target.getBoundingClientRect();const before=e.clientY<rect.top+rect.height/2;const targetPair=abRowPair(target);if(before){target.before(dragging);dragging.after(pair);}else{(targetPair||target).after(dragging);dragging.after(pair);}});
    let pointerRow=null;
    table.addEventListener('pointerdown',(e)=>{const handle=e.target.closest('.ab-drag');if(!handle)return;pointerRow=handle.closest('.ab-item-row');pointerRow?.setPointerCapture?.(e.pointerId);pointerRow?.classList.add('is-pointer-dragging');e.preventDefault();});
    table.addEventListener('pointermove',(e)=>{if(!pointerRow)return;const hit=document.elementFromPoint(e.clientX,e.clientY)?.closest('.ab-item-row');if(!hit||hit===pointerRow||!table.contains(hit))return;const pair=abRowPair(pointerRow), hitPair=abRowPair(hit);const r=hit.getBoundingClientRect();if(e.clientY<r.top+r.height/2){hit.before(pointerRow);pointerRow.after(pair);}else{(hitPair||hit).after(pointerRow);pointerRow.after(pair);}});
    const finish=()=>{if(!pointerRow)return;pointerRow.classList.remove('is-pointer-dragging');pointerRow=null;abRenumber(table);abRecalc(table);}; table.addEventListener('pointerup',finish);table.addEventListener('pointercancel',finish);
    document.querySelector('[name=discount_type]')?.addEventListener('change',()=>abRecalc(table));document.querySelector('[name=discount_value]')?.addEventListener('input',()=>abRecalc(table));document.querySelector('[name=document_tax_code]')?.addEventListener('change',()=>abRecalc(table));
    abRenumber(table);abRecalc(table);
  });

  $$('[data-ab-catalog]').forEach((button)=>button.addEventListener('click',()=>{const table=$('[data-ab-items]');if(!table)return;const kind=button.dataset.kind||'material';const type=kind==='service'?'labour':(kind==='material'?'material':'other');const purchase=abNum(button.dataset.purchase)>0?button.dataset.purchase:(button.dataset.sales||0);abInsertRow(table,{catalogId:button.dataset.id,description:button.dataset.name,detail:button.dataset.description,unit:button.dataset.unit,purchase,type});}));
  $('[data-ab-catalog-search]')?.addEventListener('input',(e)=>{const q=e.target.value.trim().toLocaleLowerCase('de-DE');$$('[data-ab-catalog]').forEach((button)=>button.hidden=!!q&&!button.textContent.toLocaleLowerCase('de-DE').includes(q));});
  const legalTexts={standard:'Wir freuen uns, wenn unser Angebot Ihre Zustimmung findet. Für Rückfragen stehen wir Ihnen jederzeit gerne zur Verfügung.',widerruf:'Widerruf und vorzeitiger Arbeitsbeginn: Bitte prüfen und ergänzen Sie hier die für Ihren Betrieb und den konkreten Vertrag erforderliche Widerrufsbelehrung sowie die ausdrückliche Zustimmung zum vorzeitigen Arbeitsbeginn.',zahlung:'Zahlungsbedingungen: Der Rechnungsbetrag ist innerhalb des vereinbarten Zahlungsziels ohne Abzug fällig. Vereinbartes Skonto gilt nur bei fristgerechtem Zahlungseingang.',ausfuehrung:'Ausführungsbedingungen: Termine und Ausführungsbeginn werden nach Auftragsbestätigung abgestimmt. Änderungen des Leistungsumfangs werden vor Ausführung dokumentiert und freigegeben.'};
  $('[data-legal-template]')?.addEventListener('change',(e)=>{const target=$('[data-closing-text]');if(target&&e.target.value&&legalTexts[e.target.value])target.value=legalTexts[e.target.value];});

  const setupVoice'''
    text, count = doc_pattern.subn(doc_new, text, count=1)
    if count != 1:
        raise RuntimeError("A+Bau document JS anchor changed")
    write(rel, text)


def patch_css() -> None:
    rel = "static/css/kayi-next.css"
    css = read(rel)
    if MARKER not in css:
        css += r'''

/* A+BAU TOOLTIME COMMERCIAL + FINANCE UPGRADE 2026-08-12 */
:root{--ab-gold:#c9a13b;--ab-gold-soft:#f5edd8;--ab-black:#111315;--ab-silver:#e8eaec}.nx-sidebar{background:linear-gradient(180deg,#111315,#1a1d20)!important}.nx-brand.ab-brand{gap:10px;align-items:center}.ab-brand img{width:54px;height:42px;object-fit:cover;border-radius:9px;border:1px solid rgba(201,161,59,.38)}.ab-brand strong{letter-spacing:.02em}.ab-brand small{max-width:150px;white-space:normal;line-height:1.2;color:#c9a13b}.nx-btn-primary,.nx-btn-accent{background:linear-gradient(135deg,#b88b26,#d7b454)!important;border-color:#c9a13b!important;color:#111315!important}.ab-document-form{display:grid;gap:16px}.ab-services-card{overflow:hidden}.ab-item-table-wrap{overflow:auto;padding-bottom:3px}.ab-item-table{width:100%;min-width:1500px;border-collapse:separate;border-spacing:0}.ab-item-table th{font-size:11px;color:#6b7280;text-align:left;padding:9px 7px;border-bottom:1px solid var(--nx-line);white-space:nowrap}.ab-item-table td{padding:8px 6px;border-bottom:1px solid var(--nx-line);vertical-align:top}.ab-item-table .nx-control{min-width:0}.ab-drag-cell{width:34px}.ab-drag{border:0;background:transparent;cursor:grab;font-size:18px;color:#7a7f85;padding:8px}.ab-item-row.is-dragging,.ab-item-row.is-pointer-dragging{opacity:.55;background:var(--ab-gold-soft)}.ab-pos{font-weight:800;color:#667085}.ab-num{min-width:92px}.ab-title-cell{min-width:260px}.ab-detail{margin-top:7px;resize:vertical}.ab-suffix{display:flex;align-items:center;gap:5px}.ab-suffix span{font-weight:800;color:#667085}.ab-item-table output{display:block;padding:11px 5px;white-space:nowrap;font-weight:700}.ab-item-subrow td{padding-top:0;background:#fafafa}.ab-item-subrow label{display:flex;align-items:center;gap:10px;font-size:12px;font-weight:700}.ab-service-model{max-width:220px}.ab-add-bar{display:flex;align-items:center;gap:12px;padding:14px 18px}.ab-document-bottom{display:grid;grid-template-columns:minmax(0,1.45fr) minmax(330px,.55fr);gap:16px;align-items:start}.ab-catalog-search{padding:0 16px 12px}.ab-catalog-list{display:grid;gap:7px;max-height:440px;overflow:auto;padding:0 16px 16px}.ab-catalog-item{display:flex;align-items:center;justify-content:space-between;gap:12px;border:1px solid var(--nx-line);background:#fff;border-radius:12px;padding:11px 13px;text-align:left;cursor:pointer}.ab-catalog-item:hover{border-color:#c9a13b;background:#fffcf5}.ab-catalog-item span{display:grid;gap:3px}.ab-catalog-item small{color:#667085}.ab-catalog-item strong{white-space:nowrap}.ab-summary-card{position:sticky;top:82px}.ab-summary-lines{display:grid;gap:9px;margin-top:13px}.ab-summary-lines>div{display:flex;justify-content:space-between;gap:12px}.ab-summary-lines span{color:#667085}.ab-summary-lines .ab-grand-total{border-top:1px solid var(--nx-line);padding-top:13px;margin-top:3px;font-size:18px}.ab-muted-total{font-size:12px}.ab-summary-controls{border-top:1px solid var(--nx-line);margin-top:15px;padding-top:15px;display:grid;gap:13px}.ab-summary-controls label{display:grid;gap:6px;font-size:12px;font-weight:800}.ab-inline{display:grid;grid-template-columns:1fr 1fr;gap:7px}.ab-template-select{max-width:320px}.nx-finance-kpis{display:grid;grid-template-columns:repeat(6,minmax(0,1fr));gap:12px}.nx-finance-kpis>div{border:1px solid var(--nx-line);background:#fff;border-radius:16px;padding:15px;display:grid;gap:4px}.nx-finance-kpis small{font-weight:800;color:#667085}.nx-finance-kpis b{font-size:22px}.nx-finance-kpis span{font-size:11px;color:#8b9199}.nx-finance-filter{margin-top:16px}
@media(max-width:1180px){.ab-document-bottom{grid-template-columns:1fr}.ab-summary-card{position:static}.nx-finance-kpis{grid-template-columns:repeat(3,1fr)}}
@media(max-width:720px){.ab-item-table-wrap{overflow:visible}.ab-item-table{min-width:0;display:block}.ab-item-table thead{display:none}.ab-item-table tbody{display:grid;gap:12px;padding:12px}.ab-item-row{display:grid;grid-template-columns:34px 44px 1fr 1fr;border:1px solid var(--nx-line);border-radius:15px;padding:10px;background:#fff}.ab-item-row td{display:block;border:0;padding:5px;min-width:0}.ab-item-row td:nth-child(3),.ab-item-row td:nth-child(6),.ab-item-row td:nth-child(7),.ab-item-row td:nth-child(8),.ab-item-row td:nth-child(9),.ab-item-row td:nth-child(10),.ab-item-row td:nth-child(11){grid-column:1/-1}.ab-item-subrow{display:block;margin-top:-13px;border:1px solid var(--nx-line);border-top:0;border-radius:0 0 15px 15px;padding:8px 12px;background:#fafafa}.ab-item-subrow td{display:none}.ab-item-subrow td[colspan]{display:block}.ab-add-bar{align-items:flex-start;flex-direction:column}.nx-finance-kpis{grid-template-columns:1fr 1fr}.ab-inline{grid-template-columns:1fr}.ab-template-select{max-width:none;width:100%}}
'''
        write(rel, css)


def install_logo() -> None:
    src = ROOT / "branding" / "ab-bau-logo.webp"
    if src.exists():
        dst = ROOT / "static" / "brand" / "ab-bau-logo.webp"
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dst)


def install_tests() -> None:
    write("tests/test_ab_bau_tooltime_finance_upgrade.py", r'''from pathlib import Path
from django.test import SimpleTestCase

R = Path(__file__).resolve().parents[1]


class ABBauCommercialUpgradeTests(SimpleTestCase):
    def test_document_editor_uses_tooltime_style_commercial_fields(self):
        t = (R / "templates/rebuild/document_editor.html").read_text(encoding="utf-8")
        for marker in ("item_type", "item_purchase_price", "item_markup_percent", "item_service_model", "document_tax_code", "discount_value", "item_unit"):
            self.assertIn(marker, t)
        self.assertNotIn('name="item_tax"', t)
        self.assertIn("Alternativposition", t)
        self.assertIn("Eventualposition", t)

    def test_finance_dashboard_and_project_finance_exist(self):
        u = (R / "erp/rebuild_urls.py").read_text(encoding="utf-8")
        v = (R / "erp/rebuild_views.py").read_text(encoding="utf-8")
        p = (R / "templates/rebuild/project_detail.html").read_text(encoding="utf-8")
        self.assertIn('path("finanzen/"', u)
        self.assertIn("def finance_dashboard", v)
        self.assertIn('data-tab="finance"', p)
        self.assertIn("_project_financials", v)

    def test_time_toggle_handles_non_json_without_json_parse_crash(self):
        js = (R / "static/js/kayi-next.js").read_text(encoding="utf-8")
        self.assertIn("const raw = await response.text()", js)
        self.assertIn("JSON.parse(raw)", js)
        self.assertIn("keine gültige Serverantwort", js)

    def test_brand_is_a_plus_bau_and_german(self):
        base = (R / "templates/rebuild/base.html").read_text(encoding="utf-8")
        self.assertIn("A+Bau", base)
        self.assertIn("Alles organisiert. Alles im Griff.", base)
        self.assertIn("Finanzen", base)
        self.assertNotIn(">KAYI<", base)

    def test_commercial_sidecar_models_are_installed(self):
        m = (R / "erp/ab_bau_commercial.py").read_text(encoding="utf-8")
        migration = (R / "erp/migrations/0009_ab_bau_commercial.py").read_text(encoding="utf-8")
        self.assertIn("class CommercialDocumentSettings", m)
        self.assertIn("class CommercialItemMeta", m)
        self.assertIn("purchase_price", migration)
''')


def main() -> None:
    install_commercial_models()
    patch_commercial_views()
    patch_project_finance()
    patch_urls()
    patch_templates_and_brand()
    patch_javascript()
    patch_css()
    install_logo()
    install_tests()
    print("A+Bau ToolTime commercial + finance upgrade installed")


if __name__ == "__main__":
    main()
