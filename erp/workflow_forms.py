from __future__ import annotations

from django import forms
from django.contrib.auth.models import User

from erp.models import (
    BugReport,
    ChangeOrder,
    CustomerSurvey,
    Employee,
    PurchaseOrder,
    SiteReport,
    WorkMedia,
)


class StyledFormMixin:
    def _style(self):
        for field in self.fields.values():
            if isinstance(field.widget, (forms.CheckboxInput, forms.RadioSelect)):
                continue
            field.widget.attrs.setdefault("class", "form-control")
            if isinstance(field.widget, forms.Textarea):
                field.widget.attrs.setdefault("rows", 4)


class EmployeeAccountForm(StyledFormMixin, forms.ModelForm):
    create_account = forms.BooleanField(label="Eigenes App-Konto anlegen", required=False, initial=True)
    username = forms.CharField(label="Benutzername", required=False)
    password = forms.CharField(label="Startpasswort", required=False, widget=forms.PasswordInput)
    role = forms.ChoiceField(label="App-Rolle", choices=[
        ("technician", "Monteur – nur eigene Arbeit, keine Preise"),
        ("project_manager", "Projektleitung"),
        ("office", "Büro"),
        ("accounting", "Buchhaltung"),
    ], initial="technician", required=False)

    class Meta:
        model = Employee
        fields = ("first_name", "last_name", "email", "phone", "trade", "active", "color", "can_view_prices")

    def __init__(self, *args, organization=None, **kwargs):
        self.organization = organization
        super().__init__(*args, **kwargs)
        self._style()

    def clean(self):
        data = super().clean()
        if data.get("create_account"):
            if data.get("password") and len(data.get("password", "")) < 10:
                self.add_error("password", "Mindestens 10 Zeichen verwenden oder leer lassen, um eine Einladung vorzubereiten.")
            if data.get("username") and User.objects.filter(username=data.get("username", "")).exists():
                self.add_error("username", "Benutzername ist bereits vergeben.")
        if data.get("role") == "technician":
            data["can_view_prices"] = False
        return data


class ChangeOrderForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = ChangeOrder
        fields = ("title", "description", "amount_net", "tax_rate", "status")

    def __init__(self, *args, can_view_prices=True, **kwargs):
        super().__init__(*args, **kwargs)
        if not can_view_prices:
            self.fields.pop("amount_net", None)
            self.fields.pop("tax_rate", None)
            self.fields.pop("status", None)
        self._style()


class WorkMediaForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = WorkMedia
        fields = ("stage", "kind", "title", "caption", "file", "visible_to_customer")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._style()

    def clean_file(self):
        upload = self.cleaned_data["file"]
        allowed = {
            "image/jpeg", "image/png", "image/webp",
            "video/mp4", "video/webm", "video/quicktime",
            "audio/mpeg", "audio/mp4", "audio/webm", "audio/wav",
        }
        if getattr(upload, "content_type", "") not in allowed:
            raise forms.ValidationError("Unterstützt werden Foto, MP4/WebM-Video und Audio.")
        if upload.size > 120 * 1024 * 1024:
            raise forms.ValidationError("Datei ist größer als 120 MB.")
        return upload


class SiteReportForm(StyledFormMixin, forms.ModelForm):
    execution_satisfied = forms.TypedChoiceField(
        label="Mit der Ausführung zufrieden", required=False,
        choices=[("", "Nicht angegeben"), ("1", "Ja"), ("0", "Nein")],
        coerce=lambda value: value == "1", empty_value=None, widget=forms.RadioSelect,
    )
    employee_punctual = forms.TypedChoiceField(
        label="Servicemitarbeiter pünktlich", required=False,
        choices=[("", "Nicht angegeben"), ("1", "Ja"), ("0", "Nein")],
        coerce=lambda value: value == "1", empty_value=None, widget=forms.RadioSelect,
    )

    class Meta:
        model = SiteReport
        fields = (
            "title", "report_text", "voice_file", "execution_satisfied",
            "employee_punctual", "repair_duration", "tenant_fault",
        )
        labels = {
            "title": "Titel",
            "report_text": "Bericht / Notizen vor Ort",
            "voice_file": "Sprachnotiz",
            "repair_duration": "Ausführungsdauer der Reparatur",
            "tenant_fault": "Mieterverschulden",
        }
        widgets = {
            "report_text": forms.Textarea(attrs={"rows": 5, "placeholder": "Arbeiten, Besonderheiten und Abweichungen dokumentieren …"}),
            "repair_duration": forms.TextInput(attrs={"placeholder": "z. B. 1 Std. 45 Min."}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._style()


class PurchaseOrderForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = PurchaseOrder
        fields = ("project", "supplier", "status", "ordered_at", "expected_at", "total_net", "external_reference", "notes")
        widgets = {
            "ordered_at": forms.DateInput(attrs={"type": "date"}),
            "expected_at": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, organization=None, **kwargs):
        super().__init__(*args, **kwargs)
        if organization:
            self.fields["project"].queryset = self.fields["project"].queryset.filter(organization=organization)
            self.fields["supplier"].queryset = self.fields["supplier"].queryset.filter(organization=organization)
        self._style()


class BugReportForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = BugReport
        fields = ("project", "title", "description", "page_url", "screenshot")

    def __init__(self, *args, organization=None, **kwargs):
        super().__init__(*args, **kwargs)
        if organization:
            self.fields["project"].queryset = self.fields["project"].queryset.filter(organization=organization)
        self._style()


class SurveyForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = CustomerSurvey
        fields = (
            "rating_quality", "rating_punctuality", "rating_team",
            "rating_cleanliness", "comment", "allow_public_review",
        )
        widgets = {
            "rating_quality": forms.RadioSelect(choices=[(i, str(i)) for i in range(1, 6)]),
            "rating_punctuality": forms.RadioSelect(choices=[(i, str(i)) for i in range(1, 6)]),
            "rating_team": forms.RadioSelect(choices=[(i, str(i)) for i in range(1, 6)]),
            "rating_cleanliness": forms.RadioSelect(choices=[(i, str(i)) for i in range(1, 6)]),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._style()
