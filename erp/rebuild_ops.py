from __future__ import annotations

import re

from django import forms
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from . import models as m
from .rebuild_views import StyledModelForm, _org


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


class ReceiptExpenseForm(forms.Form):
    """Upload-first receipt capture matching ToolTime's expense flow."""

    ALLOWED_EXTENSIONS = {".pdf", ".xml", ".jpg", ".jpeg", ".png"}
    MAX_FILE_SIZE = 10 * 1024 * 1024

    customer = forms.ModelChoiceField(queryset=m.Customer.objects.none(), required=False)
    project = forms.ModelChoiceField(queryset=m.Project.objects.none(), required=False)
    supplier = forms.CharField(required=False, max_length=180)
    receipt_file = forms.FileField(required=True)
    amount_net = forms.DecimalField(required=True, min_value=0, max_digits=14, decimal_places=2, localize=True)
    tax_rate = forms.DecimalField(required=True, min_value=0, max_value=100, max_digits=5, decimal_places=2, initial=19, localize=True)
    expense_date = forms.DateField(required=True, initial=timezone.localdate, widget=forms.DateInput(attrs={"type": "date"}))
    category = forms.CharField(required=False, max_length=100)
    paid = forms.BooleanField(required=False)
    description = forms.CharField(required=False, max_length=240)

    def __init__(self, *args, organization=None, customer=None, **kwargs):
        super().__init__(*args, **kwargs)
        if organization is None:
            return
        customers = m.Customer.objects.filter(organization=organization, active=True).order_by("company", "last_name", "first_name")
        projects = m.Project.objects.filter(organization=organization, archived=False).select_related("customer").order_by("-updated_at")
        self.fields["customer"].queryset = customers
        if customer is not None:
            projects = projects.filter(customer=customer)
            self.fields["customer"].initial = customer
        self.fields["project"].queryset = projects

    def clean_receipt_file(self):
        upload = self.cleaned_data["receipt_file"]
        name = (getattr(upload, "name", "") or "").lower()
        suffix = "." + name.rsplit(".", 1)[-1] if "." in name else ""
        if suffix not in self.ALLOWED_EXTENSIONS:
            raise ValidationError("Bitte PDF, XML, JPG, JPEG oder PNG hochladen.")
        if getattr(upload, "size", 0) > self.MAX_FILE_SIZE:
            raise ValidationError("Der Beleg darf maximal 10 MB groß sein.")
        return upload

    def clean(self):
        cleaned = super().clean()
        customer = cleaned.get("customer")
        project = cleaned.get("project")
        if project is not None and customer is not None and project.customer_id != customer.pk:
            self.add_error("project", "Das Projekt gehört nicht zum ausgewählten Kunden.")
        elif project is not None and customer is None:
            cleaned["customer"] = project.customer
        return cleaned


class EmployeeForm(StyledModelForm):
    # A_BAU_EMPLOYEE_ROLE_EDITOR
    role = forms.ChoiceField(label="Rolle", required=True, choices=())
    username = forms.CharField(label="App-Benutzername", required=False)
    password = forms.CharField(label="Startpasswort", required=False, widget=forms.PasswordInput(render_value=True))

    class Meta:
        model = m.Employee
        fields = ["first_name", "last_name", "email", "phone", "trade", "hourly_cost", "hourly_rate", "active", "color"]
        widgets = {"color": forms.TextInput(attrs={"type": "color"})}

    def __init__(self, *args, can_manage_roles=False, **kwargs):
        super().__init__(*args, **kwargs)
        # Legacy employee creation did not require accounting values. Keep that
        # low-friction behavior in the rebuilt UI and use model defaults.
        for name in ("hourly_cost", "hourly_rate", "color"):
            self.fields[name].required = False

        self.fields["role"].choices = list(m.UserProfile.Role.choices)
        current_role = m.UserProfile.Role.TECHNICIAN
        if self.instance and self.instance.user_id:
            profile = m.UserProfile.objects.filter(user_id=self.instance.user_id).first()
            if profile and profile.role:
                current_role = profile.role
        self.fields["role"].initial = current_role
        self.initial.setdefault("role", current_role)
        self.fields["role"].disabled = not can_manage_roles
        self.fields["role"].help_text = (
            "Legt fest, welche Bereiche dieser App-Benutzer sehen und bearbeiten darf."
            if can_manage_roles
            else "Die Benutzerrolle kann nur von einem Administrator geändert werden."
        )
        self.order_fields([
            "first_name", "last_name", "email", "phone", "trade", "hourly_cost",
            "hourly_rate", "active", "color", "role", "username", "password",
        ])

        if not self.is_bound:
            self.fields["hourly_cost"].initial = self.instance.hourly_cost if self.instance and self.instance.pk else 0
            self.fields["hourly_rate"].initial = self.instance.hourly_rate if self.instance and self.instance.pk else 0
            self.fields["color"].initial = self.instance.color if self.instance and self.instance.pk else "#2f80ed"
            if self.instance and self.instance.user_id:
                self.fields["username"].initial = self.instance.user.username

    def clean_hourly_cost(self):
        return self.cleaned_data.get("hourly_cost") or 0

    def clean_hourly_rate(self):
        return self.cleaned_data.get("hourly_rate") or 0

    def clean_color(self):
        return self.cleaned_data.get("color") or "#2f80ed"


def _can_manage_employee_roles(request) -> bool:
    profile = getattr(request.user, "profile", None)
    return bool(
        request.user.is_superuser
        or getattr(profile, "role", "") == m.UserProfile.Role.ADMIN
    )


def _employee_number(org) -> str:
    existing = m.Employee.objects.filter(organization=org).count() + 1
    candidate = f"M-{existing:04d}"
    while m.Employee.objects.filter(organization=org, employee_number=candidate).exists():
        existing += 1
        candidate = f"M-{existing:04d}"
    return candidate


def _username_candidate(form: EmployeeForm, employee: m.Employee) -> str:
    explicit = (form.cleaned_data.get("username") or "").strip()
    if explicit:
        return explicit
    if employee.email:
        base = employee.email.split("@", 1)[0]
    else:
        base = f"{employee.first_name}.{employee.last_name}"
    base = re.sub(r"[^a-zA-Z0-9._-]+", ".", base).strip("._-").lower() or f"monteur{employee.pk or ''}"
    User = get_user_model()
    candidate = base
    suffix = 2
    while User.objects.filter(username=candidate).exclude(pk=employee.user_id).exists():
        candidate = f"{base}{suffix}"
        suffix += 1
    return candidate


def _ensure_employee_login(org, employee: m.Employee, form: EmployeeForm, *, can_manage_roles=False) -> None:
    """Create/update the linked app user without silently forcing every employee to technician."""
    User = get_user_model()
    username = _username_candidate(form, employee)
    password = (form.cleaned_data.get("password") or "").strip()
    had_linked_user = bool(employee.user_id)

    if employee.user_id:
        user = employee.user
        user.username = username
        if employee.email:
            user.email = employee.email
        if password:
            user.set_password(password)
        user.save()
    else:
        user = User(username=username, email=employee.email or "")
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.save()
        employee.user = user
        employee.save(update_fields=["user", "updated_at"])

    profile, _ = m.UserProfile.objects.get_or_create(user=user)
    valid_roles = {value for value, _label in m.UserProfile.Role.choices}
    existing_role = profile.role if profile.role in valid_roles else m.UserProfile.Role.TECHNICIAN
    requested_role = form.cleaned_data.get("role")

    if can_manage_roles and requested_role in valid_roles:
        role = requested_role
    elif had_linked_user:
        # A crafted POST from office/technician must never escalate or demote roles.
        role = existing_role
    else:
        # New employees created by a non-admin retain the safe historical default.
        role = m.UserProfile.Role.TECHNICIAN

    profile.organization = org
    profile.role = role
    profile.phone = employee.phone or profile.phone
    profile.is_mobile_worker = role == m.UserProfile.Role.TECHNICIAN
    profile.save()


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



def _receipt_numeric_id(value):
    value = str(value or "").strip()
    return int(value) if value.isdigit() else None


def _receipt_context_customer(request, org):
    customer_id = _receipt_numeric_id(
        request.POST.get("customer")
        or request.GET.get("customer")
        or request.GET.get("customerId")
    )
    project_id = _receipt_numeric_id(request.POST.get("project") or request.GET.get("project"))
    project = None
    if project_id:
        project = (
            m.Project.objects.filter(organization=org, pk=project_id, archived=False)
            .select_related("customer")
            .first()
        )
    customer = None
    if customer_id:
        customer = m.Customer.objects.filter(organization=org, pk=customer_id, active=True).first()
    if customer is None and project is not None:
        customer = project.customer
    if project is not None and customer is not None and project.customer_id != customer.pk:
        project = None
    return customer, project


@login_required
def expense_list(request):
    org = _org(request)
    from erp.services.permissions import role_for
    if role_for(request.user) not in {"admin", "office", "project_manager", "accounting"}:
        raise PermissionDenied("Belege sind nur für das Büro freigegeben.")
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
    from erp.services.permissions import role_for
    if role_for(request.user) not in {"admin", "office", "project_manager", "accounting"}:
        raise PermissionDenied("Belege sind nur für das Büro freigegeben.")
    expense = get_object_or_404(m.Expense, organization=org, pk=pk) if pk else None

    # Existing expenses keep the detailed accounting editor. New expenses use the
    # ToolTime receipt-first workflow and create the linked Document automatically.
    if expense is not None or request.GET.get("mode") == "manual":
        form = ExpenseForm(request.POST or None, instance=expense, organization=org)
        if request.method == "POST" and form.is_valid():
            obj = form.save(commit=False)
            obj.organization = org
            obj.save()
            messages.success(request, "Ausgabe gespeichert.")
            return redirect("next-expenses")
        return render(request, "rebuild/ops_form.html", {"form": form, "kind": "expense", "object": expense})

    selected_customer, selected_project = _receipt_context_customer(request, org)
    initial = {"expense_date": timezone.localdate(), "tax_rate": 19}
    if selected_customer is not None:
        initial["customer"] = selected_customer
    if selected_project is not None:
        initial["project"] = selected_project

    form = ReceiptExpenseForm(
        request.POST or None,
        request.FILES or None,
        organization=org,
        customer=selected_customer,
        initial=initial,
    )

    if request.method == "POST" and form.is_valid():
        project = form.cleaned_data.get("project")
        customer = form.cleaned_data.get("customer")
        if customer is None and project is not None:
            customer = project.customer
        upload = form.cleaned_data["receipt_file"]
        safe_name = (getattr(upload, "name", "beleg") or "beleg").rsplit("/", 1)[-1]
        description = (form.cleaned_data.get("description") or "").strip() or safe_name
        supplier = (form.cleaned_data.get("supplier") or "").strip()

        with transaction.atomic():
            document = m.Document(
                organization=org,
                customer=customer,
                project=project,
                title=safe_name,
                category="other",
                mime_type=getattr(upload, "content_type", "") or "",
                size=getattr(upload, "size", 0) or 0,
                metadata={
                    "kind": "expense_receipt",
                    "source": "tooltime-receipt-create",
                    "supplier": supplier,
                    "amount_net": str(form.cleaned_data["amount_net"]),
                    "tax_rate": str(form.cleaned_data["tax_rate"]),
                },
                uploaded_by=request.user,
            )
            document.file.save(safe_name, upload, save=False)
            document.save()
            expense = m.Expense.objects.create(
                organization=org,
                supplier=supplier,
                description=description,
                amount_net=form.cleaned_data["amount_net"],
                tax_rate=form.cleaned_data["tax_rate"],
                expense_date=form.cleaned_data["expense_date"],
                category=(form.cleaned_data.get("category") or "").strip(),
                paid=bool(form.cleaned_data.get("paid")),
                project=project,
                document=document,
            )

        messages.success(request, "Beleg und Ausgabe wurden gespeichert.")
        if customer is not None:
            return redirect("next-customer-detail", pk=customer.pk)
        return redirect("next-expenses")

    suppliers = list(
        m.Expense.objects.filter(organization=org)
        .exclude(supplier="")
        .order_by("supplier")
        .values_list("supplier", flat=True)
        .distinct()[:200]
    )
    customers = form.fields["customer"].queryset
    projects = form.fields["project"].queryset
    cancel_url = (
        f"/customers/{selected_customer.pk}/" if selected_customer is not None else "/expenses/"
    )
    return render(request, "rebuild/expense_receipt_form.html", {
        "receipt_form": form,
        "selected_customer": selected_customer,
        "selected_project": selected_project,
        "customers": customers,
        "projects": projects,
        "suppliers": suppliers,
        "cancel_url": cancel_url,
    })


@login_required
def employee_list(request):
    org = _org(request)
    query = request.GET.get("q", "").strip()
    employees = m.Employee.objects.filter(organization=org).select_related("user")
    if query:
        employees = employees.filter(
            Q(first_name__icontains=query)
            | Q(last_name__icontains=query)
            | Q(email__icontains=query)
            | Q(phone__icontains=query)
            | Q(employee_number__icontains=query)
            | Q(trade__icontains=query)
        )
    employees = employees.order_by("-active", "last_name", "first_name")
    return render(request, "rebuild/employees.html", {"employees": employees, "query": query})


@login_required
@require_http_methods(["GET", "POST"])
def employee_edit(request, pk=None):
    org = _org(request)
    employee = get_object_or_404(m.Employee, organization=org, pk=pk) if pk else None
    can_manage_roles = _can_manage_employee_roles(request)
    form = EmployeeForm(
        request.POST or None,
        instance=employee,
        can_manage_roles=can_manage_roles,
    )
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            obj = form.save(commit=False)
            obj.organization = org
            if not obj.employee_number:
                obj.employee_number = _employee_number(org)
            obj.save()
            _ensure_employee_login(
                org,
                obj,
                form,
                can_manage_roles=can_manage_roles,
            )
        messages.success(request, "Mitarbeiter und App-Berechtigung gespeichert.")
        return redirect("next-employees")
    return render(
        request,
        "rebuild/ops_form.html",
        {"form": form, "kind": "employee", "object": employee, "can_manage_roles": can_manage_roles},
    )
