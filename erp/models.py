from __future__ import annotations

import hashlib
import mimetypes
import uuid
from decimal import Decimal
from pathlib import Path

from django.conf import settings
from django.contrib.auth.models import User
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Sum
from django.utils import timezone


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class Organization(TimeStampedModel):
    name = models.CharField(max_length=180, default="A+Bau")
    legal_name = models.CharField(max_length=220, blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=60, blank=True)
    address = models.TextField(blank=True)
    tax_id = models.CharField(max_length=80, blank=True)
    iban = models.CharField(max_length=60, blank=True)
    logo = models.ImageField(upload_to="organization/", blank=True)
    settings = models.JSONField(default=dict, blank=True)

    def __str__(self) -> str:
        return self.name


class UserProfile(TimeStampedModel):
    class Role(models.TextChoices):
        ADMIN = "admin", "Administrator"
        OFFICE = "office", "Büro"
        PROJECT_MANAGER = "project_manager", "Projektleitung"
        TECHNICIAN = "technician", "Monteur"
        ACCOUNTING = "accounting", "Buchhaltung"
        READONLY = "readonly", "Nur Lesen"

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    organization = models.ForeignKey(Organization, on_delete=models.SET_NULL, null=True, blank=True)
    role = models.CharField(max_length=32, choices=Role.choices, default=Role.OFFICE)
    phone = models.CharField(max_length=60, blank=True)
    avatar = models.ImageField(upload_to="avatars/", blank=True)
    color = models.CharField(max_length=20, default="#c6a15b")
    is_mobile_worker = models.BooleanField(default=False)
    preferences = models.JSONField(default=dict, blank=True)

    def __str__(self) -> str:
        return f"{self.user.get_full_name() or self.user.username} · {self.get_role_display()}"


class Customer(TimeStampedModel):
    class Type(models.TextChoices):
        PRIVATE = "private", "Privatkunde"
        BUSINESS = "business", "Geschäftskunde"
        INSURANCE = "insurance", "Versicherung"
        PROPERTY_MANAGER = "property_manager", "Hausverwaltung"

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="customers")
    number = models.CharField(max_length=30)
    type = models.CharField(max_length=32, choices=Type.choices, default=Type.PRIVATE)
    company = models.CharField(max_length=180, blank=True)
    salutation = models.CharField(max_length=30, blank=True)
    first_name = models.CharField(max_length=100, blank=True)
    last_name = models.CharField(max_length=100, blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=60, blank=True)
    mobile = models.CharField(max_length=60, blank=True)
    street = models.CharField(max_length=180, blank=True)
    postal_code = models.CharField(max_length=20, blank=True)
    city = models.CharField(max_length=120, blank=True)
    country = models.CharField(max_length=2, default="DE")
    vat_id = models.CharField(max_length=80, blank=True)
    debtor_number = models.CharField(max_length=80, blank=True)
    routing_id = models.CharField(max_length=80, blank=True)
    supplier_id = models.CharField(max_length=80, blank=True)
    notes = models.TextField(blank=True)
    tags = models.JSONField(default=list, blank=True)
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ["company", "last_name", "first_name"]
        constraints = [models.UniqueConstraint(fields=["organization", "number"], name="unique_customer_number")]

    @property
    def display_name(self) -> str:
        return self.company or " ".join(filter(None, [self.first_name, self.last_name])) or self.number

    def __str__(self) -> str:
        return f"{self.number} · {self.display_name}"


class ObjectLocation(TimeStampedModel):
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="object_locations")
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name="object_locations")
    name = models.CharField(max_length=180, default="Objekt")
    street = models.CharField(max_length=180)
    postal_code = models.CharField(max_length=20)
    city = models.CharField(max_length=120)
    floor = models.CharField(max_length=60, blank=True)
    access_notes = models.TextField(blank=True)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)

    def __str__(self) -> str:
        return f"{self.name} · {self.street}, {self.city}"


class Employee(TimeStampedModel):
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="employees")
    user = models.OneToOneField(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="employee")
    employee_number = models.CharField(max_length=30)
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=60, blank=True)
    trade = models.CharField(max_length=120, blank=True)
    hourly_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    hourly_rate = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    active = models.BooleanField(default=True)
    color = models.CharField(max_length=20, default="#2f80ed")
    can_view_prices = models.BooleanField(default=False)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["organization", "employee_number"], name="unique_employee_number")]

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()

    def __str__(self) -> str:
        return self.full_name


class Project(TimeStampedModel):
    class JobType(models.TextChoices):
        PRIVATE = "private", "Privatauftrag"
        INSURANCE = "insurance", "Versicherung / B&O"

    class Status(models.TextChoices):
        INQUIRY = "inquiry", "Anfrage"
        PLANNING = "planning", "Planung"
        QUOTED = "quoted", "Angebot"
        CONFIRMED = "confirmed", "Beauftragt"
        IN_PROGRESS = "in_progress", "In Ausführung"
        WAITING = "waiting", "Wartet"
        REVIEW = "review", "Abnahme"
        INVOICED = "invoiced", "Abgerechnet"
        COMPLETED = "completed", "Abgeschlossen"
        CANCELLED = "cancelled", "Storniert"

    class Priority(models.TextChoices):
        LOW = "low", "Niedrig"
        NORMAL = "normal", "Normal"
        HIGH = "high", "Hoch"
        URGENT = "urgent", "Dringend"

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="projects")
    job_type = models.CharField(max_length=20, choices=JobType.choices, default=JobType.PRIVATE)
    price_source = models.ForeignKey("PriceSource", on_delete=models.SET_NULL, null=True, blank=True, related_name="projects")
    number = models.CharField(max_length=30)
    title = models.CharField(max_length=220)
    customer = models.ForeignKey(Customer, on_delete=models.PROTECT, related_name="projects")
    object_location = models.ForeignKey(ObjectLocation, on_delete=models.SET_NULL, null=True, blank=True, related_name="projects")
    manager = models.ForeignKey(Employee, on_delete=models.SET_NULL, null=True, blank=True, related_name="managed_projects")
    members = models.ManyToManyField(Employee, related_name="projects", blank=True)
    status = models.CharField(max_length=24, choices=Status.choices, default=Status.INQUIRY)
    priority = models.CharField(max_length=16, choices=Priority.choices, default=Priority.NORMAL)
    description = models.TextField(blank=True)
    internal_notes = models.TextField(blank=True)
    external_reference = models.CharField(max_length=100, blank=True)
    insurance_claim_number = models.CharField(max_length=100, blank=True)
    planned_start = models.DateField(null=True, blank=True)
    planned_end = models.DateField(null=True, blank=True)
    actual_start = models.DateField(null=True, blank=True)
    actual_end = models.DateField(null=True, blank=True)
    budget = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    progress = models.PositiveSmallIntegerField(default=0)
    archived = models.BooleanField(default=False)

    class Meta:
        ordering = ["-created_at"]
        constraints = [models.UniqueConstraint(fields=["organization", "number"], name="unique_project_number")]
        indexes = [models.Index(fields=["organization", "status"]), models.Index(fields=["planned_start", "planned_end"])]

    def __str__(self) -> str:
        return f"{self.number} · {self.title}"


class Task(TimeStampedModel):
    class Status(models.TextChoices):
        OPEN = "open", "Offen"
        IN_PROGRESS = "in_progress", "In Arbeit"
        BLOCKED = "blocked", "Blockiert"
        DONE = "done", "Erledigt"
        CANCELLED = "cancelled", "Storniert"

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="tasks")
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="tasks", null=True, blank=True)
    title = models.CharField(max_length=220)
    description = models.TextField(blank=True)
    assigned_to = models.ForeignKey(Employee, on_delete=models.SET_NULL, null=True, blank=True, related_name="tasks")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.OPEN)
    priority = models.CharField(max_length=16, choices=Project.Priority.choices, default=Project.Priority.NORMAL)
    due_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["status", "due_at", "-created_at"]

    def __str__(self) -> str:
        return self.title


class CalendarEvent(TimeStampedModel):
    class Type(models.TextChoices):
        APPOINTMENT = "appointment", "Termin"
        SITE = "site", "Baustelle"
        INSPECTION = "inspection", "Besichtigung"
        DELIVERY = "delivery", "Lieferung"
        INTERNAL = "internal", "Intern"

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="events")
    customer = models.ForeignKey(
        "Customer",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="calendar_events",
    )

    recurrence_series = models.UUIDField(null=True, blank=True, db_index=True, editable=False)
    recurrence_rule = models.CharField(
        max_length=16,
        choices=[
            ("none", "Keine Wiederholung"),
            ("daily", "Täglich"),
            ("weekdays", "Werktags"),
            ("weekly", "Wöchentlich"),
            ("biweekly", "Alle zwei Wochen"),
            ("monthly", "Monatlich"),
            ("half_yearly", "Halbjährlich"),
            ("yearly", "Jährlich"),
            ("custom", "Benutzerdefiniert"),
        ],
        default="none",
        editable=False,
    )
    recurrence_index = models.PositiveIntegerField(default=0, editable=False)
    recurrence_interval = models.PositiveSmallIntegerField(default=1, editable=False)
    recurrence_unit = models.CharField(
        max_length=12,
        choices=[
            ("day", "Tag(e)"),
            ("weekday", "Werktag(e)"),
            ("week", "Woche(n)"),
            ("month", "Monat(e)"),
            ("year", "Jahr(e)"),
        ],
        default="day",
        editable=False,
    )
    recurrence_until = models.DateField(null=True, blank=True, editable=False)

    source_quote = models.ForeignKey(
        "erp.Quote", null=True, blank=True, on_delete=models.SET_NULL, related_name="generated_appointments"
    )
    work_report = models.TextField(blank=True, default="")

    project = models.ForeignKey(Project, on_delete=models.CASCADE, null=True, blank=True, related_name="events")
    title = models.CharField(max_length=220)
    type = models.CharField(max_length=20, choices=Type.choices, default=Type.APPOINTMENT)
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField()
    all_day = models.BooleanField(default=False)
    location = models.CharField(max_length=240, blank=True)
    notes = models.TextField(blank=True)
    reminder_minutes = models.JSONField(default=list, blank=True)
    attendees = models.ManyToManyField(Employee, related_name="events", blank=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name="created_events")

    class Meta:
        ordering = ["starts_at"]

    def __str__(self) -> str:
        return self.title


class CatalogItem(TimeStampedModel):
    class Kind(models.TextChoices):
        SERVICE = "service", "Leistung"
        MATERIAL = "material", "Material"
        TRAVEL = "travel", "Anfahrt"
        DISPOSAL = "disposal", "Entsorgung"
        FREE = "free", "Freiposition"

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="catalog_items")
    code = models.CharField(max_length=80)
    name = models.CharField(max_length=240)
    description = models.TextField(blank=True)
    kind = models.CharField(max_length=20, choices=Kind.choices, default=Kind.SERVICE)
    unit = models.CharField(max_length=30, default="Stk.")
    purchase_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    sales_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    tax_rate = models.DecimalField(max_digits=5, decimal_places=2, default=19)
    supplier = models.CharField(max_length=160, blank=True)
    external_codes = models.JSONField(default=dict, blank=True)
    active = models.BooleanField(default=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["organization", "code"], name="unique_catalog_code")]
        ordering = ["code"]

    def __str__(self) -> str:
        return f"{self.code} · {self.name}"


class ProjectMaterial(TimeStampedModel):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="materials")
    catalog_item = models.ForeignKey(CatalogItem, on_delete=models.SET_NULL, null=True, blank=True)
    name = models.CharField(max_length=240)
    quantity = models.DecimalField(max_digits=12, decimal_places=3, default=1)
    unit = models.CharField(max_length=30, default="Stk.")
    unit_cost = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    ordered = models.BooleanField(default=False)
    delivered = models.BooleanField(default=False)
    notes = models.TextField(blank=True)

    @property
    def total_price(self) -> Decimal:
        return self.quantity * self.unit_price


class TimeEntry(TimeStampedModel):
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="time_entries")
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name="time_entries")
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="time_entries")
    task = models.ForeignKey(Task, on_delete=models.SET_NULL, null=True, blank=True, related_name="time_entries")
    started_at = models.DateTimeField()
    ended_at = models.DateTimeField(null=True, blank=True)
    break_minutes = models.PositiveIntegerField(default=0)
    description = models.TextField(blank=True)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    approved = models.BooleanField(default=False)
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="approved_time_entries")

    class Meta:
        ordering = ["-started_at"]

    @property
    def duration_minutes(self) -> int:
        end = self.ended_at or timezone.now()
        return max(0, int((end - self.started_at).total_seconds() / 60) - self.break_minutes)

    @property
    def duration_hours(self) -> Decimal:
        return (Decimal(self.duration_minutes) / Decimal(60)).quantize(Decimal("0.01"))


class Document(TimeStampedModel):
    class Category(models.TextChoices):
        PHOTO = "photo", "Foto"
        QUOTE = "quote", "Angebot"
        INVOICE = "invoice", "Rechnung"
        REPORT = "report", "Arbeitsbericht"
        CONTRACT = "contract", "Vertrag"
        DELIVERY = "delivery", "Lieferschein"
        OTHER = "other", "Sonstiges"

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="documents")
    project = models.ForeignKey(Project, on_delete=models.CASCADE, null=True, blank=True, related_name="documents")
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, null=True, blank=True, related_name="documents")
    title = models.CharField(max_length=240)
    category = models.CharField(max_length=20, choices=Category.choices, default=Category.OTHER)
    file = models.FileField(upload_to="documents/%Y/%m/")
    mime_type = models.CharField(max_length=120, blank=True)
    size = models.PositiveBigIntegerField(default=0)
    sha256 = models.CharField(max_length=64, blank=True)
    uploaded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name="uploaded_documents")
    extracted_text = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    version = models.PositiveIntegerField(default=1)

    def save(self, *args, **kwargs):
        if self.file and hasattr(self.file, "size"):
            self.size = self.file.size
            self.mime_type = mimetypes.guess_type(self.file.name)[0] or "application/octet-stream"
            pos = self.file.tell() if hasattr(self.file, "tell") else None
            digest = hashlib.sha256()
            for chunk in self.file.chunks():
                digest.update(chunk)
            self.sha256 = digest.hexdigest()
            if pos is not None:
                self.file.seek(pos)
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return self.title


class RoomMeasurement(TimeStampedModel):
    class Method(models.TextChoices):
        MANUAL = "manual", "Manuell"
        AI_PHOTO = "ai_photo", "KI-Fotoaufmaß"
        AR_LIDAR = "ar_lidar", "AR / LiDAR"

    class Status(models.TextChoices):
        DRAFT = "draft", "Entwurf"
        ANALYZING = "analyzing", "Analyse läuft"
        REVIEW = "review", "Zu prüfen"
        CONFIRMED = "confirmed", "Bestätigt"

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="room_measurements")
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="room_measurements")
    name = models.CharField(max_length=160, default="Raum")
    method = models.CharField(max_length=20, choices=Method.choices, default=Method.MANUAL)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    length_m = models.DecimalField(max_digits=8, decimal_places=3, null=True, blank=True, validators=[MinValueValidator(Decimal("0.01"))])
    width_m = models.DecimalField(max_digits=8, decimal_places=3, null=True, blank=True, validators=[MinValueValidator(Decimal("0.01"))])
    height_m = models.DecimalField(max_digits=8, decimal_places=3, null=True, blank=True, validators=[MinValueValidator(Decimal("0.01"))])
    deductions_area_m2 = models.DecimalField(max_digits=10, decimal_places=3, default=0, validators=[MinValueValidator(Decimal("0"))])
    waste_percent = models.DecimalField(max_digits=5, decimal_places=2, default=10, validators=[MinValueValidator(Decimal("0"))])
    confidence = models.DecimalField(max_digits=5, decimal_places=4, default=0, validators=[MinValueValidator(Decimal("0")), MaxValueValidator(Decimal("1"))])
    reference_type = models.CharField(max_length=40, blank=True)
    reference_width_cm = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    reference_height_cm = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    ai_summary = models.TextField(blank=True)
    ai_warnings = models.JSONField(default=list, blank=True)
    ai_payload = models.JSONField(default=dict, blank=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="created_room_measurements")
    confirmed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="confirmed_room_measurements")
    confirmed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["project", "created_at"]
        indexes = [models.Index(fields=["organization", "status"]), models.Index(fields=["project", "created_at"])]

    @property
    def floor_area_m2(self):
        if self.length_m is None or self.width_m is None:
            return None
        return (self.length_m * self.width_m).quantize(Decimal("0.01"))

    @property
    def perimeter_m(self):
        if self.length_m is None or self.width_m is None:
            return None
        return (Decimal("2") * (self.length_m + self.width_m)).quantize(Decimal("0.01"))

    @property
    def gross_wall_area_m2(self):
        if self.perimeter_m is None or self.height_m is None:
            return None
        return (self.perimeter_m * self.height_m).quantize(Decimal("0.01"))

    @property
    def wall_area_m2(self):
        if self.gross_wall_area_m2 is None:
            return None
        return max(Decimal("0"), self.gross_wall_area_m2 - self.deductions_area_m2).quantize(Decimal("0.01"))

    @property
    def floor_with_waste_m2(self):
        if self.floor_area_m2 is None:
            return None
        return (self.floor_area_m2 * (Decimal("1") + self.waste_percent / Decimal("100"))).quantize(Decimal("0.01"))

    @property
    def wall_with_waste_m2(self):
        if self.wall_area_m2 is None:
            return None
        return (self.wall_area_m2 * (Decimal("1") + self.waste_percent / Decimal("100"))).quantize(Decimal("0.01"))

    def __str__(self) -> str:
        return f"{self.project.number} · {self.name}"


class MeasurementCapture(TimeStampedModel):
    class Kind(models.TextChoices):
        DOORWAY = "doorway", "Von der Tür"
        WALL_1 = "wall_1", "Wand 1"
        WALL_2 = "wall_2", "Wand 2"
        WALL_3 = "wall_3", "Wand 3"
        WALL_4 = "wall_4", "Wand 4"
        FLOOR = "floor", "Boden"
        CEILING = "ceiling", "Decke"
        CONNECTIONS = "connections", "Anschlüsse"
        WINDOWS = "windows", "Fenster / Türen"
        DAMAGE = "damage", "Schäden"
        OTHER = "other", "Weitere Aufnahme"

    measurement = models.ForeignKey(RoomMeasurement, on_delete=models.CASCADE, related_name="captures")
    kind = models.CharField(max_length=24, choices=Kind.choices, default=Kind.OTHER)
    image = models.ImageField(upload_to="measurements/%Y/%m/")
    mime_type = models.CharField(max_length=120, blank=True)
    size = models.PositiveBigIntegerField(default=0)
    sha256 = models.CharField(max_length=64, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    annotations = models.JSONField(default=list, blank=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="measurement_captures")

    class Meta:
        ordering = ["created_at"]

    def save(self, *args, **kwargs):
        if self.image and hasattr(self.image, "size"):
            self.size = self.image.size
            self.mime_type = mimetypes.guess_type(self.image.name)[0] or "application/octet-stream"
            pos = self.image.tell() if hasattr(self.image, "tell") else None
            digest = hashlib.sha256()
            for chunk in self.image.chunks():
                digest.update(chunk)
            self.sha256 = digest.hexdigest()
            if pos is not None:
                self.image.seek(pos)
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.measurement} · {self.get_kind_display()}"


class NativeRoomScan(TimeStampedModel):
    class Provider(models.TextChoices):
        APPLE_ROOMPLAN = "apple_roomplan", "Apple RoomPlan / LiDAR"
        ANDROID_ARCORE_DEPTH = "android_arcore_depth", "Android ARCore Depth"

    class Status(models.TextChoices):
        UPLOADING = "uploading", "Upload läuft"
        REVIEW = "review", "Zu prüfen"
        CONFIRMED = "confirmed", "Bestätigt"
        REJECTED = "rejected", "Verworfen"
        FAILED = "failed", "Fehlgeschlagen"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="native_room_scans")
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="native_room_scans")
    measurement = models.OneToOneField(RoomMeasurement, on_delete=models.SET_NULL, null=True, blank=True, related_name="native_scan")
    client_scan_id = models.UUIDField()
    provider = models.CharField(max_length=32, choices=Provider.choices)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.REVIEW)
    room_name = models.CharField(max_length=160, default="Raum")
    app_version = models.CharField(max_length=40, blank=True)
    device_model = models.CharField(max_length=120, blank=True)
    operating_system = models.CharField(max_length=80, blank=True)
    confidence = models.DecimalField(max_digits=5, decimal_places=4, default=0, validators=[MinValueValidator(Decimal("0")), MaxValueValidator(Decimal("1"))])
    raw_payload = models.JSONField(default=dict, blank=True)
    normalized_payload = models.JSONField(default=dict, blank=True)
    model_file = models.FileField(upload_to="native-scans/%Y/%m/", blank=True)
    model_mime_type = models.CharField(max_length=120, blank=True)
    model_size = models.PositiveBigIntegerField(default=0)
    model_sha256 = models.CharField(max_length=64, blank=True)
    preview_file = models.FileField(upload_to="native-scans/previews/%Y/%m/", blank=True)
    warnings = models.JSONField(default=list, blank=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="created_native_room_scans")
    confirmed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="confirmed_native_room_scans")
    confirmed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["organization", "client_scan_id"], name="erp_native_scan_org_client_uniq"),
        ]
        indexes = [
            models.Index(fields=["organization", "status"]),
            models.Index(fields=["project", "created_at"]),
        ]

    def save(self, *args, **kwargs):
        if self.model_file and hasattr(self.model_file, "size"):
            self.model_size = self.model_file.size
            self.model_mime_type = mimetypes.guess_type(self.model_file.name)[0] or "application/octet-stream"
            pos = self.model_file.tell() if hasattr(self.model_file, "tell") else None
            digest = hashlib.sha256()
            for chunk in self.model_file.chunks():
                digest.update(chunk)
            self.model_sha256 = digest.hexdigest()
            if pos is not None:
                self.model_file.seek(pos)
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.project.number} · {self.room_name} · {self.get_provider_display()}"


class Quote(TimeStampedModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "Entwurf"
        REVIEW = "review", "Prüfung"
        SENT = "sent", "Gesendet"
        ACCEPTED = "accepted", "Angenommen"
        REJECTED = "rejected", "Abgelehnt"
        EXPIRED = "expired", "Abgelaufen"

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="quotes")
    source_event = models.ForeignKey(
        "erp.CalendarEvent", null=True, blank=True, on_delete=models.SET_NULL, related_name="generated_quotes"
    )

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="quotes")
    number = models.CharField(max_length=40)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    issue_date = models.DateField(default=timezone.localdate)
    valid_until = models.DateField(null=True, blank=True)
    intro_text = models.TextField(blank=True)
    outro_text = models.TextField(blank=True)
    discount_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name="created_quotes")
    sent_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["organization", "number"], name="unique_quote_number")]
        ordering = ["-issue_date", "-created_at"]

    @property
    def net_total(self) -> Decimal:
        base = self.items.aggregate(v=Sum(models.F("quantity") * models.F("unit_price"), output_field=models.DecimalField()))["v"] or Decimal("0")
        return base * (Decimal("1") - self.discount_percent / Decimal("100"))

    @property
    def tax_total(self) -> Decimal:
        discount_factor = Decimal("1") - self.discount_percent / Decimal("100")
        return sum(
            (item.net_total * discount_factor * item.tax_rate / Decimal("100") for item in self.items.all()),
            Decimal("0"),
        )

    @property
    def gross_total(self) -> Decimal:
        return self.net_total + self.tax_total

    def __str__(self) -> str:
        return self.number


class QuoteItem(TimeStampedModel):
    quote = models.ForeignKey(Quote, on_delete=models.CASCADE, related_name="items")
    position = models.PositiveIntegerField(default=1)
    catalog_item = models.ForeignKey(CatalogItem, on_delete=models.SET_NULL, null=True, blank=True)
    code = models.CharField(max_length=80, blank=True)
    description = models.TextField()
    quantity = models.DecimalField(max_digits=12, decimal_places=3, default=1, validators=[MinValueValidator(Decimal("0"))])
    unit = models.CharField(max_length=30, default="Stk.")
    unit_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    tax_rate = models.DecimalField(max_digits=5, decimal_places=2, default=19)
    ai_generated = models.BooleanField(default=False)
    approved = models.BooleanField(default=True)

    class Meta:
        ordering = ["position"]

    @property
    def net_total(self) -> Decimal:
        return self.quantity * self.unit_price


class Invoice(TimeStampedModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "Entwurf"
        REVIEW = "review", "Prüfung"
        SENT = "sent", "Gesendet"
        PARTIAL = "partial", "Teilbezahlt"
        PAID = "paid", "Bezahlt"
        OVERDUE = "overdue", "Überfällig"
        CANCELLED = "cancelled", "Storniert"

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="invoices")
    source_event = models.ForeignKey(
        "erp.CalendarEvent", null=True, blank=True, on_delete=models.SET_NULL, related_name="generated_invoices"
    )

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="invoices")
    quote = models.ForeignKey(Quote, on_delete=models.SET_NULL, null=True, blank=True, related_name="invoices")
    number = models.CharField(max_length=40)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    issue_date = models.DateField(default=timezone.localdate)
    due_date = models.DateField()
    service_date = models.DateField(null=True, blank=True)
    intro_text = models.TextField(blank=True)
    outro_text = models.TextField(blank=True)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name="created_invoices")
    sent_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["organization", "number"], name="unique_invoice_number")]
        ordering = ["-issue_date", "-created_at"]

    @property
    def net_total(self) -> Decimal:
        return sum((item.net_total for item in self.items.all()), Decimal("0"))

    @property
    def tax_total(self) -> Decimal:
        return sum((item.net_total * item.tax_rate / Decimal("100") for item in self.items.all()), Decimal("0"))

    @property
    def gross_total(self) -> Decimal:
        return self.net_total + self.tax_total

    @property
    def paid_total(self) -> Decimal:
        return self.payments.aggregate(v=Sum("amount"))["v"] or Decimal("0")

    @property
    def outstanding_total(self) -> Decimal:
        return max(Decimal("0"), self.gross_total - self.paid_total)

    def refresh_status(self) -> None:
        outstanding = self.outstanding_total
        if outstanding <= 0 and self.gross_total > 0:
            self.status = self.Status.PAID
        elif self.paid_total > 0:
            self.status = self.Status.PARTIAL
        elif self.due_date < timezone.localdate() and self.status not in {self.Status.DRAFT, self.Status.CANCELLED}:
            self.status = self.Status.OVERDUE
        self.save(update_fields=["status", "updated_at"])

    def __str__(self) -> str:
        return self.number


class InvoiceItem(TimeStampedModel):
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name="items")
    position = models.PositiveIntegerField(default=1)
    catalog_item = models.ForeignKey(CatalogItem, on_delete=models.SET_NULL, null=True, blank=True)
    code = models.CharField(max_length=80, blank=True)
    description = models.TextField()
    quantity = models.DecimalField(max_digits=12, decimal_places=3, default=1)
    unit = models.CharField(max_length=30, default="Stk.")
    unit_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    tax_rate = models.DecimalField(max_digits=5, decimal_places=2, default=19)
    ai_generated = models.BooleanField(default=False)
    approved = models.BooleanField(default=True)

    class Meta:
        ordering = ["position"]

    @property
    def net_total(self) -> Decimal:
        return self.quantity * self.unit_price


class RoomModelRevision(TimeStampedModel):
    """Versioned, editable parametric room model derived from a scan or manual measurement."""

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="room_model_revisions")
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="room_model_revisions")
    measurement = models.ForeignKey(RoomMeasurement, on_delete=models.CASCADE, related_name="model_revisions")
    source_scan = models.ForeignKey(NativeRoomScan, on_delete=models.SET_NULL, null=True, blank=True, related_name="model_revisions")
    revision = models.PositiveIntegerField()
    label = models.CharField(max_length=160, blank=True)
    state = models.JSONField(default=dict)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="created_room_model_revisions")

    class Meta:
        ordering = ["-revision", "-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["measurement", "revision"], name="erp_room_model_measurement_revision_uniq"),
        ]
        indexes = [
            models.Index(fields=["organization", "measurement", "revision"], name="erp_roommod_organiz_0cfda5_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.measurement} · Modell v{self.revision}"


class Payment(TimeStampedModel):
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name="payments")
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    paid_at = models.DateField(default=timezone.localdate)
    method = models.CharField(max_length=80, default="Überweisung")
    reference = models.CharField(max_length=180, blank=True)
    recorded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self.invoice.refresh_status()


class Expense(TimeStampedModel):
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="expenses")
    project = models.ForeignKey(Project, on_delete=models.SET_NULL, null=True, blank=True, related_name="expenses")
    supplier = models.CharField(max_length=180)
    description = models.CharField(max_length=240)
    amount_net = models.DecimalField(max_digits=14, decimal_places=2)
    tax_rate = models.DecimalField(max_digits=5, decimal_places=2, default=19)
    expense_date = models.DateField(default=timezone.localdate)
    document = models.ForeignKey(Document, on_delete=models.SET_NULL, null=True, blank=True)
    category = models.CharField(max_length=100, blank=True)
    paid = models.BooleanField(default=False)

    @property
    def amount_gross(self) -> Decimal:
        return self.amount_net * (Decimal("1") + self.tax_rate / Decimal("100"))


class EmailMessage(TimeStampedModel):
    class Direction(models.TextChoices):
        INBOUND = "inbound", "Eingang"
        OUTBOUND = "outbound", "Ausgang"
        DRAFT = "draft", "Entwurf"

    class Status(models.TextChoices):
        NEW = "new", "Neu"
        CLASSIFIED = "classified", "Klassifiziert"
        REVIEW = "review", "Prüfung"
        APPROVED = "approved", "Freigegeben"
        SENT = "sent", "Gesendet"
        FAILED = "failed", "Fehler"

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="emails")
    project = models.ForeignKey(Project, on_delete=models.SET_NULL, null=True, blank=True, related_name="emails")
    customer = models.ForeignKey(Customer, on_delete=models.SET_NULL, null=True, blank=True, related_name="emails")
    message_id = models.CharField(max_length=255, blank=True, db_index=True)
    direction = models.CharField(max_length=20, choices=Direction.choices)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.NEW)
    sender = models.EmailField(blank=True)
    recipients = models.JSONField(default=list)
    cc = models.JSONField(default=list)
    subject = models.CharField(max_length=300, blank=True)
    body_text = models.TextField(blank=True)
    body_html = models.TextField(blank=True)
    received_at = models.DateTimeField(null=True, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    classification = models.JSONField(default=dict, blank=True)
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="approved_emails")

    class Meta:
        ordering = ["-received_at", "-created_at"]


class AIConversation(TimeStampedModel):
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="ai_conversations")
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="ai_conversations")
    project = models.ForeignKey(Project, on_delete=models.SET_NULL, null=True, blank=True, related_name="ai_conversations")
    title = models.CharField(max_length=220, default="Neue Unterhaltung")


class AIMessage(TimeStampedModel):
    class Role(models.TextChoices):
        USER = "user", "Benutzer"
        ASSISTANT = "assistant", "Assistent"
        SYSTEM = "system", "System"

    conversation = models.ForeignKey(AIConversation, on_delete=models.CASCADE, related_name="messages")
    role = models.CharField(max_length=20, choices=Role.choices)
    content = models.TextField()
    model = models.CharField(max_length=80, blank=True)
    usage = models.JSONField(default=dict, blank=True)
    structured_data = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["created_at"]


class IntegrationConfig(TimeStampedModel):
    class Provider(models.TextChoices):
        GMX = "gmx", "GMX"
        TOOLTIME = "tooltime", "ToolTime"
        BUNDO = "bundo", "B&O Portal"
        OPENAI = "openai", "OpenAI"
        DATEV = "datev", "DATEV"
        MARKETPLACE = "marketplace", "Material-Marktplatz"
        WEBPUSH = "webpush", "PWA Push"

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="integrations")
    provider = models.CharField(max_length=30, choices=Provider.choices)
    enabled = models.BooleanField(default=False)
    config = models.JSONField(default=dict, blank=True)
    last_sync_at = models.DateTimeField(null=True, blank=True)
    last_error = models.TextField(blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["organization", "provider"], name="unique_integration_provider")]


class AutomationJob(TimeStampedModel):
    class Status(models.TextChoices):
        PENDING = "pending", "Wartet"
        RUNNING = "running", "Läuft"
        REVIEW = "review", "Prüfung erforderlich"
        APPROVED = "approved", "Freigegeben"
        COMPLETED = "completed", "Abgeschlossen"
        FAILED = "failed", "Fehlgeschlagen"
        CANCELLED = "cancelled", "Abgebrochen"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="automation_jobs")
    project = models.ForeignKey(Project, on_delete=models.SET_NULL, null=True, blank=True, related_name="automation_jobs")
    kind = models.CharField(max_length=80)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    input_data = models.JSONField(default=dict, blank=True)
    output_data = models.JSONField(default=dict, blank=True)
    error = models.TextField(blank=True)
    requested_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name="automation_jobs")
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="approved_automation_jobs")
    approved_at = models.DateTimeField(null=True, blank=True)


class Notification(TimeStampedModel):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="notifications")
    title = models.CharField(max_length=220)
    message = models.TextField(blank=True)
    level = models.CharField(max_length=20, default="info")
    url = models.CharField(max_length=300, blank=True)
    read_at = models.DateTimeField(null=True, blank=True)
    scheduled_for = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]


class ActivityLog(models.Model):
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="activities", null=True, blank=True)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    verb = models.CharField(max_length=120)
    entity_type = models.CharField(max_length=100, blank=True)
    entity_id = models.CharField(max_length=100, blank=True)
    description = models.TextField(blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["organization", "created_at"]), models.Index(fields=["entity_type", "entity_id"])]


class Sequence(TimeStampedModel):
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="sequences")
    key = models.CharField(max_length=40)
    year = models.PositiveIntegerField()
    value = models.PositiveIntegerField(default=0)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["organization", "key", "year"], name="unique_sequence")]


class Supplier(TimeStampedModel):
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="suppliers")
    number = models.CharField(max_length=40)
    name = models.CharField(max_length=220)
    contact_name = models.CharField(max_length=180, blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=60, blank=True)
    website = models.URLField(blank=True)
    street = models.CharField(max_length=180, blank=True)
    postal_code = models.CharField(max_length=20, blank=True)
    city = models.CharField(max_length=120, blank=True)
    notes = models.TextField(blank=True)
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]
        constraints = [models.UniqueConstraint(fields=["organization", "number"], name="unique_supplier_number")]

    def __str__(self) -> str:
        return self.name


class PriceSource(TimeStampedModel):
    class Kind(models.TextChoices):
        CATALOG = "catalog", "Leistungskatalog"
        CUSTOMER = "customer", "Kundenpreisliste"
        INSURANCE = "insurance", "Versicherung"
        SUPPLIER = "supplier", "Lieferant"
        PARTNER = "partner", "Geschäftspartner"
        MAPPING = "mapping", "Mapping"
        OTHER = "other", "Sonstiges"

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="price_sources")
    supplier = models.ForeignKey(Supplier, on_delete=models.SET_NULL, null=True, blank=True, related_name="price_sources")
    name = models.CharField(max_length=240)
    kind = models.CharField(max_length=24, choices=Kind.choices, default=Kind.OTHER)
    original_filename = models.CharField(max_length=255)
    raw_file = models.FileField(upload_to="price_sources/raw/%Y/%m/", blank=True)
    sha256 = models.CharField(max_length=64)
    mime_type = models.CharField(max_length=120, blank=True)
    currency = models.CharField(max_length=3, default="EUR")
    valid_from = models.DateField(null=True, blank=True)
    valid_until = models.DateField(null=True, blank=True)
    imported_at = models.DateTimeField(null=True, blank=True)
    imported_rows = models.PositiveIntegerField(default=0)
    import_summary = models.JSONField(default=dict, blank=True)
    active = models.BooleanField(default=True)
    share_enabled = models.BooleanField(default=False)
    share_token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)

    class Meta:
        ordering = ["name", "-created_at"]
        constraints = [models.UniqueConstraint(fields=["organization", "sha256"], name="unique_price_source_hash")]

    def __str__(self) -> str:
        return self.name


class PriceItem(TimeStampedModel):
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="price_items")
    source = models.ForeignKey(PriceSource, on_delete=models.CASCADE, related_name="items")
    code = models.CharField(max_length=120, blank=True)
    description = models.TextField()
    category = models.CharField(max_length=180, blank=True)
    unit = models.CharField(max_length=40, blank=True)
    purchase_price = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    sales_price = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    tax_rate = models.DecimalField(max_digits=5, decimal_places=2, default=19)
    external_data = models.JSONField(default=dict, blank=True)
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ["source", "code", "description"]
        indexes = [
            models.Index(fields=["organization", "code"], name="erp_priceit_organiz_d491f7_idx"),
            models.Index(fields=["organization", "source"], name="erp_priceit_organiz_a4c8db_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.code} · {self.description[:80]}" if self.code else self.description[:100]


class WorkMedia(TimeStampedModel):
    class Stage(models.TextChoices):
        BEFORE = "before", "Vorher"
        DURING = "during", "Während"
        AFTER = "after", "Nachher"
        DAMAGE = "damage", "Schaden"
        OTHER = "other", "Sonstiges"

    class Kind(models.TextChoices):
        PHOTO = "photo", "Foto"
        VIDEO = "video", "Video"
        AUDIO = "audio", "Audio"

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="work_media")
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="work_media")
    employee = models.ForeignKey(Employee, on_delete=models.SET_NULL, null=True, blank=True, related_name="work_media")
    kind = models.CharField(max_length=20, choices=Kind.choices, default=Kind.PHOTO)
    stage = models.CharField(max_length=20, choices=Stage.choices, default=Stage.DURING)
    title = models.CharField(max_length=220, blank=True)
    caption = models.TextField(blank=True)
    file = models.FileField(upload_to="work_media/%Y/%m/")
    mime_type = models.CharField(max_length=120, blank=True)
    size = models.PositiveBigIntegerField(default=0)
    annotations = models.JSONField(default=list, blank=True)
    visible_to_customer = models.BooleanField(default=False)
    uploaded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="uploaded_work_media")

    class Meta:
        ordering = ["stage", "created_at"]

    def save(self, *args, **kwargs):
        if self.file and hasattr(self.file, "size"):
            self.size = self.file.size
            self.mime_type = mimetypes.guess_type(self.file.name)[0] or "application/octet-stream"
        super().save(*args, **kwargs)


class ChangeOrder(TimeStampedModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "Entwurf"
        SENT = "sent", "Zur Unterschrift"
        ACCEPTED = "accepted", "Bestätigt"
        REJECTED = "rejected", "Abgelehnt"
        INVOICED = "invoiced", "Abgerechnet"

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="change_orders")
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="change_orders")
    number = models.CharField(max_length=40)
    title = models.CharField(max_length=240)
    description = models.TextField()
    amount_net = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    tax_rate = models.DecimalField(max_digits=5, decimal_places=2, default=19)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    public_token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    requested_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name="requested_change_orders")
    signed_name = models.CharField(max_length=180, blank=True)
    signature_data = models.TextField(blank=True)
    signed_at = models.DateTimeField(null=True, blank=True)
    customer_comment = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [models.UniqueConstraint(fields=["organization", "number"], name="unique_change_order_number")]

    @property
    def amount_gross(self):
        return self.amount_net * (Decimal("1") + self.tax_rate / Decimal("100"))


class ChangeOrderAttachment(TimeStampedModel):
    change_order = models.ForeignKey(ChangeOrder, on_delete=models.CASCADE, related_name="attachments")
    file = models.FileField(upload_to="change_orders/%Y/%m/")
    title = models.CharField(max_length=220, blank=True)
    uploaded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)


class SiteReport(TimeStampedModel):
    class Kind(models.TextChoices):
        GENERIC = "generic", "Vor-Ort-Bericht"
        BANDO = "bando", "B&O Leistungsnachweis / Regiebericht"

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="site_reports")
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="site_reports")
    employee = models.ForeignKey(Employee, on_delete=models.SET_NULL, null=True, blank=True, related_name="site_reports")
    kind = models.CharField(max_length=20, choices=Kind.choices, default=Kind.GENERIC)
    title = models.CharField(max_length=220, default="Vor-Ort-Bericht")
    report_text = models.TextField(blank=True)
    voice_file = models.FileField(upload_to="site_reports/audio/%Y/%m/", blank=True)
    execution_satisfied = models.BooleanField(null=True, blank=True)
    employee_punctual = models.BooleanField(null=True, blank=True)
    repair_duration = models.CharField(max_length=120, blank=True)
    tenant_fault = models.BooleanField(default=False)
    service_lines = models.JSONField(default=list, blank=True)
    material_lines = models.JSONField(default=list, blank=True)
    customer_signature = models.TextField(blank=True)
    signed_name = models.CharField(max_length=180, blank=True)
    signed_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name="created_site_reports")

    class Meta:
        ordering = ["-created_at"]


class CustomerSurvey(TimeStampedModel):
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="surveys")
    project = models.OneToOneField(Project, on_delete=models.CASCADE, related_name="survey")
    token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    sent_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    rating_quality = models.PositiveSmallIntegerField(null=True, blank=True, validators=[MinValueValidator(1), MaxValueValidator(5)])
    rating_punctuality = models.PositiveSmallIntegerField(null=True, blank=True, validators=[MinValueValidator(1), MaxValueValidator(5)])
    rating_team = models.PositiveSmallIntegerField(null=True, blank=True, validators=[MinValueValidator(1), MaxValueValidator(5)])
    rating_cleanliness = models.PositiveSmallIntegerField(null=True, blank=True, validators=[MinValueValidator(1), MaxValueValidator(5)])
    comment = models.TextField(blank=True)
    allow_public_review = models.BooleanField(default=False)


class CustomerPortalAccess(TimeStampedModel):
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="customer_portals")
    project = models.OneToOneField(Project, on_delete=models.CASCADE, related_name="customer_portal")
    token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    active = models.BooleanField(default=True)
    last_viewed_at = models.DateTimeField(null=True, blank=True)

    def __str__(self) -> str:
        return f"Kundenportal · {self.project}"


class PurchaseOrder(TimeStampedModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "Entwurf"
        ORDERED = "ordered", "Bestellt"
        RECEIVED = "received", "Geliefert"
        INVOICED = "invoiced", "Lieferantenrechnung"
        CANCELLED = "cancelled", "Storniert"

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="purchase_orders")
    project = models.ForeignKey(Project, on_delete=models.SET_NULL, null=True, blank=True, related_name="purchase_orders")
    supplier = models.ForeignKey(Supplier, on_delete=models.SET_NULL, null=True, blank=True, related_name="purchase_orders")
    number = models.CharField(max_length=40)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    ordered_at = models.DateField(null=True, blank=True)
    expected_at = models.DateField(null=True, blank=True)
    total_net = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    external_reference = models.CharField(max_length=180, blank=True)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name="created_purchase_orders")

    class Meta:
        ordering = ["-created_at"]
        constraints = [models.UniqueConstraint(fields=["organization", "number"], name="unique_purchase_order_number")]


class PurchaseDocument(TimeStampedModel):
    class Kind(models.TextChoices):
        ORDER = "order", "Bestellung"
        RECEIPT = "receipt", "Bestellbestätigung"
        DELIVERY = "delivery", "Lieferschein"
        INVOICE = "invoice", "Lieferantenrechnung"

    purchase_order = models.ForeignKey(PurchaseOrder, on_delete=models.CASCADE, related_name="documents")
    kind = models.CharField(max_length=20, choices=Kind.choices)
    file = models.FileField(upload_to="purchase_documents/%Y/%m/")
    title = models.CharField(max_length=220, blank=True)
    uploaded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)


class BugReport(TimeStampedModel):
    class Status(models.TextChoices):
        OPEN = "open", "Offen"
        REVIEW = "review", "Prüfung"
        RESOLVED = "resolved", "Gelöst"

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="bug_reports")
    project = models.ForeignKey(Project, on_delete=models.SET_NULL, null=True, blank=True, related_name="bug_reports")
    title = models.CharField(max_length=220)
    description = models.TextField()
    page_url = models.CharField(max_length=500, blank=True)
    screenshot = models.ImageField(upload_to="bug_reports/%Y/%m/", blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.OPEN)
    reported_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name="bug_reports")

    class Meta:
        ordering = ["-created_at"]

# A+Bau commercial extension; kept separate to avoid rewriting the stable ERP schema.
from .ab_bau_commercial import CommercialDocumentSettings, CommercialItemMeta

# A+Bau pre-project approval extension.
from .project_approval import ProjectApprovalFlow

# German invoice compliance sidecar models.
from .invoice_compliance import CustomerInvoiceProfile, InvoiceAuditEvent, InvoiceComplianceRecord, InvoiceNumberSequence

# ToolTime-Funktionsparität für kaufmännische Dokumente.
from .tooltime_parity_finance import ToolTimeCommercialProfile, ToolTimeDocumentMeta, ToolTimeNumberSequence, ToolTimeTextTemplate, ToolTimeDunningRecord, ToolTimePositionAsset, ToolTimeDatevAccount, ToolTimeMixedSubitem, ToolTimeDocumentDelivery, ToolTimePaymentTransaction, ToolTimePayout


class AppointmentServiceGroup(models.Model):
    organization = models.ForeignKey("erp.Organization", on_delete=models.CASCADE, related_name="appointment_service_groups")
    event = models.ForeignKey("erp.CalendarEvent", on_delete=models.CASCADE, related_name="service_groups")
    title = models.CharField(max_length=220, blank=True, default="")
    position = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["position", "id"]


class AppointmentServiceItem(models.Model):
    KINDS = [
        ("labour", "Arbeitszeit"),
        ("material", "Material"),
        ("mixed", "Mischposition"),
        ("other", "Sonstiges"),
    ]
    organization = models.ForeignKey("erp.Organization", on_delete=models.CASCADE, related_name="appointment_service_items")
    event = models.ForeignKey("erp.CalendarEvent", on_delete=models.CASCADE, related_name="service_items")
    group = models.ForeignKey("erp.AppointmentServiceGroup", null=True, blank=True, on_delete=models.CASCADE, related_name="items")
    catalog_item = models.ForeignKey("erp.CatalogItem", null=True, blank=True, on_delete=models.SET_NULL, related_name="appointment_uses")
    source_quote_item = models.ForeignKey("erp.QuoteItem", null=True, blank=True, on_delete=models.SET_NULL, related_name="appointment_copies")
    position = models.PositiveIntegerField(default=1)
    kind = models.CharField(max_length=16, choices=KINDS, default="other")
    code = models.CharField(max_length=80, blank=True)
    description = models.TextField()
    quantity = models.DecimalField(max_digits=12, decimal_places=3, default=1)
    unit = models.CharField(max_length=30, default="Stk.")
    purchase_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    tax_rate = models.DecimalField(max_digits=5, decimal_places=2, default=19)
    mixed_payload = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["position", "id"]
