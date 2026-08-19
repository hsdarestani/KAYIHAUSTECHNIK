from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

migration = '''from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("erp", "0013_tooltime_finance_parity")]
    operations = [
        migrations.AlterField(
            model_name="tooltimepositionasset",
            name="invoice_item",
            field=models.OneToOneField(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="tooltime_asset",
                to="erp.invoiceitem",
            ),
        ),
        migrations.AlterField(
            model_name="tooltimepositionasset",
            name="quote_item",
            field=models.OneToOneField(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="tooltime_asset",
                to="erp.quoteitem",
            ),
        ),
    ]
'''

path = ROOT / "erp" / "migrations" / "0014_tooltime_position_asset_links.py"
path.write_text(migration, encoding="utf-8")
print("ToolTime-Positionsbild-Migration mit dem finalen Django-State ausgerichtet.")
