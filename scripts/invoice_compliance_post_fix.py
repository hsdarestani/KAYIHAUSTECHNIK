from pathlib import Path

MIGRATION = Path("erp/migrations/0012_invoice_germany_compliance.py")

if not MIGRATION.exists():
    raise RuntimeError("Generated invoice compliance migration is missing")

text = MIGRATION.read_text(encoding="utf-8")
anchor = '                ("validation_errors", models.JSONField(blank=True, default=list)),\n'
expected = (
    anchor
    + '                ("created_at", models.DateTimeField(auto_now_add=True)),\n'
    + '                ("updated_at", models.DateTimeField(auto_now=True)),\n'
)

# Check the InvoiceComplianceRecord block itself, not the migration globally;
# other created_at/updated_at fields exist on the neighboring models.
if expected not in text:
    if anchor not in text:
        raise RuntimeError("InvoiceComplianceRecord validation_errors migration anchor changed")
    text = text.replace(anchor, expected, 1)
    MIGRATION.write_text(text, encoding="utf-8")

verify = MIGRATION.read_text(encoding="utf-8")
if expected not in verify:
    raise RuntimeError("InvoiceComplianceRecord timestamp migration alignment failed")

print("Invoice compliance migration state aligned with created_at/updated_at fields.")
