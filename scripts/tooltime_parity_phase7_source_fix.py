from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# The Phase-7 patcher embeds an f-string PDF body inside a raw multiline source
# patch. Normalize the inner delimiter before Python imports/runs the patcher.
path = ROOT / "scripts" / "tooltime_parity_phase7_e2e_flow.py"
text = path.read_text(encoding="utf-8")
old_open = "    body = f'''<html><body style=\"font-family:Arial,sans-serif;font-size:11px;color:#202428\">\n"
new_open = '    body = f"""<html><body style="font-family:Arial,sans-serif;font-size:11px;color:#202428">\n'
old_close = "</body></html>'''\n    payload = html_to_pdf_bytes(inject_business_pdf_identity(body, org=quote.organization, document_kind=\"Auftragsbestätigung\"))\n"
new_close = '</body></html>"""\n    payload = html_to_pdf_bytes(inject_business_pdf_identity(body, org=quote.organization, document_kind="Auftragsbestätigung"))\n'
if old_open in text:
    text = text.replace(old_open, new_open, 1)
if old_close in text:
    text = text.replace(old_close, new_close, 1)
compile(text, str(path), "exec")
path.write_text(text, encoding="utf-8")

# The assembled finance source has passed through several historical repair layers,
# so the exact one-line invoice_dunning anchor is not stable. Apply the role guard
# directly to the assembled target here. The Phase-7 patcher sees the marker and
# intentionally skips its legacy exact-anchor fallback afterwards.
finance_path = ROOT / "erp" / "tooltime_parity_finance.py"
finance = finance_path.read_text(encoding="utf-8")
if "Mahnungen sind nur für Büro" not in finance:
    function_marker = "def invoice_dunning(request, pk):\n"
    start = finance.find(function_marker)
    if start < 0:
        raise RuntimeError("Phase 7 source repair: invoice_dunning function missing")
    window_end = min(len(finance), start + 1200)
    segment = finance[start:window_end]
    semicolon_line = "    org = _org(request); invoice = get_object_or_404(m.Invoice, organization=org, pk=pk)\n"
    plain_org_line = "    org = _org(request)\n"
    invoice_line = "    invoice = get_object_or_404(m.Invoice, organization=org, pk=pk)\n"
    guard = (
        "    role = str(getattr(getattr(request.user, \"profile\", None), \"role\", \"\") or \"\")\n"
        "    if not (getattr(request.user, \"is_superuser\", False) or role in {\"admin\", \"office\", \"project_manager\", \"accounting\"}):\n"
        "        messages.error(request, \"Mahnungen sind nur für Büro, Projektleitung oder Buchhaltung freigegeben.\")\n"
        "        return redirect(\"next-invoices\")\n"
    )
    if semicolon_line in segment:
        replacement = plain_org_line + guard + invoice_line
        finance = finance[:start] + segment.replace(semicolon_line, replacement, 1) + finance[window_end:]
    else:
        org_pos = finance.find(plain_org_line, start, window_end)
        invoice_pos = finance.find(invoice_line, start, window_end)
        if org_pos < 0 or invoice_pos < 0 or invoice_pos < org_pos:
            raise RuntimeError("Phase 7 source repair: invoice_dunning organization/invoice lookup anchor missing")
        insert_at = org_pos + len(plain_org_line)
        finance = finance[:insert_at] + guard + finance[insert_at:]
    compile(finance, str(finance_path), "exec")
    finance_path.write_text(finance, encoding="utf-8")

print("ToolTime Phase 7 source repair: PDF delimiter and dunning role guard are assembly-tolerant.")
