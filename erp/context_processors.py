from django.utils import timezone
from django.db.models import Q
from erp.models import Notification, TimeEntry
from erp.services.permissions import can_manage_finance, can_view_prices, role_for


def navigation_context(request):
    if not getattr(request, "user", None) or not request.user.is_authenticated:
        return {}
    profile = getattr(request.user, "profile", None)
    organization = getattr(profile, "organization", None)
    active_timer = None
    if hasattr(request.user, "employee"):
        active_timer = TimeEntry.objects.filter(employee=request.user.employee, ended_at__isnull=True).select_related("project").first()
    due_notifications = Notification.objects.filter(user=request.user, read_at__isnull=True).filter(Q(scheduled_for__isnull=True) | Q(scheduled_for__lte=timezone.now()))
    return {
        "current_organization": organization,
        "unread_notifications": due_notifications[:10],
        "unread_notification_count": due_notifications.count(),
        "can_view_prices_global": can_view_prices(request.user),
        "can_manage_finance_global": can_manage_finance(request.user),
        "current_role": role_for(request.user),
        "is_technician": role_for(request.user) == "technician",
        "can_manage_company": role_for(request.user) in {"admin", "office", "project_manager", "accounting"},
        "active_timer": active_timer,
        "now": timezone.now(),
    }
