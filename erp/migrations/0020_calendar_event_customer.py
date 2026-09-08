from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("erp", "0019_tooltime_online_acceptance"),
    ]

    operations = [
        migrations.AddField(
            model_name="calendarevent",
            name="customer",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="calendar_events",
                to="erp.customer",
            ),
        ),
    ]
