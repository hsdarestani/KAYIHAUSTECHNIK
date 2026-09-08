from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver
from erp.models import Organization, UserProfile


@receiver(post_save, sender=User)
def ensure_profile(sender, instance, created, **kwargs):
    if not created:
        return
    organization = Organization.objects.first()
    UserProfile.objects.create(
        user=instance,
        organization=organization,
        role=UserProfile.Role.ADMIN if instance.is_superuser else UserProfile.Role.OFFICE,
    )
