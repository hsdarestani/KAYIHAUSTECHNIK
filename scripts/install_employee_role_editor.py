from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OPS_PATH = ROOT / "erp" / "rebuild_ops.py"
MARKER = "A_BAU_EMPLOYEE_ROLE_EDITOR"

if not OPS_PATH.exists():
    raise RuntimeError("Employee role editor target missing: erp/rebuild_ops.py")

text = OPS_PATH.read_text(encoding="utf-8")

if MARKER not in text:
    old_fields = '''class EmployeeForm(StyledModelForm):
    username = forms.CharField(label="App-Benutzername", required=False)
    password = forms.CharField(label="Startpasswort", required=False, widget=forms.PasswordInput(render_value=True))
'''
    new_fields = '''class EmployeeForm(StyledModelForm):
    # A_BAU_EMPLOYEE_ROLE_EDITOR
    role = forms.ChoiceField(label="Rolle", required=True, choices=())
    username = forms.CharField(label="App-Benutzername", required=False)
    password = forms.CharField(label="Startpasswort", required=False, widget=forms.PasswordInput(render_value=True))
'''
    if old_fields not in text:
        raise RuntimeError("EmployeeForm field anchor changed")
    text = text.replace(old_fields, new_fields, 1)

    old_init = '''    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Legacy employee creation did not require accounting values. Keep that
        # low-friction behavior in the rebuilt UI and use model defaults.
        for name in ("hourly_cost", "hourly_rate", "color"):
            self.fields[name].required = False
        if not self.is_bound:
            self.fields["hourly_cost"].initial = self.instance.hourly_cost if self.instance and self.instance.pk else 0
            self.fields["hourly_rate"].initial = self.instance.hourly_rate if self.instance and self.instance.pk else 0
            self.fields["color"].initial = self.instance.color if self.instance and self.instance.pk else "#2f80ed"
            if self.instance and self.instance.user_id:
                self.fields["username"].initial = self.instance.user.username
'''
    new_init = '''    def __init__(self, *args, can_manage_roles=False, **kwargs):
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
'''
    if old_init not in text:
        raise RuntimeError("EmployeeForm init anchor changed")
    text = text.replace(old_init, new_init, 1)

    helper_anchor = '''\ndef _employee_number(org) -> str:\n'''
    helper = '''\ndef _can_manage_employee_roles(request) -> bool:\n    profile = getattr(request.user, "profile", None)\n    return bool(\n        request.user.is_superuser\n        or getattr(profile, "role", "") == m.UserProfile.Role.ADMIN\n    )\n\n\ndef _employee_number(org) -> str:\n'''
    if helper_anchor not in text:
        raise RuntimeError("Employee role permission helper anchor changed")
    text = text.replace(helper_anchor, helper, 1)

    start = text.find("def _ensure_technician_login(org, employee: m.Employee, form: EmployeeForm) -> None:\n")
    end = text.find("\n\n@login_required\ndef task_list", start)
    if start < 0 or end < 0:
        raise RuntimeError("Legacy technician-login helper anchor changed")
    login_helper = '''def _ensure_employee_login(org, employee: m.Employee, form: EmployeeForm, *, can_manage_roles=False) -> None:
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
'''
    text = text[:start] + login_helper + text[end:]

    old_edit = '''def employee_edit(request, pk=None):
    org = _org(request)
    employee = get_object_or_404(m.Employee, organization=org, pk=pk) if pk else None
    form = EmployeeForm(request.POST or None, instance=employee)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            obj = form.save(commit=False)
            obj.organization = org
            if not obj.employee_number:
                obj.employee_number = _employee_number(org)
            obj.save()
            _ensure_technician_login(org, obj, form)
        messages.success(request, "Mitarbeiter gespeichert. App-Zugang ist mit der Monteur-Rolle verknüpft.")
        return redirect("next-employees")
    return render(request, "rebuild/ops_form.html", {"form": form, "kind": "employee", "object": employee})
'''
    new_edit = '''def employee_edit(request, pk=None):
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
'''
    if old_edit not in text:
        raise RuntimeError("Employee edit view anchor changed")
    text = text.replace(old_edit, new_edit, 1)

OPS_PATH.write_text(text, encoding="utf-8")

TEST_PATH = ROOT / "tests" / "test_ab_bau_employee_role_editor.py"
TEST_PATH.write_text(r'''from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from erp import models as m


User = get_user_model()


class ABBauEmployeeRoleEditorTests(TestCase):
    def setUp(self):
        self.org = m.Organization.objects.create(name="A+Bau Rollen Test")
        self.admin = User.objects.create_user("role-admin", password="testpass")
        self.admin.profile.organization = self.org
        self.admin.profile.role = m.UserProfile.Role.ADMIN
        self.admin.profile.save()

        self.target_user = User.objects.create_user("target-tech", password="testpass")
        self.target_user.profile.organization = self.org
        self.target_user.profile.role = m.UserProfile.Role.TECHNICIAN
        self.target_user.profile.is_mobile_worker = True
        self.target_user.profile.save()
        self.employee = m.Employee.objects.create(
            organization=self.org,
            employee_number="M-ROLE-1",
            first_name="Max",
            last_name="Muster",
            email="max@example.com",
            active=True,
            user=self.target_user,
        )
        self.client = Client()

    def _payload(self, role):
        return {
            "first_name": "Max",
            "last_name": "Muster",
            "email": "max@example.com",
            "phone": "",
            "trade": "Sanitär",
            "hourly_cost": "0",
            "hourly_rate": "0",
            "active": "on",
            "color": "#2f80ed",
            "role": role,
            "username": "target-tech",
            "password": "",
        }

    def test_admin_sees_role_selector_and_can_change_role(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("next-employee-edit", args=[self.employee.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'name="role"')
        self.assertContains(response, "Rolle")

        response = self.client.post(
            reverse("next-employee-edit", args=[self.employee.pk]),
            self._payload("office"),
        )
        self.assertEqual(response.status_code, 302)
        self.target_user.profile.refresh_from_db()
        self.assertEqual(self.target_user.profile.role, "office")
        self.assertFalse(self.target_user.profile.is_mobile_worker)

    def test_non_admin_cannot_escalate_role_with_crafted_post(self):
        office = User.objects.create_user("office-editor", password="testpass")
        office.profile.organization = self.org
        office.profile.role = "office"
        office.profile.save()
        self.client.force_login(office)

        response = self.client.post(
            reverse("next-employee-edit", args=[self.employee.pk]),
            self._payload("admin"),
        )
        self.assertEqual(response.status_code, 302)
        self.target_user.profile.refresh_from_db()
        self.assertEqual(self.target_user.profile.role, m.UserProfile.Role.TECHNICIAN)
        self.assertTrue(self.target_user.profile.is_mobile_worker)

    def test_editing_employee_no_longer_resets_existing_role_to_technician(self):
        self.target_user.profile.role = "project_manager"
        self.target_user.profile.is_mobile_worker = False
        self.target_user.profile.save()
        office = User.objects.create_user("office-editor-2", password="testpass")
        office.profile.organization = self.org
        office.profile.role = "office"
        office.profile.save()
        self.client.force_login(office)

        response = self.client.post(
            reverse("next-employee-edit", args=[self.employee.pk]),
            self._payload("technician"),
        )
        self.assertEqual(response.status_code, 302)
        self.target_user.profile.refresh_from_db()
        self.assertEqual(self.target_user.profile.role, "project_manager")
        self.assertFalse(self.target_user.profile.is_mobile_worker)
''', encoding="utf-8")

# Assembly guard: both UI and server-side authorization must be present.
final_text = OPS_PATH.read_text(encoding="utf-8")
for needle in (
    'role = forms.ChoiceField(label="Rolle"',
    "def _can_manage_employee_roles",
    "def _ensure_employee_login",
    "can_manage_roles=can_manage_roles",
    "profile.role = role",
):
    if needle not in final_text:
        raise RuntimeError(f"Employee role editor incomplete: {needle}")
if "profile.role = m.UserProfile.Role.TECHNICIAN\n    profile.phone" in final_text:
    raise RuntimeError("Legacy forced technician role is still active")

print("A+Bau employee role editor installed: admin-managed roles with server-side escalation protection.")
