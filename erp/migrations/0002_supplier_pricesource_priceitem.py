from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("erp", "0001_initial")]

    operations = [
        migrations.CreateModel(
            name="Supplier",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("number", models.CharField(max_length=40)),
                ("name", models.CharField(max_length=220)),
                ("contact_name", models.CharField(blank=True, max_length=180)),
                ("email", models.EmailField(blank=True, max_length=254)),
                ("phone", models.CharField(blank=True, max_length=60)),
                ("website", models.URLField(blank=True)),
                ("street", models.CharField(blank=True, max_length=180)),
                ("postal_code", models.CharField(blank=True, max_length=20)),
                ("city", models.CharField(blank=True, max_length=120)),
                ("notes", models.TextField(blank=True)),
                ("active", models.BooleanField(default=True)),
                ("organization", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="suppliers", to="erp.organization")),
            ],
            options={"ordering": ["name"]},
        ),
        migrations.AddConstraint(
            model_name="supplier",
            constraint=models.UniqueConstraint(fields=("organization", "number"), name="unique_supplier_number"),
        ),
        migrations.CreateModel(
            name="PriceSource",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("name", models.CharField(max_length=240)),
                ("kind", models.CharField(choices=[("catalog", "Leistungskatalog"), ("customer", "Kundenpreisliste"), ("insurance", "Versicherung"), ("supplier", "Lieferant"), ("partner", "Geschäftspartner"), ("mapping", "Mapping"), ("other", "Sonstiges")], default="other", max_length=24)),
                ("original_filename", models.CharField(max_length=255)),
                ("raw_file", models.FileField(blank=True, upload_to="price_sources/raw/%Y/%m/")),
                ("sha256", models.CharField(max_length=64)),
                ("mime_type", models.CharField(blank=True, max_length=120)),
                ("currency", models.CharField(default="EUR", max_length=3)),
                ("valid_from", models.DateField(blank=True, null=True)),
                ("valid_until", models.DateField(blank=True, null=True)),
                ("imported_at", models.DateTimeField(blank=True, null=True)),
                ("imported_rows", models.PositiveIntegerField(default=0)),
                ("import_summary", models.JSONField(blank=True, default=dict)),
                ("active", models.BooleanField(default=True)),
                ("organization", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="price_sources", to="erp.organization")),
                ("supplier", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="price_sources", to="erp.supplier")),
            ],
            options={"ordering": ["name", "-created_at"]},
        ),
        migrations.AddConstraint(
            model_name="pricesource",
            constraint=models.UniqueConstraint(fields=("organization", "sha256"), name="unique_price_source_hash"),
        ),
        migrations.CreateModel(
            name="PriceItem",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("code", models.CharField(blank=True, max_length=120)),
                ("description", models.TextField()),
                ("category", models.CharField(blank=True, max_length=180)),
                ("unit", models.CharField(blank=True, max_length=40)),
                ("purchase_price", models.DecimalField(blank=True, decimal_places=2, max_digits=14, null=True)),
                ("sales_price", models.DecimalField(blank=True, decimal_places=2, max_digits=14, null=True)),
                ("tax_rate", models.DecimalField(decimal_places=2, default=19, max_digits=5)),
                ("external_data", models.JSONField(blank=True, default=dict)),
                ("active", models.BooleanField(default=True)),
                ("organization", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="price_items", to="erp.organization")),
                ("source", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="items", to="erp.pricesource")),
            ],
            options={"ordering": ["source", "code", "description"]},
        ),
        migrations.AddIndex(model_name="priceitem", index=models.Index(fields=["organization", "code"], name="erp_priceit_organiz_d491f7_idx")),
        migrations.AddIndex(model_name="priceitem", index=models.Index(fields=["organization", "source"], name="erp_priceit_organiz_a4c8db_idx")),
    ]
