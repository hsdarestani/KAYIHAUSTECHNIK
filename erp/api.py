from __future__ import annotations

import logging
import uuid

from django.db.models import Q
from django.utils import timezone
from django.conf import settings
from django.shortcuts import redirect
from django.contrib.auth import authenticate
from rest_framework import routers, status, viewsets
from rest_framework.authtoken.models import Token
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from erp.models import (
    AIConversation, AIMessage, AutomationJob, CalendarEvent, CatalogItem, Customer,
    Document, EmailMessage, Employee, Expense, Invoice, ObjectLocation, Payment,
    PriceItem, PriceSource, Project, ProjectMaterial, Quote, Supplier, Task, TimeEntry, NativeRoomScan, RoomMeasurement,
)
from erp.serializers import (
    AutomationJobSerializer, CalendarEventSerializer, CatalogItemSerializer,
    CustomerSerializer, DocumentSerializer, EmailMessageSerializer, EmployeeSerializer,
    ExpenseSerializer, InvoiceSerializer, ObjectLocationSerializer, PaymentSerializer,
    PriceItemSerializer, PriceSourceSerializer, ProjectMaterialSerializer, ProjectSerializer, QuoteSerializer, SupplierSerializer, TaskSerializer,
    TimeEntrySerializer, NativeRoomScanSerializer,
)
from erp.services.ai import analyze_room_photos, chat
from erp.services.numbering import next_number
from erp.services.native_scans import create_native_scan, parse_payload
from erp.services.permissions import can_view_prices, can_write, role_for


logger = logging.getLogger(__name__)


def organization_for(user):
    profile = getattr(user, "profile", None)
    return getattr(profile, "organization", None)


class OrganizationScopedViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    organization_field = "organization"

    def get_queryset(self):
        org = organization_for(self.request.user)
        qs = self.queryset.all()
        return qs.filter(**{self.organization_field: org})

    def perform_create(self, serializer):
        if not can_write(self.request.user):
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied()
        serializer.save(**{self.organization_field: organization_for(self.request.user)})

    def perform_update(self, serializer):
        if not can_write(self.request.user):
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied()
        serializer.save()

    def perform_destroy(self, instance):
        if not can_write(self.request.user):
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied()
        instance.delete()


class PriceAccessMixin:
    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        if not can_view_prices(request.user):
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("Mitarbeiter dürfen keine Preise oder Finanzdaten abrufen.")


class TechnicianReadOnlyMixin:
    def _deny_technician_write(self):
        if role_for(self.request.user) == "technician":
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("Mitarbeiter dürfen Stammdaten und Einsatzplanung nicht verändern.")

    def perform_create(self, serializer):
        self._deny_technician_write()
        return super().perform_create(serializer)

    def perform_update(self, serializer):
        self._deny_technician_write()
        return super().perform_update(serializer)

    def perform_destroy(self, instance):
        self._deny_technician_write()
        return super().perform_destroy(instance)


class CustomerViewSet(TechnicianReadOnlyMixin, OrganizationScopedViewSet):
    queryset = Customer.objects.all()
    serializer_class = CustomerSerializer
    def get_queryset(self):
        qs = super().get_queryset()
        if role_for(self.request.user) == "technician":
            employee = getattr(self.request.user, "employee", None)
            return qs.filter(projects__members=employee).distinct() if employee else qs.none()
        return qs
    search_fields = ["number", "company", "first_name", "last_name", "email", "phone"]
    ordering_fields = ["number", "company", "last_name", "created_at"]
    def perform_create(self, serializer):
        self._deny_technician_write()
        org = organization_for(self.request.user)
        serializer.save(organization=org, number=next_number(org, "customer"))


class ObjectLocationViewSet(TechnicianReadOnlyMixin, OrganizationScopedViewSet):
    queryset = ObjectLocation.objects.all()
    serializer_class = ObjectLocationSerializer
    def get_queryset(self):
        qs = super().get_queryset()
        if role_for(self.request.user) == "technician":
            employee = getattr(self.request.user, "employee", None)
            return qs.filter(projects__members=employee).distinct() if employee else qs.none()
        return qs
    search_fields = ["name", "street", "city", "customer__company"]


class EmployeeViewSet(TechnicianReadOnlyMixin, OrganizationScopedViewSet):
    queryset = Employee.objects.all()
    serializer_class = EmployeeSerializer
    def get_queryset(self):
        qs = super().get_queryset()
        if role_for(self.request.user) == "technician":
            return qs.filter(user=self.request.user)
        return qs
    search_fields = ["employee_number", "first_name", "last_name", "trade"]
    def perform_create(self, serializer):
        self._deny_technician_write()
        org = organization_for(self.request.user)
        serializer.save(organization=org, employee_number=next_number(org, "employee"))


class ProjectViewSet(TechnicianReadOnlyMixin, OrganizationScopedViewSet):
    queryset = Project.objects.select_related("customer", "manager")
    serializer_class = ProjectSerializer

    def retrieve(self, request, *args, **kwargs):
        # A project clicked in the web app must open the A+Bau project screen,
        # never DRF's browsable API. Native/API consumers still receive JSON.
        accepts_html = "text/html" in request.headers.get("Accept", "")
        explicitly_json = request.query_params.get("format") == "json" or request.headers.get("X-Requested-With") == "XMLHttpRequest"
        if accepts_html and not explicitly_json:
            project = self.get_object()
            return redirect("project-detail", pk=project.pk)
        return super().retrieve(request, *args, **kwargs)

    def get_queryset(self):
        qs = super().get_queryset()
        if role_for(self.request.user) == "technician":
            employee = getattr(self.request.user, "employee", None)
            return qs.filter(Q(members=employee) | Q(manager=employee)).distinct() if employee else qs.none()
        return qs
    search_fields = ["number", "title", "description", "customer__company", "customer__last_name"]
    filterset_fields = ["status", "priority", "customer", "manager"]
    ordering_fields = ["number", "created_at", "planned_start", "status"]
    def perform_create(self, serializer):
        self._deny_technician_write()
        org = organization_for(self.request.user)
        serializer.save(organization=org, number=next_number(org, "project"))


class TaskViewSet(OrganizationScopedViewSet):
    queryset = Task.objects.select_related("project", "assigned_to")
    serializer_class = TaskSerializer
    def get_queryset(self):
        qs = super().get_queryset()
        if role_for(self.request.user) == "technician":
            return qs.filter(assigned_to__user=self.request.user)
        return qs
    search_fields = ["title", "description", "project__title"]
    filterset_fields = ["status", "priority", "project", "assigned_to"]
    def perform_create(self, serializer):
        if role_for(self.request.user) == "technician":
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("Mitarbeiter können keine neuen Aufgaben disponieren.")
        return super().perform_create(serializer)
    def perform_update(self, serializer):
        if role_for(self.request.user) == "technician" and serializer.instance.assigned_to_id != getattr(getattr(self.request.user, "employee", None), "pk", None):
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied()
        serializer.save()


class CalendarEventViewSet(TechnicianReadOnlyMixin, OrganizationScopedViewSet):
    queryset = CalendarEvent.objects.select_related("project")
    serializer_class = CalendarEventSerializer
    def get_queryset(self):
        qs = super().get_queryset()
        if role_for(self.request.user) == "technician":
            return qs.filter(attendees__user=self.request.user).distinct()
        return qs
    search_fields = ["title", "location", "notes"]
    filterset_fields = ["type", "project"]
    def perform_create(self, serializer):
        self._deny_technician_write()
        serializer.save(organization=organization_for(self.request.user), created_by=self.request.user)


class CatalogItemViewSet(PriceAccessMixin, OrganizationScopedViewSet):
    queryset = CatalogItem.objects.all()
    serializer_class = CatalogItemSerializer
    search_fields = ["code", "name", "description", "supplier"]
    filterset_fields = ["kind", "active"]


class ProjectMaterialViewSet(PriceAccessMixin, OrganizationScopedViewSet):
    queryset = ProjectMaterial.objects.select_related("project", "catalog_item")
    serializer_class = ProjectMaterialSerializer
    organization_field = "project__organization"
    search_fields = ["name", "project__title"]
    filterset_fields = ["project", "ordered", "delivered"]
    def perform_create(self, serializer):
        if not can_write(self.request.user):
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied()
        project = serializer.validated_data["project"]
        if project.organization_id != organization_for(self.request.user).id:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied()
        serializer.save()


class TimeEntryViewSet(OrganizationScopedViewSet):
    queryset = TimeEntry.objects.select_related("employee", "project")
    serializer_class = TimeEntrySerializer
    def get_queryset(self):
        qs = super().get_queryset()
        if role_for(self.request.user) == "technician":
            return qs.filter(employee__user=self.request.user)
        return qs
    search_fields = ["description", "employee__first_name", "employee__last_name", "project__title"]
    filterset_fields = ["employee", "project", "approved"]
    def perform_create(self, serializer):
        if role_for(self.request.user) == "technician":
            employee = getattr(self.request.user, "employee", None)
            project = serializer.validated_data.get("project")
            if serializer.validated_data.get("employee") != employee or not project or not project.members.filter(pk=getattr(employee, "pk", None)).exists():
                from rest_framework.exceptions import PermissionDenied
                raise PermissionDenied()
        return super().perform_create(serializer)


class DocumentViewSet(OrganizationScopedViewSet):
    queryset = Document.objects.select_related("project", "customer")
    serializer_class = DocumentSerializer
    def get_queryset(self):
        qs = super().get_queryset()
        if role_for(self.request.user) == "technician":
            employee = getattr(self.request.user, "employee", None)
            return qs.filter(Q(project__members=employee) | Q(project__manager=employee)).distinct() if employee else qs.none()
        return qs
    search_fields = ["title", "extracted_text", "project__title", "customer__company"]
    filterset_fields = ["category", "project", "customer"]
    def perform_create(self, serializer):
        if role_for(self.request.user) == "technician":
            employee = getattr(self.request.user, "employee", None)
            project = serializer.validated_data.get("project")
            if not project or not Project.objects.filter(pk=project.pk).filter(Q(members=employee) | Q(manager=employee)).exists():
                from rest_framework.exceptions import PermissionDenied
                raise PermissionDenied()
        serializer.save(organization=organization_for(self.request.user), uploaded_by=self.request.user)


class QuoteViewSet(PriceAccessMixin, OrganizationScopedViewSet):
    queryset = Quote.objects.select_related("project", "project__customer").prefetch_related("items")
    serializer_class = QuoteSerializer
    search_fields = ["number", "project__title", "project__customer__company"]
    filterset_fields = ["status", "project"]
    def perform_create(self, serializer):
        org = organization_for(self.request.user)
        serializer.save(organization=org, number=next_number(org, "quote"), created_by=self.request.user)


class InvoiceViewSet(PriceAccessMixin, OrganizationScopedViewSet):
    queryset = Invoice.objects.select_related("project", "project__customer").prefetch_related("items", "payments")
    serializer_class = InvoiceSerializer
    search_fields = ["number", "project__title", "project__customer__company"]
    filterset_fields = ["status", "project"]
    def perform_create(self, serializer):
        org = organization_for(self.request.user)
        serializer.save(organization=org, number=next_number(org, "invoice"), created_by=self.request.user)


class PaymentViewSet(PriceAccessMixin, viewsets.ModelViewSet):
    queryset = Payment.objects.select_related("invoice")
    serializer_class = PaymentSerializer
    permission_classes = [IsAuthenticated]
    def get_queryset(self):
        return self.queryset.filter(invoice__organization=organization_for(self.request.user))
    def perform_create(self, serializer):
        serializer.save(recorded_by=self.request.user)


class ExpenseViewSet(PriceAccessMixin, OrganizationScopedViewSet):
    queryset = Expense.objects.select_related("project")
    serializer_class = ExpenseSerializer
    search_fields = ["supplier", "description", "category"]
    filterset_fields = ["project", "paid", "category"]


class EmailMessageViewSet(OrganizationScopedViewSet):
    queryset = EmailMessage.objects.select_related("project", "customer")
    serializer_class = EmailMessageSerializer
    search_fields = ["subject", "sender", "body_text"]
    filterset_fields = ["direction", "status", "project", "customer"]


class AutomationJobViewSet(OrganizationScopedViewSet):
    queryset = AutomationJob.objects.select_related("project", "requested_by")
    serializer_class = AutomationJobSerializer
    search_fields = ["kind", "project__title"]
    filterset_fields = ["kind", "status", "project"]
    def perform_create(self, serializer):
        serializer.save(organization=organization_for(self.request.user), requested_by=self.request.user)




class SupplierViewSet(PriceAccessMixin, OrganizationScopedViewSet):
    queryset = Supplier.objects.all()
    serializer_class = SupplierSerializer
    search_fields = ["number", "name", "contact_name", "email", "phone"]
    def perform_create(self, serializer):
        org = organization_for(self.request.user)
        serializer.save(organization=org, number=next_number(org, "supplier"))


class PriceSourceViewSet(PriceAccessMixin, OrganizationScopedViewSet):
    queryset = PriceSource.objects.select_related("supplier")
    serializer_class = PriceSourceSerializer
    search_fields = ["name", "original_filename", "supplier__name"]
    filterset_fields = ["kind", "supplier", "active"]
    http_method_names = ["get", "head", "options"]


class PriceItemViewSet(PriceAccessMixin, OrganizationScopedViewSet):
    queryset = PriceItem.objects.select_related("source", "source__supplier")
    serializer_class = PriceItemSerializer
    search_fields = ["code", "description", "category", "source__name"]
    filterset_fields = ["source", "category", "active"]
    http_method_names = ["get", "head", "options"]


router = routers.DefaultRouter()
router.register("suppliers", SupplierViewSet)
router.register("price-sources", PriceSourceViewSet)
router.register("price-items", PriceItemViewSet)
router.register("customers", CustomerViewSet)
router.register("objects", ObjectLocationViewSet)
router.register("employees", EmployeeViewSet)
router.register("projects", ProjectViewSet, basename="api-project")
router.register("tasks", TaskViewSet)
router.register("events", CalendarEventViewSet)
router.register("catalog", CatalogItemViewSet)
router.register("materials", ProjectMaterialViewSet)
router.register("time-entries", TimeEntryViewSet)
router.register("documents", DocumentViewSet)
router.register("quotes", QuoteViewSet)
router.register("invoices", InvoiceViewSet)
router.register("payments", PaymentViewSet)
router.register("expenses", ExpenseViewSet)
router.register("emails", EmailMessageViewSet)
router.register("automation-jobs", AutomationJobViewSet)


class GlobalSearchAPIView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request):
        org = organization_for(request.user)
        q = request.GET.get("q", "").strip()
        if len(q) < 2:
            return Response({"results": []})
        results = []
        projects = Project.objects.filter(organization=org)
        documents = Document.objects.filter(organization=org)
        if role_for(request.user) == "technician":
            employee = getattr(request.user, "employee", None)
            projects = projects.filter(Q(members=employee) | Q(manager=employee)).distinct() if employee else projects.none()
            documents = documents.filter(project__in=projects)
        else:
            for item in Customer.objects.filter(organization=org).filter(Q(company__icontains=q) | Q(first_name__icontains=q) | Q(last_name__icontains=q) | Q(number__icontains=q))[:8]:
                results.append({"type": "Kunde", "title": item.display_name, "subtitle": item.number, "url": f"/list/customers/?q={item.number}"})
        for item in projects.filter(Q(title__icontains=q) | Q(number__icontains=q) | Q(description__icontains=q))[:8]:
            results.append({"type": "Projekt", "title": item.title, "subtitle": item.number, "url": f"/projects/{item.pk}/"})
        for item in documents.filter(Q(title__icontains=q) | Q(extracted_text__icontains=q))[:8]:
            results.append({"type": "Dokument", "title": item.title, "subtitle": item.get_category_display(), "url": f"/list/documents/?q={item.title}"})
        return Response({"results": results[:20]})


class AIChatAPIView(APIView):
    permission_classes = [IsAuthenticated]
    def post(self, request):
        org = organization_for(request.user)
        text = str(request.data.get("message", "")).strip()
        project_id = request.data.get("project_id")
        conversation_id = request.data.get("conversation_id")
        if not text:
            return Response({"error": "Nachricht fehlt."}, status=400)
        project_qs = Project.objects.filter(organization=org)
        if role_for(request.user) == "technician":
            employee = getattr(request.user, "employee", None)
            project_qs = project_qs.filter(Q(members=employee) | Q(manager=employee)).distinct() if employee else project_qs.none()
        project = project_qs.filter(pk=project_id).first() if project_id else None
        if project_id and not project:
            return Response({"error": "Projekt nicht gefunden oder nicht zugewiesen."}, status=404)
        if conversation_id:
            conversation = AIConversation.objects.filter(organization=org, user=request.user, pk=conversation_id).first()
        else:
            conversation = None
        if not conversation:
            conversation = AIConversation.objects.create(organization=org, user=request.user, project=project, title=text[:100])
        AIMessage.objects.create(conversation=conversation, role=AIMessage.Role.USER, content=text)
        history = list(conversation.messages.values("role", "content"))
        context = ""
        if project:
            context = f"Projekt {project.number}: {project.title}\nKunde: {project.customer.display_name}\nBeschreibung: {project.description}\nStatus: {project.get_status_display()}"
        try:
            # KAYI_STORE_AI_CHAT_CONSENT
            from erp.store_views import has_ai_consent
            if not has_ai_consent(request.user):
                return Response({"detail": "Vor der KI-Verarbeitung ist deine ausdrückliche Einwilligung in den Einstellungen erforderlich.", "consent_required": True, "settings_url": "/settings/next/"}, status=428)
            # A_BAU_LEGACY_AI_ADMIN_GUARD 2026-08-12 · generic chat
            from . import ai_role_permissions as _ai_perm
            from django.http import JsonResponse as _AIRoleJsonResponse
            if _ai_perm.role_for(request.user) != _ai_perm.ADMIN:
                return _AIRoleJsonResponse({"detail": "Dieser alte KI-Endpunkt ist nur für Administratoren freigeschaltet. Bitte die rollenbasierte A+Bau KI verwenden."}, status=403)
            output, usage = chat(org, history, context)
        except Exception:
            logger.exception("A+Bau AI chat request failed")
            return Response({"error": "A+Bau AI ist momentan nicht erreichbar. Bitte erneut versuchen."}, status=503)
        message = AIMessage.objects.create(conversation=conversation, role=AIMessage.Role.ASSISTANT, content=output, model="configured", usage=usage)
        return Response({"conversation_id": conversation.pk, "message_id": message.pk, "answer": output})


class RoomMeasurementAnalyzeAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        images = request.FILES.getlist("images")
        if not images:
            return Response({"error": "Bitte mindestens ein Raumfoto aufnehmen."}, status=400)
        if len(images) > 10:
            return Response({"error": "Maximal 10 Aufnahmen pro Analyse."}, status=400)
        total_size = 0
        for image in images:
            total_size += image.size
            if image.size > 12 * 1024 * 1024:
                return Response({"error": f"{image.name}: Aufnahme ist größer als 12 MB."}, status=400)
            if getattr(image, "content_type", "") not in {"image/jpeg", "image/png", "image/webp"}:
                return Response({"error": f"{image.name}: nicht unterstütztes Bildformat."}, status=400)
        if total_size > 45 * 1024 * 1024:
            return Response({"error": "Die Aufnahmen sind zusammen größer als 45 MB."}, status=400)
        calibration = {
            "reference_type": str(request.data.get("reference_type", "")),
            "reference_width_cm": request.data.get("reference_width_cm") or None,
            "reference_height_cm": request.data.get("reference_height_cm") or None,
            "ar_metadata": request.data.get("ar_metadata") or None,
            "capture_sequence": request.data.get("capture_sequence") or None,
        }
        if calibration["reference_type"] == "a4":
            calibration["reference_width_cm"] = 21.0
            calibration["reference_height_cm"] = 29.7
        try:
            # KAYI_STORE_AI_PHOTO_CONSENT
            from erp.store_views import has_ai_consent
            if not has_ai_consent(request.user):
                return Response({"detail": "Vor der KI-Fotoanalyse ist deine ausdrückliche Einwilligung in den Einstellungen erforderlich.", "consent_required": True, "settings_url": "/settings/next/"}, status=428)
            # A_BAU_LEGACY_AI_ADMIN_GUARD 2026-08-12 · photo measurement
            from . import ai_role_permissions as _ai_perm
            from django.http import JsonResponse as _AIRoleJsonResponse
            if _ai_perm.role_for(request.user) != _ai_perm.ADMIN:
                return _AIRoleJsonResponse({"detail": "Dieser alte KI-Endpunkt ist nur für Administratoren freigeschaltet. Bitte die rollenbasierte A+Bau KI verwenden."}, status=403)
            result = analyze_room_photos(organization_for(request.user), images, calibration)
        except Exception:
            logger.exception("A+Bau AI photo measurement failed")
            return Response({"error": "KI-Aufmaß konnte momentan nicht ausgewertet werden. Bitte erneut versuchen."}, status=502)
        result["requires_confirmation"] = True
        result["disclaimer"] = "KI-Werte sind ein prüfpflichtiger Entwurf und ersetzen kein bestätigtes Aufmaß."
        return Response(result)


class NativeRoomScanAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, scan_id=None):
        org = organization_for(request.user)
        queryset = NativeRoomScan.objects.select_related("project", "measurement").filter(organization=org)
        if role_for(request.user) == "technician":
            employee = getattr(request.user, "employee", None)
            queryset = queryset.filter(Q(project__members=employee) | Q(project__manager=employee)).distinct() if employee else queryset.none()
        if scan_id:
            scan = queryset.filter(pk=scan_id).first()
            if not scan:
                return Response({"detail": "Scan nicht gefunden."}, status=404)
            return Response(NativeRoomScanSerializer(scan, context={"request": request}).data)
        project_id = request.query_params.get("project")
        if project_id:
            queryset = queryset.filter(project_id=project_id)
        return Response(NativeRoomScanSerializer(queryset[:100], many=True, context={"request": request}).data)

    def post(self, request, scan_id=None):
        if scan_id:
            return Response({"detail": "POST für diese Adresse nicht unterstützt."}, status=405)
        org = organization_for(request.user)
        if not org:
            return Response({"detail": "Keine Organisation zugeordnet."}, status=400)
        project_qs = Project.objects.filter(organization=org, pk=request.data.get("project_id"))
        if role_for(request.user) == "technician":
            employee = getattr(request.user, "employee", None)
            project_qs = project_qs.filter(Q(members=employee) | Q(manager=employee)).distinct() if employee else project_qs.none()
        project = project_qs.first()
        if not project:
            return Response({"project_id": "Projekt nicht gefunden oder nicht zugewiesen."}, status=404)
        try:
            payload = parse_payload(request.data.get("payload"))
            try:
                client_scan_id = uuid.UUID(str(request.data.get("client_scan_id", "")))
            except (TypeError, ValueError, AttributeError):
                return Response({"client_scan_id": "Gültige UUID erforderlich."}, status=400)
            scan, created = create_native_scan(
                organization=org,
                project=project,
                user=request.user,
                client_scan_id=client_scan_id,
                provider=str(request.data.get("provider", "")),
                payload=payload,
                model_file=request.FILES.get("model_file"),
                preview_file=request.FILES.get("preview_file"),
                app_version=request.data.get("app_version", ""),
                device_model=request.data.get("device_model", ""),
                operating_system=request.data.get("operating_system", ""),
            )
        except Exception as exc:
            from django.core.exceptions import ValidationError
            if isinstance(exc, ValidationError):
                detail = exc.message_dict if hasattr(exc, "message_dict") else {"detail": exc.messages}
                return Response(detail, status=400)
            return Response({"detail": str(exc)}, status=400)
        data = NativeRoomScanSerializer(scan, context={"request": request}).data
        data["created"] = created
        data["requires_confirmation"] = True
        return Response(data, status=201 if created else 200)


class TimeStartAPIView(APIView):
    permission_classes = [IsAuthenticated]
    def post(self, request):
        employee = getattr(request.user, "employee", None)
        if not employee:
            return Response({"error": "Kein Mitarbeiterprofil zugeordnet."}, status=400)
        if TimeEntry.objects.filter(employee=employee, ended_at__isnull=True).exists():
            return Response({"error": "Es läuft bereits eine Zeiterfassung."}, status=409)
        project = Project.objects.filter(
            organization=organization_for(request.user),
            pk=request.data.get("project_id"),
        ).filter(Q(members=employee) | Q(manager=employee)).distinct().first()
        if not project:
            return Response({"error": "Projekt nicht gefunden."}, status=404)
        entry = TimeEntry.objects.create(
            organization=project.organization,
            employee=employee,
            project=project,
            started_at=timezone.now(),
            description=str(request.data.get("description", "")),
            latitude=request.data.get("latitude") or None,
            longitude=request.data.get("longitude") or None,
        )
        return Response(TimeEntrySerializer(entry).data, status=201)


class TimeStopAPIView(APIView):
    permission_classes = [IsAuthenticated]
    def post(self, request):
        employee = getattr(request.user, "employee", None)
        if not employee:
            return Response({"error": "Kein Mitarbeiterprofil zugeordnet."}, status=400)
        entry = TimeEntry.objects.filter(employee=employee, ended_at__isnull=True).first()
        if not entry:
            return Response({"error": "Keine laufende Zeiterfassung."}, status=404)
        entry.ended_at = timezone.now()
        entry.break_minutes = max(0, int(request.data.get("break_minutes", 0) or 0))
        entry.description = str(request.data.get("description", entry.description))
        entry.save(update_fields=["ended_at", "break_minutes", "description", "updated_at"])
        return Response(TimeEntrySerializer(entry).data)


class MobileLoginAPIView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    def post(self, request):
        username = str(request.data.get("username", "")).strip()
        password = str(request.data.get("password", ""))
        user = authenticate(request=request, username=username, password=password)
        if not user or not user.is_active:
            return Response({"detail": "Ungültige Zugangsdaten."}, status=status.HTTP_400_BAD_REQUEST)
        token, _ = Token.objects.get_or_create(user=user)
        profile = getattr(user, "profile", None)
        return Response({"token": token.key, "user": {"id": user.pk, "username": user.username, "name": user.get_full_name(), "role": getattr(profile, "role", ""), "organization": getattr(getattr(profile, "organization", None), "name", "")}})


class MobileLogoutAPIView(APIView):
    permission_classes = [IsAuthenticated]
    def post(self, request):
        Token.objects.filter(user=request.user).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class MobileConfigAPIView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    def get(self, request):
        return Response({
            "version": settings.APP_VERSION,
            "minimum_supported_version": "2.0.0",
            "privacy_url": request.build_absolute_uri("/datenschutz/"),
            "support_url": request.build_absolute_uri("/support/"),
            "account_deletion_url": request.build_absolute_uri("/konto-loeschen/"),
            "terms_url": request.build_absolute_uri("/terms/"),
            "features": {
                "camera": True,
                "room_measurement": True,
                "ai_photo_measurement": True,
                "measurement_requires_human_confirmation": True,
                "native_ar_lidar_capture": True,
                "ios_roomplan_capture": True,
                "ios_roomplan_requires_lidar": True,
                "android_arcore_depth_capture": True,
                "android_arcore_depth_quality": "device_dependent_beta",
                "native_scan_upload_endpoint": request.build_absolute_uri("/api/native-scans/"),
                "geolocation": True,
                "push": True,
                "push_mode": "pwa_browser_notifications",
                "native_push": False,
                "offline_queue": True,
            },
        })


class AccountDeletionAPIView(APIView):
    permission_classes = [IsAuthenticated]
    def post(self, request):
        profile = request.user.profile
        profile.preferences = {**profile.preferences, "deletion_requested_at": timezone.now().isoformat(), "deletion_source": "mobile_api"}
        profile.save(update_fields=["preferences", "updated_at"])
        return Response({"status": "requested"}, status=status.HTTP_202_ACCEPTED)
