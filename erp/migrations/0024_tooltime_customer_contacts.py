from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("erp", "0023_appointment_process_parity")]

    operations = [
        migrations.AddField(
            model_name="customer",
            name="debtor_number",
            field=models.CharField(blank=True, max_length=80),
        ),
        migrations.AddField(
            model_name="customer",
            name="routing_id",
            field=models.CharField(blank=True, max_length=80),
        ),
        migrations.AddField(
            model_name="customer",
            name="supplier_id",
            field=models.CharField(blank=True, max_length=80),
        ),
    ]
