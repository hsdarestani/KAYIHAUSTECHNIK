from django.core.management.base import BaseCommand, CommandError
from erp.models import Organization
from erp.services.reference_data import import_reference_tree


class Command(BaseCommand):
    help = "Importiert versionierte Preis- und Katalogdateien aus einem Serververzeichnis."

    def add_arguments(self, parser):
        parser.add_argument("root")
        parser.add_argument("--organization-id", type=int)

    def handle(self, *args, **options):
        org = Organization.objects.filter(pk=options.get("organization_id")).first() if options.get("organization_id") else Organization.objects.exclude(settings__is_demo=True).first() or Organization.objects.first()
        if not org:
            raise CommandError("Keine Organisation vorhanden.")
        result = import_reference_tree(options["root"], org)
        self.stdout.write(self.style.SUCCESS(f"{result['files']} Dateien, {result['rows']} Preispositionen importiert."))
        for error in result["errors"]:
            self.stderr.write(f"{error['file']}: {error['error']}")
