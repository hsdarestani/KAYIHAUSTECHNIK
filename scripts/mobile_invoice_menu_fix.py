from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CSS_PATH = ROOT / "static/css/tooltime-invoices-exact.css"
MARKER = "A+BAU MOBILE INVOICE MENU FIX 2026-08-22"

PATCH = r'''
/* A+BAU MOBILE INVOICE MENU FIX 2026-08-22 */
@media(max-width:720px){
  .tti-table tr[data-invoice-row] td.tti-actions{
    box-sizing:border-box!important;
    width:100%!important;
    max-width:100%!important;
    justify-content:flex-end!important;
  }
  .tti-table tr[data-invoice-row] td.tti-actions::before{
    display:none!important;
  }
  .tti-table tr[data-invoice-row] .tti-row-menu{
    margin-left:auto!important;
    max-width:100%!important;
  }
  .tti-table tr[data-invoice-row] .tti-row-menu>div{
    left:auto!important;
    right:0!important;
    box-sizing:border-box!important;
    max-width:calc(100vw - 48px)!important;
  }
  .tti-table tr[data-invoice-row] .tti-row-menu a,
  .tti-table tr[data-invoice-row] .tti-row-menu button{
    max-width:100%!important;
    overflow-wrap:anywhere;
  }
}
'''

if not CSS_PATH.exists():
    raise RuntimeError("ToolTime invoice CSS missing; run source assembly before mobile invoice menu fix")

css = CSS_PATH.read_text(encoding="utf-8")
if MARKER not in css:
    css = css.rstrip() + "\n" + PATCH.lstrip()
    CSS_PATH.write_text(css, encoding="utf-8")

final = CSS_PATH.read_text(encoding="utf-8")
for required in (
    MARKER,
    "td.tti-actions",
    "width:100%!important",
    "justify-content:flex-end!important",
    "td.tti-actions::before",
    "right:0!important",
    "left:auto!important",
    "max-width:calc(100vw - 48px)!important",
):
    if required not in final:
        raise RuntimeError(f"Mobile invoice menu guard missing: {required}")

print("A+Bau mobile invoice action menu fixed: dropdown stays inside narrow phone viewports.")
