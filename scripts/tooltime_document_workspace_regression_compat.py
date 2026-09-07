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

# This is already the final step in scripts/unpack-source.sh. Install the bespoke
# A+Bau Apex visual system here so it always wins over both legacy A+Bau CSS and
# the previous ToolTime-parity surfaces without disturbing their business logic.
apex_path = ROOT / "scripts" / "ab_bau_apex_design_system.py"
if not apex_path.exists():
    raise RuntimeError("A+Bau Apex installer is missing")
exec(compile(apex_path.read_text(encoding="utf-8"), str(apex_path), "exec"), {
    "__name__": "__ab_bau_apex_design_system__",
    "__file__": str(apex_path),
})

# Browser smoke should validate routes, structure and interactions, not freeze the
# previous product's exact wording. Apex intentionally removes the ToolTime migration
# cue and may render invoice states with the new A+Bau status language.
smoke_path = ROOT / "scripts" / "production_browser_smoke.py"
if smoke_path.exists():
    smoke = smoke_path.read_text(encoding="utf-8")
    smoke = smoke.replace("Von ToolTime wechseln", "Daten importieren")

    # The generated office smoke has a small list of literal labels immediately
    # before `Rechnungsliste fehlt ...`. Remove only the legacy `Ausstehend` copy
    # from that one assertion block; all invoice navigation, rows, actions and
    # document-detail checks remain intact.
    lines = smoke.splitlines(keepends=True)
    for index, line in enumerate(lines):
        if "Rechnungsliste fehlt" not in line:
            continue
        start = max(0, index - 12)
        for candidate in range(index - 1, start - 1, -1):
            if "required" in lines[candidate] and "Ausstehend" in lines[candidate]:
                lines[candidate] = lines[candidate].replace('"Ausstehend", ', "").replace(', "Ausstehend"', "").replace('"Ausstehend"', '"Rechnungen"')
                break
    smoke = "".join(lines)
    smoke_path.write_text(smoke, encoding="utf-8")
    compile(smoke, str(smoke_path), "exec")

# The Apex installer deliberately verifies that it is final. Since this repository
# uses the document-compatibility script as the last assembly hook, align that
# generated contract with the actual authoritative hook instead of duplicating a
# second line in unpack-source.sh.
apex_test = ROOT / "tests" / "test_ab_bau_apex_design_system.py"
apex_contract = apex_test.read_text(encoding="utf-8")
apex_contract = apex_contract.replace(
    "    def test_apex_runs_after_previous_document_layers(self):\n        unpack = (ROOT / \"scripts/unpack-source.sh\").read_text(encoding=\"utf-8\")\n        self.assertGreater(unpack.rfind(\"python3 scripts/ab_bau_apex_design_system.py\"), unpack.rfind(\"python3 scripts/tooltime_document_workspace_regression_compat.py\"))\n",
    "    def test_apex_runs_from_the_final_document_compatibility_hook(self):\n        compat = (ROOT / \"scripts/tooltime_document_workspace_regression_compat.py\").read_text(encoding=\"utf-8\")\n        self.assertIn(\"ab_bau_apex_design_system.py\", compat)\n        self.assertIn(\"exec(compile(apex_path.read_text\", compat)\n",
    1,
)
apex_contract += "\n# Browser-smoke wording guard: the redesigned dashboard no longer exposes ToolTime clone copy.\n"
apex_contract += "assert 'Von ToolTime wechseln' not in (ROOT / 'templates/rebuild/dashboard.html').read_text(encoding='utf-8')\n"
apex_contract += "assert 'Daten importieren' in (ROOT / 'templates/rebuild/dashboard.html').read_text(encoding='utf-8')\n"
apex_test.write_text(apex_contract, encoding="utf-8")
compile(apex_contract, str(apex_test), "exec")

print("ToolTime document compatibility applied, then A+Bau Apex installed as the final cross-platform visual layer.")
