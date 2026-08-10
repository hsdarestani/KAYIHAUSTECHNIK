from django.urls import path

from . import store_views

urlpatterns = [
    path("datenschutz/", store_views.privacy_policy, name="store-privacy"),
    path("support/", store_views.support_page, name="store-support"),
    path("konto-loeschen/", store_views.account_deletion_page, name="store-account-deletion"),
    path("settings/privacy/ai-consent/", store_views.ai_consent, name="store-ai-consent"),
]
