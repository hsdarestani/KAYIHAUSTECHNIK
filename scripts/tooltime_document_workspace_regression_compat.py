from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# The previous quote-detail layer intentionally tested the temporary ?preview=1
# workaround. The final document workspace replaces that workaround with a
# dedicated same-origin endpoint, so keep the older regression suite aligned with
# the stronger contract instead of restoring the broken iframe behaviour.
test_path = ROOT / "tests" / "test_tooltime_quote_postdraft_detail_contract.py"
text = test_path.read_text(encoding="utf-8")
text = text.replace(
    "def test_pdf_supports_inline_preview_without_changing_download_contract(self):",
    "def test_pdf_supports_dedicated_inline_preview_without_changing_download_contract(self):",
    1,
)
text = text.replace(
    "        self.assertIn('?preview=1', detail)\n",
    "        self.assertIn('next-quote-preview', detail)\n        self.assertNotIn(\"next-quote-pdf' quote.pk %}?preview=1\", detail)\n",
    1,
)
test_path.write_text(text, encoding="utf-8")
compile(text, str(test_path), "exec")

# Do not guess an E-Rechnung download route. The finalized workspace already
# exposes the canonical immutable PDF and E-Rechnung status. A dedicated XML
# download button should only be added if the compliance layer provides a named
# route for it.
template_path = ROOT / "templates" / "rebuild" / "invoice_detail.html"
template = template_path.read_text(encoding="utf-8")
template = template.replace(
    "{% if compliance.original_xml_document_id %}<a class=\"nx-btn\" href=\"{% url 'invoice-compliance-xml' invoice.pk %}\">E-Rechnung herunterladen</a>{% endif %}",
    "",
)
template_path.write_text(template, encoding="utf-8")

print("ToolTime document workspace regression compatibility applied: dedicated quote preview is authoritative and no unverified XML route is rendered.")
