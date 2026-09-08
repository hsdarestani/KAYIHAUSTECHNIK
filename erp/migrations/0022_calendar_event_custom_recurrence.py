from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("erp", "0021_calendar_event_recurrence"),
    ]

    operations = [
        migrations.AddField(
            model_name="calendarevent",
            name="recurrence_interval",
            field=models.PositiveSmallIntegerField(default=1, editable=False),
        ),
        migrations.AddField(
            model_name="calendarevent",
            name="recurrence_unit",
            field=models.CharField(
                choices=[
                    ("day", "Tag(e)"),
                    ("weekday", "Werktag(e)"),
                    ("week", "Woche(n)"),
                    ("month", "Monat(e)"),
                    ("year", "Jahr(e)"),
                ],
                default="day",
                editable=False,
                max_length=12,
            ),
        ),
        migrations.AddField(
            model_name="calendarevent",
            name="recurrence_until",
            field=models.DateField(blank=True, editable=False, null=True),
        ),
    ]
