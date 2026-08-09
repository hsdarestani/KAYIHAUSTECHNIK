from django.urls import path

from . import rebuild_views as views


urlpatterns = [
    path("", views.dashboard, name="next-dashboard"),
    path("customers/", views.customer_list, name="next-customers"),
    path("customers/new/", views.customer_create, name="next-customer-create"),
    path("customers/<int:pk>/", views.customer_detail, name="next-customer-detail"),
    path("projects/", views.project_list, name="next-projects"),
    path("projects/new/", views.project_create, name="next-project-create"),
    path("projects/<int:pk>/", views.project_detail, name="next-project-detail"),
    path("appointments/", views.appointment_list, name="next-appointments"),
    path("appointments/new/", views.appointment_create, name="next-appointment-create"),
    path("appointments/<int:pk>/", views.appointment_detail, name="next-appointment-detail"),
    path("appointments/<int:event_pk>/time/", views.time_toggle, name="next-time-toggle"),
    path("appointments/<int:pk>/document/", views.appointment_document, name="next-appointment-document"),
    path("appointments/<int:pk>/ai-report/", views.ai_structure_report, name="next-ai-report"),
    path("field/", views.field_home, name="next-field"),
    path("time/", views.time_overview, name="next-time"),
    path("quotes/", views.quote_list, name="next-quotes"),
    path("quotes/new/", views.quote_editor, name="next-quote-create"),
    path("quotes/<int:pk>/", views.quote_editor, name="next-quote-edit"),
    path("invoices/", views.invoice_list, name="next-invoices"),
    path("invoices/new/", views.invoice_editor, name="next-invoice-create"),
    path("invoices/<int:pk>/", views.invoice_editor, name="next-invoice-edit"),
    path("invoices/<int:pk>/payment/", views.invoice_payment, name="next-invoice-payment"),
    path("migration/tooltime/", views.migration_import, name="next-tooltime-migration"),
    path("settings/next/", views.settings_page, name="next-settings"),
]
