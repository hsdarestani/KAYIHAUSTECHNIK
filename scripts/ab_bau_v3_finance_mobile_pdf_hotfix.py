from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MARKER = "A+BAU V3 FINANCE + MOBILE + PDF HOTFIX 2026-09-08"
VERSION = "20260908-finance-mobile-pdf-2"


def read(rel: str) -> str:
    path = ROOT / rel
    if not path.exists():
        raise RuntimeError(f"V3 finance/mobile/PDF hotfix target missing: {rel}")
    return path.read_text(encoding="utf-8")


def write(rel: str, text: str) -> None:
    path = ROOT / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def install_assets() -> None:
    write("static/css/ab-bau-v3-finance-mobile-pdf-hotfix.css", r"""
/* A+BAU V3 FINANCE + MOBILE + PDF HOTFIX 2026-09-08 */
body.ab-apex :where(.ttq-page,.tti-page,.ttc-page){display:grid;gap:18px;max-width:none!important;color:var(--v3-text,#15171a)!important}
body.ab-apex :where(.ttq-topbar,.tti-topbar,.ttc-topbar){
  position:relative;isolation:isolate;overflow:hidden;min-height:154px;margin:0!important;padding:28px 30px!important;
  display:flex!important;align-items:flex-start!important;justify-content:space-between!important;gap:24px!important;
  border:1px solid rgba(255,255,255,.07)!important;border-radius:28px!important;
  background:radial-gradient(circle at 82% 5%,rgba(225,195,111,.20),transparent 24rem),linear-gradient(135deg,#090b0e 0%,#11151a 58%,#181b20 100%)!important;
  box-shadow:0 28px 72px rgba(7,9,11,.24)!important;color:#f5f1e8!important
}
body.ab-apex :where(.ttq-topbar,.tti-topbar,.ttc-topbar):before{content:"";position:absolute;z-index:-1;inset:0;background:linear-gradient(116deg,transparent 0 64%,rgba(255,255,255,.03) 64% 64.35%,transparent 64.35% 100%);pointer-events:none}
body.ab-apex :where(.ttq-topbar,.tti-topbar,.ttc-topbar):after{content:"";position:absolute;z-index:-1;right:-58px;bottom:-112px;width:260px;height:260px;border:1px solid rgba(199,163,75,.16);border-radius:50%;box-shadow:0 0 0 34px rgba(199,163,75,.025),0 0 0 68px rgba(199,163,75,.014);pointer-events:none}
body.ab-apex :where(.ttq-heading,.tti-heading,.ttc-heading){display:grid!important;gap:8px!important;align-content:start!important}
body.ab-apex :where(.ttq-heading,.tti-heading,.ttc-heading):before{content:"COMMERCIAL";display:flex;align-items:center;gap:8px;color:#898f96;font-size:8.5px;font-weight:850;letter-spacing:.19em}
body.ab-apex :where(.ttq-heading,.tti-heading,.ttc-heading):after{content:"";width:28px;height:1px;background:#c7a34b;position:absolute;margin-top:4px}
body.ab-apex :where(.ttq-heading h1,.tti-heading h1,.ttc-heading h1){margin:12px 0 0!important;color:#f8f4eb!important;font-size:clamp(34px,4vw,54px)!important;line-height:.96!important;letter-spacing:-.055em!important;font-weight:770!important}
body.ab-apex :where(.ttq-help,.tti-help,.ttc-help){display:none!important}
body.ab-apex :where(.ttq-top-actions,.tti-top-actions,.ttc-top-actions){position:relative;z-index:2;display:flex!important;align-items:center!important;gap:9px!important;margin-top:2px}
body.ab-apex :where(.ttq-search,.tti-search,.ttc-search){min-width:min(330px,34vw)!important;height:44px!important;margin:0!important;padding:0 13px!important;border:1px solid rgba(255,255,255,.12)!important;border-radius:12px!important;background:rgba(255,255,255,.055)!important;box-shadow:inset 0 1px 0 rgba(255,255,255,.035)!important;color:#d9d9d7!important;backdrop-filter:blur(8px)}
body.ab-apex :where(.ttq-search,.tti-search,.ttc-search) input{color:#f5f5f3!important;background:transparent!important;border:0!important;box-shadow:none!important}
body.ab-apex :where(.ttq-search,.tti-search,.ttc-search) input::placeholder{color:#777d83!important}
body.ab-apex :where(.ttq-search,.tti-search,.ttc-search)>span{color:#cbb46f!important}
body.ab-apex :where(.ttq-new-menu>summary,.tti-new,.ttc-new){min-height:44px!important;padding:0 16px!important;display:inline-flex!important;align-items:center!important;justify-content:center!important;gap:7px!important;border:1px solid #d1ae58!important;border-radius:12px!important;background:linear-gradient(180deg,#d4b25f,#b99037)!important;color:#211a09!important;font-size:11px!important;font-weight:820!important;text-decoration:none!important;box-shadow:0 10px 26px rgba(0,0,0,.18)!important;cursor:pointer}
body.ab-apex .ttq-new-menu{position:relative}
body.ab-apex .ttq-new-menu>summary{list-style:none}body.ab-apex .ttq-new-menu>summary::-webkit-details-marker{display:none}
body.ab-apex .ttq-menu-card{border-color:#30343a!important;border-radius:14px!important;background:#121519!important;box-shadow:0 26px 60px rgba(0,0,0,.34)!important}
body.ab-apex .ttq-menu-card a{color:#eeeae2!important}body.ab-apex .ttq-menu-card small{color:#858b92!important}

body.ab-apex :where(.ttq-filters,.tti-filters,.ttc-filters){margin:0!important;padding:13px 14px!important;display:flex!important;align-items:center!important;gap:9px!important;border:1px solid var(--apex-line,#ded8cc)!important;border-radius:17px!important;background:rgba(255,254,250,.94)!important;box-shadow:0 10px 28px rgba(16,18,21,.045)!important}
body.ab-apex :where(.ttq-select select,.tti-select select,.ttc-select select,.ttq-mobile-sort select,.tti-mobile-sort select,.ttc-mobile-sort select,.tti-date-filter>summary){min-height:42px!important;border:1px solid #cfc6b8!important;border-radius:11px!important;background:#fffdf9!important;color:#34312c!important;font-size:11px!important;font-weight:720!important}
body.ab-apex .tti-date-popover{border-color:var(--apex-line,#ded8cc)!important;border-radius:15px!important;background:#fffdf9!important;box-shadow:0 24px 55px rgba(16,18,21,.16)!important}

body.ab-apex .tti-kpis{max-width:none!important;margin:0!important;display:grid!important;grid-template-columns:repeat(4,minmax(0,1fr))!important;gap:10px!important;background:transparent!important;overflow:visible!important}
body.ab-apex .tti-kpi{min-height:108px;padding:17px 18px!important;border:1px solid var(--apex-line,#ded8cc)!important;border-radius:17px!important;background:linear-gradient(180deg,#fffefa,#f8f4eb)!important;box-shadow:0 12px 28px rgba(16,18,21,.045)!important}
body.ab-apex .tti-kpi:after{content:"";position:absolute;left:18px!important;right:auto!important;top:auto!important;bottom:0!important;width:44px!important;height:2px!important;background:#c7a34b!important}
body.ab-apex .tti-kpi span{color:#827c72!important;font-size:9px!important;font-weight:820!important;letter-spacing:.08em!important;text-transform:uppercase}
body.ab-apex .tti-kpi strong{display:block;margin-top:11px;color:#17191c!important;font-size:clamp(19px,2vw,27px)!important;letter-spacing:-.035em!important;font-weight:780!important}
body.ab-apex .tti-kpi[data-invoice-kpi="overdue"]:after,body.ab-apex .tti-kpi[data-invoice-kpi="dunning"]:after{background:#b94747!important}

body.ab-apex :where(.ttq-table-wrap,.tti-table-wrap,.ttc-table-wrap){margin:0!important;border:1px solid var(--apex-line,#ded8cc)!important;border-radius:20px!important;background:#fffefa!important;box-shadow:0 16px 42px rgba(16,18,21,.055)!important;overflow:auto!important}
body.ab-apex :where(.ttq-table,.tti-table,.ttc-table){margin:0!important;background:#fffefa!important}
body.ab-apex :where(.ttq-table th,.tti-table th,.ttc-table th){padding:14px!important;background:#f4f0e7!important;color:#8b857b!important;border-bottom:1px solid #ddd5c8!important;font-size:9px!important;font-weight:850!important;letter-spacing:.09em!important;text-transform:uppercase!important}
body.ab-apex :where(.ttq-table td,.tti-table td,.ttc-table td){padding:16px 14px!important;border-bottom:1px solid #ece6dc!important;color:#55534e!important}
body.ab-apex :where(.ttq-table,.tti-table,.ttc-table) tbody tr{transition:background .12s ease}
body.ab-apex :where(.ttq-table,.tti-table,.ttc-table) tbody tr:hover{background:#faf6ed!important}
body.ab-apex :where(.ttq-title,.tti-title,.ttc-title,.ttc-code){color:#24272b!important;font-weight:780!important}
body.ab-apex :where(.ttq-pagination,.tti-pagination,.ttc-pagination){margin:0!important;padding:0 4px!important;color:#777169!important}
body.ab-apex :where(.ttq-page-buttons,.tti-page-buttons,.ttc-page-buttons) :where(a,span){border-color:#d8d0c3!important;border-radius:10px!important;background:#fffefa!important;color:#383a3d!important}

body.ab-apex:has(.tt-document-form) .nx-content{max-width:1540px!important}
body.ab-apex:has(.tt-document-form) .tt-pagehead{position:relative;overflow:hidden;min-height:150px;margin:0 0 18px!important;padding:27px 29px!important;border:1px solid rgba(255,255,255,.07)!important;border-radius:28px!important;background:radial-gradient(circle at 84% 0,rgba(225,195,111,.20),transparent 24rem),linear-gradient(135deg,#090b0e,#13171c 63%,#191c20)!important;color:#f6f2e9!important;box-shadow:0 28px 72px rgba(7,9,11,.22)!important}
body.ab-apex:has(.tt-document-form) .tt-pagehead:before{content:"DOCUMENT STUDIO";display:block;margin-bottom:10px;color:#8f949a;font-size:8.5px;font-weight:850;letter-spacing:.19em}
body.ab-apex:has(.tt-document-form) .tt-pagehead h1{margin:0!important;color:#fff!important;font-size:clamp(34px,4vw,52px)!important;letter-spacing:-.055em!important}
body.ab-apex:has(.tt-document-form) .tt-eyebrow{color:#d6ba69!important}
body.ab-apex:has(.tt-document-form) .tt-head-actions{position:relative;z-index:2;align-self:flex-start}
body.ab-apex:has(.tt-document-form) .tt-head-actions .nx-badge{border-color:rgba(255,255,255,.12)!important;background:rgba(255,255,255,.07)!important;color:#e8e6e0!important}
body.ab-apex .tt-document-form{display:grid!important;gap:16px!important}
body.ab-apex .tt-document-form>.tt-card,body.ab-apex .tt-document-form>.tt-services{margin:0!important;padding:21px!important;border:1px solid var(--apex-line,#ded8cc)!important;border-radius:20px!important;background:rgba(255,254,250,.97)!important;box-shadow:0 14px 34px rgba(16,18,21,.045)!important}
body.ab-apex .tt-document-form :where(h2,.tt-section-title h2){color:#1c1e21!important;font-size:17px!important;letter-spacing:-.025em!important}
body.ab-apex .tt-document-form :where(input,select,textarea){border-color:#cfc6b8!important;border-radius:11px!important;background:#fff!important}
body.ab-apex .tt-document-form .tt-service-group{overflow:hidden!important;border:1px solid #ddd5c8!important;border-radius:16px!important;background:#fffdf9!important;box-shadow:none!important}
body.ab-apex .tt-document-form .tt-service-group>header{min-height:52px!important;padding:0 13px!important;background:#f3efe6!important;border-bottom:1px solid #e4ddd1!important}
body.ab-apex .tt-document-form .tt-add-position{min-height:44px!important;color:#806526!important}
body.ab-apex .tt-document-form :where(.nx-btn-accent,.ab-primary-action,button[type="submit"]){border-color:#b89033!important;background:linear-gradient(180deg,#d4b25f,#b99037)!important;color:#211a09!important}

@media(max-width:860px){
  body.ab-apex .nx-content{padding-bottom:calc(124px + env(safe-area-inset-bottom))!important}
  body.ab-apex .ab-mobile-dock{z-index:80!important;min-height:64px!important}
  body.ab-apex .ab-mobile-dock :where(a,button){min-height:52px!important;touch-action:manipulation}
  body.ab-apex .ab-v3-mobile-fab{display:grid!important;place-items:center!important;position:fixed!important;right:14px!important;bottom:calc(88px + env(safe-area-inset-bottom))!important;width:54px!important;height:54px!important;min-width:54px!important;min-height:54px!important;margin:0!important;border-radius:17px!important;z-index:84!important}
  body.ab-apex :where(.nx-assistant-fab,.assistant-fab){position:fixed!important;right:78px!important;bottom:calc(88px + env(safe-area-inset-bottom))!important;width:54px!important;height:54px!important;min-width:54px!important;min-height:54px!important;margin:0!important;border-radius:17px!important;z-index:84!important}
  body.ab-apex.nx-menu-open :where(.ab-v3-mobile-fab,.nx-assistant-fab,.assistant-fab){opacity:0!important;visibility:hidden!important;pointer-events:none!important}
  body.ab-apex :where(.ttq-page,.tti-page,.ttc-page){gap:12px!important}
  body.ab-apex :where(.ttq-topbar,.tti-topbar,.ttc-topbar){min-height:0!important;padding:22px 18px 20px!important;display:grid!important;gap:20px!important;border-radius:22px!important}
  body.ab-apex :where(.ttq-heading h1,.tti-heading h1,.ttc-heading h1){font-size:34px!important}
  body.ab-apex :where(.ttq-top-actions,.tti-top-actions,.ttc-top-actions){display:grid!important;grid-template-columns:minmax(0,1fr) auto!important;width:100%!important;margin:0!important}
  body.ab-apex :where(.ttq-search,.tti-search,.ttc-search){min-width:0!important;width:100%!important}
  body.ab-apex :where(.ttq-new-menu,.tti-new,.ttc-new){width:auto!important}
  body.ab-apex :where(.ttq-filters,.tti-filters,.ttc-filters){display:grid!important;grid-template-columns:repeat(2,minmax(0,1fr))!important;padding:12px!important;border-radius:16px!important}
  body.ab-apex :where(.ttq-filters,.tti-filters,.ttc-filters) :where(label,select,details){width:100%!important;min-width:0!important}
  body.ab-apex :where(.ttq-select select,.tti-select select,.ttc-select select,.ttq-mobile-sort select,.tti-mobile-sort select,.ttc-mobile-sort select){width:100%!important}
  body.ab-apex .tti-kpis{grid-template-columns:repeat(2,minmax(0,1fr))!important;gap:8px!important}
  body.ab-apex .tti-kpi{min-height:94px!important;padding:15px!important}
  body.ab-apex :where(.ttq-table-wrap,.tti-table-wrap,.ttc-table-wrap){border:0!important;border-radius:0!important;background:transparent!important;box-shadow:none!important;overflow:visible!important}
  body.ab-apex :where(.ttq-table,.tti-table,.ttc-table),body.ab-apex :where(.ttq-table,.tti-table,.ttc-table) tbody{display:block!important;background:transparent!important}
  body.ab-apex :where(.ttq-table,.tti-table) thead{display:none!important}
  body.ab-apex .ttc-table thead{display:block!important;position:absolute!important;width:1px!important;height:1px!important;margin:-1px!important;padding:0!important;overflow:hidden!important;clip:rect(0,0,0,0)!important;clip-path:inset(50%)!important;white-space:nowrap!important}
  body.ab-apex .ttc-table thead tr{display:block!important}
  body.ab-apex .ttc-table thead th{display:inline-block!important;width:auto!important;height:auto!important}
  body.ab-apex :where(.ttq-table tr[data-quote-row],.tti-table tr[data-invoice-row],.ttc-table tr[data-catalogue-row]){display:grid!important;grid-template-columns:1fr!important;gap:0!important;margin:0 0 10px!important;padding:15px 16px!important;border:1px solid #ddd5c8!important;border-radius:18px!important;background:linear-gradient(180deg,#fffefa,#fbf8f1)!important;box-shadow:0 10px 26px rgba(16,18,21,.05)!important}
  body.ab-apex :where(.ttq-table tr[data-quote-row],.tti-table tr[data-invoice-row],.ttc-table tr[data-catalogue-row]) td{display:flex!important;align-items:flex-start!important;justify-content:space-between!important;gap:14px!important;padding:7px 0!important;border:0!important;text-align:right!important;white-space:normal!important}
  body.ab-apex :where(.ttq-table tr[data-quote-row],.tti-table tr[data-invoice-row],.ttc-table tr[data-catalogue-row]) td:before{content:attr(data-label)!important;flex:0 0 38%;color:#9a9389!important;font-size:8px!important;font-weight:850!important;letter-spacing:.08em!important;text-transform:uppercase!important;text-align:left!important}
  body.ab-apex :where(.ttq-table tr[data-quote-row],.tti-table tr[data-invoice-row],.ttc-table tr[data-catalogue-row]) :where(.ttq-title,.tti-title,.ttc-title){max-width:100%!important;white-space:normal!important;text-align:right!important}
  body.ab-apex:has(.tt-document-form) .tt-pagehead{min-height:0!important;padding:22px 18px!important;border-radius:22px!important}
  body.ab-apex:has(.tt-document-form) .tt-pagehead h1{font-size:34px!important}
  body.ab-apex .tt-document-form{gap:11px!important}
  body.ab-apex .tt-document-form>.tt-card,body.ab-apex .tt-document-form>.tt-services{padding:16px!important;border-radius:17px!important}
  body.ab-apex .tt-document-form .tt-two{grid-template-columns:minmax(0,1fr)!important;gap:12px!important}
  body.ab-apex .tt-document-form :where(input,select,textarea){min-height:48px!important;font-size:16px!important}
}
@media(max-width:520px){
  body.ab-apex :where(.ttq-top-actions,.tti-top-actions,.ttc-top-actions){grid-template-columns:minmax(0,1fr)!important}
  body.ab-apex :where(.ttq-new-menu,.ttq-new-menu>summary,.tti-new,.ttc-new){width:100%!important}
  body.ab-apex :where(.ttq-filters,.tti-filters,.ttc-filters){grid-template-columns:minmax(0,1fr)!important}
  body.ab-apex .tti-kpis{grid-template-columns:minmax(0,1fr)!important}
  body.ab-apex :where(.nx-assistant-fab,.assistant-fab){right:76px!important}
}
""")

    write("static/js/ab-bau-v3-finance-mobile-pdf-hotfix.js", r"""
(() => {
  "use strict";
  const MARK = "A_BAU_V3_FINANCE_MOBILE_PDF_HOTFIX_2026_09_08";
  if (window[MARK]) return;
  window[MARK] = true;
  const body = document.body;
  if (!body) return;

  const menuButton = document.querySelector("[data-nx-menu]");
  const sidebar = document.querySelector(".nx-sidebar");
  const overlay = document.querySelector("[data-nx-menu-overlay]");
  const mobile = () => window.matchMedia("(max-width: 860px)").matches;
  const setMenu = (open) => {
    const next = Boolean(open && mobile());
    body.classList.toggle("nx-menu-open", next);
    menuButton?.setAttribute("aria-expanded", next ? "true" : "false");
    sidebar?.toggleAttribute("data-ab-mobile-open", next);
    if (next) {
      document.querySelector("[data-ab-v3-command].is-open [data-ab-v3-command-close]")?.click();
    }
  };

  document.addEventListener("click", (event) => {
    const more = event.target.closest?.("[data-ab-open-menu]");
    if (!more) return;
    event.preventDefault();
    event.stopImmediatePropagation();
    setMenu(true);
  }, true);

  overlay?.addEventListener("click", () => setMenu(false));
  sidebar?.querySelectorAll("a").forEach((link) => link.addEventListener("click", () => {
    if (mobile()) setMenu(false);
  }));
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && body.classList.contains("nx-menu-open")) setMenu(false);
  });
  window.matchMedia("(min-width: 861px)").addEventListener?.("change", (event) => {
    if (event.matches) setMenu(false);
  });

  if (document.querySelector(".ttq-page")) body.classList.add("ab-v3-quotes");
  if (document.querySelector(".tti-page")) body.classList.add("ab-v3-invoices");
  if (document.querySelector(".ttc-page")) body.classList.add("ab-v3-catalogue");
  if (document.querySelector(".tt-document-form")) body.classList.add("ab-v3-document-editor");
  body.dataset.abFinanceMobilePdfHotfix = "ready";
})();
""")


def patch_base() -> None:
    rel = "templates/rebuild/base.html"
    text = read(rel)
    css = f'<link rel="stylesheet" href="/static/css/ab-bau-v3-finance-mobile-pdf-hotfix.css?v={VERSION}">'
    js = f'<script src="/static/js/ab-bau-v3-finance-mobile-pdf-hotfix.js?v={VERSION}" defer></script>'
    if "ab-bau-v3-finance-mobile-pdf-hotfix.css" not in text:
        if "</head>" not in text:
            raise RuntimeError("V3 finance/mobile/PDF hotfix: base head anchor missing")
        text = text.replace("</head>", f"  {css}\n</head>", 1)
    if "ab-bau-v3-finance-mobile-pdf-hotfix.js" not in text:
        if "</body>" not in text:
            raise RuntimeError("V3 finance/mobile/PDF hotfix: base body anchor missing")
        text = text.replace("</body>", f"{js}\n</body>", 1)
    write(rel, text)


def patch_logo_persistence() -> None:
    rel = "erp/tooltime_parity_views.py"
    text = read(rel)
    save_line = "                org.logo.save(logo.name, logo, save=True)\n"
    show_line = '                cfg.setdefault("logo", {})["show"] = True\n'
    if show_line not in text:
        if save_line not in text:
            raise RuntimeError("V3 PDF logo hotfix: organization logo save anchor missing")
        text = text.replace(save_line, save_line + show_line, 1)
    write(rel, text)


def patch_pdf_logo_embedding() -> None:
    rel = "erp/services/business_pdf_identity.py"
    text = read(rel)
    if "import base64\n" not in text:
        future = "from __future__ import annotations\n"
        if future not in text:
            raise RuntimeError("V3 PDF logo hotfix: helper future import missing")
        text = text.replace(future, future + "\nimport base64\n", 1)

    if "def _file_data_uri(field):" not in text:
        anchor = "def business_identity(org):\n"
        if anchor not in text:
            raise RuntimeError("V3 PDF logo hotfix: business_identity anchor missing")
        helper = r"""
def _file_data_uri(field):
    # PDF generation must not depend on public MEDIA_URL/reverse-proxy reachability.
    try:
        name = str(getattr(field, "name", "") or "")
        if not name:
            return ""
        ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
        mime = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg"}.get(ext)
        if not mime:
            return ""
        field.open("rb")
        try:
            payload = field.read()
        finally:
            field.close()
        if not payload:
            return ""
        encoded = base64.b64encode(payload).decode("ascii")
        return f"data:{mime};base64,{encoded}"
    except Exception:
        return ""


"""
        text = text.replace(anchor, helper + anchor, 1)

    old = '            logo_html = f\'<div class="kayi-document-logo" style="text-align:{position}"><img src="{_e(org.logo.url)}" style="max-width:{width}px;max-height:80px"></div>\'\n'
    new = '            logo_src = _file_data_uri(org.logo)\n            if logo_src:\n                logo_html = f\'<div class="kayi-document-logo" style="text-align:{position}"><img src="{logo_src}" style="max-width:{width}px;max-height:80px"></div>\'\n'
    if "logo_src = _file_data_uri(org.logo)" not in text:
        if old not in text:
            raise RuntimeError("V3 PDF logo hotfix: public MEDIA_URL logo anchor missing")
        text = text.replace(old, new, 1)

    write(rel, text)


def install_tests() -> None:
    write("tests/test_ab_bau_v3_finance_mobile_pdf_hotfix.py", r"""from pathlib import Path
from django.test import SimpleTestCase

ROOT = Path(__file__).resolve().parents[1]


class ABauV3FinanceMobilePdfHotfixTests(SimpleTestCase):
    def test_hotfix_assets_load_after_assembled_shell(self):
        base = (ROOT / "templates/rebuild/base.html").read_text(encoding="utf-8")
        self.assertIn("ab-bau-v3-finance-mobile-pdf-hotfix.css", base)
        self.assertIn("ab-bau-v3-finance-mobile-pdf-hotfix.js", base)

    def test_finance_surfaces_share_v3_visual_language(self):
        css = (ROOT / "static/css/ab-bau-v3-finance-mobile-pdf-hotfix.css").read_text(encoding="utf-8")
        for marker in (
            ".ttq-topbar", ".tti-topbar", ".ttc-topbar", ".tt-document-form",
            ".ttq-table-wrap", ".tti-kpis", "linear-gradient(135deg,#090b0e",
            "env(safe-area-inset-bottom)",
        ):
            self.assertIn(marker, css)

    def test_mobile_more_owns_menu_state_and_fabs_do_not_overlap_dock(self):
        js = (ROOT / "static/js/ab-bau-v3-finance-mobile-pdf-hotfix.js").read_text(encoding="utf-8")
        css = (ROOT / "static/css/ab-bau-v3-finance-mobile-pdf-hotfix.css").read_text(encoding="utf-8")
        for marker in ("[data-ab-open-menu]", "stopImmediatePropagation", "nx-menu-open", "aria-expanded"):
            self.assertIn(marker, js)
        self.assertIn(".ab-v3-mobile-fab", css)
        self.assertIn(".nx-assistant-fab", css)
        self.assertIn("bottom:calc(88px + env(safe-area-inset-bottom))", css)
        self.assertIn("right:78px", css)

    def test_mobile_catalogue_keeps_semantic_headers_for_smoke_and_accessibility(self):
        css = (ROOT / "static/css/ab-bau-v3-finance-mobile-pdf-hotfix.css").read_text(encoding="utf-8")
        self.assertIn(".ttc-table thead{display:block!important;position:absolute!important", css)
        self.assertIn(".ttc-table thead th{display:inline-block!important", css)
        self.assertNotIn(":where(.ttq-table,.tti-table,.ttc-table) thead{display:none!important}", css)

    def test_logo_upload_auto_enables_and_pdf_embeds_storage_bytes(self):
        views = (ROOT / "erp/tooltime_parity_views.py").read_text(encoding="utf-8")
        helper = (ROOT / "erp/services/business_pdf_identity.py").read_text(encoding="utf-8")
        self.assertIn('cfg.setdefault("logo", {})["show"] = True', views)
        self.assertIn("def _file_data_uri(field):", helper)
        self.assertIn("base64.b64encode(payload)", helper)
        self.assertIn("logo_src = _file_data_uri(org.logo)", helper)
        self.assertNotIn('_e(org.logo.url)', helper)

    def test_hotfix_runs_after_v3_catalogue_parity(self):
        unpack = (ROOT / "scripts/unpack-source.sh").read_text(encoding="utf-8")
        self.assertGreater(
            unpack.rfind("python3 scripts/ab_bau_v3_finance_mobile_pdf_hotfix.py"),
            unpack.rfind("python3 scripts/ab_bau_v3_catalogue_text_layout_parity.py"),
        )
""")


def guard() -> None:
    base = read("templates/rebuild/base.html")
    css = read("static/css/ab-bau-v3-finance-mobile-pdf-hotfix.css")
    js = read("static/js/ab-bau-v3-finance-mobile-pdf-hotfix.js")
    views = read("erp/tooltime_parity_views.py")
    helper = read("erp/services/business_pdf_identity.py")
    for marker in ("ab-bau-v3-finance-mobile-pdf-hotfix.css", "ab-bau-v3-finance-mobile-pdf-hotfix.js"):
        if marker not in base:
            raise RuntimeError(f"V3 finance/mobile/PDF base contract missing: {marker}")
    for marker in (MARKER, ".ttq-topbar", ".tti-topbar", ".ttc-topbar", ".tt-document-form", ".ab-v3-mobile-fab", ".nx-assistant-fab", ".ttc-table thead{display:block!important"):
        if marker not in css:
            raise RuntimeError(f"V3 finance/mobile/PDF CSS contract missing: {marker}")
    for marker in ("[data-ab-open-menu]", "stopImmediatePropagation", "nx-menu-open"):
        if marker not in js:
            raise RuntimeError(f"V3 mobile menu runtime contract missing: {marker}")
    if 'cfg.setdefault("logo", {})["show"] = True' not in views:
        raise RuntimeError("V3 PDF logo upload no longer enables the configured logo")
    for marker in ("def _file_data_uri(field):", "base64.b64encode(payload)", "logo_src = _file_data_uri(org.logo)"):
        if marker not in helper:
            raise RuntimeError(f"V3 PDF logo embedding contract missing: {marker}")


def main() -> None:
    install_assets()
    patch_base()
    patch_logo_persistence()
    patch_pdf_logo_embedding()
    install_tests()
    guard()
    print(f"{MARKER}: Mehr navigation, FAB spacing, commercial V3 styling and reliable PDF logo embedding installed.")


if __name__ == "__main__":
    main()
