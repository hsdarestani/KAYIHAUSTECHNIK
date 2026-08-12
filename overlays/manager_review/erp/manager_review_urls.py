from django.urls import path

from . import manager_review_views as views


urlpatterns = [
    path("einsatzpruefung/", views.review_queue, name="field-review-queue"),
    path("einsatzpruefung/<int:pk>/", views.review_detail, name="field-review-detail"),
    path("einsatzpruefung/<int:pk>/freigeben/", views.approve_completion, name="field-review-approve"),
    path("einsatzpruefung/<int:pk>/aenderung/", views.request_changes, name="field-review-changes"),
]
