import os
import secrets
from pathlib import Path
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from erp.models import Organization, UserProfile


class Command(BaseCommand):
    help = "Erstellt Organisation und initialen Administrator, falls noch kein Benutzer existiert."

    def add_arguments(self, parser):
        parser.add_argument("--credentials-file", default="/runtime/admin_credentials.txt")

    def handle(self, *args, **options):
        org, _ = Organization.objects.get_or_create(name=os.getenv("ORGANIZATION_NAME", "A+Bau"), defaults={"legal_name": "A+Bau"})
        if User.objects.exists():
            self.stdout.write("Benutzer vorhanden; Bootstrap übersprungen.")
            return
        username = os.getenv("INITIAL_ADMIN_USERNAME", "admin")
        password = os.getenv("INITIAL_ADMIN_PASSWORD") or secrets.token_urlsafe(18)
        email = os.getenv("INITIAL_ADMIN_EMAIL", "admin@kayi.local")
        user = User.objects.create_superuser(username=username, email=email, password=password)
        profile = user.profile
        profile.organization = org
        profile.role = UserProfile.Role.ADMIN
        profile.save(update_fields=["organization", "role", "updated_at"])
        path = Path(options["credentials_file"])
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"URL=https://kayi.smarbiz.sbs\nUsername={username}\nPassword={password}\n", encoding="utf-8")
        path.chmod(0o600)
        self.stdout.write(self.style.SUCCESS(f"Administrator erstellt. Zugangsdaten: {path}"))
