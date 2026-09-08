from django.utils.deprecation import MiddlewareMixin
from erp.models import ActivityLog


class ActivityMiddleware(MiddlewareMixin):
    WRITE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}

    def process_response(self, request, response):
        if request.method in self.WRITE_METHODS and getattr(request, "user", None) and request.user.is_authenticated:
            if not request.path.startswith("/admin/jsi18n") and response.status_code < 500:
                profile = getattr(request.user, "profile", None)
                organization = getattr(profile, "organization", None)
                forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
                ip = forwarded.split(",")[0].strip() if forwarded else request.META.get("REMOTE_ADDR")
                try:
                    ActivityLog.objects.create(
                        organization=organization,
                        user=request.user,
                        verb=request.method,
                        entity_type="http",
                        entity_id=request.path[:100],
                        description=f"{request.method} {request.path}"[:500],
                        ip_address=ip,
                        metadata={"status": response.status_code},
                    )
                except Exception:
                    pass
        return response
