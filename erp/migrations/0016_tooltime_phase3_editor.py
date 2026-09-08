from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("erp", "0015_tooltime_phase2_settings")]
    operations = [
        migrations.AddField(
            model_name="tooltimedocumentmeta",
            name="customer",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="tooltime_document_meta", to="erp.customer"),
        ),
        migrations.AddField(
            model_name="commercialitemmeta",
            name="show_subitems_in_pdf",
            field=models.BooleanField(default=True),
        ),
        migrations.CreateModel(
            name="ToolTimeMixedSubitem",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("item_type", models.CharField(choices=[("material", "Material"), ("labour", "Lohn"), ("other", "Sonstiges")], default="material", max_length=16)),
                ("description", models.CharField(max_length=300)),
                ("quantity", models.DecimalField(decimal_places=3, default=1, max_digits=12)),
                ("unit", models.CharField(default="Stk.", max_length=30)),
                ("purchase_price", models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ("sales_price", models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ("sort_order", models.PositiveIntegerField(default=0)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("invoice_item", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="tooltime_mixed_subitems", to="erp.invoiceitem")),
                ("organization", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="tooltime_mixed_subitems", to="erp.organization")),
                ("quote_item", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="tooltime_mixed_subitems", to="erp.quoteitem")),
            ],
            options={"ordering": ["sort_order", "id"]},
        ),
    ]
