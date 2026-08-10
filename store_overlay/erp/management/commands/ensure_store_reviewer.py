from __future__ import annotations

import os

from django.contrib.auth import get_user_model
from django.core.management import BaseCommand, call_command

from erp.models import Organization, UserProfile


class Command(BaseCommand):
    help = "Creates or refreshes a store-review account from environment secrets without committing credentials."

    def handle(self, *args, **options):
        username = os.environ.get("KAYI_REVIEW_USERNAME", "").strip()
        password = os.environ.get("KAYI_REVIEW_PASSWORD", "")
        email = os.environ.get("KAYI_REVIEW_EMAIL", "").strip()
        if not username or not password:
            self.stdout.write("Store reviewer account not configured; set KAYI_REVIEW_USERNAME and KAYI_REVIEW_PASSWORD to enable it.")
            return

        # Keep review data isolated from real customer data and idempotently seed a
        # representative office/field/finance dataset the reviewer can navigate.
        call_command("seed_demo_data")
        org = Organization.objects.filter(settings__is_demo=True).first() or Organization.objects.filter(name__icontains="Demo").first()
        if org is None:
            org = Organization.objects.create(name="KAYI Store Review Demo", settings={"is_demo": True, "store_review": True})

        User = get_user_model()
        user, _created = User.objects.get_or_create(username=username, defaults={"email": email})
        if email and user.email != email:
            user.email = email
        user.is_active = True
        user.set_password(password)
        user.save()

        profile, _ = UserProfile.objects.get_or_create(user=user)
        profile.organization = org
        profile.role = "admin"
        profile.is_mobile_worker = False
        prefs = dict(profile.preferences or {})
        prefs.update({"store_review_account": True, "store_review_demo_only": True})
        profile.preferences = prefs
        profile.save()

        self.stdout.write(self.style.SUCCESS(f"Store reviewer account {username!r} is ready in isolated demo organization {org.name!r}."))
