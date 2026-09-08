from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MARKER = "A+BAU V3 CATALOGUE MOBILE HEADER OVERFLOW FIX 2026-09-08"
UPLOAD_MARKER = "A+BAU V3 SETTINGS LOGO MULTIPART FIX 2026-09-08"
DASHBOARD_MARKER = "A+BAU V3 DASHBOARD HERO FLOW FIX 2026-09-08"
QUOTE_MENU_MARKER = "A+BAU V3 QUOTES NEW MENU OVERFLOW FIX 2026-09-08"
QUOTE_EDITOR_MARKER = "A+BAU V3 QUOTE EDITOR TOOLTIME PARITY FIX 2026-09-08"
POSITION_MODEL_MARKER = "A+BAU V3 POSITION MODEL READABILITY FIX 2026-09-08"
EDITOR_RUNTIME_MARKER = "A+BAU V3 QUOTE EDITOR RUNTIME FIX 2026-09-08"
CACHE_VERSION = "20260908-finance-mobile-pdf-6"
CSS_REL = "static/css/ab-bau-v3-finance-mobile-pdf-hotfix.css"
SETTINGS_REL = "templates/rebuild/tooltime_settings.html"
BASE_REL = "templates/rebuild/base.html"
DOCUMENT_REL = "templates/rebuild/document_editor.html"
POSITION_REL = "templates/rebuild/_tooltime_position.html"
FINANCE_JS_REL = "static/js/tooltime-parity-finance.js"
TEST_REL = "tests/test_ab_bau_v3_catalogue_mobile_header_overflow_fix.py"

MOBILE_FIX = r"""

/* A+BAU V3 CATALOGUE MOBILE HEADER OVERFLOW FIX 2026-09-08
   The mobile catalogue is rendered as labelled cards and has its own sort control.
   Keep the desktop semantic table header intact, but remove the table header from
   mobile layout so its intrinsic TH widths cannot escape the phone viewport. */
@media(max-width:860px){
  body.ab-apex .ttc-table thead{display:none!important}
}
"""

DASHBOARD_FIX = r"""

/* A+BAU V3 DASHBOARD HERO FLOW FIX 2026-09-08
   The KPI strip used to be absolutely pinned to the hero bottom. At desktop zoom
   levels and on shorter viewports that let the two-line greeting and intro copy
   physically collide with the KPI labels. Keep both rows in normal layout flow so
   the hero grows with its content instead of allowing any overlap. */
@media(min-width:1101px){
  body.ab-v3 .ab-v3-dashboard-hero{
    min-height:0!important;
    height:auto!important;
    display:grid!important;
    grid-template-rows:auto auto!important;
    align-content:start!important;
    row-gap:28px!important;
  }
  body.ab-v3 .ab-v3-hero-top{min-height:0!important}
  body.ab-v3 .ab-v3-hero-copy{min-width:0;max-width:calc(100% - 260px)}
  body.ab-v3 .ab-v3-hero-copy h1{
    max-width:680px!important;
    font-size:clamp(38px,4vw,60px)!important;
    line-height:.98!important;
  }
  body.ab-v3 .ab-v3-hero-copy p{max-width:640px!important;margin-top:14px!important}
  body.ab-v3 .ab-v3-metrics{
    position:relative!important;
    inset:auto!important;
    left:auto!important;
    right:auto!important;
    bottom:auto!important;
    width:100%!important;
    margin:0!important;
  }
}
@media(min-width:1101px) and (max-width:1380px){
  body.ab-v3 .ab-v3-hero-copy{max-width:calc(100% - 230px)}
  body.ab-v3 .ab-v3-hero-copy h1{font-size:clamp(36px,4.2vw,54px)!important}
}
"""

QUOTE_MENU_FIX = r"""

/* A+BAU V3 QUOTES NEW MENU OVERFLOW FIX 2026-09-08
   The Neues Angebot dropdown is taller than the commercial hero. The hero used
   overflow:hidden for decoration, which clipped the open menu at its bottom edge.
   Let the menu escape the hero, keep it above following content, and on phones make
   it follow the full-width trigger column instead of escaping the viewport. */
body.ab-apex .ttq-topbar{
  overflow:visible!important;
  z-index:30!important;
}
body.ab-apex .ttq-top-actions,
body.ab-apex .ttq-new-menu{
  position:relative!important;
  z-index:40!important;
}
body.ab-apex .ttq-menu-card{
  position:absolute!important;
  top:calc(100% + 10px)!important;
  right:0!important;
  left:auto!important;
  z-index:60!important;
  min-width:220px!important;
  max-width:min(320px,calc(100vw - 32px))!important;
}
@media(max-width:520px){
  body.ab-apex .ttq-menu-card{
    left:0!important;
    right:auto!important;
    width:100%!important;
    min-width:0!important;
    max-width:100%!important;
    box-sizing:border-box!important;
  }
}
"""

QUOTE_EDITOR_FIX = r"""

/* A+BAU V3 QUOTE EDITOR TOOLTIME PARITY FIX 2026-09-08
   Keep the A+Bau-specific position model readable without adding a fourteenth grid
   column, and make the lower calculation card follow ToolTime's cost/markup hierarchy. */
body.ab-apex .tt-service-model-field{
  display:grid!important;
  grid-template-columns:minmax(110px,auto) minmax(190px,320px)!important;
  align-items:center!important;
  justify-content:start!important;
  gap:10px!important;
  margin-top:2px!important;
  font-size:12px!important;
  font-weight:750!important;
  color:var(--nx-muted,#667085)!important;
}
body.ab-apex .tt-service-model{
  display:block!important;
  width:100%!important;
  min-width:190px!important;
  min-height:38px!important;
  font-size:13px!important;
  font-weight:700!important;
}
body.ab-apex .tt-position-columns{
  display:grid;
  grid-template-columns:28px 42px 125px 75px 75px minmax(250px,1.7fr) 95px 90px 90px 100px 100px 120px 36px;
  gap:7px;
  align-items:end;
  padding:8px 10px 3px;
  color:#667085;
  font-size:10px;
  font-weight:800;
  line-height:1.15;
}
body.ab-apex .tt-position-columns span{min-width:0}
body.ab-apex .tt-summary-card{padding:18px!important}
body.ab-apex .tt-summary-card h3{margin-bottom:12px!important}
body.ab-apex .tt-summary-details{display:grid;gap:2px;padding:2px 0 9px 12px}
body.ab-apex .tt-summary-subline{
  display:flex;
  justify-content:space-between;
  gap:14px;
  padding:3px 0;
  color:#667085;
  font-size:12px;
}
body.ab-apex .tt-summary-subline strong{color:#344054;font-size:12px}
body.ab-apex .tt-summary-divider{border-top:1px solid var(--nx-line,#e5e7eb);margin-top:8px;padding-top:10px}
body.ab-apex .tt-summary-card>.tt-link{padding-left:0!important;margin:0 0 6px!important;text-align:left!important}
@media(max-width:1100px){
  body.ab-apex .tt-position-columns{display:none!important}
  body.ab-apex .tt-service-model-field{grid-template-columns:1fr!important}
  body.ab-apex .tt-service-model{display:block!important;min-width:0!important}
}
"""

EDITOR_RUNTIME = r'''

// A+BAU V3 QUOTE EDITOR RUNTIME FIX 2026-09-08
(() => {
  'use strict';
  const editor = document.querySelector('.tt-document-form');
  if (!editor) return;
  const top = document.querySelector('.tt-document-top');
  const customerSelect = document.querySelector('[data-customer-select]');
  const projectSelect = document.querySelector('[data-project-select]');
  const projectForm = document.querySelector('[data-quick-project-form]');
  const templateModal = document.querySelector('[data-template-modal]');
  const money = new Intl.NumberFormat('de-DE', {style:'currency', currency:'EUR'});
  const num = value => {
    const parsed = Number(String(value ?? '0').replace(',', '.'));
    return Number.isFinite(parsed) ? parsed : 0;
  };

  // Own template opening in capture phase so older finance/V3 click handlers never
  // open a second chooser behind the first one. Close any stale sibling modal first.
  document.addEventListener('click', event => {
    const trigger = event.target.closest('[data-template-open]');
    if (!trigger) return;
    event.preventDefault();
    event.stopImmediatePropagation();
    document.querySelectorAll('.tt-modal').forEach(modal => {
      if (modal !== templateModal) modal.hidden = true;
    });
    window.ttTemplateKind = trigger.dataset.templateOpen || 'intro';
    if (templateModal) templateModal.hidden = false;
  }, true);

  const showProjectError = message => {
    const error = projectForm?.querySelector('[data-quick-error]');
    if (error) error.textContent = message || '';
  };

  const csrf = () => editor.querySelector('[name=csrfmiddlewaretoken]')?.value || '';

  const createProject = ({url, title, customerId}) => new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open('POST', new URL(url, window.location.origin).href, true);
    xhr.withCredentials = true;
    xhr.setRequestHeader('X-CSRFToken', csrf());
    xhr.setRequestHeader('X-Requested-With', 'XMLHttpRequest');
    xhr.setRequestHeader('Accept', 'application/json');
    xhr.setRequestHeader('Content-Type', 'application/x-www-form-urlencoded;charset=UTF-8');
    xhr.timeout = 15000;
    xhr.onload = () => {
      let data = null;
      try { data = JSON.parse(xhr.responseText || '{}'); } catch (_) {}
      if (xhr.status >= 200 && xhr.status < 300 && data?.ok) {
        resolve(data);
        return;
      }
      const fallback = xhr.status === 403
        ? 'Sitzung abgelaufen. Bitte die Seite neu laden und erneut versuchen.'
        : `Projekt konnte nicht angelegt werden${xhr.status ? ` (HTTP ${xhr.status})` : ''}.`;
      reject(new Error(data?.error || fallback));
    };
    xhr.onerror = () => reject(new Error('Projekt konnte wegen eines Netzwerkfehlers nicht angelegt werden. Bitte erneut versuchen.'));
    xhr.ontimeout = () => reject(new Error('Die Projektanlage hat zu lange gedauert. Bitte erneut versuchen.'));
    const body = new URLSearchParams({title, customer_id: customerId, csrfmiddlewaretoken: csrf()});
    xhr.send(body.toString());
  });

  // Replace the older fetch-based quick-project owner. The production symptom was
  // the browser-level TypeError "Failed to fetch"; same-origin XHR keeps cookies and
  // CSRF deterministic and surfaces the actual server/network failure to the user.
  projectForm?.addEventListener('submit', async event => {
    event.preventDefault();
    event.stopImmediatePropagation();
    const title = projectForm.elements.title?.value?.trim() || '';
    const customerId = customerSelect?.value || '';
    if (!customerId) { showProjectError('Bitte zuerst einen Kunden auswählen.'); return; }
    if (!title) { showProjectError('Bitte einen Projekttitel eingeben.'); return; }
    const url = top?.dataset.quickProjectUrl || '';
    if (!url) { showProjectError('Die Projekt-Schnittstelle ist nicht verfügbar.'); return; }
    const submit = projectForm.querySelector('[type=submit]');
    if (submit) submit.disabled = true;
    showProjectError('');
    try {
      const data = await createProject({url, title, customerId});
      const option = new Option(`${data.project.number} · ${data.project.title}`, data.project.id, true, true);
      option.dataset.customerId = String(data.project.customer_id);
      option.dataset.address = data.project.address || '';
      projectSelect?.appendChild(option);
      projectSelect?.dispatchEvent(new Event('change', {bubbles:true}));
      const modal = projectForm.closest('.tt-modal');
      if (modal) modal.hidden = true;
      projectForm.reset();
    } catch (error) {
      showProjectError(error?.message || 'Projekt konnte nicht angelegt werden.');
    } finally {
      if (submit) submit.disabled = false;
    }
  }, true);

  const summaryValue = (selector, value) => {
    const output = document.querySelector(selector);
    if (output) output.textContent = money.format(value);
  };

  function updateBreakdown() {
    const costs = {material:0, labour:0, other:0};
    const markups = {material:0, labour:0, other:0};
    editor.querySelectorAll('[data-position]').forEach(row => {
      const quantity = num(row.querySelector('[name=item_quantity]')?.value);
      const purchase = num(row.querySelector('[name=item_purchase_price]')?.value);
      const markupPercent = num(row.querySelector('[name=item_markup_percent]')?.value);
      const type = row.querySelector('[name=item_type]')?.value || 'other';
      const bucket = type === 'material' ? 'material' : (type === 'labour' ? 'labour' : 'other');
      costs[bucket] += quantity * purchase;
      markups[bucket] += quantity * purchase * markupPercent / 100;
    });
    summaryValue('[data-summary-cost-material]', costs.material);
    summaryValue('[data-summary-cost-labour]', costs.labour);
    summaryValue('[data-summary-cost-other]', costs.other);
    summaryValue('[data-summary-markup-material]', markups.material);
    summaryValue('[data-summary-markup-labour]', markups.labour);
    summaryValue('[data-summary-markup-other]', markups.other);
  }

  function ensurePositionHeaders() {
    editor.querySelectorAll('[data-service-group]').forEach(group => {
      if (group.querySelector(':scope > .tt-position-columns')) return;
      const body = group.querySelector(':scope > [data-group-body]');
      if (!body) return;
      const header = document.createElement('div');
      header.className = 'tt-position-columns';
      header.setAttribute('aria-hidden', 'true');
      header.innerHTML = '<span></span><span>Nr.</span><span>Typ</span><span>Menge</span><span>Einheit</span><span>Beschreibung</span><span>Einkaufspreis</span><span>Aufschlag</span><span>Aufschlagwert</span><span>VK</span><span>Einzelpreis</span><span>Gesamtpreis</span><span></span>';
      body.before(header);
    });
  }

  editor.addEventListener('input', updateBreakdown);
  editor.addEventListener('change', updateBreakdown);
  const groups = editor.querySelector('[data-service-groups]');
  if (groups) new MutationObserver(() => { ensurePositionHeaders(); updateBreakdown(); }).observe(groups, {childList:true, subtree:true});
  ensurePositionHeaders();
  updateBreakdown();
})();
'''


def install_css() -> None:
    path = ROOT / CSS_REL
    if not path.exists():
        raise RuntimeError(f"Catalogue/dashboard/quotes hotfix target missing: {CSS_REL}")
    text = path.read_text(encoding="utf-8")
    changed = False
    if MARKER not in text:
        text = text.rstrip() + MOBILE_FIX + "\n"
        changed = True
    if DASHBOARD_MARKER not in text:
        text = text.rstrip() + DASHBOARD_FIX + "\n"
        changed = True
    if QUOTE_MENU_MARKER not in text:
        text = text.rstrip() + QUOTE_MENU_FIX + "\n"
        changed = True
    if QUOTE_EDITOR_MARKER not in text:
        text = text.rstrip() + QUOTE_EDITOR_FIX + "\n"
        changed = True
    if changed:
        path.write_text(text, encoding="utf-8")


def bust_css_cache() -> None:
    path = ROOT / BASE_REL
    if not path.exists():
        raise RuntimeError(f"Final V3 cache-bust target missing: {BASE_REL}")
    text = path.read_text(encoding="utf-8")
    pattern = r'(/static/css/ab-bau-v3-finance-mobile-pdf-hotfix\.css\?v=)[^\"\']+'
    if not re.search(pattern, text):
        raise RuntimeError("Final V3 cache-bust link is missing")
    text = re.sub(pattern, rf'\g<1>{CACHE_VERSION}', text)
    path.write_text(text, encoding="utf-8")


def install_settings_logo_multipart_fix() -> None:
    """Ensure the Texte & Layout form actually transmits selected logo/header files."""
    path = ROOT / SETTINGS_REL
    if not path.exists():
        raise RuntimeError(f"Settings upload target missing: {SETTINGS_REL}")
    text = path.read_text(encoding="utf-8")
    layout_marker = '<input type="hidden" name="section" value="layout">'
    marker_pos = text.find(layout_marker)
    if marker_pos < 0:
        raise RuntimeError("Settings logo multipart fix: layout form marker missing")
    form_start = text.rfind("<form", 0, marker_pos)
    form_end = text.find(">", form_start)
    if form_start < 0 or form_end < 0:
        raise RuntimeError("Settings logo multipart fix: layout form bounds missing")
    opening = text[form_start:form_end + 1]
    if 'enctype="multipart/form-data"' not in opening:
        opening = opening[:-1] + ' enctype="multipart/form-data" data-ab-logo-multipart-fix="20260908">'
        text = text[:form_start] + opening + text[form_end + 1:]
    elif "data-ab-logo-multipart-fix" not in opening:
        opening = opening[:-1] + ' data-ab-logo-multipart-fix="20260908">'
        text = text[:form_start] + opening + text[form_end + 1:]
    path.write_text(text, encoding="utf-8")


def install_position_model_readability_fix() -> None:
    path = ROOT / POSITION_REL
    if not path.exists():
        raise RuntimeError(f"Position template missing: {POSITION_REL}")
    text = path.read_text(encoding="utf-8")
    if POSITION_MODEL_MARKER in text:
        return
    match = re.search(r'\n<select class="nx-control tt-service-model" name="item_service_model">.*?</select>', text)
    if not match:
        raise RuntimeError("item_service_model select not found in position template")
    select_html = match.group(0).strip()
    text = text[:match.start()] + text[match.end():]
    anchor = '\n</div>\n<input class="nx-control tt-money" name="item_purchase_price"'
    if anchor not in text:
        raise RuntimeError("Position description close anchor missing")
    replacement = (
        f'\n  <!-- {POSITION_MODEL_MARKER} -->\n'
        f'  <label class="tt-service-model-field"><span>Positionsmodell</span>{select_html}</label>'
        '\n</div>\n<input class="nx-control tt-money" name="item_purchase_price"'
    )
    text = text.replace(anchor, replacement, 1)
    path.write_text(text, encoding="utf-8")


def install_document_summary_parity() -> None:
    path = ROOT / DOCUMENT_REL
    if not path.exists():
        raise RuntimeError(f"Document editor missing: {DOCUMENT_REL}")
    text = path.read_text(encoding="utf-8")
    if 'data-tooltime-summary-parity="20260908"' in text:
        return
    text = text.replace(
        '<div class="tt-card tt-summary-card"><h3>Kalkulationsübersicht</h3>',
        '<div class="tt-card tt-summary-card" data-tooltime-summary-parity="20260908"><h3>Kalkulationsübersicht</h3>',
        1,
    )
    old = (
        '<div class="tt-summary-line"><span>Gesamtkosten</span><strong data-summary-cost>0,00 €</strong></div>'
        '<div class="tt-summary-line"><span>Gesamtmarge</span><strong data-summary-margin>0,00 €</strong></div>'
        '<button type="button" class="tt-link" data-adjust-markups>Margen anpassen</button>'
    )
    new = (
        '<div class="tt-summary-line"><span>Gesamtkosten</span><strong data-summary-cost>0,00 €</strong></div>'
        '<div class="tt-summary-details">'
        '<div class="tt-summary-subline"><span>Materialkosten</span><strong data-summary-cost-material>0,00 €</strong></div>'
        '<div class="tt-summary-subline"><span>Lohnkosten</span><strong data-summary-cost-labour>0,00 €</strong></div>'
        '<div class="tt-summary-subline"><span>Sonstige Kosten</span><strong data-summary-cost-other>0,00 €</strong></div>'
        '</div>'
        '<div class="tt-summary-line tt-summary-divider"><span>Gesamtaufschlag</span><strong data-summary-margin>0,00 €</strong></div>'
        '<div class="tt-summary-details">'
        '<div class="tt-summary-subline"><span>Aufschlag Material</span><strong data-summary-markup-material>0,00 €</strong></div>'
        '<div class="tt-summary-subline"><span>Aufschlag Lohn</span><strong data-summary-markup-labour>0,00 €</strong></div>'
        '<div class="tt-summary-subline"><span>Aufschlag Sonstiges</span><strong data-summary-markup-other>0,00 €</strong></div>'
        '</div>'
        '<button type="button" class="tt-link" data-adjust-markups>Margen anpassen</button>'
    )
    if old not in text:
        raise RuntimeError("ToolTime calculation summary anchor missing")
    text = text.replace(old, new, 1)
    path.write_text(text, encoding="utf-8")


def install_editor_runtime_fix() -> None:
    path = ROOT / FINANCE_JS_REL
    if not path.exists():
        raise RuntimeError(f"Finance runtime missing: {FINANCE_JS_REL}")
    text = path.read_text(encoding="utf-8")
    if EDITOR_RUNTIME_MARKER not in text:
        text = text.rstrip() + EDITOR_RUNTIME + "\n"
        path.write_text(text, encoding="utf-8")


def install_test() -> None:
    path = ROOT / TEST_REL
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        r'''from pathlib import Path
from django.test import SimpleTestCase

ROOT = Path(__file__).resolve().parents[1]


class ABauV3CatalogueMobileHeaderOverflowFixTests(SimpleTestCase):
    def test_mobile_catalogue_header_does_not_participate_in_layout(self):
        css = (ROOT / "static/css/ab-bau-v3-finance-mobile-pdf-hotfix.css").read_text(encoding="utf-8")
        self.assertIn("A+BAU V3 CATALOGUE MOBILE HEADER OVERFLOW FIX 2026-09-08", css)
        self.assertIn("body.ab-apex .ttc-table thead{display:none!important}", css)

    def test_desktop_catalogue_header_contract_still_exists(self):
        template = (ROOT / "templates/rebuild/catalogue.html").read_text(encoding="utf-8")
        self.assertIn("<thead>", template)
        self.assertIn("<th>Artikelnummer</th>", template)

    def test_layout_form_posts_uploaded_logo_as_multipart(self):
        template = (ROOT / "templates/rebuild/tooltime_settings.html").read_text(encoding="utf-8")
        marker = '<input type="hidden" name="section" value="layout">'
        marker_pos = template.index(marker)
        form_start = template.rfind("<form", 0, marker_pos)
        form_end = template.index(">", form_start)
        opening = template[form_start:form_end + 1]
        self.assertIn('enctype="multipart/form-data"', opening)
        self.assertIn('data-ab-logo-multipart-fix="20260908"', opening)

    def test_dashboard_hero_keeps_greeting_and_kpis_in_separate_flow_rows(self):
        css = (ROOT / "static/css/ab-bau-v3-finance-mobile-pdf-hotfix.css").read_text(encoding="utf-8")
        self.assertIn("A+BAU V3 DASHBOARD HERO FLOW FIX 2026-09-08", css)
        self.assertIn("grid-template-rows:auto auto!important", css)
        self.assertIn("body.ab-v3 .ab-v3-metrics", css)
        self.assertIn("position:relative!important", css)
        self.assertIn("inset:auto!important", css)

    def test_new_quote_menu_is_not_clipped_by_commercial_hero(self):
        css = (ROOT / "static/css/ab-bau-v3-finance-mobile-pdf-hotfix.css").read_text(encoding="utf-8")
        self.assertIn("A+BAU V3 QUOTES NEW MENU OVERFLOW FIX 2026-09-08", css)
        self.assertIn("body.ab-apex .ttq-topbar{", css)
        self.assertIn("overflow:visible!important", css)
        self.assertIn("z-index:30!important", css)
        self.assertIn("body.ab-apex .ttq-menu-card{", css)
        self.assertIn("top:calc(100% + 10px)!important", css)
        self.assertIn("z-index:60!important", css)

    def test_phone_quote_menu_stays_inside_full_width_trigger_column(self):
        css = (ROOT / "static/css/ab-bau-v3-finance-mobile-pdf-hotfix.css").read_text(encoding="utf-8")
        self.assertIn("@media(max-width:520px)", css)
        self.assertIn("left:0!important", css)
        self.assertIn("width:100%!important", css)
        self.assertIn("min-width:0!important", css)
        self.assertIn("max-width:100%!important", css)

    def test_position_service_model_is_readable_and_not_a_fourteenth_grid_cell(self):
        position = (ROOT / "templates/rebuild/_tooltime_position.html").read_text(encoding="utf-8")
        css = (ROOT / "static/css/ab-bau-v3-finance-mobile-pdf-hotfix.css").read_text(encoding="utf-8")
        self.assertIn("A+BAU V3 POSITION MODEL READABILITY FIX 2026-09-08", position)
        self.assertIn('class="tt-service-model-field"', position)
        self.assertIn('name="item_service_model"', position)
        self.assertLess(position.index('name="item_service_model"'), position.index('name="item_purchase_price"'))
        self.assertIn("body.ab-apex .tt-service-model{", css)
        self.assertIn("min-width:190px!important", css)

    def test_tooltime_calculation_breakdown_is_present(self):
        template = (ROOT / "templates/rebuild/document_editor.html").read_text(encoding="utf-8")
        self.assertIn('data-tooltime-summary-parity="20260908"', template)
        for field in (
            "data-summary-cost-material",
            "data-summary-cost-labour",
            "data-summary-cost-other",
            "data-summary-markup-material",
            "data-summary-markup-labour",
            "data-summary-markup-other",
        ):
            self.assertIn(field, template)

    def test_template_modal_is_single_owner_and_project_create_has_xhr_fallback(self):
        runtime = (ROOT / "static/js/tooltime-parity-finance.js").read_text(encoding="utf-8")
        self.assertIn("A+BAU V3 QUOTE EDITOR RUNTIME FIX 2026-09-08", runtime)
        self.assertIn("event.stopImmediatePropagation()", runtime)
        self.assertIn("new XMLHttpRequest()", runtime)
        self.assertIn("X-Requested-With", runtime)
        self.assertIn("data-summary-cost-material", runtime)
        self.assertIn("MutationObserver", runtime)

    def test_final_hotfix_css_is_cache_busted(self):
        base = (ROOT / "templates/rebuild/base.html").read_text(encoding="utf-8")
        self.assertIn("ab-bau-v3-finance-mobile-pdf-hotfix.css?v=20260908-finance-mobile-pdf-6", base)
''',
        encoding="utf-8",
    )


def guard() -> None:
    css = (ROOT / CSS_REL).read_text(encoding="utf-8")
    for required in (
        MARKER,
        "body.ab-apex .ttc-table thead{display:none!important}",
        DASHBOARD_MARKER,
        "grid-template-rows:auto auto!important",
        "body.ab-v3 .ab-v3-metrics",
        QUOTE_MENU_MARKER,
        "body.ab-apex .ttq-topbar{",
        "overflow:visible!important",
        "body.ab-apex .ttq-menu-card{",
        "top:calc(100% + 10px)!important",
        "@media(max-width:520px)",
        "left:0!important",
        "width:100%!important",
        "max-width:100%!important",
        QUOTE_EDITOR_MARKER,
        "body.ab-apex .tt-service-model{",
        "min-width:190px!important",
        "body.ab-apex .tt-summary-details",
    ):
        if required not in css:
            raise RuntimeError(f"Final V3 layout guard failed: {required}")

    base = (ROOT / BASE_REL).read_text(encoding="utf-8")
    if f"ab-bau-v3-finance-mobile-pdf-hotfix.css?v={CACHE_VERSION}" not in base:
        raise RuntimeError("Final V3 hotfix CSS cache version was not installed")

    settings = (ROOT / SETTINGS_REL).read_text(encoding="utf-8")
    layout_marker = '<input type="hidden" name="section" value="layout">'
    marker_pos = settings.find(layout_marker)
    form_start = settings.rfind("<form", 0, marker_pos)
    form_end = settings.find(">", form_start)
    opening = settings[form_start:form_end + 1] if marker_pos >= 0 and form_start >= 0 and form_end >= 0 else ""
    if 'enctype="multipart/form-data"' not in opening or 'data-ab-logo-multipart-fix="20260908"' not in opening:
        raise RuntimeError("Settings logo upload form is not multipart; selected files would be dropped")

    position = (ROOT / POSITION_REL).read_text(encoding="utf-8")
    if POSITION_MODEL_MARKER not in position or 'class="tt-service-model-field"' not in position:
        raise RuntimeError("Position model readability fix was not installed")

    document = (ROOT / DOCUMENT_REL).read_text(encoding="utf-8")
    for required in ('data-tooltime-summary-parity="20260908"', "data-summary-cost-material", "data-summary-markup-labour"):
        if required not in document:
            raise RuntimeError(f"ToolTime summary parity guard failed: {required}")

    runtime = (ROOT / FINANCE_JS_REL).read_text(encoding="utf-8")
    for required in (EDITOR_RUNTIME_MARKER, "event.stopImmediatePropagation()", "new XMLHttpRequest()", "X-Requested-With", "MutationObserver"):
        if required not in runtime:
            raise RuntimeError(f"Quote editor runtime guard failed: {required}")


def main() -> None:
    install_css()
    bust_css_cache()
    install_settings_logo_multipart_fix()
    install_position_model_readability_fix()
    install_document_summary_parity()
    install_editor_runtime_fix()
    install_test()
    guard()
    print(f"{MARKER}: mobile catalogue table header removed from layout; desktop header preserved.")
    print(f"{UPLOAD_MARKER}: Texte & Layout now submits logo/header uploads as multipart form data.")
    print(f"{DASHBOARD_MARKER}: dashboard greeting and KPI strip now remain in separate layout rows.")
    print(f"{QUOTE_MENU_MARKER}: Neues Angebot dropdown renders fully above following content and stays inside phone viewport.")
    print(f"{QUOTE_EDITOR_MARKER}: project creation, single template modal, readable position model and ToolTime calculation hierarchy installed.")


if __name__ == "__main__":
    main()
