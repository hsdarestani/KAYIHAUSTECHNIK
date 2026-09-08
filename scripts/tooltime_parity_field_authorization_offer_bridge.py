from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MARKER = "A+BAU FIELD AUTHORIZATION USES ANGEBOT EDITOR 2026-09-08"


def read(rel: str) -> str:
    path = ROOT / rel
    if not path.exists():
        raise RuntimeError(f"Angebot/Freigabe bridge target missing: {rel}")
    return path.read_text(encoding="utf-8")


def write(rel: str, text: str) -> None:
    path = ROOT / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if new in text:
        return text
    if old not in text:
        raise RuntimeError(f"Angebot/Freigabe bridge anchor changed: {label}")
    return text.replace(old, new, 1)


def share_angebot_editor_parts() -> tuple[str, list[str]]:
    """Make the final Angebot markup the single source for both screens."""
    rel = "templates/rebuild/document_editor.html"
    editor = read(rel)
    original = editor

    service_include = "{% include 'rebuild/_tooltime_services_editor.html' %}"
    if service_include not in editor:
        start = editor.find('<section class="tt-services"')
        end = editor.find('<div class="tt-bottom-grid"', start)
        if start < 0 or end < 0 or end <= start:
            raise RuntimeError("Final Angebot service editor bounds missing")
        services = editor[start:end].rstrip() + "\n"
        write("templates/rebuild/_tooltime_services_editor.html", services)
        editor = editor[:start] + service_include + "\n" + editor[end:]
    elif not (ROOT / "templates/rebuild/_tooltime_services_editor.html").exists():
        raise RuntimeError("Shared Angebot service partial missing")

    summary_include = "{% include 'rebuild/_tooltime_calculation_summary.html' %}"
    if summary_include not in editor:
        start = editor.find('<aside class="tt-summary"')
        end = editor.find("</aside>", start)
        if start < 0 or end < 0:
            raise RuntimeError("Final Angebot calculation summary bounds missing")
        end += len("</aside>")
        summary = editor[start:end] + "\n"
        write("templates/rebuild/_tooltime_calculation_summary.html", summary)
        editor = editor[:start] + summary_include + editor[end:]
    elif not (ROOT / "templates/rebuild/_tooltime_calculation_summary.html").exists():
        raise RuntimeError("Shared Angebot calculation summary partial missing")

    article_include = "{% include 'rebuild/_tooltime_article_modal.html' %}"
    if article_include not in editor:
        start = editor.find('<div class="tt-modal" data-article-modal')
        next_modal = editor.find('<div class="tt-modal" data-template-modal', start)
        if start < 0 or next_modal < 0 or next_modal <= start:
            raise RuntimeError("Final Angebot article modal bounds missing")
        article_modal = editor[start:next_modal].rstrip() + "\n"
        write("templates/rebuild/_tooltime_article_modal.html", article_modal)
        editor = editor[:start] + article_include + "\n" + editor[next_modal:]
    elif not (ROOT / "templates/rebuild/_tooltime_article_modal.html").exists():
        raise RuntimeError("Shared Angebot article modal partial missing")

    if MARKER not in editor:
        editor = editor.replace("{% block content %}", "{% block content %}\n{# " + MARKER + " #}", 1)
    write(rel, editor)

    asset_tags = []
    for match in re.finditer(r"<(?:link|script)\b[^>]*tooltime[^>]*>(?:</script>)?", original, flags=re.I):
        tag = match.group(0).strip()
        if tag and tag not in asset_tags:
            asset_tags.append(tag)
    if not any("tooltime-parity-finance.css" in tag for tag in asset_tags):
        raise RuntimeError("Final Angebot finance stylesheet reference missing")
    if not any("tooltime-parity-finance.js" in tag for tag in asset_tags):
        raise RuntimeError("Final Angebot finance runtime reference missing")
    return editor, asset_tags


def patch_appointment_template(asset_tags: list[str]) -> None:
    rel = "templates/rebuild/appointment_detail.html"
    text = read(rel)

    if "tooltime_parity" not in text.split("{% block content %}", 1)[0]:
        text = replace_once(text, "{% load static %}", "{% load static tooltime_parity %}", "load ToolTime template tags")

    context_line = "{% tooltime_context request None 'authorization' as tt %}"
    if context_line not in text:
        text = replace_once(text, "{% block content %}", "{% block content %}\n" + context_line, "authorization ToolTime context")

    for tag in asset_tags:
        if tag not in text:
            text = text.replace(context_line, context_line + "\n" + tag, 1)

    form_start = text.find('<form method="post" enctype="multipart/form-data" action="{% url \'field-authorization-sign\' event.pk %}"')
    if form_start < 0:
        raise RuntimeError("Field authorization form start missing")
    form_tag_end = text.find(">", form_start)
    form_tag = text[form_start:form_tag_end + 1]
    if 'class="tt-document-form"' not in form_tag:
        replacement = form_tag[:-1]
        replacement += ' class="tt-document-form"'
        if "data-article-search-url=" not in replacement:
            replacement += ' data-article-search-url="{% url \'next-article-search\' %}"'
        replacement += ">"
        text = text[:form_start] + replacement + text[form_tag_end + 1:]

    heading = text.find("<b>Preisgrundlage</b>", form_start)
    sign_block = text.find('<div class="fa-block fa-sign-block">', heading)
    price_block_start = text.rfind('<div class="fa-block">', form_start, heading)
    if heading < 0 or sign_block < 0 or price_block_start < 0:
        raise RuntimeError("Field authorization price block bounds missing")

    price_block = '''<div class="fa-block fa-angebot-pricing">
        <div class="fa-block-head"><div><b>Preisgrundlage</b><small>Der Kunde sieht genau diese Positionen vor der Unterschrift.</small></div></div>
        <div class="fa-segmented fa-price-mode">{% for value,label in pricing_modes %}<label><input type="radio" name="pricing_mode" value="{{ value }}" {% if forloop.first %}checked{% endif %}><span>{{ label }}</span></label>{% endfor %}</div>
        {% include 'rebuild/_tooltime_services_editor.html' %}
        <div class="tt-authorization-calculation">
          {% include 'rebuild/_tooltime_calculation_summary.html' with kind='authorization' %}
        </div>
        <label data-cap-wrap hidden><span>Kostenlimit brutto</span><div class="tt-inline"><input class="nx-control" name="price_cap_gross" type="number" min="0" step="0.01" placeholder="optional"><span>€</span></div></label>
      </div>

      '''
    text = text[:price_block_start] + price_block + text[sign_block:]

    # The article browser and the new-position template are the same ones used by Angebote.
    form_start = text.find('class="tt-document-form"')
    form_close = text.find("</form>", form_start)
    if form_close < 0:
        raise RuntimeError("Field authorization form close missing")
    after_form = form_close + len("</form>")
    shared_extras = "\n{% include 'rebuild/_tooltime_article_modal.html' %}\n<template id=\"tt-position-template\">{% include 'rebuild/_tooltime_position.html' %}</template>"
    if "rebuild/_tooltime_article_modal.html" not in text:
        text = text[:after_form] + shared_extras + text[after_form:]

    if MARKER not in text:
        text = text.replace(context_line, context_line + "\n{# " + MARKER + " #}", 1)
    write(rel, text)


def patch_field_pricing_parser() -> None:
    """Read exactly the fields emitted by the shared Angebot position editor."""
    rel = "erp/services/field_authorization.py"
    text = read(rel)
    pattern = re.compile(r"def parse_items\(post\) -> list\[dict\[str, Any\]\]:\n.*?(?=\n\ndef totals_for_items\()", re.S)
    replacement = r'''def parse_items(post) -> list[dict[str, Any]]:
    descriptions = post.getlist("item_description")
    quantities = post.getlist("item_quantity")
    units = post.getlist("item_unit")
    purchases = post.getlist("item_purchase_price")
    markups = post.getlist("item_markup_percent")
    item_types = post.getlist("item_type")
    details = post.getlist("item_detail")
    groups = post.getlist("item_group")
    service_models = post.getlist("item_service_model")
    catalog_ids = post.getlist("item_catalog_id")
    discount_type = (post.get("discount_type") or "percent").strip()
    discount_value = max(Decimal("0"), money(post.get("discount_value") or "0"))
    tax_code = (post.get("document_tax_code") or "19").strip()
    document_tax_rate = Decimal("19") if tax_code == "19" else (Decimal("7") if tax_code == "7" else Decimal("0"))
    items: list[dict[str, Any]] = []
    for index, description in enumerate(descriptions):
        description = (description or "").strip()
        if not description:
            continue
        qty = max(Decimal("0"), money(quantities[index] if index < len(quantities) else "1"))
        purchase = max(Decimal("0"), money(purchases[index] if index < len(purchases) else "0"))
        markup = money(markups[index] if index < len(markups) else "0")
        unit_price = (purchase * (Decimal("1") + markup / Decimal("100"))).quantize(MONEY, rounding=ROUND_HALF_UP)
        line_net = (qty * unit_price).quantize(MONEY, rounding=ROUND_HALF_UP)
        line_tax = (line_net * document_tax_rate / Decimal("100")).quantize(MONEY, rounding=ROUND_HALF_UP)
        service_model = ((service_models[index] if index < len(service_models) else "normal") or "normal").strip()
        items.append({
            "position": len(items) + 1,
            "description": description[:500],
            "detail": ((details[index] if index < len(details) else "") or "")[:4000],
            "quantity": str(qty),
            "unit": ((units[index] if index < len(units) else "Stk.") or "Stk.")[:30],
            "purchase_price": str(purchase),
            "markup_percent": str(markup),
            "unit_price": str(unit_price),
            "tax_rate": str(document_tax_rate),
            "net": str(line_net),
            "tax": str(line_tax),
            "gross": str(line_net + line_tax),
            "item_type": ((item_types[index] if index < len(item_types) else "material") or "material")[:30],
            "group": ((groups[index] if index < len(groups) else "") or "")[:240],
            "service_model": service_model[:30],
            "catalog_id": ((catalog_ids[index] if index < len(catalog_ids) else "") or "").strip(),
            "included_in_total": service_model == "normal",
            "discount_type": discount_type,
            "discount_value": str(discount_value),
            "document_tax_rate": str(document_tax_rate),
        })
    return items
'''
    text, count = pattern.subn(replacement.rstrip(), text, count=1)
    if count != 1:
        raise RuntimeError("Field authorization parse_items function changed")

    totals_pattern = re.compile(r"def totals_for_items\(items: Iterable\[dict\[str, Any\]\]\) -> dict\[str, str\]:\n.*?(?=\n\ndef decode_signature\()", re.S)
    totals_replacement = r'''def totals_for_items(items: Iterable[dict[str, Any]]) -> dict[str, str]:
    rows = list(items)
    base_net = sum((money(item.get("net")) for item in rows if item.get("included_in_total", True)), Decimal("0"))
    if not rows:
        return {"net": "0.00", "tax": "0.00", "gross": "0.00"}
    discount_type = str(rows[0].get("discount_type") or "percent")
    discount_value = max(Decimal("0"), money(rows[0].get("discount_value") or "0"))
    discount = min(base_net, discount_value) if discount_type == "fixed" else (base_net * discount_value / Decimal("100"))
    taxable = max(Decimal("0"), base_net - discount).quantize(MONEY, rounding=ROUND_HALF_UP)
    rate = money(rows[0].get("document_tax_rate") or "19")
    tax = (taxable * rate / Decimal("100")).quantize(MONEY, rounding=ROUND_HALF_UP)
    return {"net": str(taxable), "tax": str(tax), "gross": str((taxable + tax).quantize(MONEY, rounding=ROUND_HALF_UP))}
'''
    text, count = totals_pattern.subn(totals_replacement.rstrip(), text, count=1)
    if count != 1:
        raise RuntimeError("Field authorization totals_for_items function changed")
    write(rel, text)


def patch_field_ai_adapter() -> None:
    """Keep the existing KI handoff, but write suggestions into Angebot rows."""
    rel = "static/js/field-authorization.js"
    text = read(rel)
    marker = "A+BAU ANGEBOT ROW ADAPTER 2026-09-08"
    if marker in text:
        return
    anchor = "    bindPricing(form);\n"
    if anchor not in text:
        raise RuntimeError("Field authorization bindPricing anchor changed")
    adapter = r'''    bindPricing(form);
    // A+BAU ANGEBOT ROW ADAPTER 2026-09-08
    if (!form._appendPriceItems) form._appendPriceItems = (items) => {
      const group = form.querySelector('[data-service-group]');
      const body = group?.querySelector('[data-group-body]');
      const template = document.querySelector('#tt-position-template');
      if (!body || !template) return;
      body.querySelectorAll('[data-position]').forEach((row) => row.remove());
      (items?.length ? items : [{}]).forEach((item) => {
        const row = template.content.firstElementChild.cloneNode(true);
        row.querySelector('[name=item_description]').value = item.description || '';
        row.querySelector('[name=item_quantity]').value = item.quantity || '1';
        row.querySelector('[name=item_unit]').value = item.unit || 'Stk.';
        row.querySelector('[name=item_purchase_price]').value = item.unit_price || '0.00';
        row.querySelector('[name=item_markup_percent]').value = '0';
        body.appendChild(row);
      });
      body.dispatchEvent(new Event('input', {bubbles:true}));
    };
'''
    text = text.replace(anchor, adapter, 1)
    write(rel, text)


def validate() -> None:
    editor = read("templates/rebuild/document_editor.html")
    appointment = read("templates/rebuild/appointment_detail.html")
    service = read("erp/services/field_authorization.py")
    field_js = read("static/js/field-authorization.js")
    for text, label in ((editor, "Angebot"), (appointment, "Termin")):
        if "rebuild/_tooltime_services_editor.html" not in text:
            raise RuntimeError(f"{label} does not use shared Angebot services editor")
        if "rebuild/_tooltime_calculation_summary.html" not in text:
            raise RuntimeError(f"{label} does not use shared Angebot calculation summary")
    required = [
        'class="tt-document-form"',
        "data-article-search-url",
        "rebuild/_tooltime_article_modal.html",
        "tt-position-template",
        "tooltime-parity-finance.css",
        "tooltime-parity-finance.js",
    ]
    for needle in required:
        if needle not in appointment:
            raise RuntimeError(f"Termin Angebot integration missing: {needle}")
    if "data-price-table" in appointment or "data-add-price-row" in appointment:
        raise RuntimeError("Legacy Termin price table still present")
    for field in ("item_purchase_price", "item_markup_percent", "item_service_model", "item_group", "item_type"):
        if field not in service:
            raise RuntimeError(f"Signed authorization snapshot missing Angebot field: {field}")
    if "A+BAU ANGEBOT ROW ADAPTER 2026-09-08" not in field_js:
        raise RuntimeError("Field KI adapter is not connected to shared Angebot rows")
    compile(service, "erp/services/field_authorization.py", "exec")


share_editor, assets = share_angebot_editor_parts()
patch_appointment_template(assets)
patch_field_pricing_parser()
patch_field_ai_adapter()
validate()
print("Termin-Freigabe und Angebote verwenden denselben Positionseditor, dieselbe Kalkulation und denselben Artikelbrowser.")
