from django.core.management.base import BaseCommand
from erp.models import Organization
from erp.services.tooltime_pay import run_automatic_dunning


class Command(BaseCommand):
    help = "Führt die konfigurierten automatischen Mahnstufen mandantenweise aus."

    def handle(self, *args, **options):
        total = 0
        for org in Organization.objects.order_by("pk"):
            total += run_automatic_dunning(org, created_by=None)
        self.stdout.write(self.style.SUCCESS(f"Automatisches Mahnwesen: {total} neue Stufe(n)."))
