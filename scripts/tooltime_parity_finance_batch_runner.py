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
runpy.run_path(str(ROOT / "scripts" / "tooltime_parity_migration_alignment.py"), run_name="__main__")
runpy.run_path(str(ROOT / "scripts" / "tooltime_parity_browser_smoke.py"), run_name="__main__")
runpy.run_path(str(ROOT / "scripts" / "tooltime_parity_legacy_contract_bridge.py"), run_name="__main__")

# Die Abschluss-Erweiterung setzt den Mahnmail-Text in einen generierten Python-
# String ein. In einem normalen Triple-String würden dabei \n-Sequenzen zu echten
# Zeilenumbrüchen innerhalb des f-Strings und damit zu ungültigem Python. Repariere
# exakt diesen generierten Block und validiere danach die finalen Python-Module.
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

for rel in (
    "erp/tooltime_parity_views.py",
    "erp/tooltime_parity_finance.py",
    "erp/services/tooltime_parity_finance.py",
):
    path = ROOT / rel
    compile(path.read_text(encoding="utf-8"), str(path), "exec")

print("ToolTime-Finalprüfung erfolgreich: Mahnwesen und generierte Python-Module sind syntaktisch gültig.")
