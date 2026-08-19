from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MARKER = "KAYI GLOBAL TIME PDF CATALOG UPGRADE 2026-08-20"
VERSION = "20260820-global-time-pdf-catalog-1"


def read(rel: str) -> str:
    path = ROOT / rel
    if not path.exists():
        raise RuntimeError(f"Missing upgrade target: {rel}")
    return path.read_text(encoding="utf-8")


def write(rel: str, text: str) -> None:
    path = ROOT / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def append_once(rel: str, marker: str, content: str) -> None:
    text = read(rel)
    if marker in text:
        return
    write(rel, text.rstrip() + "\n\n" + content.strip() + "\n")


def patch_time_inputs() -> None:
    time_pattern = re.compile(r'<input(?P<attrs>[^>]*\btype=["\'](?:time|datetime-local)["\'][^>]*)>', re.I)
    changed = 0
    for path in (ROOT / "templates").rglob("*.html"):
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue

        def repl(match: re.Match[str]) -> str:
            attrs = match.group("attrs")
            if re.search(r'\bstep\s*=', attrs, re.I):
                attrs = re.sub(r'\bstep\s*=\s*["\'][^"\']*["\']', 'step="600"', attrs, count=1, flags=re.I)
            else:
                attrs += ' step="600"'
            return f"<input{attrs}>"

        updated = time_pattern.sub(repl, text)
        if updated != text:
            path.write_text(updated, encoding="utf-8")
            changed += 1

    append_once(
        "static/js/kayi-next.js",
        "KAYI 10-MINUTE TIME GRID 2026-08-20",
        r'''
// KAYI 10-MINUTE TIME GRID 2026-08-20
(() => {
  const STEP_SECONDS = 600;
  const roundMinutes = (minutes) => Math.max(0, Math.min(1430, Math.round(minutes / 10) * 10));
  const normalize = (field) => {
    if (!(field instanceof HTMLInputElement) || !['time','datetime-local'].includes(field.type)) return;
    field.step = String(STEP_SECONDS);
    const raw = field.value;
    if (!raw) return;
    if (field.type === 'time') {
      const m = raw.match(/^(\d{2}):(\d{2})/); if (!m) return;
      const total = roundMinutes(Number(m[1]) * 60 + Number(m[2]));
      const next = `${String(Math.floor(total / 60)).padStart(2,'0')}:${String(total % 60).padStart(2,'0')}`;
      if (next !== raw.slice(0,5)) field.value = next;
      return;
    }
    const m = raw.match(/^(\d{4}-\d{2}-\d{2})T(\d{2}):(\d{2})/); if (!m) return;
    const total = roundMinutes(Number(m[2]) * 60 + Number(m[3]));
    const next = `${m[1]}T${String(Math.floor(total / 60)).padStart(2,'0')}:${String(total % 60).padStart(2,'0')}`;
    if (next !== raw.slice(0,16)) field.value = next;
  };
  const apply = (root=document) => root.querySelectorAll?.('input[type="time"],input[type="datetime-local"]').forEach((field) => { field.step = String(STEP_SECONDS); });
  document.addEventListener('change', (event) => normalize(event.target), true);
  document.addEventListener('blur', (event) => normalize(event.target), true);
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', () => apply()); else apply();
  new MutationObserver((records) => records.forEach((record) => record.addedNodes.forEach((node) => { if (node.nodeType === 1) { if (node.matches?.('input[type="time"],input[type="datetime-local"]')) node.step=String(STEP_SECONDS); apply(node); } }))).observe(document.documentElement, {childList:true, subtree:true});
})();
''',
    )
    print(f"10-minute time grid applied to {changed} template files plus dynamic inputs")


def install_live_pricing_api() -> None:
    write(
        "erp/live_pricing_views.py",
        r'''from __future__ import annotations

from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import JsonResponse
from django.views.decorators.http import require_GET

from . import models as m
from .rebuild_views import _is_field_user, _org


ZERO = Decimal("0")


def _price_item_payload(row):
    sales = getattr(row, "sales_price", None)
    purchase = getattr(row, "purchase_price", None)
    price = sales if sales is not None and sales > ZERO else purchase
    return {
        "kind": "price_item",
        "id": row.pk,
        "code": (getattr(row, "code", "") or "").strip(),
        "name": (getattr(row, "description", "") or "").strip(),
        "description": (getattr(row, "description", "") or "").strip(),
        "unit": (getattr(row, "unit", "") or "Stk.").strip(),
        "purchase_price": str(price or ZERO),
        "sales_price": str(price or ZERO),
        "tax_rate": str(getattr(row, "tax_rate", None) or "19"),
        "source": getattr(getattr(row, "source", None), "name", "") or "Preisliste",
    }


def _catalog_payload(row):
    purchase = getattr(row, "purchase_price", None) or ZERO
    sales = getattr(row, "sales_price", None) or ZERO
    effective = sales if sales > ZERO else purchase
    return {
        "kind": "catalog",
        "id": row.pk,
        "code": (getattr(row, "code", "") or "").strip(),
        "name": (getattr(row, "name", "") or "").strip(),
        "description": (getattr(row, "description", "") or "").strip(),
        "unit": (getattr(row, "unit", "") or "Stk.").strip(),
        "purchase_price": str(purchase if purchase > ZERO else effective),
        "sales_price": str(effective),
        "tax_rate": str(getattr(row, "tax_rate", None) or "19"),
        "source": "Leistungskatalog",
    }


def _is_owner_source(source) -> bool:
    summary = getattr(source, "import_summary", None)
    if isinstance(summary, dict) and summary.get("kind") in {"owner_upload", "customer_upload", "price_library_upload"}:
        return True
    name = (getattr(source, "name", "") or "").casefold()
    filename = (getattr(source, "original_filename", "") or "").casefold()
    return any(token in name or token in filename for token in ("privat", "eigene", "kunde", "customer", "kayi_p", "kayi p"))


def _matches_reference(source) -> bool:
    name = f"{getattr(source, 'name', '')} {getattr(source, 'original_filename', '')}".casefold()
    return any(token in name for token in ("b&o", "b+o", "b und o", "bo ", "va04", "referenz"))


@login_required
@require_GET
def live_pricing_search(request):
    if _is_field_user(request):
        return JsonResponse({"ok": False, "error": "Keine Preisberechtigung."}, status=403)
    org = _org(request)
    family = (request.GET.get("catalog") or "catalog").strip().lower()
    query = (request.GET.get("q") or "").strip()
    limit = max(5, min(int(request.GET.get("limit") or 30), 60))

    if family == "catalog":
        qs = m.CatalogItem.objects.filter(organization=org, active=True)
        if query:
            qs = qs.filter(Q(code__icontains=query) | Q(name__icontains=query) | Q(description__icontains=query))
        rows = list(qs.order_by("name")[:limit])
        return JsonResponse({"ok": True, "catalog": family, "results": [_catalog_payload(row) for row in rows]})

    source_qs = m.PriceSource.objects.filter(organization=org, active=True).order_by("name")
    sources = list(source_qs)
    if family == "own":
        selected = [source for source in sources if _is_owner_source(source)]
        if not selected:
            selected = [source for source in sources if not _matches_reference(source)]
    elif family == "reference":
        selected = [source for source in sources if _matches_reference(source)]
        if not selected:
            selected = [source for source in sources if not _is_owner_source(source)]
    else:
        selected = sources

    source_ids = [source.pk for source in selected]
    qs = m.PriceItem.objects.filter(organization=org, source_id__in=source_ids, source__active=True).select_related("source")
    qs = qs.filter(Q(sales_price__gt=0) | Q(purchase_price__gt=0))
    if query:
        qs = qs.filter(Q(code__icontains=query) | Q(description__icontains=query))
    rows = list(qs.order_by("source__name", "description")[:limit])
    return JsonResponse({"ok": True, "catalog": family, "results": [_price_item_payload(row) for row in rows]})
''',
    )

    urls_rel = "erp/rebuild_urls.py"
    urls = read(urls_rel)
    import_line = "from . import live_pricing_views as live_pricing\n"
    if import_line not in urls:
        anchor = "from . import rebuild_views as views\n"
        if anchor not in urls:
            raise RuntimeError("rebuild URL import anchor changed")
        urls = urls.replace(anchor, anchor + import_line, 1)
    route = '    path("pricing/live-search/", live_pricing.live_pricing_search, name="next-live-pricing-search"),\n'
    if route not in urls:
        path_anchor = 'urlpatterns = [\n'
        if path_anchor not in urls:
            raise RuntimeError("rebuild urlpatterns anchor changed")
        urls = urls.replace(path_anchor, path_anchor + route, 1)
    write(urls_rel, urls)


def patch_document_editor() -> None:
    rel = "templates/rebuild/document_editor.html"
    text = read(rel)
    if "data-live-pricing-url" not in text:
        text = text.replace(
            "data-ab-commercial-form",
            "data-ab-commercial-form data-live-pricing-url=\"{% url 'next-live-pricing-search' %}\"",
            1,
        )
    text = text.replace(
        'name="item_description"',
        'name="item_description" autocomplete="off" data-live-price-input',
    )
    if "data-live-catalog-family" not in text:
        search_anchor = '<div class="ab-catalog-search"><input class="nx-control" type="search"'
        selector = '''<div class="ab-catalog-family"><label>Preisquelle<select class="nx-control" data-live-catalog-family><option value="catalog">Leistungskatalog</option><option value="own">Eigene / Privat-Preisliste</option><option value="reference">Referenz / B&amp;O</option></select></label></div>\n      '''
        if search_anchor in text:
            text = text.replace(search_anchor, selector + search_anchor, 1)
        else:
            anchor = '<section class="nx-card ab-catalog-card">'
            if anchor not in text:
                raise RuntimeError("Document editor catalog card anchor changed")
            text = text.replace(anchor, anchor + selector, 1)
    write(rel, text)

    append_once(
        "static/js/kayi-next.js",
        "KAYI DIRECT POSITION LIVE PRICING 2026-08-20",
        r'''
// KAYI DIRECT POSITION LIVE PRICING 2026-08-20
(() => {
  const form = document.querySelector('[data-ab-commercial-form][data-live-pricing-url]');
  if (!form) return;
  const endpoint = form.dataset.livePricingUrl;
  const familySelect = form.querySelector('[data-live-catalog-family]');
  const panel = form.querySelector('[data-ab-catalog-list]');
  const panelSearch = form.querySelector('[data-ab-catalog-search]');
  const money = new Intl.NumberFormat('de-DE',{style:'currency',currency:'EUR'});
  let family = familySelect?.value || 'catalog';
  let timer = null;
  let requestSerial = 0;

  const esc = (value) => String(value ?? '').replace(/[&<>"']/g,(ch)=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
  const num = (value) => { const n=Number(String(value ?? '0').replace(',','.')); return Number.isFinite(n)?n:0; };
  const rowFor = (input) => input.closest('.ab-item-row');
  const setValue = (el, value) => { if (!el) return; el.value = value ?? ''; el.dispatchEvent(new Event('input',{bubbles:true})); el.dispatchEvent(new Event('change',{bubbles:true})); };

  const applyResult = (row, item) => {
    if (!row || !item) return;
    const price = num(item.sales_price || item.purchase_price);
    const purchase = num(item.purchase_price || item.sales_price || price);
    setValue(row.querySelector('[name=item_description]'), item.name || item.description || '');
    const detail = row.querySelector('[name=item_detail]'); if (detail && item.description && item.description !== item.name) setValue(detail, item.description);
    const unit = row.querySelector('[name=item_unit]'); if (unit && item.unit) { const option=[...unit.options].find(o=>o.value===item.unit||o.textContent.trim()===item.unit); if(option) setValue(unit, option.value); }
    setValue(row.querySelector('[name=item_purchase_price]'), purchase.toFixed(2));
    setValue(row.querySelector('[name=item_markup_percent]'), '0');
    setValue(row.querySelector('[name=item_price]'), price.toFixed(2));
    const catalogId = row.querySelector('[name=item_catalog_id]'); if (catalogId) catalogId.value = item.kind === 'catalog' ? (item.id || '') : '';
    row.dataset.priceSource = item.source || family;
    row.querySelector('[data-live-price-popover]')?.remove();
  };

  const fetchRows = async (q='', limit=30) => {
    const serial = ++requestSerial;
    const url = new URL(endpoint, window.location.origin); url.searchParams.set('catalog',family); url.searchParams.set('limit',String(limit)); if(q) url.searchParams.set('q',q);
    try { const response=await fetch(url,{headers:{'X-Requested-With':'XMLHttpRequest'}}); const data=await response.json(); if(serial!==requestSerial) return []; return data.ok&&Array.isArray(data.results)?data.results:[]; }
    catch (_) { return []; }
  };

  const resultButton = (item, row) => {
    const button=document.createElement('button'); button.type='button'; button.className='ab-live-price-option';
    button.innerHTML=`<span><b>${esc(item.name||item.description||'Position')}</b><small>${esc([item.code,item.unit,item.source].filter(Boolean).join(' · '))}</small></span><strong>${money.format(num(item.sales_price||item.purchase_price))}</strong>`;
    button.addEventListener('mousedown',(e)=>e.preventDefault());
    button.addEventListener('click',()=>applyResult(row,item));
    return button;
  };

  const showInline = async (input) => {
    const q=input.value.trim(); const row=rowFor(input); row?.querySelector('[data-live-price-popover]')?.remove(); if(q.length<2||!row) return;
    const rows=await fetchRows(q,8); if(!document.body.contains(input)||input.value.trim()!==q) return;
    const pop=document.createElement('div'); pop.className='ab-live-price-popover'; pop.dataset.livePricePopover='';
    rows.forEach(item=>pop.appendChild(resultButton(item,row)));
    if(!rows.length){ const empty=document.createElement('div'); empty.className='ab-live-price-empty'; empty.textContent='Keine passende Preisposition gefunden.'; pop.appendChild(empty); }
    input.parentElement.style.position='relative'; input.parentElement.appendChild(pop);
  };

  form.addEventListener('input',(event)=>{ const input=event.target.closest?.('[data-live-price-input]'); if(!input)return; clearTimeout(timer); timer=setTimeout(()=>showInline(input),180); });
  form.addEventListener('keydown',(event)=>{ const input=event.target.closest?.('[data-live-price-input]'); if(!input)return; const pop=rowFor(input)?.querySelector('[data-live-price-popover]'); if((event.key==='Enter'||event.key==='Tab')&&pop){ const first=pop.querySelector('.ab-live-price-option'); if(first){ if(event.key==='Enter')event.preventDefault(); first.click(); } } });
  form.addEventListener('focusout',(event)=>{ const input=event.target.closest?.('[data-live-price-input]'); if(input)setTimeout(()=>rowFor(input)?.querySelector('[data-live-price-popover]')?.remove(),160); });

  const renderPanel = async (q='') => {
    if(!panel)return; panel.innerHTML='<div class="nx-muted" style="padding:12px 16px">Preise werden geladen …</div>';
    const rows=await fetchRows(q,50); panel.innerHTML='';
    if(!rows.length){panel.innerHTML='<div class="nx-empty">Keine Positionen in dieser Preisquelle gefunden.</div>';return;}
    rows.forEach(item=>{ const button=document.createElement('button'); button.type='button'; button.className='ab-catalog-item'; button.innerHTML=`<span><b>${esc(item.name||item.description)}</b><small>${esc([item.code,item.unit,item.source].filter(Boolean).join(' · '))}</small></span><strong>${money.format(num(item.sales_price||item.purchase_price))}</strong>`; button.addEventListener('click',()=>{ const table=form.querySelector('[data-ab-items]'); const target=[...table.querySelectorAll('.ab-item-row')].find(r=>!r.querySelector('[name=item_description]')?.value.trim())||table.querySelector('.ab-item-row:last-of-type'); if(target) applyResult(target,item); }); panel.appendChild(button); });
  };

  familySelect?.addEventListener('change',()=>{ family=familySelect.value||'catalog'; if(panelSearch)panelSearch.value=''; renderPanel(''); });
  panelSearch?.addEventListener('input',(event)=>{ clearTimeout(timer); timer=setTimeout(()=>renderPanel(event.target.value.trim()),180); });
  renderPanel('');
})();
''',
    )

    append_once(
        "static/css/kayi-next.css",
        "KAYI DIRECT POSITION LIVE PRICING 2026-08-20",
        r'''
/* KAYI DIRECT POSITION LIVE PRICING 2026-08-20 */
.ab-catalog-family{padding:0 16px 12px}.ab-catalog-family label{display:grid;gap:6px;font-size:12px;font-weight:800}.ab-live-price-popover{position:absolute;z-index:80;left:0;right:0;top:calc(100% + 4px);background:#fff;border:1px solid var(--nx-line,#dfe4e7);border-radius:12px;box-shadow:0 14px 38px rgba(17,24,39,.14);max-height:300px;overflow:auto;padding:5px}.ab-live-price-option{width:100%;border:0;background:#fff;display:flex;justify-content:space-between;align-items:center;gap:12px;padding:9px 10px;border-radius:9px;text-align:left;cursor:pointer}.ab-live-price-option:hover,.ab-live-price-option:focus{background:#f7f4ea;outline:none}.ab-live-price-option span{display:grid;gap:2px;min-width:0}.ab-live-price-option b{white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.ab-live-price-option small{color:#6b7280;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.ab-live-price-option strong{white-space:nowrap;color:#5b4615}.ab-live-price-empty{padding:10px;color:#6b7280;font-size:12px}
''',
    )


def install_business_pdf_identity() -> None:
    write(
        "erp/services/business_pdf_identity.py",
        r"""from __future__ import annotations

import html
from datetime import date, datetime


def _settings(org):
    raw = getattr(org, "settings", None)
    return raw if isinstance(raw, dict) else {}


def _first(org, *keys, default=""):
    settings = _settings(org)
    for key in keys:
        value = getattr(org, key, None)
        if value not in (None, ""):
            return str(value).strip()
        value = settings.get(key)
        if value not in (None, ""):
            return str(value).strip()
    legal = settings.get("legal") if isinstance(settings.get("legal"), dict) else {}
    for key in keys:
        value = legal.get(key)
        if value not in (None, ""):
            return str(value).strip()
    return default


def business_identity(org):
    street = _first(org, "street", "address_street", "company_street")
    house = _first(org, "house_number", "street_number", "address_number")
    postal = _first(org, "postal_code", "zip", "zipcode", "address_zip")
    city = _first(org, "city", "address_city")
    country = _first(org, "country", "address_country", default="Deutschland")
    return {
        "name": _first(org, "legal_name", "company_name", "name", default="KAYI Haustechnik"),
        "street": " ".join(part for part in (street, house) if part),
        "city_line": " ".join(part for part in (postal, city) if part),
        "country": country,
        "email": _first(org, "email", "company_email"),
        "phone": _first(org, "phone", "company_phone", "telephone"),
        "website": _first(org, "website", "url"),
        "tax_number": _first(org, "tax_number", "steuer_number", "steuernummer"),
        "vat_id": _first(org, "vat_id", "vat_number", "ust_id", "ustid", "umsatzsteuer_id"),
        "register": _first(org, "commercial_register", "register_number", "handelsregister"),
        "register_court": _first(org, "register_court", "amtsgericht"),
        "managing_director": _first(org, "managing_director", "geschaeftsfuehrer", "geschäftsführer", "owner_name"),
        "iban": _first(org, "iban", "bank_iban"),
        "bic": _first(org, "bic", "bank_bic"),
        "bank": _first(org, "bank_name", "bank"),
    }


def _e(value):
    return html.escape(str(value or ""))


def legal_footer_html(org):
    d = business_identity(org)
    address = " · ".join(part for part in (d["street"], d["city_line"], d["country"]) if part)
    tax = " · ".join(part for part in (f"Steuernr. {d['tax_number']}" if d['tax_number'] else "", f"USt-IdNr. {d['vat_id']}" if d['vat_id'] else "") if part)
    register = " · ".join(part for part in (f"{d['register_court']} {d['register']}".strip() if d['register'] else "", f"Geschäftsführung: {d['managing_director']}" if d['managing_director'] else "") if part)
    bank = " · ".join(part for part in (d["bank"], f"IBAN {d['iban']}" if d['iban'] else "", f"BIC {d['bic']}" if d['bic'] else "") if part)
    lines = [address, tax, register, bank]
    return '<div class="kayi-legal-footer">' + ''.join(f'<div>{_e(line)}</div>' for line in lines if line) + '</div>'


def document_reference_html(document, document_kind: str):
    if document is None:
        return ""
    number = getattr(document, "number", "") or ""
    issue = getattr(document, "issue_date", None)
    if isinstance(issue, (date, datetime)):
        issue = issue.strftime("%d.%m.%Y")
    label = "Angebotsnummer" if document_kind.lower().startswith("angebot") else "Rechnungsnummer" if document_kind.lower().startswith("rechnung") else "Dokumentnummer"
    parts = [f"{label}: {number}" if number else "", f"Datum: {issue}" if issue else ""]
    return '<div class="kayi-document-reference">' + ' · '.join(_e(part) for part in parts if part) + '</div>'


def inject_business_pdf_identity(source_html: str, *, org, document=None, document_kind="Dokument") -> str:
    if not source_html or "KAYI_BUSINESS_PDF_IDENTITY_20260820" in source_html:
        return source_html
    identity = business_identity(org)
    contact = " · ".join(part for part in (identity["email"], identity["phone"], identity["website"]) if part)
    header = f'''<!-- KAYI_BUSINESS_PDF_IDENTITY_20260820 --><div class="kayi-business-header"><b>{_e(identity['name'])}</b><span>{_e(contact)}</span></div>{document_reference_html(document, document_kind)}'''
    standard = '''<div class="kayi-document-standard"><span>Alle Beträge gemäß ausgewiesener Umsatzsteuer.</span><span>Zahlungs- und Leistungsbedingungen ergeben sich aus dem jeweiligen Dokument und den vereinbarten Vertragsunterlagen.</span></div>'''
    css = '''<style>.kayi-business-header{display:flex;justify-content:space-between;gap:16px;align-items:flex-start;border-bottom:1px solid #dfe5e7;padding:0 0 7px;margin:0 0 10px;font-size:9px}.kayi-business-header b{font-size:13px}.kayi-business-header span{text-align:right;color:#68737a}.kayi-document-reference{font-size:9px;font-weight:700;margin:-4px 0 10px;color:#465158}.kayi-document-standard{border-top:1px solid #e3e7e8;margin-top:10px;padding-top:6px;font-size:7.5px;color:#6d777e;display:grid;gap:2px}.kayi-legal-footer{border-top:1px solid #dfe5e7;margin-top:7px;padding-top:6px;font-size:7.5px;line-height:1.35;color:#68737a;display:grid;gap:2px}</style>'''
    if "</head>" in source_html:
        source_html = source_html.replace("</head>", css + "</head>", 1)
    if "<body" in source_html:
        source_html = re_sub_body(source_html, header)
    footer = standard + legal_footer_html(org)
    if "</body>" in source_html:
        source_html = source_html.replace("</body>", footer + "</body>", 1)
    else:
        source_html += footer
    return source_html


def re_sub_body(source_html: str, header: str) -> str:
    import re
    return re.sub(r"(<body[^>]*>)", r"\1" + header, source_html, count=1, flags=re.I)
""",
    )

    service_rel = "erp/services/field_authorization.py"
    service = read(service_rel)
    import_line = "from erp.services.business_pdf_identity import inject_business_pdf_identity\n"
    if import_line not in service:
        anchor = "from erp import models as m\n"
        if anchor in service:
            service = service.replace(anchor, anchor + import_line, 1)
    shell = re.search(r"def _pdf_html_shell\(org, title: str, body: str\) -> str:\n(?P<body>.*?)(?=\n\ndef |\Z)", service, re.S)
    if shell and "inject_business_pdf_identity(source_html" not in shell.group(0):
        old = shell.group(0)
        body_text = shell.group("body")
        return_match = re.search(r"(?P<indent>    )return (?P<expr>f?'''[\s\S]*?''')\s*$", body_text)
        if return_match:
            expr = return_match.group("expr")
            replacement_body = body_text[:return_match.start()] + f"    source_html = {expr}\n    return inject_business_pdf_identity(source_html, org=org, document_kind=title)\n"
            service = service.replace(old, "def _pdf_html_shell(org, title: str, body: str) -> str:\n" + replacement_body, 1)
    write(service_rel, service)

    views_rel = "erp/rebuild_views.py"
    views = read(views_rel)
    helper_import = "from .services.business_pdf_identity import inject_business_pdf_identity\n"
    if helper_import not in views:
        anchor = "from . import models as m\n"
        if anchor in views:
            views = views.replace(anchor, anchor + helper_import, 1)
        else:
            first_django = views.find("from django")
            views = views[:first_django] + helper_import + views[first_django:] if first_django >= 0 else helper_import + views

    def patch_function(text: str, needle: str, doc_var: str, kind: str) -> str:
        starts = [m.start() for m in re.finditer(rf"^def\s+\w*{needle}\w*\s*\(", text, re.M | re.I)]
        offset = 0
        for start in starts:
            start += offset
            next_def = re.search(r"^def\s+|^@", text[start + 1 :], re.M)
            end = start + 1 + next_def.start() if next_def else len(text)
            block = text[start:end]
            if "inject_business_pdf_identity" in block:
                continue
            conv = re.search(r"(?P<indent>\s*)(?P<lhs>\w+)\s*=\s*html_to_pdf_bytes\((?P<htmlvar>\w+)\)", block)
            if not conv:
                continue
            htmlvar = conv.group("htmlvar")
            org_expr = "org" if re.search(r"\borg\s*=", block) else f"{doc_var}.organization"
            line = f'{conv.group("indent")}{htmlvar} = inject_business_pdf_identity({htmlvar}, org={org_expr}, document={doc_var}, document_kind="{kind}")\n'
            pos = conv.start()
            new_block = block[:pos] + line + block[pos:]
            text = text[:start] + new_block + text[end:]
            offset += len(new_block) - len(block)
        return text

    views = patch_function(views, "quote", "quote", "Angebot")
    views = patch_function(views, "invoice", "invoice", "Rechnung")
    write(views_rel, views)


def install_tests() -> None:
    write(
        "tests/test_global_time_pdf_catalog_upgrade.py",
        r'''from pathlib import Path
from django.test import SimpleTestCase

R = Path(__file__).resolve().parents[1]


class GlobalTimePdfCatalogUpgradeTests(SimpleTestCase):
    def test_global_time_grid_is_ten_minutes(self):
        js = (R / "static/js/kayi-next.js").read_text(encoding="utf-8")
        self.assertIn("KAYI 10-MINUTE TIME GRID 2026-08-20", js)
        self.assertIn("STEP_SECONDS = 600", js)

    def test_document_positions_have_live_price_typeahead_and_three_sources(self):
        template = (R / "templates/rebuild/document_editor.html").read_text(encoding="utf-8")
        js = (R / "static/js/kayi-next.js").read_text(encoding="utf-8")
        for marker in ("data-live-catalog-family", "data-live-price-input", "Eigene / Privat-Preisliste", "Referenz / B&amp;O"):
            self.assertIn(marker, template)
        self.assertIn("KAYI DIRECT POSITION LIVE PRICING 2026-08-20", js)
        self.assertTrue((R / "erp/live_pricing_views.py").exists())

    def test_pdf_identity_helper_exists(self):
        helper = (R / "erp/services/business_pdf_identity.py").read_text(encoding="utf-8")
        for marker in ("Angebotsnummer", "Rechnungsnummer", "Steuernr.", "USt-IdNr.", "Geschäftsführung"):
            self.assertIn(marker, helper)
''',
    )


def main() -> None:
    patch_time_inputs()
    install_live_pricing_api()
    patch_document_editor()
    install_business_pdf_identity()
    install_tests()
    print(MARKER + " installed")


if __name__ == "__main__":
    main()
