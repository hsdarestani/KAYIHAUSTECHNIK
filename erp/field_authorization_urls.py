from django.urls import path

from . import field_authorization_views as views
from . import project_intake_views as project_intake

urlpatterns = [
    path("field/jobs/new/", project_intake.technician_quick_job, name="field-quick-job"),
    path("projektfreigaben/<int:pk>/", project_intake.approval_review, name="project-approval-review"),
    path("projektfreigaben/", project_intake.approval_queue, name="project-approval-queue"),
    path("field/projects/<int:pk>/freigabe/", project_intake.technician_project_approval, name="field-project-approval"),
    path("field/project-intake/voice/", project_intake.intake_voice, name="field-project-intake-voice"),
    path("field/project-intake/ai/", project_intake.intake_ai, name="field-project-intake-ai"),
    path("field/customers/search/", views.customer_search, name="field-customer-search"),
    path("appointments/<int:pk>/project/attach/", views.attach_project, name="field-attach-project"),
    path("appointments/<int:pk>/authorization/catalog/", views.authorization_catalog_search, name="field-authorization-catalog"),
    path("appointments/<int:pk>/authorization/sign/", views.authorization_sign, name="field-authorization-sign"),
    path("appointments/<int:pk>/authorization/ai/", views.authorization_ai, name="field-authorization-ai"),
    path("appointments/<int:pk>/authorization/pdf/", views.authorization_pdf, name="field-authorization-pdf"),
    path("appointments/<int:pk>/completion/pdf/", views.completion_pdf, name="field-completion-pdf"),
    path("appointments/<int:pk>/room-plan.svg", views.room_plan_preview, name="field-room-plan-preview"),
    path("appointments/<int:pk>/complete/", views.complete_job, name="field-complete-job"),
]
