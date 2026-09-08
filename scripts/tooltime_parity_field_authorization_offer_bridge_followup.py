from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MARKER = "A+BAU ANGEBOT/FREIGABE BRIDGE FOLLOWUP 2026-09-08"


def read(rel: str) -> str:
    path = ROOT / rel
    if not path.exists():
        raise RuntimeError(f"Angebot/Freigabe followup target missing: {rel}")
    return path.read_text(encoding="utf-8")


def write(rel: str, text: str) -> None:
    path = ROOT / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


# Appointment authorization is not a Quote/Invoice document. Keep ToolTime context
# document-less; the event is carried only on the shared article endpoint so the
# normal document-meta registry is never asked to resolve a CalendarEvent.
template_rel = "templates/rebuild/appointment_detail.html"
template = read(template_rel)
template = template.replace(
    "{% tooltime_context request event 'authorization' as tt %}",
    "{% tooltime_context request None 'authorization' as tt %}",
)
if "{% tooltime_context request None 'authorization' as tt %}" not in template:
    raise RuntimeError("Authorization ToolTime context missing")

form_match = re.search(r'<form\b(?=[^>]*data-authorization-form)[^>]*>', template, flags=re.S)
if not form_match:
    raise RuntimeError("Final authorization form tag missing")
form_tag = form_match.group(0)
class_attrs = re.findall(r'class="([^"]*)"', form_tag)
merged_classes: list[str] = []
for value in class_attrs:
    for name in value.split():
        if name not in merged_classes:
            merged_classes.append(name)
if "tt-document-form" not in merged_classes:
    merged_classes.append("tt-document-form")
form_tag = re.sub(r'\s+class="[^"]*"', "", form_tag)
form_tag = form_tag[:-1] + f' class="{" ".join(merged_classes)}">'
article_value = "{% url 'next-article-search' %}?event={{ event.pk }}"
if "data-article-search-url=" in form_tag:
    form_tag = re.sub(
        r'data-article-search-url="[^"]*"',
        f'data-article-search-url="{article_value}"',
        form_tag,
        count=1,
    )
else:
    form_tag = form_tag[:-1] + f' data-article-search-url="{article_value}">'
template = template[:form_match.start()] + form_tag + template[form_match.end():]
if MARKER not in template:
    context_line = "{% tooltime_context request None 'authorization' as tt %}"
    template = template.replace(context_line, context_line + "\n{# " + MARKER + " #}", 1)
write(template_rel, template)


# Reuse the exact Angebot article search. Field users remain blocked unless the
# event query parameter resolves through the normal field assignment check.
views_rel = "erp/tooltime_parity_views.py"
views = read(views_rel)
article_match = re.search(
    r"def article_search\(request\):\n.*?(?=\n\n@login_required|\Z)",
    views,
    flags=re.S,
)
if not article_match:
    raise RuntimeError("Final Angebot article_search function missing")
article_block = article_match.group(0)
old_guard = '    if base._is_field_user(request): return JsonResponse({"ok": False, "error": "Keine Preisberechtigung."}, status=403)\n'
new_guard = '''    if base._is_field_user(request):
        event_pk = (request.GET.get("event") or "").strip()
        if not event_pk.isdigit():
            return JsonResponse({"ok": False, "error": "Keine Preisberechtigung."}, status=403)
        from .field_authorization_views import _event_for as _field_event_for
        field_org, _field_event = _field_event_for(request, int(event_pk))
        if field_org.pk != org.pk:
            return JsonResponse({"ok": False, "error": "Keine Preisberechtigung."}, status=403)
'''
if new_guard not in article_block:
    if old_guard not in article_block:
        raise RuntimeError("Final Angebot field pricing permission guard changed")
    article_block = article_block.replace(old_guard, new_guard, 1)
    views = views[:article_match.start()] + article_block + views[article_match.end():]
write(views_rel, views)


# Exact Angebot position contract plus backend-only fallback for pre-refresh
# Termin/mobile clients that still post item_price/item_tax.
service_rel = "erp/services/field_authorization.py"
service = read(service_rel)
parse_pattern = re.compile(
    r"def parse_items\(post\) -> list\[dict\[str, Any\]\]:\n.*?(?=\n\ndef totals_for_items\()",
    flags=re.S,
)
parse_replacement = r'''def parse_items(post) -> list[dict[str, Any]]:
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
    legacy_prices = post.getlist("item_price")
    legacy_taxes = post.getlist("item_tax")
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
        angebot_contract = index < len(purchases) or index < len(markups)
        if angebot_contract:
            purchase = max(Decimal("0"), money(purchases[index] if index < len(purchases) else "0"))
            markup = money(markups[index] if index < len(markups) else "0")
            unit_price = (purchase * (Decimal("1") + markup / Decimal("100"))).quantize(MONEY, rounding=ROUND_HALF_UP)
            tax_rate = document_tax_rate
        else:
            unit_price = max(Decimal("0"), money(legacy_prices[index] if index < len(legacy_prices) else "0"))
            purchase = unit_price
            markup = Decimal("0")
            tax_rate = max(Decimal("0"), money(legacy_taxes[index] if index < len(legacy_taxes) else document_tax_rate))
        line_net = (qty * unit_price).quantize(MONEY, rounding=ROUND_HALF_UP)
        line_tax = (line_net * tax_rate / Decimal("100")).quantize(MONEY, rounding=ROUND_HALF_UP)
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
            "tax_rate": str(tax_rate),
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
            "pricing_contract": "angebot" if angebot_contract else "legacy",
        })
    return items
'''
service, count = parse_pattern.subn(parse_replacement.rstrip(), service, count=1)
if count != 1:
    raise RuntimeError("Shared Angebot authorization parse_items function changed")

totals_pattern = re.compile(
    r"def totals_for_items\(items: Iterable\[dict\[str, Any\]\]\) -> dict\[str, str\]:\n.*?(?=\n\ndef decode_signature\()",
    flags=re.S,
)
totals_replacement = r'''def totals_for_items(items: Iterable[dict[str, Any]]) -> dict[str, str]:
    rows = list(items)
    if not rows:
        return {"net": "0.00", "tax": "0.00", "gross": "0.00"}
    included = [item for item in rows if item.get("included_in_total", True)]
    if included and all(item.get("pricing_contract") == "legacy" for item in included):
        net = sum((money(item.get("net")) for item in included), Decimal("0")).quantize(MONEY, rounding=ROUND_HALF_UP)
        tax = sum((money(item.get("tax")) for item in included), Decimal("0")).quantize(MONEY, rounding=ROUND_HALF_UP)
        return {"net": str(net), "tax": str(tax), "gross": str((net + tax).quantize(MONEY, rounding=ROUND_HALF_UP))}
    base_net = sum((money(item.get("net")) for item in included), Decimal("0"))
    discount_type = str(rows[0].get("discount_type") or "percent")
    discount_value = max(Decimal("0"), money(rows[0].get("discount_value") or "0"))
    discount = min(base_net, discount_value) if discount_type == "fixed" else (base_net * discount_value / Decimal("100"))
    taxable = max(Decimal("0"), base_net - discount).quantize(MONEY, rounding=ROUND_HALF_UP)
    rate = money(rows[0].get("document_tax_rate") or "19")
    tax = (taxable * rate / Decimal("100")).quantize(MONEY, rounding=ROUND_HALF_UP)
    return {"net": str(taxable), "tax": str(tax), "gross": str((taxable + tax).quantize(MONEY, rounding=ROUND_HALF_UP))}
'''
service, count = totals_pattern.subn(totals_replacement.rstrip(), service, count=1)
if count != 1:
    raise RuntimeError("Shared Angebot authorization totals_for_items function changed")
write(service_rel, service)


# Keep only the Termin-specific Festpreis/Schätzung/Aufwand cap behavior. Position
# rows and all calculations stay owned by tooltime-parity-finance.js.
js_rel = "static/js/field-authorization.js"
js = read(js_rel)
cap_marker = "A+BAU ANGEBOT PRICING MODE CAP 2026-09-08"
if cap_marker not in js:
    anchor = "    // A+BAU ANGEBOT ROW ADAPTER 2026-09-08\n"
    if anchor not in js:
        raise RuntimeError("Shared Angebot row adapter missing from field runtime")
    snippet = r'''    // A+BAU ANGEBOT PRICING MODE CAP 2026-09-08
    const capWrap = form.querySelector('[data-cap-wrap]');
    const syncCap = () => {
      const mode = form.querySelector('input[name=pricing_mode]:checked')?.value || 'fixed';
      if (capWrap) capWrap.hidden = mode === 'fixed';
    };
    form.querySelectorAll('input[name=pricing_mode]').forEach((radio) => radio.addEventListener('change', syncCap));
    syncCap();
'''
    js = js.replace(anchor, snippet + anchor, 1)
write(js_rel, js)


# Historical contracts inspect document_editor.html directly. The production editor
# is now composed from shared partials, so expose a non-rendered snapshot generated
# from those exact partials. It cannot drift because assembly regenerates it.
editor_rel = "templates/rebuild/document_editor.html"
editor = read(editor_rel)
contract_start = "{% comment %} A+BAU SHARED ANGEBOT SOURCE CONTRACT 2026-09-08\n"
contract_end = "\nA+BAU SHARED ANGEBOT SOURCE CONTRACT END {% endcomment %}"
if contract_start in editor:
    editor = re.sub(
        re.escape(contract_start) + r".*?" + re.escape(contract_end),
        "",
        editor,
        flags=re.S,
    )
services_source = read("templates/rebuild/_tooltime_services_editor.html").replace("{% endcomment %}", "")
summary_source = read("templates/rebuild/_tooltime_calculation_summary.html").replace("{% endcomment %}", "")
contract = contract_start + services_source + "\n" + summary_source + contract_end
editor = editor.replace("{% endblock %}", contract + "\n{% endblock %}", 1)
write(editor_rel, editor)


# Dashboard action cache busting must not rewrite this independent finance asset.
base_rel = "templates/rebuild/base.html"
base = read(base_rel)
base = re.sub(
    r"ab-bau-v3-finance-mobile-pdf-hotfix\.css\?v=[^\"'\s<]+",
    "ab-bau-v3-finance-mobile-pdf-hotfix.css?v=20260908-finance-mobile-pdf-6",
    base,
)
write(base_rel, base)


legacy_test_rel = "tests/test_final_form_voice_pricing_hardening.py"
if (ROOT / legacy_test_rel).exists():
    legacy_test = read(legacy_test_rel)
    old_assert = '        self.assertIn("data-fa-catalog-picker", template)\n'
    new_assert = '''        self.assertIn("rebuild/_tooltime_services_editor.html", template)
        self.assertIn("rebuild/_tooltime_article_modal.html", template)
        self.assertNotIn("data-price-table", template)
'''
    if old_assert in legacy_test:
        legacy_test = legacy_test.replace(old_assert, new_assert, 1)
    elif "rebuild/_tooltime_services_editor.html" not in legacy_test:
        raise RuntimeError("Final form/pricing regression test compatibility anchor changed")
    write(legacy_test_rel, legacy_test)


write("tests/test_field_authorization_angebot_bridge_final.py", r'''from pathlib import Path
from django.test import SimpleTestCase


class FieldAuthorizationAngebotBridgeFinalTests(SimpleTestCase):
    def test_termin_uses_shared_angebot_editor(self):
        template = Path("templates/rebuild/appointment_detail.html").read_text(encoding="utf-8")
        for marker in (
            "{% tooltime_context request None 'authorization' as tt %}",
            "rebuild/_tooltime_services_editor.html",
            "rebuild/_tooltime_calculation_summary.html",
            "rebuild/_tooltime_article_modal.html",
            "tt-document-form",
            "next-article-search",
            "?event={{ event.pk }}",
        ):
            self.assertIn(marker, template)
        self.assertNotIn("data-price-table", template)
        self.assertNotIn("data-add-price-row", template)

    def test_event_scoped_article_permission_and_angebot_parser(self):
        views = Path("erp/tooltime_parity_views.py").read_text(encoding="utf-8")
        service = Path("erp/services/field_authorization.py").read_text(encoding="utf-8")
        self.assertIn('_field_event_for(request, int(event_pk))', views)
        self.assertIn('purchases = post.getlist("item_purchase_price")', service)
        self.assertIn('legacy_prices = post.getlist("item_price")', service)
        self.assertIn('"pricing_contract": "angebot" if angebot_contract else "legacy"', service)
''')


final_template = read(template_rel)
final_editor = read(editor_rel)
for needle in (
    "{% tooltime_context request None 'authorization' as tt %}",
    'class="tt-document-form',
    'data-article-search-url="{% url \'next-article-search\' %}?event={{ event.pk }}"',
    "rebuild/_tooltime_services_editor.html",
    "rebuild/_tooltime_calculation_summary.html",
    "rebuild/_tooltime_article_modal.html",
):
    if needle not in final_template:
        raise RuntimeError(f"Shared Angebot Termin form missing: {needle}")
if final_template.count('class="tt-document-form') != 1:
    raise RuntimeError("Authorization form must expose exactly one ToolTime document-form class")
if "data-price-table" in final_template or "data-add-price-row" in final_template:
    raise RuntimeError("Legacy Termin pricing table survived the Angebot integration")
for needle in (
    "Leistungsgruppe hinzufügen",
    'data-group-action="copy"',
    "document_tax_code",
    'data-tooltime-summary-parity="20260908"',
):
    if needle not in final_editor:
        raise RuntimeError(f"Shared editor source contract missing: {needle}")
if "ab-bau-v3-finance-mobile-pdf-hotfix.css?v=20260908-finance-mobile-pdf-6" not in read(base_rel):
    raise RuntimeError("Finance/mobile/PDF cache key drifted after final assembly")

print("Angebot/Freigabe bridge followup verified: canonical editor, safe event-scoped search, legacy POST fallback and source-contract compatibility are complete.")
