from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# The Phase-7 patcher embeds an f-string PDF body inside a raw multiline source
# patch. Normalize the inner delimiter before Python imports/runs the patcher.
patcher_path = ROOT / "scripts" / "tooltime_parity_phase7_e2e_flow.py"
patcher = patcher_path.read_text(encoding="utf-8")
old_open = "    body = f'''<html><body style=\"font-family:Arial,sans-serif;font-size:11px;color:#202428\">\n"
new_open = '    body = f"""<html><body style="font-family:Arial,sans-serif;font-size:11px;color:#202428">\n'
old_close = "</body></html>'''\n    payload = html_to_pdf_bytes(inject_business_pdf_identity(body, org=quote.organization, document_kind=\"Auftragsbestätigung\"))\n"
new_close = '</body></html>"""\n    payload = html_to_pdf_bytes(inject_business_pdf_identity(body, org=quote.organization, document_kind="Auftragsbestätigung"))\n'
if old_open in patcher:
    patcher = patcher.replace(old_open, new_open, 1)
if old_close in patcher:
    patcher = patcher.replace(old_close, new_close, 1)

# A raw f-string is correct for the regex pattern, but not for its replacement:
# `\"next-quotes\"` would be emitted literally into the generated Python file.
# Keep the regex backreference escaped while letting the normal f-string turn the
# quoted redirect name into valid Python source.
bad_role_replacement = r'''            rf"\1    phase7_guard = _phase7_commercial_guard(request, \"{redirect_name}\")\n"'''
good_role_replacement = r'''            f"\\1    phase7_guard = _phase7_commercial_guard(request, \"{redirect_name}\")\n"'''
if bad_role_replacement in patcher:
    patcher = patcher.replace(bad_role_replacement, good_role_replacement, 1)
if bad_role_replacement in patcher:
    raise RuntimeError("Phase 7 source repair: raw role-guard replacement remains")

# invoice_dunning is assembled into tooltime_parity_views.py, not the helper model
# module. Make the Phase-7 patcher's own dunning step a verification step so it no
# longer depends on the historical location/format of that endpoint.
fn_start = patcher.find("def patch_dunning_role() -> None:\n")
fn_end = patcher.find("\n\ndef patch_urls() -> None:\n", fn_start)
if fn_start < 0 or fn_end < 0:
    raise RuntimeError("Phase 7 source repair: patch_dunning_role boundaries missing")
replacement_fn = '''def patch_dunning_role() -> None:\n    rel = "erp/tooltime_parity_views.py"\n    text = read(rel)\n    if "Mahnungen sind nur für Büro" not in text:\n        raise RuntimeError("Phase 7 dunning role guard missing from final view endpoint")\n\n'''
patcher = patcher[:fn_start] + replacement_fn + patcher[fn_end + 2:]
compile(patcher, str(patcher_path), "exec")
patcher_path.write_text(patcher, encoding="utf-8")

# Apply the actual guard to the assembled endpoint. This is resilient to the old
# compact `org=...; invoice=...` style and the newer split-line style.
views_path = ROOT / "erp" / "tooltime_parity_views.py"
views = views_path.read_text(encoding="utf-8")
if "Mahnungen sind nur für Büro" not in views:
    function_marker = "def invoice_dunning(request, pk):\n"
    start = views.find(function_marker)
    if start < 0:
        raise RuntimeError("Phase 7 source repair: invoice_dunning view endpoint missing")
    window_end = min(len(views), start + 1800)
    segment = views[start:window_end]
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
        views = views[:start] + segment.replace(semicolon_line, replacement, 1) + views[window_end:]
    else:
        org_pos = views.find(plain_org_line, start, window_end)
        if org_pos < 0:
            raise RuntimeError("Phase 7 source repair: invoice_dunning organization anchor missing")
        insert_at = org_pos + len(plain_org_line)
        views = views[:insert_at] + guard + views[insert_at:]
    compile(views, str(views_path), "exec")
    views_path.write_text(views, encoding="utf-8")

print("ToolTime Phase 7 source repair: PDF delimiter, role-guard escaping and final dunning endpoint are assembly-tolerant.")
