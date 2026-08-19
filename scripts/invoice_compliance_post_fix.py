from pathlib import Path

MIGRATION = Path("erp/migrations/0012_invoice_germany_compliance.py")

if not MIGRATION.exists():
    raise RuntimeError("Generated invoice compliance migration is missing")

text = MIGRATION.read_text(encoding="utf-8")
created = '("created_at", models.DateTimeField(auto_now_add=True))'
updated = '("updated_at", models.DateTimeField(auto_now=True))'

if created not in text or updated not in text:
    anchor = '                ("validation_errors", models.JSONField(blank=True, default=list)),\n'
    if anchor not in text:
        raise RuntimeError("InvoiceComplianceRecord validation_errors migration anchor changed")
    insertion = (
        anchor
        + '                ("created_at", models.DateTimeField(auto_now_add=True)),\n'
        + '                ("updated_at", models.DateTimeField(auto_now=True)),\n'
    )
    text = text.replace(anchor, insertion, 1)
    MIGRATION.write_text(text, encoding="utf-8")

verify = MIGRATION.read_text(encoding="utf-8")
if created not in verify or updated not in verify:
    raise RuntimeError("InvoiceComplianceRecord timestamp migration alignment failed")

print("Invoice compliance migration state aligned with created_at/updated_at fields.")
