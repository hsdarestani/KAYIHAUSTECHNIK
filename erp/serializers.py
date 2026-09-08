from rest_framework import serializers
from erp.services.documents import validate_upload
from erp.services.permissions import can_view_prices
from erp.models import (
    AutomationJob, CalendarEvent, CatalogItem, Customer, Document, EmailMessage,
    Employee, Expense, Invoice, InvoiceItem, ObjectLocation, Payment, PriceItem, PriceSource, Project,
    ProjectMaterial, Quote, QuoteItem, Supplier, Task, TimeEntry, NativeRoomScan,
)


class CustomerSerializer(serializers.ModelSerializer):
    display_name = serializers.ReadOnlyField()
    class Meta:
        model = Customer
        exclude = ("organization",)
        read_only_fields = ("number",)


class ObjectLocationSerializer(serializers.ModelSerializer):
    class Meta:
        model = ObjectLocation
        exclude = ("organization",)


class EmployeeSerializer(serializers.ModelSerializer):
    full_name = serializers.ReadOnlyField()
    class Meta:
        model = Employee
        exclude = ("organization",)
        read_only_fields = ("employee_number",)

    def get_fields(self):
        fields = super().get_fields()
        request = self.context.get("request")
        if request and not can_view_prices(request.user):
            for name in ("hourly_cost", "hourly_rate", "can_view_prices"):
                fields.pop(name, None)
        return fields


class ProjectSerializer(serializers.ModelSerializer):
    customer_name = serializers.CharField(source="customer.display_name", read_only=True)
    ui_url = serializers.SerializerMethodField()

    def get_ui_url(self, obj):
        request = self.context.get("request")
        path = f"/projects/{obj.pk}/"
        return request.build_absolute_uri(path) if request else path

    class Meta:
        model = Project
        exclude = ("organization",)
        read_only_fields = ("number",)

    def get_fields(self):
        fields = super().get_fields()
        request = self.context.get("request")
        if request and not can_view_prices(request.user):
            for name in ("budget", "price_source"):
                fields.pop(name, None)
        return fields


class TaskSerializer(serializers.ModelSerializer):
    class Meta:
        model = Task
        exclude = ("organization",)

    def get_fields(self):
        fields = super().get_fields()
        request = self.context.get("request")
        if request and getattr(getattr(request.user, "profile", None), "role", "") == "technician":
            for name in ("project", "assigned_to", "priority", "due_at"):
                if name in fields:
                    fields[name].read_only = True
        return fields


class CalendarEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = CalendarEvent
        exclude = ("organization", "created_by")


class CatalogItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = CatalogItem
        exclude = ("organization",)


class ProjectMaterialSerializer(serializers.ModelSerializer):
    total_price = serializers.ReadOnlyField()
    class Meta:
        model = ProjectMaterial
        fields = "__all__"


class TimeEntrySerializer(serializers.ModelSerializer):
    duration_minutes = serializers.ReadOnlyField()
    duration_hours = serializers.ReadOnlyField()
    class Meta:
        model = TimeEntry
        exclude = ("organization", "approved_by")


class DocumentSerializer(serializers.ModelSerializer):
    def validate_file(self, value):
        validate_upload(value)
        return value

    class Meta:
        model = Document
        exclude = ("organization", "uploaded_by")
        read_only_fields = ("mime_type", "size", "sha256", "extracted_text", "version")


class QuoteItemSerializer(serializers.ModelSerializer):
    net_total = serializers.ReadOnlyField()
    class Meta:
        model = QuoteItem
        fields = "__all__"


class QuoteSerializer(serializers.ModelSerializer):
    items = QuoteItemSerializer(many=True, read_only=True)
    net_total = serializers.ReadOnlyField()
    tax_total = serializers.ReadOnlyField()
    gross_total = serializers.ReadOnlyField()
    class Meta:
        model = Quote
        exclude = ("organization", "created_by")
        read_only_fields = ("number",)


class InvoiceItemSerializer(serializers.ModelSerializer):
    net_total = serializers.ReadOnlyField()
    class Meta:
        model = InvoiceItem
        fields = "__all__"


class InvoiceSerializer(serializers.ModelSerializer):
    items = InvoiceItemSerializer(many=True, read_only=True)
    net_total = serializers.ReadOnlyField()
    tax_total = serializers.ReadOnlyField()
    gross_total = serializers.ReadOnlyField()
    paid_total = serializers.ReadOnlyField()
    outstanding_total = serializers.ReadOnlyField()
    class Meta:
        model = Invoice
        exclude = ("organization", "created_by")
        read_only_fields = ("number",)


class PaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        exclude = ("recorded_by",)


class ExpenseSerializer(serializers.ModelSerializer):
    amount_gross = serializers.ReadOnlyField()
    class Meta:
        model = Expense
        exclude = ("organization",)


class EmailMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = EmailMessage
        exclude = ("organization", "approved_by")
        read_only_fields = ("message_id", "sent_at")


class AutomationJobSerializer(serializers.ModelSerializer):
    class Meta:
        model = AutomationJob
        exclude = ("organization", "approved_by")
        read_only_fields = ("status", "output_data", "error", "approved_at")


class SupplierSerializer(serializers.ModelSerializer):
    class Meta:
        model = Supplier
        exclude = ("organization",)
        read_only_fields = ("number",)


class PriceSourceSerializer(serializers.ModelSerializer):
    item_count = serializers.IntegerField(source="items.count", read_only=True)
    class Meta:
        model = PriceSource
        exclude = ("organization",)
        read_only_fields = ("sha256", "imported_at", "imported_rows", "import_summary")


class PriceItemSerializer(serializers.ModelSerializer):
    source_name = serializers.CharField(source="source.name", read_only=True)
    class Meta:
        model = PriceItem
        exclude = ("organization",)


class NativeRoomScanSerializer(serializers.ModelSerializer):
    measurement_id = serializers.IntegerField(source="measurement.pk", read_only=True)
    measurement_status = serializers.CharField(source="measurement.status", read_only=True)
    model_url = serializers.SerializerMethodField()
    preview_url = serializers.SerializerMethodField()

    class Meta:
        model = NativeRoomScan
        fields = (
            "id", "project", "measurement_id", "measurement_status", "client_scan_id", "provider", "status",
            "room_name", "app_version", "device_model", "operating_system", "confidence", "normalized_payload",
            "model_url", "preview_url", "warnings", "created_at", "updated_at",
        )
        read_only_fields = fields

    def _url(self, field):
        if not field:
            return None
        request = self.context.get("request")
        return request.build_absolute_uri(field.url) if request else field.url

    def get_model_url(self, obj):
        return self._url(obj.model_file)

    def get_preview_url(self, obj):
        return self._url(obj.preview_file)
