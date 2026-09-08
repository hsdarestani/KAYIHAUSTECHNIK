from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("erp", "0020_calendar_event_customer"),
    ]

    operations = [
        migrations.AddField(
            model_name="calendarevent",
            name="recurrence_series",
            field=models.UUIDField(blank=True, db_index=True, editable=False, null=True),
        ),
        migrations.AddField(
            model_name="calendarevent",
            name="recurrence_rule",
            field=models.CharField(
                choices=[
                    ("none", "Keine Wiederholung"),
                    ("daily", "Täglich"),
                    ("weekdays", "Werktags"),
                    ("weekly", "Wöchentlich"),
                    ("biweekly", "Alle zwei Wochen"),
                    ("monthly", "Monatlich"),
                    ("half_yearly", "Halbjährlich"),
                    ("yearly", "Jährlich"),
                    ("custom", "Benutzerdefiniert"),
                ],
                default="none",
                editable=False,
                max_length=16,
            ),
        ),
        migrations.AddField(
            model_name="calendarevent",
            name="recurrence_index",
            field=models.PositiveIntegerField(default=0, editable=False),
        ),
    ]
