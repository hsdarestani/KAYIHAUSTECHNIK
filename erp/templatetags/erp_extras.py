from decimal import Decimal
from django import template
from django.utils import timezone
from django.utils.formats import date_format

register = template.Library()


@register.filter
def attr(obj, name):
    value = getattr(obj, name, "")
    if callable(value):
        try:
            value = value()
        except TypeError:
            pass
    return value


@register.filter
def human(value):
    if value is None or value == "":
        return "–"
    if isinstance(value, bool):
        return "Ja" if value else "Nein"
    if isinstance(value, Decimal):
        return f"{value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    if hasattr(value, "strftime"):
        try:
            return date_format(value, "d.m.Y H:i" if hasattr(value, "hour") else "d.m.Y")
        except Exception:
            return str(value)
    return value


@register.filter
def money(value):
    try:
        value = Decimal(value)
        return f"{value:,.2f} €".replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        return value


@register.filter
def status_class(value):
    value = str(value or "").lower()
    if value in {"paid", "completed", "accepted", "done", "approved", "active"}:
        return "success"
    if value in {"overdue", "failed", "cancelled", "rejected", "urgent"}:
        return "danger"
    if value in {"review", "waiting", "partial", "high", "sent"}:
        return "warning"
    return "info"

@register.filter
def singular_resource(value):
    return {
        "suppliers": "supplier", "customers": "customer", "objects": "object", "employees": "employee",
        "projects": "project", "tasks": "task", "events": "event",
        "catalog": "catalog", "materials": "material", "time": "time",
        "documents": "document", "expenses": "expense",
    }.get(value, str(value).rstrip("s"))

@register.filter
def dict_get(mapping, key):
    try:
        return mapping.get(key)
    except Exception:
        return None

@register.filter
def event_top(value):
    try:
        local = timezone.localtime(value)
        return max(0, (local.hour - 7) * 64 + local.minute * 64 / 60)
    except Exception:
        return 0


@register.filter
def event_height(event):
    try:
        minutes = max(30, int((event.ends_at - event.starts_at).total_seconds() / 60))
        return max(30, minutes * 64 / 60 - 5)
    except Exception:
        return 48


@register.filter
def event_color(value):
    return {
        "appointment": "event-blue",
        "site": "event-red",
        "inspection": "event-purple",
        "delivery": "event-green",
        "internal": "event-orange",
    }.get(str(value), "event-blue")
