from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path
from erp import api, views

urlpatterns = [
    path("admin/", admin.site.urls),
    path("login/", auth_views.LoginView.as_view(template_name="registration/login.html"), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("", include("erp.urls")),
    path("api/", include(api.router.urls)),
    path("api/mobile/login/", api.MobileLoginAPIView.as_view(), name="api-mobile-login"),
    path("api/mobile/logout/", api.MobileLogoutAPIView.as_view(), name="api-mobile-logout"),
    path("api/mobile/config/", api.MobileConfigAPIView.as_view(), name="api-mobile-config"),
    path("api/mobile/account-deletion/", api.AccountDeletionAPIView.as_view(), name="api-mobile-account-deletion"),
    path("api/search/", api.GlobalSearchAPIView.as_view(), name="api-search"),
    path("api/ai/chat/", api.AIChatAPIView.as_view(), name="api-ai-chat"),
    path("api/measurements/analyze/", api.RoomMeasurementAnalyzeAPIView.as_view(), name="api-room-measurement-analyze"),
    path("api/native-scans/", api.NativeRoomScanAPIView.as_view(), name="api-native-scans"),
    path("api/native-scans/<uuid:scan_id>/", api.NativeRoomScanAPIView.as_view(), name="api-native-scan-detail"),
    path("api/time/start/", api.TimeStartAPIView.as_view(), name="api-time-start"),
    path("api/time/stop/", api.TimeStopAPIView.as_view(), name="api-time-stop"),
    path("api/health/", views.healthcheck, name="healthcheck"),
    path("sw.js", views.service_worker, name="service-worker"),
]
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
