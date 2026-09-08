import json
from unittest import mock
from datetime import timedelta

from django.contrib.auth.models import User
from django.contrib.sessions.middleware import SessionMiddleware
from django.http import JsonResponse
from django.test import Client, RequestFactory, TestCase
from django.urls import reverse
from django.utils import timezone

from erp import ai_role_permissions as perms
from erp import assistant_views, field_authorization_views, room_planner_views
from erp.models import CalendarEvent, Customer, Employee, Organization, Project, UserProfile


class AIRolePermissionHardeningTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name="KI RBAC Test")

        self.admin = self._user("admin-ai", UserProfile.Role.ADMIN)
        self.office = self._user("office-ai", UserProfile.Role.OFFICE)
        self.accounting = self._user("accounting-ai", UserProfile.Role.ACCOUNTING)
        self.pm = self._user("pm-ai", UserProfile.Role.PROJECT_MANAGER)
        self.tech = self._user("tech-ai", UserProfile.Role.TECHNICIAN)
        self.other = self._user("other-ai", UserProfile.Role.TECHNICIAN)
        self.readonly = self._user("readonly-ai", UserProfile.Role.READONLY)

        self.pm_employee = self._employee(self.pm, "M-PM", "Paula", "Leitung")
        self.tech_employee = self._employee(self.tech, "M-TECH", "Tom", "Monteur")
        self.other_employee = self._employee(self.other, "M-OTHER", "Otto", "Fremd")

        self.assigned_customer = Customer.objects.create(
            organization=self.org, number="K-ASSIGNED", company="Assigned Kunde"
        )
        self.secret_customer = Customer.objects.create(
            organization=self.org, number="K-SECRET", company="Secret Kunde"
        )
        self.assigned_project = Project.objects.create(
            organization=self.org, number="P-ASSIGNED", title="Assigned Bad",
            customer=self.assigned_customer, manager=self.pm_employee, status="in_progress"
        )
        self.assigned_project.members.add(self.tech_employee)
        self.secret_project = Project.objects.create(
            organization=self.org, number="P-SECRET", title="Secret Villa",
            customer=self.secret_customer, manager=self.other_employee, status="in_progress"
        )
        now = timezone.now()
        self.assigned_event = CalendarEvent.objects.create(
            organization=self.org, project=self.assigned_project, title="Assigned Einsatz",
            starts_at=now, ends_at=now + timedelta(hours=1), type="site"
        )
        self.assigned_event.attendees.add(self.tech_employee)
        self.secret_event = CalendarEvent.objects.create(
            organization=self.org, project=self.secret_project, title="Secret Einsatz",
            starts_at=now, ends_at=now + timedelta(hours=1), type="site"
        )
        self.secret_event.attendees.add(self.other_employee)

    def _user(self, username, role):
        user = User.objects.create_user(username=username, password="safe-test-password", email=f"{username}@example.test")
        user.profile.organization = self.org
        user.profile.role = role
        user.profile.is_mobile_worker = role == UserProfile.Role.TECHNICIAN
        user.profile.save()
        return user

    def _employee(self, user, number, first, last):
        return Employee.objects.create(
            organization=self.org, user=user, employee_number=number,
            first_name=first, last_name=last, email=user.email, active=True
        )

    def _request(self, user, path="/assistant/command/"):
        request = RequestFactory().post(path, data={})
        request.user = user
        middleware = SessionMiddleware(lambda req: None)
        middleware.process_request(request)
        request.session.save()
        return request

    def test_technician_entity_search_is_assignment_scoped(self):
        assigned = perms.entity_search_context(self.tech, self.org, "Assigned")
        secret = perms.entity_search_context(self.tech, self.org, "Secret")
        self.assertTrue(any(item["id"] == self.assigned_project.pk and item["route"] == "projects" for item in assigned))
        self.assertTrue(any(item["id"] == self.assigned_customer.pk and item["route"] == "customers" for item in assigned))
        self.assertFalse(any(item["id"] == self.secret_project.pk for item in secret))
        self.assertFalse(any(item["id"] == self.secret_customer.pk for item in secret))
        self.assertFalse(any(item["id"] == self.other_employee.pk for item in secret))

    def test_project_manager_scope_does_not_include_unassigned_project(self):
        self.assertTrue(perms.project_allowed(self.pm, self.org, self.assigned_project.pk))
        self.assertFalse(perms.project_allowed(self.pm, self.org, self.secret_project.pk))
        matches = perms.entity_search_context(self.pm, self.org, "Secret")
        self.assertFalse(any(item["id"] == self.secret_project.pk for item in matches))

    def test_non_commercial_roles_never_send_price_context_to_ki(self):
        payload = {
            "message": "Dokumentiere den Einsatz",
            "path": f"/projects/{self.assigned_project.pk}/",
            "fields": [
                {"name": "description", "label": "Beschreibung", "value": "Bad"},
                {"name": "unit_price", "label": "Verkaufspreis", "value": "999.00"},
                {"name": "purchase_price", "label": "Einkauf", "value": "500.00"},
                {
                    "name": "customer", "label": "Kunde", "value": str(self.assigned_customer.pk),
                    "options": [
                        {"value": str(self.assigned_customer.pk), "label": "Assigned Kunde"},
                        {"value": str(self.secret_customer.pk), "label": "Secret Kunde"},
                    ],
                },
            ],
            "catalog": [{"name": "Waschtisch", "code": "X1", "unit": "Stk.", "price": "1234.56", "purchase_price": "800"}],
            "history": [{"role": "assistant", "content": "Secret price was 1234 EUR"}],
        }
        safe = perms.sanitize_assistant_payload(self.tech, self.org, payload)
        names = {field["name"] for field in safe["fields"]}
        self.assertIn("description", names)
        self.assertNotIn("unit_price", names)
        self.assertNotIn("purchase_price", names)
        customer = next(field for field in safe["fields"] if field["name"] == "customer")
        self.assertEqual([option["value"] for option in customer["options"]], [str(self.assigned_customer.pk)])
        self.assertNotIn("price", safe["catalog"][0])
        self.assertNotIn("purchase_price", safe["catalog"][0])
        self.assertEqual(safe["history"], [])

    def test_price_request_is_rejected_before_llm_for_technician(self):
        client = Client()
        self.assertTrue(client.login(username=self.tech.username, password="safe-test-password"))
        with mock.patch.object(assistant_views, "_create_response") as provider:
            response = client.post(
                reverse("next-assistant-command"),
                data=json.dumps({"message": "Wie hoch ist der Verkaufspreis und die Marge?", "path": "/field/", "fields": [], "catalog": []}),
                content_type="application/json",
            )
        self.assertEqual(response.status_code, 403)
        self.assertIn("Preisdaten", response.json()["error"])
        provider.assert_not_called()

    def test_forged_actions_are_filtered_again_server_side(self):
        safe_payload = {
            "fields": [{"name": "description", "label": "Beschreibung", "value": ""}],
            "catalog": [{"name": "Material", "code": "A"}],
        }
        actions = [
            {"type": "set_field", "target": "unit_price", "value": "999", "count": 0},
            {"type": "navigate", "target": "invoices", "value": "", "count": 0},
            {"type": "navigate_record", "target": "projects", "value": str(self.secret_project.pk), "count": 0},
            {"type": "navigate_record", "target": "projects", "value": str(self.assigned_project.pk), "count": 0},
            {"type": "set_field", "target": "description", "value": "OK", "count": 0},
        ]
        filtered = perms.filter_actions(self.tech, self.org, safe_payload, actions)
        self.assertEqual(
            [(item["type"], item["target"]) for item in filtered],
            [("navigate_record", "projects"), ("set_field", "description")],
        )
        self.assertEqual(filtered[0]["value"], str(self.assigned_project.pk))

    def test_old_admin_session_matches_are_requeried_after_role_downgrade(self):
        request = self._request(self.tech)
        request.session["kayi_ai_entity_state"] = {
            "query": "Secret",
            "matches": [{"route": "projects", "id": self.secret_project.pk, "label": "Secret Villa"}],
            "role": "admin",
        }
        request.session.save()
        result = assistant_views._resolve_entity_search(request, self.org, "project")
        self.assertEqual(result["query"], "Secret")
        self.assertEqual(result["matches"], [])
        self.assertEqual(request.session["kayi_ai_entity_state"]["role"], "technician")

    def test_field_ai_strips_catalog_sales_prices_for_technician(self):
        request = self._request(self.tech, f"/appointments/{self.assigned_event.pk}/authorization/ai/")
        fake = JsonResponse({
            "ok": True,
            "summary": "Vorschlag",
            "positions": [{
                "description": "Waschtisch",
                "quantity": "1",
                "unit": "Stk.",
                "unit_price": "999.00",
                "sales_price": "999.00",
                "purchase_price": "400.00",
                "tax_rate": "19.00",
                "margin": "599.00",
            }],
        })
        with mock.patch.object(field_authorization_views, "_ab_role_original_authorization_ai", return_value=fake):
            response = field_authorization_views.authorization_ai(request, self.assigned_event.pk)
        self.assertEqual(response.status_code, 200)
        body = json.loads(response.content.decode("utf-8"))
        position = body["positions"][0]
        for forbidden in ("unit_price", "sales_price", "purchase_price", "tax_rate", "margin"):
            self.assertNotIn(forbidden, position)
        self.assertTrue(body["pricing_locked"])
        self.assertTrue(body["requires_office_pricing"])

    def test_voice_ai_cannot_probe_another_technicians_event(self):
        request = self._request(self.tech, f"/appointments/{self.secret_event.pk}/voice/")
        with mock.patch.object(assistant_views, "_ab_role_original_appointment_voice") as original:
            response = assistant_views.appointment_voice(request, self.secret_event.pk)
        self.assertEqual(response.status_code, 404)
        original.assert_not_called()

    def test_room_ai_cannot_probe_unassigned_project(self):
        request = self._request(self.pm, f"/configurator/?project={self.secret_project.pk}")
        with mock.patch.object(room_planner_views, "_ab_role_original_room_planner_vision") as original:
            response = room_planner_views.room_planner_vision(request, self.secret_project.pk)
        self.assertEqual(response.status_code, 404)
        original.assert_not_called()

    def test_admin_office_accounting_keep_commercial_ai_permission(self):
        for user in (self.admin, self.office, self.accounting):
            with self.subTest(role=perms.role_for(user)):
                self.assertTrue(perms.can_view_prices(user))
                payload = {
                    "fields": [{"name": "unit_price", "label": "Preis", "value": "123"}],
                    "catalog": [{"name": "X", "price": "123"}],
                }
                safe = perms.sanitize_assistant_payload(user, self.org, payload)
                self.assertEqual(safe["fields"][0]["value"], "123")

    def test_readonly_ai_cannot_mutate_drafts(self):
        payload = {"fields": [{"name": "description", "label": "Beschreibung", "value": ""}], "catalog": []}
        actions = [{"type": "set_field", "target": "description", "value": "x", "count": 0}]
        self.assertEqual(perms.filter_actions(self.readonly, self.org, payload, actions), [])
