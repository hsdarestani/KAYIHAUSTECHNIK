from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

views_path = ROOT / "erp" / "tooltime_parity_views.py"
text = views_path.read_text(encoding="utf-8")

# Phase 5 may run after earlier layers already expanded the django.http import.
# Normalize that import semantically. Quote previews are byte-backed because the
# PDF payload is already materialized; canonical invoice/document downloads may
# continue using FileResponse where streaming is useful.
http_lines = [line for line in text.splitlines() if line.startswith("from django.http import ")]
if not http_lines:
    raise RuntimeError("Phase 5 django.http import anchor missing")
http_line = http_lines[0]
http_names = [name.strip() for name in http_line.removeprefix("from django.http import ").split(",") if name.strip()]
for required in ("FileResponse", "Http404", "HttpResponse", "JsonResponse"):
    if required not in http_names:
        http_names.append(required)
text = text.replace(http_line, "from django.http import " + ", ".join(sorted(set(http_names))), 1)

old_helper = '''def _phase5_quote_pdf_bytes(quote):
    meta = meta_for(quote, "quote", create=False)
    if not meta or not meta.finalized_at:
        raise ValueError("PDF und Versand sind erst nach dem Fertigstellen des Angebots verfügbar.")
'''
new_helper = '''def _phase5_quote_pdf_bytes(quote, *, require_finalized=True):
    meta = meta_for(quote, "quote")
    if require_finalized and not meta.finalized_at:
        raise ValueError("Der Versand ist erst nach dem Fertigstellen des Angebots verfügbar.")
'''
if old_helper in text:
    text = text.replace(old_helper, new_helper, 1)
elif new_helper not in text:
    raise RuntimeError("Phase 5 quote-preview helper anchor missing")

# A ToolTime-like PDF preview should be a useful commercial document, not a thin
# technical export. Enrich the same authoritative quote calculation with project,
# customer and company context. Drafts stay visibly marked and never consume an
# official offer number.
detail_anchor = '''    intro = html.escape(str(getattr(quote, "intro_text", "") or "")).replace("\\n", "<br>")
    outro = html.escape(str(getattr(quote, "outro_text", "") or "")).replace("\\n", "<br>")
'''
detail_block = '''    intro = html.escape(str(getattr(quote, "intro_text", "") or "")).replace("\\n", "<br>")
    outro = html.escape(str(getattr(quote, "outro_text", "") or "")).replace("\\n", "<br>")
    org = quote.organization
    project = getattr(quote, "project", None)
    project_label = " · ".join(filter(None, [str(getattr(project, "number", "") or ""), str(getattr(project, "title", "") or "")]))
    document_number = quote.number or meta.final_number or "ENTWURF"
    draft_notice = "" if meta.finalized_at else (
        "<div style='margin:0 0 16px;padding:9px 12px;border:1px solid #d6b15e;background:#fff8e8'>"
        "<strong>ENTWURF · Angebotsvorschau</strong><br>"
        "Diese Vorschau besitzt noch keine endgültige Angebotsnummer und ist nicht zum Versand freigegeben."
        "</div>"
    )
    customer_details = "<br>".join(filter(None, [
        html.escape(str(customer_name)),
        html.escape(str(getattr(customer, "company", "") or "")) if customer and getattr(customer, "company", "") != customer_name else "",
        html.escape(str(getattr(customer, "email", "") or "")) if customer else "",
        html.escape(str(getattr(customer, "phone", "") or getattr(customer, "mobile", "") or "")) if customer else "",
    ]))
    company_details = " · ".join(filter(None, [
        str(getattr(org, "legal_name", "") or getattr(org, "name", "") or ""),
        str(getattr(org, "address", "") or "").replace("\\n", ", "),
        ("E-Mail: " + str(getattr(org, "email", ""))) if getattr(org, "email", "") else "",
        ("Tel.: " + str(getattr(org, "phone", ""))) if getattr(org, "phone", "") else "",
    ]))
    legal_details = " · ".join(filter(None, [
        ("Steuernummer/USt.-ID: " + str(getattr(org, "tax_id", ""))) if getattr(org, "tax_id", "") else "",
        ("IBAN: " + str(getattr(org, "iban", ""))) if getattr(org, "iban", "") else "",
    ]))
    context_block = (
        draft_notice
        + "<table style='width:100%;margin:0 0 16px;border-collapse:collapse'><tr>"
        + "<td style='vertical-align:top;width:55%'><strong>Kunde</strong><br>" + customer_details + ("<br>" + html.escape(address) if address else "") + "</td>"
        + "<td style='vertical-align:top'><strong>Dokument</strong><br>Nr.: " + html.escape(str(document_number))
        + ("<br>Projekt: " + html.escape(project_label) if project_label else "")
        + f"<br>Datum: {quote.issue_date:%d.%m.%Y}</td></tr></table>"
    )
    intro = context_block + ("<div style='margin:0 0 16px'>" + intro + "</div>" if intro else "")
    footer_details = "<div style='margin-top:24px;padding-top:10px;border-top:1px solid #ddd;font-size:9px;color:#555'>" + html.escape(company_details)
    if legal_details:
        footer_details += "<br>" + html.escape(legal_details)
    footer_details += "</div>"
    outro = ("<div style='margin-top:18px'>" + outro + "</div>" if outro else "") + footer_details
'''
if detail_anchor in text:
    text = text.replace(detail_anchor, detail_block, 1)
elif "draft_notice = \"\" if meta.finalized_at" not in text:
    raise RuntimeError("Phase 5 quote PDF detail anchor missing")

old_heading = '''<h1 style="margin-bottom:4px">{html.escape(meta.document_title or 'Angebot')} {html.escape(quote.number or meta.final_number or '')}</h1>
'''
new_heading = '''<h1 style="margin-bottom:4px">{html.escape(meta.document_title or 'Angebot')} {html.escape(str(document_number))}</h1>
'''
if old_heading in text:
    text = text.replace(old_heading, new_heading, 1)
elif new_heading not in text:
    raise RuntimeError("Phase 5 quote PDF heading anchor missing")

old_quote_pdf = '''def quote_pdf(request, pk):
    org = _org(request)
    quote = get_object_or_404(m.Quote, organization=org, pk=pk)
    try:
        payload = _phase5_quote_pdf_bytes(quote)
'''
old_quote_pdf_local_stream = '''def quote_pdf(request, pk):
    from django.http import FileResponse

    org = _org(request)
    quote = get_object_or_404(m.Quote, organization=org, pk=pk)
    try:
        # A draft PDF is a preview only. It does not allocate/finalize a number and
        # it is never eligible for the e-mail delivery workflow below.
        payload = _phase5_quote_pdf_bytes(quote, require_finalized=False)
'''
new_quote_pdf = '''def quote_pdf(request, pk):
    org = _org(request)
    quote = get_object_or_404(m.Quote, organization=org, pk=pk)
    try:
        # A draft PDF is a preview only. It does not allocate/finalize a number and
        # it is never eligible for the e-mail delivery workflow below.
        payload = _phase5_quote_pdf_bytes(quote, require_finalized=False)
'''
if old_quote_pdf in text:
    text = text.replace(old_quote_pdf, new_quote_pdf, 1)
elif old_quote_pdf_local_stream in text:
    text = text.replace(old_quote_pdf_local_stream, new_quote_pdf, 1)
elif new_quote_pdf not in text:
    raise RuntimeError("Phase 5 quote-preview route anchor missing")

old_quote_response = '''    return FileResponse(io.BytesIO(payload), as_attachment=True, content_type="application/pdf", filename=f"angebot-{quote.number or quote.pk}.pdf")
'''
new_quote_response = '''    response = HttpResponse(payload, content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="angebot-{quote.number or quote.pk}.pdf"'
    return response
'''
if old_quote_response in text:
    text = text.replace(old_quote_response, new_quote_response, 1)
elif new_quote_response not in text:
    raise RuntimeError("Phase 5 quote PDF response anchor missing")

views_path.write_text(text, encoding="utf-8")
compile(text, str(views_path), "exec")

# Keep the Phase-5 contract precise: PDF preview is allowed for drafts, actual
# delivery still requires a finalized quote and remains server-enforced.
test_path = ROOT / "tests" / "test_tooltime_phase5_communication_contract.py"
test_text = test_path.read_text(encoding="utf-8")
test_text = test_text.replace(
    "def test_real_email_routes_and_pdf_download_are_post_finalization_only(self):",
    "def test_pdf_preview_exists_but_real_email_is_post_finalization_only(self):",
    1,
)
test_text = test_text.replace(
    'self.assertIn("PDF und Versand sind erst nach dem Fertigstellen des Angebots verfügbar.", views)',
    'self.assertIn("Der Versand ist erst nach dem Fertigstellen des Angebots verfügbar.", views)\n        self.assertIn("_phase5_quote_pdf_bytes(quote, require_finalized=False)", views)',
    1,
)
test_text = test_text.replace(
    '        self.assertIn("from django.http import FileResponse", views)\n',
    '        self.assertIn("HttpResponse(payload, content_type=\\"application/pdf\\")", views)\n',
    1,
)
if 'self.assertIn("HttpResponse(payload, content_type=\\"application/pdf\\")", views)' not in test_text:
    anchor = '        self.assertIn("_phase5_quote_pdf_bytes(quote, require_finalized=False)", views)\n'
    if anchor not in test_text:
        raise RuntimeError("Phase 5 quote HttpResponse test anchor missing")
    test_text = test_text.replace(anchor, anchor + '        self.assertIn("HttpResponse(payload, content_type=\\"application/pdf\\")", views)\n', 1)
if 'self.assertIn("ENTWURF · Angebotsvorschau", views)' not in test_text:
    anchor = '        self.assertIn("HttpResponse(payload, content_type=\\"application/pdf\\")", views)\n'
    if anchor not in test_text:
        raise RuntimeError("Phase 5 quote PDF richness test anchor missing")
    test_text = test_text.replace(anchor, anchor + '        self.assertIn("ENTWURF · Angebotsvorschau", views)\n        self.assertIn("Steuernummer/USt.-ID:", views)\n', 1)
test_path.write_text(test_text, encoding="utf-8")
compile(test_text, str(test_path), "exec")

print("ToolTime Phase 5 Angebots-PDF-Kompatibilität: Entwurfsvorschau enthält Kunde, Projekt, Kalkulation und Geschäftsangaben; E-Mail-Versand bleibt finalisierungspflichtig.")
