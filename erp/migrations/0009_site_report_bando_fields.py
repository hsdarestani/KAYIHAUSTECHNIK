from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("erp", "0008_rename_erp_nativ_organiz_1f223e_idx_erp_nativer_organiz_1823cd_idx_and_more")]

    operations = [
        migrations.AddField(model_name="sitereport", name="kind", field=models.CharField(choices=[("generic", "Vor-Ort-Bericht"), ("bando", "B&O Leistungsnachweis / Regiebericht")], default="generic", max_length=20)),
        migrations.AddField(model_name="sitereport", name="execution_satisfied", field=models.BooleanField(blank=True, null=True)),
        migrations.AddField(model_name="sitereport", name="employee_punctual", field=models.BooleanField(blank=True, null=True)),
        migrations.AddField(model_name="sitereport", name="repair_duration", field=models.CharField(blank=True, max_length=120)),
        migrations.AddField(model_name="sitereport", name="tenant_fault", field=models.BooleanField(default=False)),
        migrations.AddField(model_name="sitereport", name="service_lines", field=models.JSONField(blank=True, default=list)),
        migrations.AddField(model_name="sitereport", name="material_lines", field=models.JSONField(blank=True, default=list)),
    ]
