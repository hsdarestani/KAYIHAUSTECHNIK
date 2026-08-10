from __future__ import annotations

from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import get_object_or_404, render

from . import models as m
from .rebuild_views import _employee, _invoice_total, _is_field_user, _org


def _projects_for(request, org):
    projects = m.Project.objects.filter(organization=org, archived=False)
    if _is_field_user(request):
        employee = _employee(request)
        if employee is None:
            return projects.none()
        projects = projects.filter(Q(manager=employee) | Q(members=employee)).distinct()
    return projects


@login_required
def project_list(request):
    org = _org(request)
    query = request.GET.get("q", "").strip()
    status = request.GET.get("status", "").strip()
    projects = _projects_for(request, org).select_related("customer", "manager", "object_location")
    if query:
        projects = projects.filter(
            Q(number__icontains=query)
            | Q(title__icontains=query)
            | Q(customer__company__icontains=query)
            | Q(customer__last_name__icontains=query)
        )
    if status:
        projects = projects.filter(status=status)
    return render(request, "rebuild/projects.html", {
        "projects": projects.order_by("-updated_at")[:250],
        "query": query,
        "status": status,
        "statuses": m.Project._meta.get_field("status").choices,
    })


@login_required
def project_detail(request, pk):
    org = _org(request)
    project = get_object_or_404(
        _projects_for(request, org).select_related("customer", "object_location", "manager"),
        pk=pk,
    )
    appointments = project.events.prefetch_related("attendees").order_by("-starts_at")[:20]
    quotes = project.quotes.prefetch_related("items").order_by("-created_at")
    invoices = project.invoices.prefetch_related("items", "payments").order_by("-created_at")
    documents = project.documents.order_by("-created_at")[:30]
    tasks = project.tasks.order_by("status", "due_at")[:20]
    materials = project.materials.order_by("-created_at")[:20]
    invoice_gross = sum((_invoice_total(invoice)["gross"] for invoice in invoices), Decimal("0"))
    bando_report = None
    if hasattr(project, "site_reports"):
        try:
            bando_report = project.site_reports.order_by("-created_at").first()
        except Exception:
            bando_report = None
    return render(request, "rebuild/project_detail.html", {
        "project": project,
        "appointments": appointments,
        "quotes": quotes,
        "invoices": invoices,
        "documents": documents,
        "tasks": tasks,
        "materials": materials,
        "invoice_gross": invoice_gross,
        "bando_report": bando_report,
        "field_user": _is_field_user(request),
    })
