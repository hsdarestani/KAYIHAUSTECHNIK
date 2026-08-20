from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MARKER = "A+BAU TOOLTIME PHASE 14 APPOINTMENT CUSTOMER 2026-08-21"
MIGRATION_REL = "erp/migrations/0012_calendar_event_customer.py"


def _replace_once(text: str, old: str, new: str, label: str) -> str:
    if new in text:
        return text
    if old not in text:
        raise RuntimeError(f"Phase 14 appointment-customer anchor missing: {label}")
    return text.replace(old, new, 1)


def _function_block(text: str, start_marker: str, end_markers: tuple[str, ...], label: str) -> tuple[int, int, str]:
    start = text.find(start_marker)
    if start < 0:
        raise RuntimeError(f"Phase 14 function start missing: {label}")
    candidates = [text.find(marker, start + len(start_marker)) for marker in end_markers]
    candidates = [value for value in candidates if value >= 0]
    if not candidates:
        raise RuntimeError(f"Phase 14 function end missing: {label}")
    end = min(candidates)
    return start, end, text[start:end]


def patch_model(module) -> None:
    rel = "erp/models.py"
    text = module.read(rel)
    class_start = text.find("class CalendarEvent(")
    if class_start < 0:
        raise RuntimeError("Phase 14 CalendarEvent model boundary missing")
    class_end = text.find("\n\nclass ", class_start + 1)
    if class_end < 0:
        class_end = len(text)
    block = text[class_start:class_end]
    if 'related_name="calendar_events"' not in block:
        project_anchor = "\n    project = models.ForeignKey("
        pos = block.find(project_anchor)
        if pos < 0:
            raise RuntimeError("Phase 14 CalendarEvent project field anchor missing")
        field = '''
    customer = models.ForeignKey(
        "Customer",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="calendar_events",
    )
'''
        block = block[:pos] + field + block[pos:]
        text = text[:class_start] + block + text[class_end:]
    module.write(rel, text)
    compile(text, str(ROOT / rel), "exec")


def install_migration(module) -> None:
    migration = '''from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("erp", "0011_project_approval_flow"),
    ]

    operations = [
        migrations.AddField(
            model_name="calendarevent",
            name="customer",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="calendar_events",
                to="erp.customer",
            ),
        ),
    ]
'''
    module.write(MIGRATION_REL, migration)
    compile(migration, str(ROOT / MIGRATION_REL), "exec")


def patch_create_and_edit(module) -> None:
    rel = "erp/rebuild_views.py"
    text = module.read(rel)

    helper_marker = "def _appointment_customer_address(customer):"
    create_marker = '@login_required\n@require_http_methods(["GET", "POST"])\ndef appointment_create(request):\n'
    if helper_marker not in text:
        create_pos = text.find(create_marker)
        if create_pos < 0:
            raise RuntimeError("Phase 14 appointment_create boundary missing")
        helper = '''def _appointment_customer_address(customer):
    if customer is None:
        return ""
    city_line = " ".join(part for part in [customer.postal_code, customer.city] if part).strip()
    return ", ".join(part for part in [customer.street, city_line] if part)


'''
        text = text[:create_pos] + helper + text[create_pos:]

    create_start, create_end, create = _function_block(
        text,
        create_marker,
        (
            '\n\n@login_required\n@require_http_methods(["GET", "POST"])\ndef appointment_edit(request, pk):\n',
            "\n\n@login_required\ndef appointment_detail(request, pk):\n",
        ),
        "appointment_create",
    )
    create = create.replace(
        "    # Customer is presentation-only on CalendarEvent; project remains the\n    # persistent relationship and its ModelChoiceField is organization-scoped.\n",
        "    # Customer can be stored directly when no project is selected. A selected\n    # project remains authoritative for its customer to prevent mismatched links.\n",
    )
    create = _replace_once(
        create,
        "    if selected_customer is None and selected_project is not None and selected_project.customer_id:\n        selected_customer = selected_project.customer\n",
        "    if selected_project is not None and selected_project.customer_id:\n        selected_customer = selected_project.customer\n",
        "project customer authority on create",
    )
    if "event.customer = selected_customer" not in create:
        create = _replace_once(
            create,
            "        event.organization = org\n        event.created_by = request.user\n        event.save()\n",
            "        event.organization = org\n        event.created_by = request.user\n        event.customer = selected_customer\n        if not event.location and event.customer_id:\n            event.location = _appointment_customer_address(event.customer)\n        event.save()\n",
            "customer persistence on create",
        )
    text = text[:create_start] + create + text[create_end:]

    edit_marker = '@login_required\n@require_http_methods(["GET", "POST"])\ndef appointment_edit(request, pk):\n'
    edit_start, edit_end, edit = _function_block(
        text,
        edit_marker,
        ("\n\n@login_required\ndef appointment_detail(request, pk):\n",),
        "appointment_edit",
    )
    edit = _replace_once(
        edit,
        '.select_related("project", "project__customer", "project__object_location")',
        '.select_related("project", "project__customer", "project__object_location", "customer")',
        "direct customer select_related on edit",
    )
    edit = _replace_once(
        edit,
        '''    requested_customer_id = (
        request.POST.get("customer_filter") if request.method == "POST" else None
    )
''',
        '''    requested_customer_id = (
        request.POST.get("customer_filter") if request.method == "POST" else event.customer_id
    )
''',
        "direct customer edit preselection",
    )
    edit = _replace_once(
        edit,
        "    if selected_customer is None and selected_project is not None and selected_project.customer_id:\n        selected_customer = selected_project.customer\n",
        "    if selected_project is not None and selected_project.customer_id:\n        selected_customer = selected_project.customer\n",
        "project customer authority on edit",
    )
    if "updated.customer = selected_customer" not in edit:
        edit = _replace_once(
            edit,
            "        updated.created_by = event.created_by or request.user\n        updated.save()\n",
            "        updated.created_by = event.created_by or request.user\n        updated.customer = selected_customer\n        if not updated.location and updated.customer_id:\n            updated.location = _appointment_customer_address(updated.customer)\n        updated.save()\n",
            "customer persistence on edit",
        )
    text = text[:edit_start] + edit + text[edit_end:]

    module.write(rel, text)
    compile(text, str(ROOT / rel), "exec")


def patch_calendar(module) -> None:
    rel = "erp/rebuild_views.py"
    text = module.read(rel)
    start_marker = "@login_required\ndef appointment_list(request):\n"
    end_marker = "\n\n@login_required\n@require_POST\ndef appointment_move(request, pk):\n"
    start, end, block = _function_block(text, start_marker, (end_marker,), "appointment_list")

    block = _replace_once(
        block,
        '.select_related("project", "project__customer")',
        '.select_related("project", "project__customer", "customer")',
        "calendar direct customer select_related",
    )
    block = _replace_once(
        block,
        '''    if customer_filter.isdigit():
        events = events.filter(project__customer_id=int(customer_filter))
    else:
        customer_filter = ""
''',
        '''    if customer_filter.isdigit():
        events = events.filter(
            Q(project__customer_id=int(customer_filter)) | Q(customer_id=int(customer_filter))
        ).distinct()
    else:
        customer_filter = ""
''',
        "calendar direct customer filter",
    )
    block = _replace_once(
        block,
        '''            | Q(project__customer__company__icontains=query_filter)
            | Q(project__customer__first_name__icontains=query_filter)
            | Q(project__customer__last_name__icontains=query_filter)
''',
        '''            | Q(project__customer__company__icontains=query_filter)
            | Q(project__customer__first_name__icontains=query_filter)
            | Q(project__customer__last_name__icontains=query_filter)
            | Q(customer__company__icontains=query_filter)
            | Q(customer__first_name__icontains=query_filter)
            | Q(customer__last_name__icontains=query_filter)
''',
        "calendar direct customer search",
    )
    block = _replace_once(
        block,
        '''        event.ui_customer = event.project.customer.display_name if event.project_id else "Intern"
        event.ui_project = f"{event.project.number} · {event.project.title}" if event.project_id else "Interner Termin"
        event.ui_map_address = (event.location or "").strip()
''',
        '''        event_customer = event.project.customer if event.project_id and event.project.customer_id else event.customer
        event.ui_customer = event_customer.display_name if event_customer is not None else "Intern"
        event.ui_project = f"{event.project.number} · {event.project.title}" if event.project_id else ("Ohne Projekt" if event.customer_id else "Interner Termin")
        event.ui_map_address = (event.location or "").strip() or _appointment_customer_address(event_customer)
''',
        "calendar direct customer projection",
    )

    text = text[:start] + block + text[end:]
    module.write(rel, text)
    compile(text, str(ROOT / rel), "exec")


def patch_field_detail(module) -> None:
    views_rel = "erp/field_authorization_views.py"
    views = module.read(views_rel)
    views = views.replace(
        '.select_related("project", "project__customer", "project__object_location")',
        '.select_related("project", "project__customer", "project__object_location", "customer")',
    )
    module.write(views_rel, views)
    compile(views, str(ROOT / views_rel), "exec")

    template_rel = "templates/rebuild/appointment_detail.html"
    template = module.read(template_rel)
    old = "{% if event.project %}{{ event.project.number }} · {{ event.project.customer.display_name }}{% else %}Interner Termin{% endif %}"
    new = "{% if event.project %}{{ event.project.number }} · {{ event.project.customer.display_name }}{% elif event.customer %}{{ event.customer.display_name }} · Ohne Projekt{% else %}Interner Termin{% endif %}"
    template = _replace_once(template, old, new, "direct customer detail identity")
    module.write(template_rel, template)


def patch_form_copy(module) -> None:
    rel = "templates/rebuild/appointment_form.html"
    text = module.read(rel)
    text = text.replace(
        "Customer is presentation-only on CalendarEvent; project remains the persistent relationship.",
        "Customer is persisted directly when no project is selected; project customer wins when a project is selected.",
    )
    module.write(rel, text)


def install_tests(module) -> None:
    runtime_rel = "tests/test_tooltime_phase14_appointment_customer.py"
    runtime = r'''from datetime import timedelta

from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from erp import rebuild_views
from erp.models import CalendarEvent, Customer, Organization, Project, UserProfile


class ToolTimePhase14AppointmentCustomerTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name="KAYI phase14")
        self.other_org = Organization.objects.create(name="KAYI phase14 other")
        self.user = User.objects.create_user("phase14-office", password="safe-test-password")
        UserProfile.objects.update_or_create(
            user=self.user,
            defaults={"organization": self.org, "role": UserProfile.Role.ADMIN, "is_mobile_worker": False},
        )
        self.client = Client()
        self.assertTrue(self.client.login(username="phase14-office", password="safe-test-password"))
        self.customer = Customer.objects.create(
            organization=self.org,
            number="K-P14-1",
            type="business",
            company="Direktkunde Phase14",
            street="Kundenstraße 14",
            postal_code="60314",
            city="Frankfurt",
        )
        self.project_customer = Customer.objects.create(
            organization=self.org,
            number="K-P14-2",
            type="business",
            company="Projektkunde Phase14",
            street="Projektweg 2",
            postal_code="60315",
            city="Frankfurt",
        )
        self.project = Project.objects.create(
            organization=self.org,
            number="P-P14-1",
            title="Phase 14 Projekt",
            customer=self.project_customer,
            status="planning",
            priority="normal",
        )

    def _payload(self, title, *, customer=None, project=None, location=""):
        form = rebuild_views.AppointmentForm(organization=self.org)
        start = timezone.localtime().replace(second=0, microsecond=0) + timedelta(hours=2)
        end = start + timedelta(hours=1)
        data = {
            "title": title,
            "starts_at": start.strftime("%Y-%m-%dT%H:%M"),
            "ends_at": end.strftime("%Y-%m-%dT%H:%M"),
            "location": location,
            "project": str(project.pk) if project is not None else "",
            "customer_filter": str(customer.pk) if customer is not None else "",
        }
        for name, field in form.fields.items():
            if name in data or not field.required:
                continue
            choices = list(getattr(field, "choices", []) or [])
            usable = [value for value, _label in choices if str(value) != ""]
            data[name] = str(usable[0]) if usable else "Test"
        return data

    def test_customer_only_create_persists_customer_and_address(self):
        response = self.client.post(
            reverse("next-appointment-create"),
            self._payload("Direkter Kundentermin", customer=self.customer),
        )
        self.assertEqual(response.status_code, 302)
        event = CalendarEvent.objects.get(organization=self.org, title="Direkter Kundentermin")
        self.assertIsNone(event.project_id)
        self.assertEqual(event.customer_id, self.customer.pk)
        self.assertEqual(event.location, "Kundenstraße 14, 60314 Frankfurt")

    def test_project_customer_overrides_mismatched_customer_filter(self):
        response = self.client.post(
            reverse("next-appointment-create"),
            self._payload("Projekttermin Phase14", customer=self.customer, project=self.project),
        )
        self.assertEqual(response.status_code, 302)
        event = CalendarEvent.objects.get(organization=self.org, title="Projekttermin Phase14")
        self.assertEqual(event.project_id, self.project.pk)
        self.assertEqual(event.customer_id, self.project_customer.pk)

    def test_customer_only_event_is_filterable_searchable_and_mappable(self):
        self.client.post(
            reverse("next-appointment-create"),
            self._payload("Kundenfilter Phase14", customer=self.customer),
        )
        event = CalendarEvent.objects.get(organization=self.org, title="Kundenfilter Phase14")
        anchor = timezone.localtime(event.starts_at).date().isoformat()

        filtered = self.client.get(reverse("next-appointments"), {
            "view": "list", "date": anchor, "customer": str(self.customer.pk),
        })
        self.assertEqual(filtered.status_code, 200)
        self.assertContains(filtered, "Kundenfilter Phase14")
        self.assertContains(filtered, "Direktkunde Phase14")

        searched = self.client.get(reverse("next-appointments"), {
            "view": "list", "date": anchor, "q": "Direktkunde Phase14",
        })
        self.assertContains(searched, "Kundenfilter Phase14")

        mapped = self.client.get(reverse("next-appointments"), {"view": "map", "date": anchor})
        self.assertEqual(mapped.status_code, 200)
        self.assertContains(mapped, "Kundenfilter Phase14")
        self.assertContains(mapped, "Kundenstraße 14, 60314 Frankfurt")

    def test_edit_prefills_and_persists_direct_customer(self):
        self.client.post(
            reverse("next-appointment-create"),
            self._payload("Edit Kunde Phase14", customer=self.customer),
        )
        event = CalendarEvent.objects.get(organization=self.org, title="Edit Kunde Phase14")
        response = self.client.get(reverse("next-appointment-edit", args=[event.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, f'data-initial-customer="{self.customer.pk}"')
        self.assertContains(response, 'data-initial-project=""')

        post = self._payload("Edit Kunde Phase14 neu", customer=self.project_customer, location="")
        response = self.client.post(reverse("next-appointment-edit", args=[event.pk]), post)
        self.assertEqual(response.status_code, 302)
        event.refresh_from_db()
        self.assertEqual(event.customer_id, self.project_customer.pk)
        self.assertEqual(event.title, "Edit Kunde Phase14 neu")
        self.assertEqual(event.location, "Projektweg 2, 60315 Frankfurt")

    def test_customer_only_detail_identifies_customer_but_keeps_project_recovery(self):
        self.client.post(
            reverse("next-appointment-create"),
            self._payload("Detail Kunde Phase14", customer=self.customer),
        )
        event = CalendarEvent.objects.get(organization=self.org, title="Detail Kunde Phase14")
        response = self.client.get(reverse("next-appointment-detail", args=[event.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Direktkunde Phase14")
        self.assertContains(response, "Ohne Projekt")
'''
    module.write(runtime_rel, runtime)
    compile(runtime, str(ROOT / runtime_rel), "exec")

    contract_rel = "tests/test_tooltime_phase14_appointment_customer_contract.py"
    contract = r'''from pathlib import Path

from django.test import SimpleTestCase

ROOT = Path(__file__).resolve().parents[1]


class ToolTimePhase14AppointmentCustomerContractTests(SimpleTestCase):
    def test_native_customer_relation_and_migration_are_assembled(self):
        models = (ROOT / "erp/models.py").read_text(encoding="utf-8")
        migration = (ROOT / "erp/migrations/0012_calendar_event_customer.py").read_text(encoding="utf-8")
        views = (ROOT / "erp/rebuild_views.py").read_text(encoding="utf-8")
        detail = (ROOT / "templates/rebuild/appointment_detail.html").read_text(encoding="utf-8")

        self.assertIn('related_name="calendar_events"', models)
        self.assertIn('("erp", "0011_project_approval_flow")', migration)
        self.assertIn('name="customer"', migration)
        self.assertIn("event.customer = selected_customer", views)
        self.assertIn("updated.customer = selected_customer", views)
        self.assertIn("Q(customer_id=int(customer_filter))", views)
        self.assertIn("Q(customer__company__icontains=query_filter)", views)
        self.assertIn("_appointment_customer_address", views)
        self.assertIn("event.customer.display_name", detail)
'''
    module.write(contract_rel, contract)
    compile(contract, str(ROOT / contract_rel), "exec")


def guard(module) -> None:
    models = module.read("erp/models.py")
    migration = module.read(MIGRATION_REL)
    views = module.read("erp/rebuild_views.py")
    detail = module.read("templates/rebuild/appointment_detail.html")
    for marker in ('related_name="calendar_events"', 'customer = models.ForeignKey('):
        if marker not in models:
            raise RuntimeError(f"Phase 14 CalendarEvent customer model marker missing: {marker}")
    for marker in ('("erp", "0011_project_approval_flow")', 'name="customer"', 'to="erp.customer"'):
        if marker not in migration:
            raise RuntimeError(f"Phase 14 migration marker missing: {marker}")
    for marker in (
        "def _appointment_customer_address(customer):",
        "event.customer = selected_customer",
        "updated.customer = selected_customer",
        "Q(customer_id=int(customer_filter))",
        "Q(customer__company__icontains=query_filter)",
        'select_related("project", "project__customer", "customer")',
        "event.ui_map_address",
    ):
        if marker not in views:
            raise RuntimeError(f"Phase 14 backend marker missing: {marker}")
    if "event.customer.display_name" not in detail or "Ohne Projekt" not in detail:
        raise RuntimeError("Phase 14 customer-only appointment detail identity missing")


def run(module) -> None:
    patch_model(module)
    install_migration(module)
    patch_create_and_edit(module)
    patch_calendar(module)
    patch_field_detail(module)
    patch_form_copy(module)
    install_tests(module)
    guard(module)
    print(f"{MARKER}: customer-only appointments now persist a native customer relation, inherit a usable address and participate in search, filters, map and edit flows without creating hidden projects.")
