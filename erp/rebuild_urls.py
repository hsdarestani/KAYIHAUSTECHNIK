from django.urls import include, path

from . import rebuild_migration as migration
from . import rebuild_ops as ops
from . import rebuild_projects as projects
from . import rebuild_views as views
from . import tooltime_parity_views as tooltime_parity
from . import tooltime_invoices_exact as invoices_exact
from . import tooltime_catalogue_views as catalogue
from . import invoice_compliance_views as invoice_compliance
from . import live_pricing_views as live_pricing
from . import manager_review_views as manager_review
from . import manager_review_pdf as manager_review_pdf
from . import bo_direct_search_views as bo_search
from . import ab_bau_catalog_views as ab_catalog
from . import assistant_views as assistant
from . import field_authorization_views as field_auth


# A+BAU TOOLTIME INVOICES REGRESSION COMPAT 2026-08-21
tooltime_parity.invoice_list = invoices_exact.invoice_list


urlpatterns = [
    path("catalogue/", catalogue.catalogue_list, name="next-catalogue"),
    path("catalogue/new/", catalogue.catalogue_edit, name="next-catalogue-create"),
    path("catalogue/<int:pk>/edit/", catalogue.catalogue_edit, name="next-catalogue-edit"),
    path("catalogue/<int:pk>/delete/", catalogue.catalogue_delete, name="next-catalogue-delete"),
    path("quotes/<int:pk>/pdf/", tooltime_parity.quote_pdf, name="next-quote-pdf"),
    path("quotes/<int:pk>/preview/", tooltime_parity.quote_preview, name="next-quote-preview"),
    path("quotes/<int:pk>/send-email/", tooltime_parity.quote_send_email, name="next-quote-send-email"),
    path("invoices/<int:pk>/send-email/", tooltime_parity.invoice_send_email, name="next-invoice-send-email"),
    path("pricing/artikel-suche/", tooltime_parity.article_search, name="next-article-search"),
    path("documents/kunde-schnell-anlegen/", tooltime_parity.quick_customer_create, name="next-quick-customer-create"),
    path("documents/projekt-schnell-anlegen/", tooltime_parity.quick_project_create, name="next-quick-project-create"),
    path("invoices/<int:pk>/mahnung/", tooltime_parity.invoice_dunning, name="next-invoice-dunning"),
    path("angebot/<str:token>/", tooltime_parity.public_quote, name="next-public-quote"),
    path("settings/next/rechnung-compliance/", invoice_compliance.compliance_settings, name="invoice-compliance-settings"),
    path("invoices/<int:pk>/correction/", invoice_compliance.correction_create, name="invoice-compliance-correction"),
    path("invoices/<int:pk>/cancel/", invoice_compliance.cancellation_create, name="invoice-compliance-cancel"),
    path("invoices/<int:pk>/frozen.pdf", invoice_compliance.frozen_pdf, name="invoice-compliance-pdf"),
    path("invoices/<int:pk>/xrechnung.xml", invoice_compliance.frozen_xml, name="invoice-compliance-xml"),
    path("pricing/live-search/", live_pricing.live_pricing_search, name="next-live-pricing-search"),
    # A+Bau signed field order/freigabe routes.
    path("", include("erp.field_authorization_urls")),
    # A+Bau Room Planner Pro: project-scoped WebGL room planning and AI scene reconstruction.
    path("", include("erp.room_planner_urls")),
    path("", views.dashboard, name="next-dashboard"),
    path("customers/", views.customer_list, name="next-customers"),
    path("suppliers/", views.supplier_list, name="next-suppliers"),
    path("customers/new/", views.customer_create, name="next-customer-create"),
    path("customers/<int:pk>/", views.customer_detail, name="next-customer-detail"),
    path("customers/<int:pk>/angebot/neu/", views.customer_quote_create, name="next-customer-quote-create"),
    path("customers/<int:pk>/rechnung/neu/", views.customer_invoice_create, name="next-customer-invoice-create"),
    path("customers/<int:pk>/locations.json/", views.customer_locations_api, name="next-customer-locations-api"),
    path("projects/", projects.project_list, name="next-projects"),
    path("projects/new/", views.project_create, name="next-project-create"),
    path("projects/<int:pk>/", projects.project_detail, name="next-project-detail"),
    path("projects/<int:pk>/aktionen/", views.project_lifecycle, name="next-project-lifecycle"),
    path("appointments/", views.appointment_list, name="next-appointments"),
    path("appointments/new/", views.appointment_create, name="next-appointment-create"),
    path("appointments/<int:pk>/move/", views.appointment_move, name="next-appointment-move"),
    path("appointments/<int:pk>/edit/", views.appointment_edit, name="next-appointment-edit"),
    path("appointments/<int:pk>/angebot/", views.appointment_to_quote, name="next-appointment-to-quote"),
    path("appointments/<int:pk>/rechnung/", views.appointment_to_invoice, name="next-appointment-to-invoice"),
    path("appointments/<int:pk>/delete/", views.appointment_delete, name="next-appointment-delete"),
    path("appointments/<int:pk>/", field_auth.field_job_detail, name="next-appointment-detail"),
    path("appointments/<int:event_pk>/time/", field_auth.gated_time_toggle, name="next-time-toggle"),
    path("appointments/<int:pk>/document/", views.appointment_document, name="next-appointment-document"),
    path("appointments/<int:pk>/ai-report/", views.ai_structure_report, name="next-ai-report"),
    path("field/", views.field_home, name="next-field"),
    path("time/", views.time_overview, name="next-time"),
    path("time/<int:pk>/edit/", views.time_entry_edit, name="next-time-entry-edit"),
    path("tasks/", ops.task_list, name="next-tasks"),
    path("tasks/new/", ops.task_edit, name="next-task-create"),
    path("tasks/<int:pk>/", ops.task_edit, name="next-task-edit"),
    path("expenses/", ops.expense_list, name="next-expenses"),
    path("expenses/new/", ops.expense_edit, name="next-expense-create"),
    path("expenses/<int:pk>/", ops.expense_edit, name="next-expense-edit"),
    path("employees/", ops.employee_list, name="next-employees"),
    path("employees/new/", ops.employee_edit, name="next-employee-create"),
    path("employees/<int:pk>/", ops.employee_edit, name="next-employee-edit"),
    path("pricing/bando/search/", bo_search.bo_price_search, name="next-bo-price-search"),
    path("pricing/catalog/search/", ab_catalog.catalog_quick_search, name="next-catalog-quick-search"),
    path("quotes/", tooltime_parity.quote_list, name="next-quotes"),
    path("quotes/new/", tooltime_parity.quote_editor, name="next-quote-create"),
    path("quotes/<int:pk>/", tooltime_parity.quote_workspace, name="next-quote-edit"),
    path("quotes/<int:pk>/status/", tooltime_parity.quote_status, name="next-quote-status"),
    path("quotes/<int:pk>/auftragsbestaetigung/", tooltime_parity.quote_order_confirmation, name="next-quote-order-confirmation"),
    path("quotes/<int:pk>/termin/", views.appointment_from_quote, name="next-quote-to-appointment"),
    path("quotes/<int:pk>/rechnung/", tooltime_parity.quote_to_invoice, name="next-quote-to-invoice"),
    path("quotes/<int:pk>/rechnung-erstellen/", tooltime_parity.quote_invoice_wizard, name="next-quote-invoice-wizard"),
    path("invoices/", tooltime_parity.invoice_list, name="next-invoices"),
    path("invoices/new/", tooltime_parity.invoice_editor, name="next-invoice-create"),
    path("invoices/<int:pk>/", tooltime_parity.invoice_workspace, name="next-invoice-edit"),
    path("invoices/<int:pk>/preview/", tooltime_parity.invoice_preview, name="next-invoice-preview"),
    path("invoices/<int:pk>/payment/", tooltime_parity.invoice_payment, name="next-invoice-payment"),
    path("payments/", tooltime_parity.pay_overview, name="next-payments"),
    path("payouts/", tooltime_parity.payout_overview, name="next-payouts"),
    path("invoices/<int:pk>/payment-link/", tooltime_parity.invoice_payment_link, name="next-invoice-payment-link"),
    path("invoices/<int:pk>/dunning-toggle/", tooltime_parity.invoice_dunning_toggle, name="next-invoice-dunning-toggle"),
    path("pay/provider/webhook/", tooltime_parity.pay_provider_webhook, name="next-pay-provider-webhook"),
    path("finanzen/", views.finance_dashboard, name="next-finance"),
    path("migration/tooltime/", migration.migration_import, name="next-tooltime-migration"),
    path("einsatzpruefung/", manager_review.review_queue, name="field-review-queue"),
    path("einsatzpruefung/<int:pk>/", manager_review.review_detail, name="field-review-detail"),
    path("einsatzpruefung/<int:pk>/pdf/", manager_review_pdf.review_pdf, name="field-review-pdf"),
    path("einsatzpruefung/<int:pk>/freigeben/", manager_review.approve_completion, name="field-review-approve"),
    path("einsatzpruefung/<int:pk>/aenderung/", manager_review.request_changes, name="field-review-changes"),
    path("konto/", tooltime_parity.account_page, name="next-account"),
    path("settings/next/", tooltime_parity.settings_page, name="next-settings"),
    path("settings/next/textvorlagen/neu/", tooltime_parity.text_template_create, name="next-text-template-create"),
    path("settings/next/textvorlagen/<int:pk>/speichern/", tooltime_parity.text_template_update, name="next-text-template-update"),
    path("settings/next/textvorlagen/<int:pk>/loeschen/", tooltime_parity.text_template_delete, name="next-text-template-delete"),
    path("settings/next/textvorlagen/<int:pk>/standard/", tooltime_parity.text_template_standard, name="next-text-template-standard"),
    path("settings/next/textvorlagen/<int:pk>/verschieben/", tooltime_parity.text_template_move, name="next-text-template-move"),
    path("settings/next/layout/vorschau/", tooltime_parity.layout_preview, name="next-layout-preview"),
    path("konto/abmelden/", assistant.account_logout, name="next-logout"),
    path("appointments/<int:pk>/voice/", assistant.appointment_voice, name="next-appointment-voice"),
    path("assistant/command/", assistant.assistant_command, name="next-assistant-command"),
    path("assistant/execute/", assistant.execute_workflow, name="next-assistant-execute"),
    path("field/voice/transcribe/", assistant.field_voice_transcribe, name="next-field-voice-transcribe"),
]
