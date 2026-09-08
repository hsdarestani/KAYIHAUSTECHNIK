from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MARKER = "A+BAU V3 APPOINTMENT DETAIL LAYOUT FIX 2026-09-08"
DETAIL_REL = "templates/rebuild/appointment_detail.html"
BASE_REL = "templates/rebuild/base.html"
CSS_REL = "static/css/ab-bau-v3-appointment-detail.css"
CSS_LINK = '<link rel="stylesheet" href="/static/css/ab-bau-v3-appointment-detail.css?v=20260908-1">'


def read(rel: str) -> str:
    path = ROOT / rel
    if not path.exists():
        raise RuntimeError(f"Appointment detail layout target missing: {rel}")
    return path.read_text(encoding="utf-8")


def write(rel: str, text: str) -> None:
    path = ROOT / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def patch_detail_template() -> None:
    text = read(DETAIL_REL)
    if "data-ab-v3-appointment-detail" not in text:
        anchor = '<div class="nx-field-shell">'
        replacement = '<div class="nx-field-shell ab-v3-appointment-detail" data-ab-v3-appointment-detail>'
        if anchor not in text:
            raise RuntimeError("Appointment detail layout wrapper anchor missing")
        text = text.replace(anchor, replacement, 1)
    write(DETAIL_REL, text)


def patch_base_stylesheet() -> None:
    text = read(BASE_REL)
    if CSS_LINK not in text:
        if "</head>" not in text:
            raise RuntimeError("Appointment detail layout base </head> anchor missing")
        text = text.replace("</head>", f"  {CSS_LINK}\n</head>", 1)
    write(BASE_REL, text)


def install_css() -> None:
    write(
        CSS_REL,
        r'''/* A+BAU V3 APPOINTMENT DETAIL LAYOUT FIX 2026-09-08 */
body.ab-v3 .ab-v3-appointment-detail{
  width:100%!important;
  max-width:1240px!important;
  margin:0 auto!important;
  display:grid!important;
  gap:16px!important;
  min-width:0;
}
body.ab-v3 .ab-v3-appointment-detail>*{min-width:0}
body.ab-v3 .ab-v3-appointment-detail>.nx-pagehead{
  display:grid!important;
  grid-template-columns:minmax(0,1fr) auto!important;
  align-items:end!important;
  gap:22px!important;
  margin:0 0 2px!important;
  padding:0 2px 18px!important;
  border-bottom:1px solid var(--v3-line,#d9d2c5)!important;
}
body.ab-v3 .ab-v3-appointment-detail>.nx-pagehead h1{
  margin:5px 0 3px!important;
  font-size:clamp(28px,3vw,42px)!important;
  line-height:1.02!important;
  letter-spacing:-.045em!important;
}
body.ab-v3 .ab-v3-appointment-detail>.nx-pagehead p{margin:0!important;color:var(--v3-muted,#77736b)!important}
body.ab-v3 .ab-v3-appointment-detail>.nx-pagehead .nx-actions{
  display:flex!important;
  align-items:center!important;
  justify-content:flex-end!important;
  flex-wrap:wrap!important;
  gap:8px!important;
}

/* The production page currently contains the Phase-14 summary/process markup,
   but its old page-specific stylesheet can be dropped by later V3 assembly layers.
   Keep the final visual contract here so the information never falls back to raw text. */
body.ab-v3 .ab-v3-appointment-detail .tt-appt-detail-summary{
  display:grid!important;
  gap:16px!important;
  margin:0!important;
  padding:20px!important;
  border:1px solid var(--v3-line,#d9d2c5)!important;
  border-radius:20px!important;
  background:rgba(255,253,248,.97)!important;
  box-shadow:0 12px 34px rgba(14,16,19,.05)!important;
}
body.ab-v3 .ab-v3-appointment-detail .tt-appt-detail-summary-head{
  display:flex!important;
  align-items:center!important;
  justify-content:space-between!important;
  gap:16px!important;
  padding-bottom:14px!important;
  border-bottom:1px solid #e8e1d5!important;
}
body.ab-v3 .ab-v3-appointment-detail .tt-appt-detail-summary-head>div{display:grid!important;gap:3px!important}
body.ab-v3 .ab-v3-appointment-detail .tt-appt-detail-summary-head span,
body.ab-v3 .ab-v3-appointment-detail .tt-appt-detail-facts span,
body.ab-v3 .ab-v3-appointment-detail .tt-appt-detail-note small,
body.ab-v3 .ab-v3-appointment-detail .tt-appt-detail-location small,
body.ab-v3 .ab-v3-appointment-detail .tt-appt-process-head span{
  color:#8b857c!important;
  font-size:9px!important;
  font-weight:820!important;
  letter-spacing:.12em!important;
  text-transform:uppercase!important;
}
body.ab-v3 .ab-v3-appointment-detail .tt-appt-detail-summary-head strong,
body.ab-v3 .ab-v3-appointment-detail .tt-appt-process-head strong{
  color:#181a1d!important;
  font-size:16px!important;
  letter-spacing:-.02em!important;
}
body.ab-v3 .ab-v3-appointment-detail .tt-appt-detail-facts{
  display:grid!important;
  grid-template-columns:1.05fr .75fr 1fr 1.35fr!important;
  gap:10px!important;
}
body.ab-v3 .ab-v3-appointment-detail .tt-appt-detail-facts>div{
  display:grid!important;
  align-content:start!important;
  gap:5px!important;
  min-width:0!important;
  padding:13px 14px!important;
  border:1px solid #e7e0d5!important;
  border-radius:13px!important;
  background:#faf7f1!important;
}
body.ab-v3 .ab-v3-appointment-detail .tt-appt-detail-facts strong{
  overflow-wrap:anywhere!important;
  color:#2d3034!important;
  font-size:12px!important;
  line-height:1.45!important;
}
body.ab-v3 .ab-v3-appointment-detail .tt-appt-detail-location{
  display:flex!important;
  align-items:center!important;
  gap:12px!important;
  padding:13px 15px!important;
  border:1px solid #e4ddd0!important;
  border-radius:13px!important;
  background:#f3efe6!important;
}
body.ab-v3 .ab-v3-appointment-detail .tt-appt-detail-location>span{
  display:grid!important;
  place-items:center!important;
  flex:0 0 38px!important;
  width:38px!important;
  height:38px!important;
  border:1px solid #ddd3c2!important;
  border-radius:11px!important;
  background:#fffdf8!important;
  color:#9b7728!important;
  font-size:18px!important;
}
body.ab-v3 .ab-v3-appointment-detail .tt-appt-detail-location>div{display:grid!important;gap:3px!important;min-width:0!important}
body.ab-v3 .ab-v3-appointment-detail .tt-appt-detail-location strong{overflow-wrap:anywhere!important;font-size:12px!important;color:#2f3135!important}
body.ab-v3 .ab-v3-appointment-detail .tt-appt-detail-note{display:grid!important;gap:6px!important;padding:0 2px!important}
body.ab-v3 .ab-v3-appointment-detail .tt-appt-detail-note p{margin:0!important;color:#69645d!important;font-size:11px!important;line-height:1.6!important}

body.ab-v3 .ab-v3-appointment-detail .tt-appt-process-services{
  display:grid!important;
  gap:14px!important;
  margin:0!important;
  padding:19px 20px!important;
  border:1px solid var(--v3-line,#d9d2c5)!important;
  border-radius:18px!important;
  background:rgba(255,253,248,.97)!important;
  box-shadow:0 10px 28px rgba(14,16,19,.04)!important;
}
body.ab-v3 .ab-v3-appointment-detail .tt-appt-process-head{
  display:flex!important;
  align-items:center!important;
  justify-content:space-between!important;
  gap:14px!important;
}
body.ab-v3 .ab-v3-appointment-detail .tt-appt-process-head>div{display:grid!important;gap:3px!important}
body.ab-v3 .ab-v3-appointment-detail .tt-appt-process-group{display:grid!important;gap:7px!important}
body.ab-v3 .ab-v3-appointment-detail .tt-appt-process-group h3{margin:0!important;font-size:12px!important}
body.ab-v3 .ab-v3-appointment-detail .tt-appt-process-table{
  display:grid!important;
  overflow:hidden!important;
  border:1px solid #e5ded2!important;
  border-radius:11px!important;
}
body.ab-v3 .ab-v3-appointment-detail .tt-appt-process-table>div{
  display:grid!important;
  grid-template-columns:120px 80px 80px minmax(0,1fr)!important;
  gap:8px!important;
  padding:9px 11px!important;
  border-top:1px solid #ebe5da!important;
  font-size:11px!important;
}
body.ab-v3 .ab-v3-appointment-detail .tt-appt-process-table>.head{
  border-top:0!important;
  background:#f4f0e8!important;
  color:#817b72!important;
  font-size:8.5px!important;
  font-weight:820!important;
  letter-spacing:.08em!important;
  text-transform:uppercase!important;
}
body.ab-v3 .ab-v3-appointment-detail .tt-appt-process-actions{
  display:flex!important;
  justify-content:flex-end!important;
  flex-wrap:wrap!important;
  gap:8px!important;
}
body.ab-v3 .ab-v3-appointment-detail .tt-appt-process-actions form{margin:0!important}
body.ab-v3 .ab-v3-appointment-detail .tt-appt-process-empty{
  padding:12px!important;
  border:1px dashed #d7cfc2!important;
  border-radius:10px!important;
  background:#faf7f1!important;
  color:#7c766e!important;
  font-size:11px!important;
}

/* Keep the existing signed field workflow intact, only normalize spacing/overflow. */
body.ab-v3 .ab-v3-appointment-detail .nx-job-address,
body.ab-v3 .ab-v3-appointment-detail .nx-card{min-width:0!important;margin-top:0!important}
body.ab-v3 .ab-v3-appointment-detail .nx-doc-section,
body.ab-v3 .ab-v3-appointment-detail .tt-field-service-row,
body.ab-v3 .ab-v3-appointment-detail textarea,
body.ab-v3 .ab-v3-appointment-detail input,
body.ab-v3 .ab-v3-appointment-detail select{min-width:0!important;max-width:100%}

@media(max-width:1180px){
  body.ab-v3 .ab-v3-appointment-detail .tt-appt-detail-facts{grid-template-columns:repeat(2,minmax(0,1fr))!important}
}
@media(max-width:760px){
  body.ab-v3 .ab-v3-appointment-detail{gap:12px!important}
  body.ab-v3 .ab-v3-appointment-detail>.nx-pagehead{grid-template-columns:1fr!important;align-items:start!important;gap:13px!important;padding-bottom:14px!important}
  body.ab-v3 .ab-v3-appointment-detail>.nx-pagehead .nx-actions{justify-content:flex-start!important;width:100%!important}
  body.ab-v3 .ab-v3-appointment-detail .tt-appt-detail-summary{padding:15px!important;border-radius:16px!important}
  body.ab-v3 .ab-v3-appointment-detail .tt-appt-detail-summary-head{align-items:flex-start!important;flex-direction:column!important}
  body.ab-v3 .ab-v3-appointment-detail .tt-appt-detail-facts{grid-template-columns:1fr!important}
  body.ab-v3 .ab-v3-appointment-detail .tt-appt-process-services{padding:15px!important;border-radius:16px!important}
  body.ab-v3 .ab-v3-appointment-detail .tt-appt-process-head{align-items:flex-start!important;flex-direction:column!important}
  body.ab-v3 .ab-v3-appointment-detail .tt-appt-process-head .nx-btn{width:100%!important}
  body.ab-v3 .ab-v3-appointment-detail .tt-appt-process-table{overflow-x:auto!important}
  body.ab-v3 .ab-v3-appointment-detail .tt-appt-process-table>div{min-width:520px!important}
  body.ab-v3 .ab-v3-appointment-detail .tt-appt-process-actions{display:grid!important;grid-template-columns:1fr!important}
  body.ab-v3 .ab-v3-appointment-detail .tt-appt-process-actions .nx-btn{width:100%!important}
}
@media(max-width:480px){
  body.ab-v3 .ab-v3-appointment-detail>.nx-pagehead .nx-actions{display:grid!important;grid-template-columns:1fr 1fr!important}
  body.ab-v3 .ab-v3-appointment-detail>.nx-pagehead .nx-actions .nx-btn{width:100%!important;text-align:center!important}
}
''',
    )


def guard() -> None:
    detail = read(DETAIL_REL)
    base = read(BASE_REL)
    css = read(CSS_REL)
    for marker in (
        "data-ab-v3-appointment-detail",
        "ab-v3-appointment-detail",
        "tt-appt-detail-summary",
        "tt-appt-process-services",
    ):
        if marker not in detail:
            raise RuntimeError(f"Appointment detail layout template guard missing: {marker}")
    if CSS_LINK not in base:
        raise RuntimeError("Appointment detail layout stylesheet link missing")
    for marker in (
        "A+BAU V3 APPOINTMENT DETAIL LAYOUT FIX",
        ".tt-appt-detail-summary",
        ".tt-appt-process-services",
        "grid-template-columns:repeat(2,minmax(0,1fr))",
        "@media(max-width:760px)",
    ):
        if marker not in css:
            raise RuntimeError(f"Appointment detail layout CSS guard missing: {marker}")


def main() -> None:
    patch_detail_template()
    patch_base_stylesheet()
    install_css()
    guard()
    print(f"{MARKER}: appointment detail restored to the V3 desktop/mobile layout without changing workflow behavior.")


if __name__ == "__main__":
    main()
