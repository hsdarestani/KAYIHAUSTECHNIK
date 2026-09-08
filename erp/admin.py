from django.contrib import admin
from erp import models


class QuoteItemInline(admin.TabularInline):
    model = models.QuoteItem
    extra = 0


class InvoiceItemInline(admin.TabularInline):
    model = models.InvoiceItem
    extra = 0


@admin.register(models.Quote)
class QuoteAdmin(admin.ModelAdmin):
    list_display = ("number", "project", "status", "issue_date", "gross_total")
    list_filter = ("status", "issue_date")
    search_fields = ("number", "project__title", "project__customer__company")
    inlines = [QuoteItemInline]


@admin.register(models.Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ("number", "project", "status", "issue_date", "due_date", "gross_total", "outstanding_total")
    list_filter = ("status", "issue_date", "due_date")
    search_fields = ("number", "project__title", "project__customer__company")
    inlines = [InvoiceItemInline]


@admin.register(models.Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ("number", "title", "customer", "status", "priority", "progress")
    list_filter = ("status", "priority")
    search_fields = ("number", "title", "customer__company", "customer__last_name")
    filter_horizontal = ("members",)


@admin.register(models.Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ("number", "display_name", "type", "email", "phone", "city", "active")
    list_filter = ("type", "active")
    search_fields = ("number", "company", "first_name", "last_name", "email", "phone")


for model in [
    models.Organization, models.UserProfile, models.ObjectLocation, models.Employee,
    models.Task, models.CalendarEvent, models.CatalogItem, models.Supplier, models.PriceSource, models.PriceItem, models.ProjectMaterial,
    models.TimeEntry, models.Document, models.RoomMeasurement, models.RoomModelRevision, models.MeasurementCapture, models.NativeRoomScan, models.Payment, models.Expense,
    models.EmailMessage, models.AIConversation, models.AIMessage,
    models.IntegrationConfig, models.AutomationJob, models.Notification,
    models.WorkMedia, models.ChangeOrder, models.ChangeOrderAttachment,
    models.SiteReport, models.CustomerSurvey, models.CustomerPortalAccess, models.PurchaseOrder, models.PurchaseDocument,
    models.BugReport, models.ActivityLog, models.Sequence,
]:
    try:
        admin.site.register(model)
    except admin.sites.AlreadyRegistered:
        pass

admin.site.site_header = "A+Bau Administration"
admin.site.site_title = "A+Bau"
admin.site.index_title = "Systemverwaltung"
