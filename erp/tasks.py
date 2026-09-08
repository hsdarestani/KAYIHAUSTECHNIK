from celery import shared_task
from django.utils import timezone
from erp.models import Document, IntegrationConfig, Invoice, Notification, Organization
from erp.services.documents import extract_text
from erp.services.emailing import sync_gmx


@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=True, max_retries=3)
def extract_document_text(self, document_id: int):
    document = Document.objects.get(pk=document_id)
    document.extracted_text = extract_text(document.file.path)
    document.save(update_fields=["extracted_text", "updated_at"])
    return {"document_id": document_id, "characters": len(document.extracted_text)}


@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=True, max_retries=3)
def sync_gmx_mailbox(self):
    total = 0
    for organization in Organization.objects.all():
        integration = IntegrationConfig.objects.filter(organization=organization, provider=IntegrationConfig.Provider.GMX, enabled=True).first()
        if not integration:
            continue
        try:
            count = sync_gmx(organization)
            total += count
            integration.last_sync_at = timezone.now()
            integration.last_error = ""
            integration.save(update_fields=["last_sync_at", "last_error", "updated_at"])
        except Exception as exc:
            integration.last_error = str(exc)
            integration.save(update_fields=["last_error", "updated_at"])
            raise
    return total


@shared_task
def create_overdue_notifications():
    today = timezone.localdate()
    created = 0
    for invoice in Invoice.objects.filter(due_date__lt=today).exclude(status__in=[Invoice.Status.PAID, Invoice.Status.CANCELLED]):
        invoice.refresh_status()
        users = [u for u in invoice.organization.userprofile_set.select_related("user").all() if u.role in {"admin", "accounting", "office"}]
        for profile in users:
            exists = Notification.objects.filter(user=profile.user, title__contains=invoice.number, created_at__date=today).exists()
            if not exists:
                Notification.objects.create(user=profile.user, title=f"Rechnung {invoice.number} überfällig", message=f"Offener Betrag: {invoice.outstanding_total} €", level="danger", url=f"/invoices/{invoice.pk}/")
                created += 1
    return created


@shared_task
def prepare_calendar_reminders():
    """Create due in-app/PWA notifications for assigned employees.

    Event forms create scheduled Notification rows. This task acts as a safety net
    for older events and keeps reminder delivery idempotent.
    """
    from datetime import timedelta
    from erp.models import CalendarEvent

    now = timezone.now()
    horizon = now + timedelta(minutes=10)
    created = 0
    events = CalendarEvent.objects.filter(starts_at__gte=now, starts_at__lte=now + timedelta(days=8)).prefetch_related("attendees__user")
    for event in events:
        for employee in event.attendees.all():
            if not employee.user_id:
                continue
            for minutes in event.reminder_minutes or [60]:
                scheduled = event.starts_at - timedelta(minutes=int(minutes))
                if scheduled > horizon:
                    continue
                _, was_created = Notification.objects.get_or_create(
                    user=employee.user,
                    title=f"Termin: {event.title}",
                    url=f"/calendar/?event={event.pk}",
                    scheduled_for=scheduled,
                    defaults={"message": f"{event.starts_at:%d.%m.%Y %H:%M} · {event.location}", "level": "info"},
                )
                created += int(was_created)
    return created
