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

# Das generierte View-Modul benutzt ein echtes datetime.timedelta und verlässt
# sich nicht auf einen nicht garantierten Alias im Django-timezone-Modul.
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
runpy.run_path(str(ROOT / "scripts" / "tooltime_parity_browser_smoke.py"), run_name="__main__")
