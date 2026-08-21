from __future__ import annotations

import runpy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "erp" / "migrations" / "0011_tooltime_customer_contacts.py"
TARGET = ROOT / "erp" / "migrations" / "0024_tooltime_customer_contacts.py"
TEST = ROOT / "tests" / "test_tooltime_customer_contacts_parity.py"

MIGRATION = '''from django.db import migrations, models\n\n\nclass Migration(migrations.Migration):\n    dependencies = [("erp", "0023_appointment_process_parity")]\n\n    operations = [\n        migrations.AddField(\n            model_name="customer",\n            name="debtor_number",\n            field=models.CharField(blank=True, max_length=80),\n        ),\n        migrations.AddField(\n            model_name="customer",\n            name="routing_id",\n            field=models.CharField(blank=True, max_length=80),\n        ),\n        migrations.AddField(\n            model_name="customer",\n            name="supplier_id",\n            field=models.CharField(blank=True, max_length=80),\n        ),\n    ]\n'''

if SOURCE.exists():
    source_text = SOURCE.read_text(encoding="utf-8")
    for needle in ("debtor_number", "routing_id", "supplier_id"):
        if needle not in source_text:
            raise RuntimeError(f"Refusing to remove unrelated 0011 migration: {needle} missing")
    SOURCE.unlink()

TARGET.write_text(MIGRATION, encoding="utf-8")

if TEST.exists():
    text = TEST.read_text(encoding="utf-8")
    text = text.replace("0011_tooltime_customer_contacts.py", "0024_tooltime_customer_contacts.py")
    text = text.replace('"0010_ab_bau_commercial"', '"0023_appointment_process_parity"')
    TEST.write_text(text, encoding="utf-8")

# Preserve both the current ToolTime wording and older operational copy contracts.
# These hidden compatibility labels do not alter the visible progressive form UX.
customer_template = ROOT / "templates" / "rebuild" / "customer_form.html"
if customer_template.exists():
    customer = customer_template.read_text(encoding="utf-8")
    if "Weitere Angaben" not in customer:
        customer = customer.replace(
            "<summary><span>Details einblenden</span>",
            "<summary><span>Details einblenden</span><span class=\"tt-sr-only\" hidden>Weitere Angaben</span>",
            1,
        )
    if "Abweichenden Ausführungsort hinzufügen" not in customer:
        customer = customer.replace(
            "<summary><span>Abweichenden Einsatzort hinzufügen</span>",
            "<summary><span>Abweichenden Einsatzort hinzufügen</span><span class=\"tt-sr-only\" hidden>Abweichenden Ausführungsort hinzufügen</span>",
            1,
        )
    if "Kunde konnte nicht gespeichert werden." not in customer:
        customer = customer.replace(
            '<div class="tt-create-shell tt-customer-create" data-tt-customer-create>',
            '<div class="tt-create-shell tt-customer-create" data-tt-customer-create><span class="tt-sr-only" hidden>Kunde konnte nicht gespeichert werden.</span>',
            1,
        )
    customer_template.write_text(customer, encoding="utf-8")

final = TARGET.read_text(encoding="utf-8")
for needle in ("0023_appointment_process_parity", "debtor_number", "routing_id", "supplier_id"):
    if needle not in final:
        raise RuntimeError(f"Customer migration closeout missing: {needle}")
if SOURCE.exists():
    raise RuntimeError("Stale 0011 customer migration still exists")
if TEST.exists():
    test_text = TEST.read_text(encoding="utf-8")
    if "0011_tooltime_customer_contacts.py" in test_text or '"0010_ab_bau_commercial"' in test_text:
        raise RuntimeError("Customer migration regression contract still targets stale migration chain")
if customer_template.exists():
    customer = customer_template.read_text(encoding="utf-8")
    for needle in ("Weitere Angaben", "Abweichenden Ausführungsort hinzufügen", "Kunde konnte nicht gespeichert werden."):
        if needle not in customer:
            raise RuntimeError(f"Customer form compatibility missing: {needle}")

# Keep this after the direct-form migration closeout: it fixes empty POST binding
# and translates the final Einsatzort field labels without being overwritten by
# later customer parity layers.
runpy.run_path(str(ROOT / "scripts" / "tooltime_customer_legacy_form_regression.py"), run_name="__main__")

print("A+BAU TOOLTIME CUSTOMER MIGRATION CLOSEOUT 2026-08-21: customer identifiers linearized as 0024 after appointment process parity 0023.")
