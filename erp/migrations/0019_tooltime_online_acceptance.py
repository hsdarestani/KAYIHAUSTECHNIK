from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("erp", "0018_tooltime_pay")]
    operations = [
        migrations.AddField(
            model_name="tooltimedocumentmeta",
            name="acceptance_details",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name="tooltimedocumentmeta",
            name="withdrawn_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
