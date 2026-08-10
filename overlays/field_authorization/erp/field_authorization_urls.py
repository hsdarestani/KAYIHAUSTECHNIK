from django.urls import path

from . import field_authorization_views as views

urlpatterns = [
    path("field/jobs/new/", views.quick_job, name="field-quick-job"),
    path("field/customers/search/", views.customer_search, name="field-customer-search"),
    path("appointments/<int:pk>/authorization/sign/", views.authorization_sign, name="field-authorization-sign"),
    path("appointments/<int:pk>/authorization/ai/", views.authorization_ai, name="field-authorization-ai"),
    path("appointments/<int:pk>/authorization/pdf/", views.authorization_pdf, name="field-authorization-pdf"),
    path("appointments/<int:pk>/completion/pdf/", views.completion_pdf, name="field-completion-pdf"),
    path("appointments/<int:pk>/room-plan.svg", views.room_plan_preview, name="field-room-plan-preview"),
    path("appointments/<int:pk>/complete/", views.complete_job, name="field-complete-job"),
]
