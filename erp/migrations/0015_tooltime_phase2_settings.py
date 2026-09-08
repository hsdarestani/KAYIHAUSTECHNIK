from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("erp", "0014_tooltime_position_asset_links")]
    operations = [
        migrations.AddField(
            model_name="tooltimedocumentmeta",
            name="default_attachment_ids",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.CreateModel(
            name="ToolTimeDatevAccount",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("party_type", models.CharField(choices=[("customer", "Debitor"), ("supplier", "Kreditor")], max_length=20)),
                ("party_key", models.CharField(max_length=120)),
                ("party_name", models.CharField(blank=True, max_length=240)),
                ("account_number", models.CharField(max_length=5)),
                ("source", models.CharField(choices=[("automatic", "Automatisch"), ("customer_number", "Kundennummer"), ("import", "DATEV-Import"), ("manual", "Manuell")], default="automatic", max_length=30)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("organization", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="tooltime_datev_accounts", to="erp.organization")),
            ],
            options={"ordering": ["party_type", "account_number", "id"]},
        ),
        migrations.AddConstraint(model_name="tooltimedatevaccount", constraint=models.UniqueConstraint(fields=("organization", "party_type", "party_key"), name="uniq_tooltime_datev_party")),
        migrations.AddConstraint(model_name="tooltimedatevaccount", constraint=models.UniqueConstraint(fields=("organization", "account_number"), name="uniq_tooltime_datev_number")),
    ]
