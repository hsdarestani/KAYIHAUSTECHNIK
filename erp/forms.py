from decimal import Decimal
from django import forms
from django.db.models import Q
from django.forms import inlineformset_factory
from erp.models import (
    CalendarEvent,
    CatalogItem,
    Customer,
    Document,
    EmailMessage,
    Employee,
    Expense,
    Invoice,
    InvoiceItem,
    ObjectLocation,
    Payment,
    Project,
    ProjectMaterial,
    RoomMeasurement,
    PriceItem,
    PriceSource,
    Supplier,
    Quote,
    QuoteItem,
    Task,
    TimeEntry,
)
from erp.services.documents import validate_upload
from erp.services.pricing import commercial_price_sources, is_material_only_source, preferred_price_source, price_source_matches_job_type


class StyledModelForm(forms.ModelForm):
    """Style fields and constrain every relational choice to the active tenant/user."""

    def __init__(self, *args, organization=None, user=None, **kwargs):
        self.organization = organization
        self.current_user = user
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            if isinstance(field, (forms.ModelChoiceField, forms.ModelMultipleChoiceField)):
                field.widget.attrs.setdefault("data-searchable", "true")
                field.widget.attrs.setdefault("data-search-placeholder", f"{field.label} durchsuchen …")
                model = field.queryset.model
                if organization:
                    if hasattr(model, "organization"):
                        field.queryset = field.queryset.filter(organization=organization)
                    elif model is Payment:
                        field.queryset = field.queryset.filter(invoice__organization=organization)
                    elif model is ProjectMaterial:
                        field.queryset = field.queryset.filter(project__organization=organization)
            if isinstance(field.widget, (forms.CheckboxInput, forms.RadioSelect)):
                continue
            field.widget.attrs.setdefault("class", "form-control")
            if isinstance(field.widget, forms.Textarea):
                field.widget.attrs.setdefault("rows", 4)

        if user and getattr(getattr(user, "profile", None), "role", "") == "technician":
            employee = getattr(user, "employee", None)
            assigned_projects = Project.objects.filter(organization=organization)
            assigned_projects = assigned_projects.filter(
                Q(members=employee) | Q(manager=employee)
            ).distinct() if employee else assigned_projects.none()
            for field in self.fields.values():
                if not isinstance(field, (forms.ModelChoiceField, forms.ModelMultipleChoiceField)):
                    continue
                model = field.queryset.model
                if model is Project:
                    field.queryset = assigned_projects
                elif model is Employee:
                    field.queryset = Employee.objects.filter(pk=getattr(employee, "pk", None))
                elif model is Task:
                    field.queryset = Task.objects.filter(organization=organization, assigned_to=employee)
                elif model is Customer:
                    field.queryset = Customer.objects.none()


class CustomerForm(StyledModelForm):
    class Meta:
        model = Customer
        exclude = ("organization", "number", "tags")


class ObjectLocationForm(StyledModelForm):
    class Meta:
        model = ObjectLocation
        exclude = ("organization",)


class EmployeeForm(StyledModelForm):
    class Meta:
        model = Employee
        exclude = ("organization", "employee_number", "user")


class ProjectForm(StyledModelForm):
    class Meta:
        model = Project
        exclude = ("organization", "number", "archived")
        widgets = {"members": forms.SelectMultiple(attrs={"class": "form-control", "size": 6})}


class TaskForm(StyledModelForm):
    class Meta:
        model = Task
        exclude = ("organization", "completed_at")
        widgets = {"due_at": forms.DateTimeInput(attrs={"type": "datetime-local", "class": "form-control"})}


class CalendarEventForm(StyledModelForm):
    reminders = forms.MultipleChoiceField(
        label="Erinnerungen / Push",
        required=False,
        choices=[("0", "Sofort"), ("15", "15 Minuten vorher"), ("60", "1 Stunde vorher"), ("1440", "1 Tag vorher"), ("10080", "1 Woche vorher")],
        widget=forms.CheckboxSelectMultiple,
    )

    class Meta:
        model = CalendarEvent
        exclude = ("organization", "created_by", "reminder_minutes")
        widgets = {
            "starts_at": forms.DateTimeInput(attrs={"type": "datetime-local", "class": "form-control"}),
            "ends_at": forms.DateTimeInput(attrs={"type": "datetime-local", "class": "form-control"}),
            "attendees": forms.SelectMultiple(attrs={"class": "form-control", "size": 6}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            self.fields["reminders"].initial = [str(v) for v in self.instance.reminder_minutes]

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.reminder_minutes = [int(v) for v in self.cleaned_data.get("reminders", [])]
        if commit:
            instance.save()
            self.save_m2m()
        return instance


class CatalogItemForm(StyledModelForm):
    class Meta:
        model = CatalogItem
        exclude = ("organization", "external_codes")


class ProjectMaterialForm(StyledModelForm):
    class Meta:
        model = ProjectMaterial
        exclude = ()


class TimeEntryForm(StyledModelForm):
    class Meta:
        model = TimeEntry
        exclude = ("organization", "approved", "approved_by")
        widgets = {
            "started_at": forms.DateTimeInput(attrs={"type": "datetime-local", "class": "form-control"}),
            "ended_at": forms.DateTimeInput(attrs={"type": "datetime-local", "class": "form-control"}),
        }


class DocumentForm(StyledModelForm):
    class Meta:
        model = Document
        fields = ("project", "customer", "title", "category", "file")

    def clean_file(self):
        upload = self.cleaned_data["file"]
        validate_upload(upload)
        return upload


class QuoteForm(StyledModelForm):
    class Meta:
        model = Quote
        exclude = ("organization", "number", "created_by", "sent_at")
        widgets = {
            "issue_date": forms.DateInput(attrs={"type": "date", "class": "form-control"}),
            "valid_until": forms.DateInput(attrs={"type": "date", "class": "form-control"}),
        }


class QuoteItemForm(StyledModelForm):
    class Meta:
        model = QuoteItem
        exclude = ("quote", "ai_generated", "approved")


QuoteItemFormSet = inlineformset_factory(Quote, QuoteItem, form=QuoteItemForm, extra=3, can_delete=True)


class InvoiceForm(StyledModelForm):
    class Meta:
        model = Invoice
        exclude = ("organization", "number", "created_by", "sent_at")
        widgets = {
            "issue_date": forms.DateInput(attrs={"type": "date", "class": "form-control"}),
            "due_date": forms.DateInput(attrs={"type": "date", "class": "form-control"}),
            "service_date": forms.DateInput(attrs={"type": "date", "class": "form-control"}),
        }


class InvoiceItemForm(StyledModelForm):
    class Meta:
        model = InvoiceItem
        exclude = ("invoice", "ai_generated", "approved")


InvoiceItemFormSet = inlineformset_factory(Invoice, InvoiceItem, form=InvoiceItemForm, extra=3, can_delete=True)


class PaymentForm(StyledModelForm):
    class Meta:
        model = Payment
        exclude = ("recorded_by",)
        widgets = {"paid_at": forms.DateInput(attrs={"type": "date", "class": "form-control"})}


class ExpenseForm(StyledModelForm):
    class Meta:
        model = Expense
        exclude = ("organization",)
        widgets = {"expense_date": forms.DateInput(attrs={"type": "date", "class": "form-control"})}


class EmailDraftForm(StyledModelForm):
    recipients_text = forms.CharField(label="Empfänger", help_text="Mehrere Adressen mit Komma trennen.")
    cc_text = forms.CharField(label="CC", required=False)

    class Meta:
        model = EmailMessage
        fields = ("project", "customer", "subject", "body_text", "body_html")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            self.fields["recipients_text"].initial = ", ".join(self.instance.recipients)
            self.fields["cc_text"].initial = ", ".join(self.instance.cc)

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.recipients = [v.strip() for v in self.cleaned_data["recipients_text"].split(",") if v.strip()]
        instance.cc = [v.strip() for v in self.cleaned_data["cc_text"].split(",") if v.strip()]
        if commit:
            instance.save()
        return instance


class SupplierForm(StyledModelForm):
    class Meta:
        model = Supplier
        exclude = ("organization", "number")


class PriceSourceUploadForm(forms.Form):
    file = forms.FileField(label="Preis- oder Katalogdatei")

    def clean_file(self):
        upload = self.cleaned_data["file"]
        suffix = upload.name.lower().rsplit(".", 1)[-1] if "." in upload.name else ""
        if suffix not in {"xlsx", "xlsm", "csv", "pdf", "003", "p86"}:
            raise forms.ValidationError("Unterstützt werden XLSX, CSV, PDF, 003 und P86.")
        if upload.size > 50 * 1024 * 1024:
            raise forms.ValidationError("Datei ist größer als 50 MB.")
        return upload


class ProjectWizardForm(forms.Form):
    PROJECT_TYPES = [
        ("bathroom", "Badsanierung"),
        ("renovation", "Komplettsanierung"),
        ("new_build", "Neubau"),
        ("heating", "Heizungstausch"),
        ("water_damage", "Wasserschaden"),
        ("service", "Kundendienst"),
    ]
    project_type = forms.ChoiceField(label="Projektart", choices=PROJECT_TYPES, initial="bathroom")
    job_type = forms.ChoiceField(label="Auftragsart", choices=Project.JobType.choices, initial=Project.JobType.PRIVATE, required=False)
    price_source = forms.ModelChoiceField(label="Passende Preisliste", queryset=PriceSource.objects.none(), required=False)
    customer = forms.ModelChoiceField(label="Kunde", queryset=Customer.objects.none())
    object_location = forms.ModelChoiceField(label="Baustellenobjekt", queryset=ObjectLocation.objects.none(), required=False)
    title = forms.CharField(label="Projektname", max_length=220)
    description = forms.CharField(label="Projektbeschreibung", widget=forms.Textarea(attrs={"rows": 4}), required=False)
    priority = forms.ChoiceField(label="Priorität", choices=Project.Priority.choices, initial=Project.Priority.NORMAL)
    manager = forms.ModelChoiceField(label="Projektleitung", queryset=Employee.objects.none(), required=False)
    members = forms.ModelMultipleChoiceField(label="Mitarbeiter", queryset=Employee.objects.none(), required=False)
    new_employee_name = forms.CharField(label="Neuen Mitarbeiter direkt hinzufügen", max_length=200, required=False, help_text="Vor- und Nachname; wird dem Projekt zugeordnet.")
    new_employee_email = forms.EmailField(label="E-Mail des neuen Mitarbeiters", required=False)
    planned_start = forms.DateField(label="Geplanter Beginn", widget=forms.DateInput(attrs={"type": "date"}), required=False)
    planned_end = forms.DateField(label="Fertigstellung", widget=forms.DateInput(attrs={"type": "date"}), required=False)
    budget = forms.DecimalField(label="Budget", min_value=0, decimal_places=2, required=False)
    room_name = forms.CharField(label="Raum", max_length=160, initial="Badezimmer", required=False)
    length_m = forms.DecimalField(label="Länge (m)", min_value=0.01, decimal_places=3, required=False)
    width_m = forms.DecimalField(label="Breite (m)", min_value=0.01, decimal_places=3, required=False)
    height_m = forms.DecimalField(label="Höhe (m)", min_value=0.01, decimal_places=3, required=False)
    deductions_area_m2 = forms.DecimalField(label="Abzüge Tür/Fenster (m²)", min_value=0, decimal_places=3, initial=0, required=False)
    waste_percent = forms.DecimalField(label="Verschnitt (%)", min_value=0, decimal_places=2, initial=10, required=False)
    measurement_method = forms.ChoiceField(label="Aufmaßmethode", choices=RoomMeasurement.Method.choices, initial=RoomMeasurement.Method.MANUAL)
    reference_type = forms.ChoiceField(label="Skalenreferenz", choices=[("", "Keine"), ("a4", "A4-Blatt 21 × 29,7 cm"), ("tile", "Bekannte Fliese"), ("custom", "Eigene Referenz")], required=False)
    reference_width_cm = forms.DecimalField(label="Referenzbreite (cm)", min_value=0.1, decimal_places=2, required=False)
    reference_height_cm = forms.DecimalField(label="Referenzhöhe (cm)", min_value=0.1, decimal_places=2, required=False)
    services = forms.ModelMultipleChoiceField(label="Leistungen", queryset=CatalogItem.objects.none(), required=False)
    price_items = forms.ModelMultipleChoiceField(label="Preislistenpositionen", queryset=PriceItem.objects.none(), required=False)
    materials = forms.ModelMultipleChoiceField(label="Material", queryset=CatalogItem.objects.none(), required=False)

    def __init__(self, *args, organization=None, **kwargs):
        self.organization = organization
        super().__init__(*args, **kwargs)
        if organization:
            self.fields["customer"].queryset = Customer.objects.filter(organization=organization, active=True)
            self.fields["object_location"].queryset = ObjectLocation.objects.filter(organization=organization).select_related("customer")
            self.fields["manager"].queryset = Employee.objects.filter(organization=organization, active=True)
            self.fields["members"].queryset = Employee.objects.filter(organization=organization, active=True)
            self.fields["services"].queryset = CatalogItem.objects.filter(organization=organization, active=True, kind=CatalogItem.Kind.SERVICE)
            self.fields["price_items"].queryset = PriceItem.objects.filter(
                organization=organization, active=True, source__in=commercial_price_sources(organization)
            )
            self.fields["materials"].queryset = CatalogItem.objects.filter(organization=organization, active=True, kind=CatalogItem.Kind.MATERIAL)
            self.fields["price_source"].queryset = commercial_price_sources(organization)
            self.fields["price_source"].widget.attrs.update({"data-searchable": "true", "data-search-placeholder": "B&O, Privat oder Leistungskatalog suchen …"})
        for field in self.fields.values():
            if isinstance(field, (forms.ModelChoiceField, forms.ModelMultipleChoiceField)):
                field.widget.attrs.setdefault("data-searchable", "true")
                field.widget.attrs.setdefault("data-search-placeholder", f"{field.label} durchsuchen …")
            if isinstance(field.widget, (forms.CheckboxInput, forms.RadioSelect, forms.CheckboxSelectMultiple)):
                continue
            field.widget.attrs.setdefault("class", "form-control")

    def clean(self):
        data = super().clean()
        data["job_type"] = data.get("job_type") or Project.JobType.PRIVATE
        dimensions = [data.get("length_m"), data.get("width_m"), data.get("height_m")]
        if any(value is not None for value in dimensions) and not all(value is not None for value in dimensions):
            raise forms.ValidationError("Für ein vollständiges Aufmaß bitte Länge, Breite und Höhe angeben.")
        if data.get("reference_type") == "a4":
            data["reference_width_cm"] = Decimal("21.0")
            data["reference_height_cm"] = Decimal("29.7")
        if data.get("reference_type") in {"tile", "custom"} and not data.get("reference_width_cm"):
            self.add_error("reference_width_cm", "Bitte die bekannte Referenzbreite angeben.")
        source = data.get("price_source")
        if data.get("job_type") == Project.JobType.INSURANCE and not source:
            source = preferred_price_source(self.organization, Project.JobType.INSURANCE) if self.organization else None
            if source:
                data["price_source"] = source
            else:
                self.add_error("price_source", "Keine passende B&O-/Versicherungspreisliste mit gültigen Preisen gefunden.")
        if source and is_material_only_source(source):
            self.add_error("price_source", "JOKA und andere Lieferantenlisten gehören zum Materialeinkauf, nicht zur Angebotskalkulation.")
        elif source and not price_source_matches_job_type(source, data.get("job_type")):
            self.add_error("price_source", "Diese Preisliste passt nicht zur gewählten Auftragsart.")
        selected_price_items = data.get("price_items")
        if selected_price_items and selected_price_items.exists():
            if not source:
                self.add_error("price_source", "Für Preislistenpositionen bitte zuerst eine Preisliste wählen.")
            elif selected_price_items.exclude(source=source).exists():
                self.add_error("price_items", "Mindestens eine Position gehört nicht zur ausgewählten Preisliste.")
        return data


class RoomMeasurementForm(StyledModelForm):
    class Meta:
        model = RoomMeasurement
        fields = (
            "name", "method", "length_m", "width_m", "height_m",
            "deductions_area_m2", "waste_percent", "reference_type",
            "reference_width_cm", "reference_height_cm",
        )
        labels = {
            "name": "Raumname",
            "method": "Aufmaßmethode",
            "length_m": "Länge (m)",
            "width_m": "Breite (m)",
            "height_m": "Höhe (m)",
            "deductions_area_m2": "Abzugsfläche (m²)",
            "waste_percent": "Verschnitt (%)",
            "reference_type": "Referenzobjekt",
            "reference_width_cm": "Referenzbreite (cm)",
            "reference_height_cm": "Referenzhöhe (cm)",
        }
