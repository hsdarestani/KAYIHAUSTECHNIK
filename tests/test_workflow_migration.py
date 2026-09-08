from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase


class WorkflowMigrationTests(TransactionTestCase):
    migrate_from = (
        "erp",
        "0004_rename_erp_room_org_status_idx_erp_roommea_organiz_dd42ac_idx_and_more",
    )
    migrate_to = ("erp", "0005_workflow_release")

    def tearDown(self):
        executor = MigrationExecutor(connection)
        executor.migrate(executor.loader.graph.leaf_nodes())
        super().tearDown()

    def test_existing_price_sources_receive_distinct_share_tokens(self):
        executor = MigrationExecutor(connection)
        executor.migrate([self.migrate_from])
        old_apps = executor.loader.project_state([self.migrate_from]).apps
        Organization = old_apps.get_model("erp", "Organization")
        PriceSource = old_apps.get_model("erp", "PriceSource")

        organization = Organization.objects.create(name="Legacy KAYI tenant")
        PriceSource.objects.create(
            organization=organization,
            name="Legacy insurance A",
            kind="insurance",
            original_filename="a.xlsx",
            sha256="a" * 64,
        )
        PriceSource.objects.create(
            organization=organization,
            name="Legacy private list",
            kind="customer",
            original_filename="b.xlsx",
            sha256="b" * 64,
        )

        executor = MigrationExecutor(connection)
        executor.migrate([self.migrate_to])
        new_apps = executor.loader.project_state([self.migrate_to]).apps
        MigratedPriceSource = new_apps.get_model("erp", "PriceSource")
        tokens = list(
            MigratedPriceSource.objects.filter(organization_id=organization.pk)
            .order_by("pk")
            .values_list("share_token", flat=True)
        )

        self.assertEqual(len(tokens), 2)
        self.assertTrue(all(tokens))
        self.assertEqual(len(set(tokens)), 2)
