from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MARKER = "A+BAU MOBILE FULL RESPONSIVE 2026-08-22"
CSS_PATH = ROOT / "static/css/ab-bau-mobile-responsive.css"
BASE_PATH = ROOT / "templates/rebuild/base.html"

CSS = r'''/* A+BAU MOBILE FULL RESPONSIVE 2026-08-22 */
@media(max-width:860px){
  html,body{width:100%;max-width:100%;overflow-x:hidden!important}
  body{min-width:0!important}
  :where(.nx-shell,.nx-main,.nx-content,main,.content,.page-content,.page,.container,.container-fluid){min-width:0!important;max-width:100%!important}
  :where(.nx-pagehead,.nx-toolbar,.nx-actions,.page-actions,.toolbar,.actions,.form-actions,.tt-actions,.tti-actions,.project-actions,.invoice-actions,.quote-actions){display:flex;flex-wrap:wrap!important;gap:8px;min-width:0;max-width:100%}
  :where(.nx-pagehead,.nx-toolbar,.page-header,.toolbar)>*{min-width:0!important;max-width:100%}
  :where(.nx-grid,.nx-form-grid,.form-grid,.tt-grid,.tti-grid,.settings-grid,.finance-grid,.dashboard-grid,.project-grid,.detail-grid,.summary-grid,.kpi-grid,.stats-grid){grid-template-columns:minmax(0,1fr)!important;min-width:0!important;max-width:100%!important}
  :where(.nx-card,.card,.panel,.section,.tt-card,.tti-card,.project-card,.settings-card,.finance-card,.summary-card,.modal-content,.dialog-content){min-width:0!important;max-width:100%!important;overflow-wrap:anywhere}
  :where(form,fieldset,.nx-form,.tt-form,.tti-form){min-width:0!important;max-width:100%!important}
  :where(input:not([type=checkbox]):not([type=radio]),select,textarea,.form-control,.nx-input,.tt-input,.tti-input,.ab-locale-wrap,.ab-file-wrap){box-sizing:border-box!important;min-width:0!important;max-width:100%!important;width:100%}
  :where(.ab-file-wrap){flex-wrap:wrap!important}
  :where(.ab-file-name){max-width:100%;flex:1 1 180px}
  :where(img,video,svg){max-width:100%;height:auto}
  :where(canvas){max-width:100%}
  :where(.nx-table-wrap,.table-wrap,.table-responsive,.ab-item-table-wrap,.tt-table-wrap,.tti-table-wrap,.invoice-table-wrap,.quote-table-wrap,.catalog-table-wrap){width:100%!important;max-width:100%!important;overflow-x:auto!important;overflow-y:hidden;-webkit-overflow-scrolling:touch;overscroll-behavior-x:contain}
  :where(table,.nx-table,.ab-item-table,.tt-table,.tti-table){max-width:none}
  :where(.nx-modal,.modal,.dialog,[role=dialog]){max-width:100vw!important}
  :where(.nx-modal-dialog,.modal-dialog,.dialog,.dialog-panel,[role=dialog]){box-sizing:border-box!important;width:min(720px,calc(100vw - 24px))!important;max-width:calc(100vw - 24px)!important;max-height:calc(100dvh - 24px)!important;margin:12px auto!important;overflow:auto!important}
  :where(.fc .fc-toolbar,.fc-toolbar,.calendar-toolbar,.calendar-head,.calendar-actions){display:flex;flex-wrap:wrap!important;gap:8px!important;align-items:center}
  :where(.fc .fc-toolbar-chunk){max-width:100%;display:flex;flex-wrap:wrap;gap:4px}
  :where(.fc .fc-button-group){max-width:100%;flex-wrap:wrap}
  :where(.project-hero,.nx-project-hero,.project-detail-head,.customer-head,.employee-head){min-width:0!important;max-width:100%!important;grid-template-columns:minmax(0,1fr)!important}
  :where(.rp-shell,.rp-layout,.rp-main,.room-planner,.room-planner-layout,.room-planner-main,[data-rp-root]){min-width:0!important;max-width:100%!important}
  :where(.rp-layout,.room-planner-layout){grid-template-columns:minmax(0,1fr)!important}
  :where(.rp-toolbar,.rp-actions,.room-planner-toolbar,.room-planner-actions){display:flex;flex-wrap:wrap!important;gap:6px!important;max-width:100%}
  :where([data-rp-canvas]){display:block;max-width:100%!important;width:100%!important}
  :where(.field-actions,.field-toolbar,.field-step-actions,[data-field-actions]){display:flex;flex-wrap:wrap!important;gap:8px!important;max-width:100%}
  :where(.field-card,.field-step,.field-panel){min-width:0!important;max-width:100%!important}
  :where(.settings-tabs,.tabs,.tab-list,[role=tablist]){max-width:100%;overflow-x:auto;overflow-y:hidden;-webkit-overflow-scrolling:touch;scrollbar-width:thin}
  :where(.settings-tabs,.tabs,.tab-list,[role=tablist])>*{flex:0 0 auto}
  :where(.nx-content,.content,main){overflow-wrap:anywhere}

  /* Customer search/create toolbar: desktop sizing gave the search field a fixed
     wide track and pushed "Neuer Kunde" beyond narrow phone viewports. */
  :where(form,div,section,header):has(> .tt-new-customer){
    box-sizing:border-box!important;
    display:flex!important;
    flex-wrap:wrap!important;
    gap:8px!important;
    width:100%!important;
    min-width:0!important;
    max-width:100%!important;
  }
  :where(form,div,section,header):has(> .tt-new-customer)>input:not([type=checkbox]):not([type=radio]),
  :where(form,div,section,header):has(> .tt-new-customer)>select{
    flex:1 1 220px!important;
    width:auto!important;
    min-width:0!important;
    max-width:100%!important;
  }
  :where(form,div,section,header):has(> .tt-new-customer)>.tt-new-customer{
    flex:0 1 auto!important;
    max-width:100%!important;
  }

  /* Invoice/quote template pickers used button sizing on desktop. On narrow screens
     their flex parent could stay wider than the viewport and place the select off-canvas. */
  :where(.invoice-template-select,.quote-template-select){
    box-sizing:border-box!important;
    position:static!important;
    flex:1 1 180px!important;
    width:100%!important;
    min-width:0!important;
    max-width:100%!important;
    margin-left:0!important;
    margin-right:0!important;
    transform:none!important;
  }
  :where(div,section,header):has(> .invoice-template-select),
  :where(div,section,header):has(> .quote-template-select){
    box-sizing:border-box!important;
    min-width:0!important;
    max-width:100%!important;
    flex-wrap:wrap!important;
    overflow:visible!important;
  }
  :where(.btn-group,.input-group):has(.invoice-template-select),
  :where(.btn-group,.input-group):has(.quote-template-select){
    width:100%!important;
    min-width:0!important;
    max-width:100%!important;
    flex-wrap:wrap!important;
  }
}
@media(max-width:560px){
  :where(.nx-content,.content,main){padding-left:12px!important;padding-right:12px!important}
  :where(.nx-pagehead h1,.page-header h1,h1){font-size:clamp(22px,7vw,30px);line-height:1.12}
  :where(.nx-pagehead,.page-header){align-items:flex-start!important}
  :where(.nx-pagehead>.nx-actions,.page-header>.actions,.page-header>.page-actions){width:100%}
  :where(.nx-pagehead>.nx-actions>*,.page-header>.actions>*,.page-header>.page-actions>*){max-width:100%}
  :where(.kpi-grid,.stats-grid,.summary-grid,.dashboard-grid){grid-template-columns:minmax(0,1fr)!important}
  :where(.modal-dialog,.dialog,[role=dialog]){width:calc(100vw - 16px)!important;max-width:calc(100vw - 16px)!important;margin:8px auto!important;max-height:calc(100dvh - 16px)!important}
  :where(.fc .fc-toolbar-title){font-size:1.05rem!important}
  :where(.fc .fc-button){padding:.45em .65em!important}
  :where(.ab-file-button){max-width:100%}

  /* The customers list can inherit an 800px desktop track from its surrounding
     grid. Clamp the actual action group and controls to the physical viewport,
     not to that oversized containing block. */
  :where(form,div,section,header):has(> .tt-new-customer){
    width:calc(100vw - 48px)!important;
    max-width:calc(100vw - 48px)!important;
  }
  :where(form,div,section,header):has(> .tt-new-customer)>input:not([type=checkbox]):not([type=radio]),
  :where(form,div,section,header):has(> .tt-new-customer)>select,
  :where(form,div,section,header):has(> .tt-new-customer)>.tt-new-customer{
    box-sizing:border-box!important;
    flex:1 1 100%!important;
    width:calc(100vw - 48px)!important;
    max-width:calc(100vw - 48px)!important;
  }
}
'''

CSS_PATH.parent.mkdir(parents=True, exist_ok=True)
CSS_PATH.write_text(CSS, encoding="utf-8")

if not BASE_PATH.exists():
    raise RuntimeError("A+Bau base template missing during mobile responsive pass")
base = BASE_PATH.read_text(encoding="utf-8")
old_links = (
    '<link rel="stylesheet" href="/static/css/ab-bau-mobile-responsive.css?v=20260822-1">',
    '<link rel="stylesheet" href="/static/css/ab-bau-mobile-responsive.css?v=20260822-2">',
    '<link rel="stylesheet" href="/static/css/ab-bau-mobile-responsive.css?v=20260822-3">',
    '<link rel="stylesheet" href="/static/css/ab-bau-mobile-responsive.css?v=20260822-4">',
)
link = '<link rel="stylesheet" href="/static/css/ab-bau-mobile-responsive.css?v=20260822-4">'
for old_link in old_links:
    if old_link in base and old_link != link:
        base = base.replace(old_link, link)
if link not in base:
    if "</head>" not in base:
        raise RuntimeError("A+Bau base template has no head anchor for mobile CSS")
    base = base.replace("</head>", link + "\n</head>", 1)
BASE_PATH.write_text(base, encoding="utf-8")

TEST_PATH = ROOT / "tests/test_ab_bau_mobile_full_responsive.py"
TEST_PATH.write_text(
    r'''from pathlib import Path
from django.test import SimpleTestCase

ROOT = Path(__file__).resolve().parents[1]

class ABBauMobileFullResponsiveTests(SimpleTestCase):
    def test_global_mobile_hardening_covers_layouts_tables_modals_calendar_3d_and_field(self):
        css = (ROOT / "static/css/ab-bau-mobile-responsive.css").read_text(encoding="utf-8")
        base = (ROOT / "templates/rebuild/base.html").read_text(encoding="utf-8")
        self.assertIn("ab-bau-mobile-responsive.css?v=20260822-4", base)
        for marker in (
            "A+BAU MOBILE FULL RESPONSIVE 2026-08-22",
            "grid-template-columns:minmax(0,1fr)!important",
            "overflow-x:auto!important",
            "calc(100vw - 24px)",
            ".fc .fc-toolbar",
            "[data-rp-canvas]",
            ".field-actions",
            "[role=tablist]",
            ".tt-new-customer",
            ":has(> .tt-new-customer)",
            "calc(100vw - 48px)",
            ".invoice-template-select",
            ":has(> .invoice-template-select)",
        ):
            self.assertIn(marker, css)

    def test_mobile_browser_audit_is_part_of_source(self):
        smoke = (ROOT / "scripts/mobile_browser_smoke.py").read_text(encoding="utf-8")
        for marker in (
            "VIEWPORTS = ((390, 844), (430, 932))",
            "audit_mobile_menu",
            "audit_calendar_modes",
            "audit_room_planner",
            "audit_field_surface",
            "document horizontal overflow",
        ):
            self.assertIn(marker, smoke)
''',
    encoding="utf-8",
)

for needle in (MARKER, "[data-rp-canvas]", ".field-actions", "overflow-x:auto!important", ".tt-new-customer", "calc(100vw - 48px)", ".invoice-template-select"):
    if needle not in CSS_PATH.read_text(encoding="utf-8"):
        raise RuntimeError(f"Mobile responsive guard missing: {needle}")
compile(TEST_PATH.read_text(encoding="utf-8"), str(TEST_PATH), "exec")
print("A+Bau mobile full responsive hardening installed: global layout, forms, tables, dialogs, calendar, Room Planner, field UI, customer toolbar and invoice template controls protected.")
