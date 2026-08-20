from __future__ import annotations

import re
import runpy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "scripts" / "tooltime_parity_finance_batch.py"
text = SOURCE.read_text(encoding="utf-8")

pattern = re.compile(r"\n    html = f'''<html><body.*?</body></html>'''\n", re.S)
replacement = r'''
    fee_html = f"<p>Mahngebühr: <strong>{fee:.2f} €</strong></p>" if fee else ""
    html = (
        f"<html><body style=\"font-family:Arial,sans-serif;font-size:12px\"><h1>{heading}</h1>"
        f"<p>Rechnung: <strong>{invoice.number}</strong></p><p>Sehr geehrte Damen und Herren,</p>"
        f"<p>für die oben genannte Rechnung ist aktuell ein offener Betrag von <strong>{open_amount:.2f} €</strong> vorhanden.</p>"
        f"<p>Bitte überweisen Sie den offenen Betrag bis spätestens <strong>{due:%d.%m.%Y}</strong>.</p>"
        + fee_html
        + f"<p>Mit freundlichen Grüßen<br>{org.name}</p></body></html>"
    )
'''
text, count = pattern.subn("\n" + replacement + "\n", text, count=1)
if count != 1:
    raise RuntimeError("ToolTime-Parität: Mahnungs-HTML-Reparaturanker wurde nicht gefunden.")

text = text.replace(
    "from decimal import Decimal\n\nfrom django.contrib import messages",
    "from decimal import Decimal\nfrom datetime import timedelta\n\nfrom django.contrib import messages",
    1,
)
text = text.replace(
    "due = timezone.localdate() + timezone.timedelta(days=due_days)",
    "due = timezone.localdate() + timedelta(days=due_days)",
    1,
)

code = compile(text, str(SOURCE), "exec")
namespace = {"__name__": "__main__", "__file__": str(SOURCE), "__package__": None}
exec(code, namespace)
runpy.run_path(str(ROOT / "scripts" / "tooltime_parity_finance_completion.py"), run_name="__main__")
runpy.run_path(str(ROOT / "scripts" / "tooltime_parity_finance_ui_polish.py"), run_name="__main__")
runpy.run_path(str(ROOT / "scripts" / "tooltime_parity_invoice_wizard.py"), run_name="__main__")
runpy.run_path(str(ROOT / "scripts" / "tooltime_parity_pdf_layout_bridge_runner.py"), run_name="__main__")
runpy.run_path(str(ROOT / "scripts" / "tooltime_parity_migration_alignment.py"), run_name="__main__")
runpy.run_path(str(ROOT / "scripts" / "tooltime_parity_browser_smoke.py"), run_name="__main__")
runpy.run_path(str(ROOT / "scripts" / "tooltime_parity_legacy_contract_bridge.py"), run_name="__main__")
runpy.run_path(str(ROOT / "scripts" / "tooltime_parity_final_ui_safety.py"), run_name="__main__")
runpy.run_path(str(ROOT / "scripts" / "tooltime_parity_draft_render_fix.py"), run_name="__main__")
runpy.run_path(str(ROOT / "scripts" / "tooltime_parity_route_guard.py"), run_name="__main__")
runpy.run_path(str(ROOT / "scripts" / "tooltime_parity_phase1_text_layout.py"), run_name="__main__")
runpy.run_path(str(ROOT / "scripts" / "tooltime_parity_phase1_import_fix.py"), run_name="__main__")
runpy.run_path(str(ROOT / "scripts" / "tooltime_parity_phase2_settings_runner.py"), run_name="__main__")
runpy.run_path(str(ROOT / "scripts" / "tooltime_parity_phase2_external_js.py"), run_name="__main__")
runpy.run_path(str(ROOT / "scripts" / "tooltime_parity_phase2_browser_smoke.py"), run_name="__main__")
runpy.run_path(str(ROOT / "scripts" / "tooltime_parity_phase3_editor_runner.py"), run_name="__main__")
runpy.run_path(str(ROOT / "scripts" / "tooltime_parity_phase3_quick_create_fix.py"), run_name="__main__")
runpy.run_path(str(ROOT / "scripts" / "tooltime_parity_phase4_lifecycle.py"), run_name="__main__")
runpy.run_path(str(ROOT / "scripts" / "tooltime_parity_phase4_browser_smoke.py"), run_name="__main__")

editor_path = ROOT / "templates" / "rebuild" / "document_editor.html"
editor_text = editor_path.read_text(encoding="utf-8").replace("B&amp;O-Position suchen", "B&O-Position suchen")
editor_path.write_text(editor_text, encoding="utf-8")

views_path = ROOT / "erp" / "tooltime_parity_views.py"
views_text = views_path.read_text(encoding="utf-8")
broken_mail = re.compile(
    r'body=f"Sehr geehrte Damen und Herren,\n\nanbei erhalten Sie \{heading\.lower\(\)\} zu Rechnung \{invoice\.number\}\.\n\nMit freundlichen Grüßen\n\{org\.name\}"'
)
fixed_mail = r'body=f"Sehr geehrte Damen und Herren,\n\nanbei erhalten Sie {heading.lower()} zu Rechnung {invoice.number}.\n\nMit freundlichen Grüßen\n{org.name}"'
views_text, mail_count = broken_mail.subn(lambda _match: fixed_mail, views_text, count=1)
if mail_count != 1:
    raise RuntimeError("ToolTime-Parität: Mahnmail-Reparaturanker wurde im finalen View nicht gefunden.")
views_path.write_text(views_text, encoding="utf-8")

# Phase 5 owns the real post-finalization communication workflow. The tiny source
# repair runs first because this repository assembles generated Python from scripts
# and the quote-PDF HTML itself contains multiline string delimiters.
runpy.run_path(str(ROOT / "scripts" / "tooltime_parity_phase5_source_fix.py"), run_name="__main__")
runpy.run_path(str(ROOT / "scripts" / "tooltime_parity_phase5_communication.py"), run_name="__main__")
# Draft offers keep the established PDF-preview contract, while e-mail delivery
# remains server-side restricted to finalized offers.
runpy.run_path(str(ROOT / "scripts" / "tooltime_parity_phase5_quote_preview_compat.py"), run_name="__main__")
runpy.run_path(str(ROOT / "scripts" / "tooltime_parity_phase5_browser_smoke.py"), run_name="__main__")

# Phase 6 completes communication preferences without adding another settings
# model: sender/reply-to/templates and the SMS provider live in the existing
# organization-scoped ToolTimeCommercialProfile JSON. Provider secrets stay in ENV.
runpy.run_path(str(ROOT / "scripts" / "tooltime_parity_phase6_communication_settings.py"), run_name="__main__")
runpy.run_path(str(ROOT / "scripts" / "tooltime_parity_phase6_browser_smoke.py"), run_name="__main__")
runpy.run_path(str(ROOT / "scripts" / "tooltime_parity_phase6_ui_language_fix.py"), run_name="__main__")

# Phase 7 connects the operational and commercial chain end-to-end. The source
# repair runs first because the patcher itself embeds PDF HTML inside Python code.
runpy.run_path(str(ROOT / "scripts" / "tooltime_parity_phase7_source_fix.py"), run_name="__main__")
runpy.run_path(str(ROOT / "scripts" / "tooltime_parity_phase7_e2e_flow.py"), run_name="__main__")

# A+Bau Pay closes the outstanding ToolTime-Pay parity gap after the complete
# operational flow is installed: provider checkout/webhooks, QR, payouts and
# automatic dunning are layered on the final invoice/payment endpoints.
runpy.run_path(str(ROOT / "scripts" / "tooltime_parity_pay.py"), run_name="__main__")
# Keep Pay smoke assertions inside the authenticated office surface. The Pay
# routes intentionally remain unavailable to technician/field users. This also
# chains Phase 8 and its final browser-fixture repair.
runpy.run_path(str(ROOT / "scripts" / "tooltime_parity_pay_smoke_context_fix.py"), run_name="__main__")

# Final screenshot feedback: employee/technician Konto must be separated from
# company-wide commercial settings. Apply security and the redesigned settings
# information architecture after every parity phase so later generators cannot
# re-expose the route or restore the long single-column settings wall.
runpy.run_path(str(ROOT / "scripts" / "tooltime_settings_access_ui_fix.py"), run_name="__main__")
runpy.run_path(str(ROOT / "scripts" / "tooltime_settings_access_ui_followup.py"), run_name="__main__")
# Generic legacy page assertions predate the tabbed Settings IA. Keep the old
# coverage, but verify finance content after an actual Finanzen-tab click.
runpy.run_path(str(ROOT / "scripts" / "tooltime_settings_browser_smoke_tabs_fix.py"), run_name="__main__")

# Final assembly guard: quote_pdf returns FileResponse, therefore the symbol must
# be imported in the actual generated view regardless of historical import shape
# or earlier compatibility patches. Keep this immediately before final compile.
views_path = ROOT / "erp" / "tooltime_parity_views.py"
views_text = views_path.read_text(encoding="utf-8")
http_lines = [line for line in views_text.splitlines() if line.startswith("from django.http import ")]
if not http_lines:
    raise RuntimeError("ToolTime Phase 5 final django.http import missing")
http_line = http_lines[0]
http_names = [name.strip() for name in http_line.removeprefix("from django.http import ").split(",") if name.strip()]
for required in ("FileResponse", "Http404", "JsonResponse"):
    if required not in http_names:
        http_names.append(required)
normalized_http_line = "from django.http import " + ", ".join(sorted(set(http_names)))
views_text = views_text.replace(http_line, normalized_http_line, 1)
if "FileResponse" not in normalized_http_line:
    raise RuntimeError("ToolTime Phase 5 FileResponse import guard failed")
views_path.write_text(views_text, encoding="utf-8")

for rel in (
    "erp/tooltime_parity_views.py",
    "erp/tooltime_parity_finance.py",
    "erp/services/tooltime_parity_finance.py",
    "erp/services/tooltime_pay.py",
    "erp/templatetags/tooltime_parity.py",
):
    path = ROOT / rel
    compile(path.read_text(encoding="utf-8"), str(path), "exec")

print("ToolTime-Finalprüfung erfolgreich: Phase 1–8 plus A+Bau Pay inklusive Provider-Checkout/Webhook, QR, Auszahlungen, automatischem Mahnwesen, Auftragsbestätigung, Rollenprüfung, geschützter Unternehmenseinstellungen, canonical PDF und echter Kommunikation sind funktional verbunden.")