from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MARKER = "A+BAU RUNTIME UX + PERFORMANCE HOTFIX 2026-08-12"
VERSION = "20260812-runtime-2"


def read(rel: str) -> str:
    path = ROOT / rel
    if not path.exists():
        raise RuntimeError(f"A+Bau runtime hotfix target missing: {rel}")
    return path.read_text(encoding="utf-8")


def write(rel: str, text: str) -> None:
    path = ROOT / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def patch_time_tracking() -> None:
    # The field page loads both kayi-next.js and field-authorization.js. Both used
    # to bind the same time button, producing two concurrent POSTs. The second
    # handler also called response.json() directly, which surfaced Django HTML
    # error/CSRF pages as "Unexpected token '<'" in the UI.
    rel = "static/js/field-authorization.js"
    js = read(rel)
    old = "bindCustomerMode(); $$('[data-voice-button]').forEach(speechButton); bindPhotos(); bindAuthorization(); bindCompletion(); bindTimeToggle(); bindRevisionToggle();"
    new = "bindCustomerMode(); $$('[data-voice-button]').forEach(speechButton); bindPhotos(); bindAuthorization(); bindCompletion(); /* global kayi-next.js owns Zeiterfassung */ bindRevisionToggle();"
    if new not in js:
        if old not in js:
            raise RuntimeError("Field time-toggle init anchor changed")
        js = js.replace(old, new, 1)
    write(rel, js)

    rel = "static/js/kayi-next.js"
    js = read(rel)
    anchor = "  $$('[data-time-toggle]').forEach((button) => {\n    button.addEventListener('click', async () => {"
    replacement = "  $$('[data-time-toggle]').forEach((button) => {\n    if (button.dataset.abTimeBound === '1') return;\n    button.dataset.abTimeBound = '1';\n    button.addEventListener('click', async () => {"
    if replacement not in js:
        if anchor not in js:
            raise RuntimeError("Global time-toggle binding anchor changed")
        js = js.replace(anchor, replacement, 1)
    write(rel, js)

    rel = "erp/field_authorization_views.py"
    views = read(rel)
    csrf_import = "from django.views.decorators.csrf import ensure_csrf_cookie\n"
    if csrf_import not in views:
        anchor = "from django.views.decorators.http import require_GET, require_http_methods, require_POST\n"
        if anchor not in views:
            raise RuntimeError("Field authorization decorator import anchor changed")
        views = views.replace(anchor, anchor + csrf_import, 1)
    decorated = "@login_required\n@ensure_csrf_cookie\ndef field_job_detail(request, pk):"
    if decorated not in views:
        anchor = "@login_required\ndef field_job_detail(request, pk):"
        if anchor not in views:
            raise RuntimeError("field_job_detail decorator anchor changed")
        views = views.replace(anchor, decorated, 1)
    write(rel, views)


def install_fast_catalog_endpoint() -> None:
    write("erp/ab_bau_catalog_views.py", r'''from __future__ import annotations

from decimal import Decimal

from django.db.models import Q
from django.http import JsonResponse
from django.views.decorators.http import require_GET
from django.contrib.auth.decorators import login_required

from . import models as m
from .rebuild_views import _is_field_user, _org

ZERO = Decimal("0")


def _price(item):
    if item.sales_price is not None and item.sales_price > ZERO:
        return item.sales_price
    if item.purchase_price is not None and item.purchase_price > ZERO:
        return item.purchase_price
    return ZERO


@login_required
@require_GET
def catalog_quick_search(request):
    if _is_field_user(request):
        return JsonResponse({"ok": False, "error": "Keine Preisberechtigung."}, status=403)
    org = _org(request)
    query = (request.GET.get("q") or "").strip()
    if len(query) < 2:
        return JsonResponse({"ok": True, "query": query, "results": []})
    rows = list(
        m.CatalogItem.objects.filter(organization=org, active=True)
        .filter(Q(name__icontains=query) | Q(code__icontains=query) | Q(description__icontains=query))
        .filter(Q(sales_price__gt=0) | Q(purchase_price__gt=0))
        .only("id", "code", "name", "description", "unit", "kind", "purchase_price", "sales_price")
        .order_by("name")[:24]
    )
    return JsonResponse({
        "ok": True,
        "query": query,
        "results": [
            {
                "id": item.pk,
                "code": item.code or "",
                "name": item.name or "",
                "description": item.description or "",
                "unit": item.unit or "Stk.",
                "kind": item.kind or "material",
                "purchase": str(item.purchase_price or ZERO),
                "sales": str(_price(item)),
            }
            for item in rows
        ],
    })
''')

    rel = "erp/rebuild_urls.py"
    urls = read(rel)
    import_line = "from . import ab_bau_catalog_views as ab_catalog\n"
    if import_line not in urls:
        anchor = "from . import bo_direct_search_views as bo_search\n"
        if anchor not in urls:
            raise RuntimeError("A+Bau catalog URL import anchor changed")
        urls = urls.replace(anchor, anchor + import_line, 1)
    route = '    path("pricing/catalog/search/", ab_catalog.catalog_quick_search, name="next-catalog-quick-search"),\n'
    if route not in urls:
        anchor = '    path("pricing/bando/search/", bo_search.bo_price_search, name="next-bo-price-search"),\n'
        if anchor not in urls:
            raise RuntimeError("A+Bau catalog URL route anchor changed")
        urls = urls.replace(anchor, anchor + route, 1)
    write(rel, urls)


def patch_offer_load_path() -> None:
    rel = "erp/rebuild_views.py"
    views = read(rel)
    helper = r'''

def _fast_catalog_preview(org, limit=18):
    """Render only a small, already-priced local shortlist on first paint.

    Full B&O/VA04 discovery is intentionally asynchronous. This keeps opening a
    new Angebot/Rechnung independent of the size of the imported price library.
    """
    rows = list(
        m.CatalogItem.objects.filter(organization=org, active=True)
        .filter(Q(sales_price__gt=0) | Q(purchase_price__gt=0))
        .only("id", "code", "name", "description", "unit", "kind", "purchase_price", "sales_price")
        .order_by("name")[: max(1, min(int(limit or 18), 40))]
    )
    for item in rows:
        local_price = _money(item.sales_price) if _money(item.sales_price) > 0 else _money(item.purchase_price)
        item.effective_sales_price = local_price
        item.effective_price_source = "A+Bau-Vorlage"
        item.effective_price_source_kind = "A+Bau"
        item.effective_price_reference_code = item.code or ""
        item.effective_price_match_kind = "local"
    return rows
'''
    if "def _fast_catalog_preview(org, limit=18):" not in views:
        anchor = "\n\n@login_required\n@require_http_methods([\"GET\", \"POST\"])\ndef quote_editor(request, pk=None):"
        if anchor not in views:
            raise RuntimeError("Fast catalog helper insertion anchor changed")
        views = views.replace(anchor, helper + anchor, 1)

    quote_old = '    catalog = [item for item in catalog_with_effective_prices(org, limit=500) if item.effective_sales_price > Decimal("0")]\n'
    if quote_old in views:
        views = views.replace(quote_old, "    catalog = _fast_catalog_preview(org)\n", 1)
    elif "    catalog = _fast_catalog_preview(org)\n" not in views:
        raise RuntimeError("Offer catalog performance anchor changed")

    invoice_old = '        "catalog": [item for item in catalog_with_effective_prices(org, limit=500) if item.effective_sales_price > Decimal("0")],\n'
    if invoice_old in views:
        views = views.replace(invoice_old, '        "catalog": _fast_catalog_preview(org),\n', 1)
    elif '        "catalog": _fast_catalog_preview(org),\n' not in views:
        raise RuntimeError("Invoice catalog performance anchor changed")
    write(rel, views)

    # Align the older direct-search contract test with the deliberate lazy-load
    # architecture. The B&O endpoint remains the authoritative original-price path.
    test_rel = "tests/test_bo_direct_search.py"
    if (ROOT / test_rel).exists():
        tests = read(test_rel)
        tests = tests.replace(
            "self.assertGreaterEqual(views.count('effective_sales_price > Decimal(\"0\")'), 2)",
            'self.assertGreaterEqual(views.count("_fast_catalog_preview(org)"), 2)',
        )
        write(test_rel, tests)


def patch_document_editor() -> None:
    rel = "templates/rebuild/document_editor.html"
    template = read(rel)
    old = '<div class="ab-catalog-search"><input class="nx-control" type="search" placeholder="Katalog durchsuchen …" data-ab-catalog-search></div>'
    new = '''<div class="ab-catalog-search" data-ab-catalog-shell data-ab-catalog-search-url="{% url 'next-catalog-quick-search' %}"><input class="nx-control" type="search" placeholder="A+Bau-Vorlagen durchsuchen …" data-ab-catalog-search autocomplete="off"><small class="nx-muted" data-ab-catalog-status>Schnellzugriff: bereits bepreiste Vorlagen. Suche ab 2 Zeichen.</small></div>'''
    if new not in template:
        if old not in template:
            raise RuntimeError("Catalog search template anchor changed")
        template = template.replace(old, new, 1)

    # Keep result-heavy blocks compact so a search never turns the editor into a
    # several-screen-long page.
    template = re.sub(r"(bo-direct-search\.js' %\}\?v=)[^\"']+", rf"\g<1>{VERSION}", template)
    write(rel, template)

    rel = "static/js/kayi-next.js"
    js = read(rel)
    old = r'''  $$('[data-ab-catalog]').forEach((button)=>button.addEventListener('click',()=>{const table=$('[data-ab-items]');if(!table)return;const kind=button.dataset.kind||'material';const type=kind==='service'?'labour':(kind==='material'?'material':'other');const purchase=abNum(button.dataset.purchase)>0?button.dataset.purchase:(button.dataset.sales||0);abInsertRow(table,{catalogId:button.dataset.id,description:button.dataset.name,detail:button.dataset.description,unit:button.dataset.unit,purchase,type});}));
  $('[data-ab-catalog-search]')?.addEventListener('input',(e)=>{const q=e.target.value.trim().toLocaleLowerCase('de-DE');$$('[data-ab-catalog]').forEach((button)=>button.hidden=!!q&&!button.textContent.toLocaleLowerCase('de-DE').includes(q));});'''
    new = r'''  const abUseCatalogButton = (button) => {const table=$('[data-ab-items]');if(!table)return;const kind=button.dataset.kind||'material';const type=kind==='service'?'labour':(kind==='material'?'material':'other');const purchase=abNum(button.dataset.purchase)>0?button.dataset.purchase:(button.dataset.sales||0);abInsertRow(table,{catalogId:button.dataset.id,description:button.dataset.name,detail:button.dataset.description,unit:button.dataset.unit,purchase,type});};
  document.addEventListener('click',(event)=>{const button=event.target.closest('[data-ab-catalog]');if(!button)return;abUseCatalogButton(button);});
  const abCatalogShell=$('[data-ab-catalog-shell]'),abCatalogInput=$('[data-ab-catalog-search]'),abCatalogList=$('[data-ab-catalog-list]'),abCatalogStatus=$('[data-ab-catalog-status]');
  const abCatalogInitial=abCatalogList?.innerHTML||'';let abCatalogTimer=null,abCatalogController=null;
  const abCatalogButton=(item)=>{const button=document.createElement('button');button.type='button';button.className='ab-catalog-item';button.dataset.abCatalog='';button.dataset.id=item.id||'';button.dataset.name=item.name||'';button.dataset.description=item.description||'';button.dataset.unit=item.unit||'Stk.';button.dataset.purchase=item.purchase||'0';button.dataset.sales=item.sales||'0';button.dataset.kind=item.kind||'material';const span=document.createElement('span'),title=document.createElement('b'),meta=document.createElement('small'),price=document.createElement('strong');title.textContent=item.name||item.code||'Position';meta.textContent=`${item.code||'ohne Code'} · ${item.unit||'Stk.'}`;price.textContent=abMoney.format(abNum(item.sales));span.append(title,meta);button.append(span,price);return button;};
  const abCatalogSearch=async()=>{if(!abCatalogInput||!abCatalogList||!abCatalogShell)return;const q=abCatalogInput.value.trim();if(q.length<2){abCatalogController?.abort();abCatalogList.innerHTML=abCatalogInitial;if(abCatalogStatus)abCatalogStatus.textContent='Schnellzugriff: bereits bepreiste Vorlagen. Suche ab 2 Zeichen.';return;}abCatalogController?.abort();abCatalogController=new AbortController();if(abCatalogStatus)abCatalogStatus.textContent='Vorlagen werden gesucht …';try{const url=new URL(abCatalogShell.dataset.abCatalogSearchUrl,window.location.origin);url.searchParams.set('q',q);const response=await fetch(url,{credentials:'same-origin',headers:{'Accept':'application/json','X-Requested-With':'XMLHttpRequest'},signal:abCatalogController.signal});const raw=await response.text();let data={};try{data=raw?JSON.parse(raw):{};}catch(_){throw new Error('Katalogsuche hat keine gültige Serverantwort erhalten.');}if(!response.ok||data.ok===false)throw new Error(data.error||'Katalogsuche fehlgeschlagen.');abCatalogList.innerHTML='';(data.results||[]).forEach((item)=>abCatalogList.appendChild(abCatalogButton(item)));if(!(data.results||[]).length)abCatalogList.innerHTML='<div class="nx-empty">Keine bepreiste A+Bau-Vorlage gefunden. Für Originalpreise bitte die B&O-Suche darüber verwenden.</div>';if(abCatalogStatus)abCatalogStatus.textContent=`${(data.results||[]).length} passende Vorlagen`; }catch(error){if(error.name==='AbortError')return;if(abCatalogStatus)abCatalogStatus.textContent=error.message||'Katalogsuche fehlgeschlagen.';}};
  abCatalogInput?.addEventListener('input',()=>{clearTimeout(abCatalogTimer);abCatalogTimer=setTimeout(abCatalogSearch,260);});
  abCatalogInput?.addEventListener('keydown',(event)=>{if(event.key==='Enter'){event.preventDefault();clearTimeout(abCatalogTimer);abCatalogSearch();}});'''
    if new not in js:
        if old not in js:
            raise RuntimeError("A+Bau catalog JavaScript anchor changed")
        js = js.replace(old, new, 1)
    write(rel, js)


def patch_bo_results() -> None:
    rel = "erp/bo_direct_search_views.py"
    views = read(rel)
    views = views.replace("rows = search_bo_prices(org, query, limit=30)", "rows = search_bo_prices(org, query, limit=12)")
    write(rel, views)


def patch_visuals_and_cache() -> None:
    rel = "static/css/kayi-next.css"
    css = read(rel)
    if MARKER not in css:
        css += r'''

/* A+BAU RUNTIME UX + PERFORMANCE HOTFIX 2026-08-12 */
@media(min-width:1181px){body:has(.ab-document-form) .nx-content{max-width:1600px!important;padding-left:24px!important;padding-right:24px!important}.ab-document-bottom{grid-template-columns:minmax(0,1fr) 360px!important}}
.ab-document-meta{padding:20px!important}.ab-document-meta .nx-form-grid{gap:14px 18px}.ab-services-card>.nx-card-head{padding-bottom:12px}.ab-item-table{min-width:1320px!important}.ab-item-table thead th{position:sticky;top:0;z-index:3;background:#fbfaf7;box-shadow:0 1px 0 var(--nx-line)}.ab-item-table th,.ab-item-table td{font-size:12px}.ab-item-table .nx-control{font-size:13px}.ab-item-table th:nth-child(6),.ab-title-cell{min-width:300px!important}.ab-detail{min-height:48px;max-height:110px}.ab-item-row:hover td{background:#fffdf8}.ab-item-subrow td{background:#f8f8f7!important}.ab-item-subrow td[colspan]{padding:5px 10px 10px 126px}.ab-item-subrow label{justify-content:flex-start}.ab-bo-direct{margin:0 16px 14px;padding:14px;border:1px solid #e8e1d2;border-radius:14px;background:#fcfaf4}.ab-bo-direct h3{margin:3px 0 4px}.ab-bo-results{display:grid;gap:7px;max-height:360px;overflow:auto;overscroll-behavior:contain;padding-right:3px;margin-top:10px}.ab-bo-results .bo-direct-result{min-height:54px}.ab-catalog-divider{margin:0 16px 12px;padding-top:2px}.ab-catalog-divider{display:flex;align-items:baseline;justify-content:space-between;gap:12px}.ab-catalog-divider small{color:#72777d}.ab-catalog-search{display:grid;gap:6px}.ab-catalog-list{max-height:360px!important;overscroll-behavior:contain}.ab-catalog-item{min-height:52px}.ab-summary-card{border-top:3px solid #c9a13b}.ab-summary-lines>div{padding:2px 0}.ab-summary-controls .nx-control{min-height:40px}.ab-closing-card textarea{min-height:150px}.ab-document-form>.nx-form-actions{padding-top:2px}
@media(max-width:1180px){body:has(.ab-document-form) .nx-content{padding-left:14px!important;padding-right:14px!important}.ab-bo-direct{margin-left:12px;margin-right:12px}.ab-item-subrow td[colspan]{padding-left:12px}}
@media(max-width:720px){.ab-bo-results,.ab-catalog-list{max-height:300px!important}.ab-document-meta{padding:15px!important}.ab-item-table{min-width:0!important}.ab-item-subrow td[colspan]{padding:8px!important}}
'''
    write(rel, css)

    rel = "templates/rebuild/base.html"
    base = read(rel)
    base = re.sub(r"(kayi-next\.css' %\}\?v=)[^\"']+", rf"\g<1>{VERSION}", base)
    base = re.sub(r"(kayi-next\.js' %\}\?v=)[^\"']+", rf"\g<1>{VERSION}", base)
    write(rel, base)

    rel = "templates/rebuild/appointment_detail.html"
    template = read(rel)
    template = re.sub(r"(field-authorization\.css' %\}\?v=)[^\"']+", rf"\g<1>{VERSION}", template)
    template = re.sub(r"(field-authorization\.js' %\}\?v=)[^\"']+", rf"\g<1>{VERSION}", template)
    write(rel, template)


def install_tests() -> None:
    write("tests/test_ab_bau_runtime_ux_performance_hotfix.py", r'''from pathlib import Path
from django.test import SimpleTestCase

ROOT = Path(__file__).resolve().parents[1]


class ABBauRuntimeHotfixTests(SimpleTestCase):
    def test_field_time_toggle_has_one_owner_and_csrf_cookie(self):
        field_js = (ROOT / "static/js/field-authorization.js").read_text(encoding="utf-8")
        global_js = (ROOT / "static/js/kayi-next.js").read_text(encoding="utf-8")
        views = (ROOT / "erp/field_authorization_views.py").read_text(encoding="utf-8")
        self.assertIn("global kayi-next.js owns Zeiterfassung", field_js)
        self.assertNotIn("bindCompletion(); bindTimeToggle();", field_js)
        self.assertIn("abTimeBound", global_js)
        self.assertIn("const raw = await response.text()", global_js)
        self.assertIn("@ensure_csrf_cookie\ndef field_job_detail", views)

    def test_offer_initial_render_does_not_resolve_500_catalog_prices(self):
        views = (ROOT / "erp/rebuild_views.py").read_text(encoding="utf-8")
        self.assertIn("def _fast_catalog_preview", views)
        self.assertGreaterEqual(views.count("_fast_catalog_preview(org)"), 2)
        self.assertNotIn("catalog_with_effective_prices(org, limit=500)", views)

    def test_catalog_search_is_async_and_bo_results_are_compact(self):
        urls = (ROOT / "erp/rebuild_urls.py").read_text(encoding="utf-8")
        template = (ROOT / "templates/rebuild/document_editor.html").read_text(encoding="utf-8")
        js = (ROOT / "static/js/kayi-next.js").read_text(encoding="utf-8")
        bo = (ROOT / "erp/bo_direct_search_views.py").read_text(encoding="utf-8")
        css = (ROOT / "static/css/kayi-next.css").read_text(encoding="utf-8")
        self.assertIn("next-catalog-quick-search", urls)
        self.assertIn("data-ab-catalog-search-url", template)
        self.assertIn("abCatalogController", js)
        self.assertIn("limit=12", bo)
        self.assertIn("max-height:360px", css)
        self.assertIn("A+BAU RUNTIME UX + PERFORMANCE HOTFIX", css)
''')


def guard() -> None:
    field_js = read("static/js/field-authorization.js")
    global_js = read("static/js/kayi-next.js")
    views = read("erp/rebuild_views.py")
    urls = read("erp/rebuild_urls.py")
    template = read("templates/rebuild/document_editor.html")
    css = read("static/css/kayi-next.css")
    checks = {
        "single time owner": "global kayi-next.js owns Zeiterfassung" in field_js and "abTimeBound" in global_js,
        "fast offer catalog": views.count("_fast_catalog_preview(org)") >= 2,
        "async local catalog": "next-catalog-quick-search" in urls and "data-ab-catalog-search-url" in template,
        "compact B&O": "max-height:360px" in css,
        "visual marker": MARKER in css,
    }
    failed = [name for name, ok in checks.items() if not ok]
    if failed:
        raise RuntimeError(f"A+Bau runtime hotfix incomplete: {failed}")


patch_time_tracking()
install_fast_catalog_endpoint()
patch_offer_load_path()
patch_document_editor()
patch_bo_results()
patch_visuals_and_cache()
install_tests()
guard()
print("A+Bau runtime hotfix installed: single-owner Zeiterfassung, fast Angebot first paint, async catalog search and compact commercial UX.")
