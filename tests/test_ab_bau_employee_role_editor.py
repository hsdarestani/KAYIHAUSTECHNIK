from django.contrib.auth import get_user_model
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
