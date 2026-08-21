from __future__ import annotations

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

print("A+BAU TOOLTIME CUSTOMER MIGRATION CLOSEOUT 2026-08-21: customer identifiers linearized as 0024 after appointment process parity 0023.")
