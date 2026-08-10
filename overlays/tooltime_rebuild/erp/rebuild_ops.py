from __future__ import annotations

from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from . import models as m
from .rebuild_views import StyledModelForm, _org, _unique_number


class TaskForm(StyledModelForm):
    class Meta:
        model = m.Task
        fields = ["title", "description", "status", "priority", "due_at", "assigned_to", "project"]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 3}),
            "due_at": forms.DateTimeInput(attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"),
        }

    def __init__(self, *args, organization=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["due_at"].input_formats = ["%Y-%m-%dT%H:%M"]
        if organization:
            self.fields["assigned_to"].queryset = m.Employee.objects.filter(organization=organization, active=True)
            self.fields["project"].queryset = m.Project.objects.filter(organization=organization, archived=False)


class ExpenseForm(StyledModelForm):
    class Meta:
        model = m.Expense
        fields = ["supplier", "description", "amount_net", "tax_rate", "expense_date", "category", "paid", "project", "document"]
        widgets = {"expense_date": forms.DateInput(attrs={"type": "date"})}

    def __init__(self, *args, organization=None, **kwargs):
        super().__init__(*args, **kwargs)
        if organization:
            self.fields["project"].queryset = m.Project.objects.filter(organization=organization, archived=False)
            self.fields["document"].queryset = m.Document.objects.filter(organization=organization).order_by("-created_at")[:300]


class EmployeeForm(StyledModelForm):
    class Meta:
        model = m.Employee
        fields = ["first_name", "last_name", "email", "phone", "trade", "hourly_cost", "hourly_rate", "active", "color"]
        widgets = {"color": forms.TextInput(attrs={"type": "color"})}


@login_required
def task_list(request):
    org = _org(request)
    status = request.GET.get("status", "").strip()
    query = request.GET.get("q", "").strip()
    tasks = m.Task.objects.filter(organization=org).select_related("assigned_to", "project")
    if status:
        tasks = tasks.filter(status=status)
    if query:
        tasks = tasks.filter(Q(title__icontains=query) | Q(description__icontains=query) | Q(project__title__icontains=query))
    tasks = tasks.order_by("status", "due_at", "-created_at")[:300]
    return render(request, "rebuild/tasks.html", {"tasks": tasks, "status": status, "query": query, "statuses": m.Task._meta.get_field("status").choices})


@login_required
@require_http_methods(["GET", "POST"])
def task_edit(request, pk=None):
    org = _org(request)
    task = get_object_or_404(m.Task, organization=org, pk=pk) if pk else None
    initial = {}
    if request.GET.get("project"):
        initial["project"] = request.GET.get("project")
    form = TaskForm(request.POST or None, instance=task, organization=org, initial=initial)
    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False)
        obj.organization = org
        if obj.status == "done" and not obj.completed_at:
            obj.completed_at = timezone.now()
        elif obj.status != "done":
            obj.completed_at = None
        obj.save()
        messages.success(request, "Aufgabe gespeichert.")
        return redirect("next-tasks")
    return render(request, "rebuild/ops_form.html", {"form": form, "kind": "task", "object": task})


@login_required
def expense_list(request):
    org = _org(request)
    query = request.GET.get("q", "").strip()
    expenses = m.Expense.objects.filter(organization=org).select_related("project", "document")
    if query:
        expenses = expenses.filter(Q(supplier__icontains=query) | Q(description__icontains=query) | Q(project__title__icontains=query))
    expenses = expenses.order_by("-expense_date", "-created_at")[:300]
    return render(request, "rebuild/expenses.html", {"expenses": expenses, "query": query})


@login_required
@require_http_methods(["GET", "POST"])
def expense_edit(request, pk=None):
    org = _org(request)
    expense = get_object_or_404(m.Expense, organization=org, pk=pk) if pk else None
    initial = {"expense_date": timezone.localdate()}
    if request.GET.get("project"):
        initial["project"] = request.GET.get("project")
    form = ExpenseForm(request.POST or None, instance=expense, organization=org, initial=initial)
    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False)
        obj.organization = org
        obj.save()
        messages.success(request, "Ausgabe gespeichert.")
        return redirect("next-expenses")
    return render(request, "rebuild/ops_form.html", {"form": form, "kind": "expense", "object": expense})


@login_required
def employee_list(request):
    org = _org(request)
    employees = m.Employee.objects.filter(organization=org).select_related("user").order_by("active", "last_name", "first_name")
    return render(request, "rebuild/employees.html", {"employees": employees})


@login_required
@require_http_methods(["GET", "POST"])
def employee_edit(request, pk=None):
    org = _org(request)
    employee = get_object_or_404(m.Employee, organization=org, pk=pk) if pk else None
    form = EmployeeForm(request.POST or None, instance=employee)
    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False)
        obj.organization = org
        if not obj.employee_number:
            # Employee uses the same human-readable sequence principle as the rest of KAYI.
            existing = m.Employee.objects.filter(organization=org).count() + 1
            candidate = f"M-{existing:04d}"
            while m.Employee.objects.filter(organization=org, employee_number=candidate).exists():
                existing += 1
                candidate = f"M-{existing:04d}"
            obj.employee_number = candidate
        obj.save()
        messages.success(request, "Mitarbeiter gespeichert.")
        return redirect("next-employees")
    return render(request, "rebuild/ops_form.html", {"form": form, "kind": "employee", "object": employee})
