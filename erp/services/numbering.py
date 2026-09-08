from django.db import transaction
from django.utils import timezone
from erp.models import Sequence

PREFIXES = {"customer": "K", "project": "P", "quote": "A", "invoice": "R", "employee": "M"}


def next_number(organization, key: str) -> str:
    year = timezone.localdate().year
    with transaction.atomic():
        sequence, _ = Sequence.objects.select_for_update().get_or_create(
            organization=organization, key=key, year=year, defaults={"value": 0}
        )
        sequence.value += 1
        sequence.save(update_fields=["value", "updated_at"])
    prefix = PREFIXES.get(key, key[:1].upper())
    return f"{prefix}-{year}-{sequence.value:04d}"
