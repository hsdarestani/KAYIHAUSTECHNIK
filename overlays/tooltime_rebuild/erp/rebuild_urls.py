from django.urls import path

from . import rebuild_migration as migration
from . import rebuild_ops as ops
from . import rebuild_projects as projects
from . import rebuild_views as views


urlpatterns = [
    path("", views.dashboard, name="next-dashboard"),
    path("customers/", views.customer_list, name="next-customers"),
    path("customers/new/", views.customer_create, name="next-customer-create"),
    path("customers/<int:pk>/", views.customer_detail, name="next-customer-detail"),
    path("projects/", projects.project_list, name="next-projects"),
    path("projects/new/", views.project_create, name="next-project-create"),
    path("projects/<int:pk>/", projects.project_detail, name="next-project-detail"),
    path("appointments/", views.appointment_list, name="next-appointments"),
    path("appointments/new/", views.appointment_create, name="next-appointment-create"),
    path("appointments/<int:pk>/", views.appointment_detail, name="next-appointment-detail"),
    path("appointments/<int:event_pk>/time/", views.time_toggle, name="next-time-toggle"),
    path("appointments/<int:pk>/document/", views.appointment_document, name="next-appointment-document"),
    path("appointments/<int:pk>/ai-report/", views.ai_structure_report, name="next-ai-report"),
    path("field/", views.field_home, name="next-field"),
    path("time/", views.time_overview, name="next-time"),
    path("tasks/", ops.task_list, name="next-tasks"),
    path("tasks/new/", ops.task_edit, name="next-task-create"),
    path("tasks/<int:pk>/", ops.task_edit, name="next-task-edit"),
    path("expenses/", ops.expense_list, name="next-expenses"),
    path("expenses/new/", ops.expense_edit, name="next-expense-create"),
    path("expenses/<int:pk>/", ops.expense_edit, name="next-expense-edit"),
    path("employees/", ops.employee_list, name="next-employees"),
    path("employees/new/", ops.employee_edit, name="next-employee-create"),
    path("employees/<int:pk>/", ops.employee_edit, name="next-employee-edit"),
    path("quotes/", views.quote_list, name="next-quotes"),
    path("quotes/new/", views.quote_editor, name="next-quote-create"),
    path("quotes/<int:pk>/", views.quote_editor, name="next-quote-edit"),
    path("invoices/", views.invoice_list, name="next-invoices"),
    path("invoices/new/", views.invoice_editor, name="next-invoice-create"),
    path("invoices/<int:pk>/", views.invoice_editor, name="next-invoice-edit"),
    path("invoices/<int:pk>/payment/", views.invoice_payment, name="next-invoice-payment"),
    path("migration/tooltime/", migration.migration_import, name="next-tooltime-migration"),
    path("settings/next/", views.settings_page, name="next-settings"),
]
