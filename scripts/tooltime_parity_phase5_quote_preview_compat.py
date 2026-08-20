from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

views_path = ROOT / "erp" / "tooltime_parity_views.py"
text = views_path.read_text(encoding="utf-8")

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

old_quote_pdf = '''def quote_pdf(request, pk):
    org = _org(request)
    quote = get_object_or_404(m.Quote, organization=org, pk=pk)
    try:
        payload = _phase5_quote_pdf_bytes(quote)
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
elif new_quote_pdf not in text:
    raise RuntimeError("Phase 5 quote-preview route anchor missing")

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
test_path.write_text(test_text, encoding="utf-8")
compile(test_text, str(test_path), "exec")

print("ToolTime Phase 5 Angebots-PDF-Kompatibilität: Entwurfsvorschau bleibt verfügbar, E-Mail-Versand bleibt finalisierungspflichtig.")
