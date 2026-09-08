from __future__ import annotations

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import redirect, render, resolve_url
from django.utils import timezone
from django.views.decorators.http import require_http_methods, require_POST

AI_CONSENT_VERSION = "2026-08-10"


def _preferences(user):
    profile = getattr(user, "profile", None)
    if profile is None:
        return None, {}
    return profile, dict(profile.preferences or {})


def has_ai_consent(user) -> bool:
    if not getattr(user, "is_authenticated", False):
        return False
    _profile, preferences = _preferences(user)
    return bool(
        preferences.get("ai_third_party_consent_at")
        and preferences.get("ai_third_party_consent_version") == AI_CONSENT_VERSION
        and not preferences.get("ai_third_party_consent_revoked_at")
    )


def landing_page(request):
    """Public product presentation while preserving the authenticated dashboard at /."""
    if request.user.is_authenticated:
        from . import rebuild_views

        return rebuild_views.dashboard(request)
    return render(
        request,
        "store/landing.html",
        {
            "login_url": resolve_url(settings.LOGIN_URL),
        },
    )


def privacy_policy(request):
    return render(request, "store/privacy.html", {"ai_consent_version": AI_CONSENT_VERSION})


def support_page(request):
    return render(request, "store/support.html")


@require_http_methods(["GET", "POST"])
def account_deletion_page(request):
    submitted = False
    if request.method == "POST":
        candidate = request.user if request.user.is_authenticated else None
        if candidate is None:
            identifier = (request.POST.get("identifier") or "").strip()
            if identifier:
                User = get_user_model()
                candidate = User.objects.filter(email__iexact=identifier).first() or User.objects.filter(username__iexact=identifier).first()
        if candidate is not None:
            profile, preferences = _preferences(candidate)
            if profile is not None:
                preferences.update({
                    "deletion_requested_at": timezone.now().isoformat(),
                    "deletion_source": "public_web",
                    "deletion_identity_verification_required": True,
                })
                profile.preferences = preferences
                profile.save(update_fields=["preferences", "updated_at"])
        submitted = True
    return render(request, "store/account_deletion.html", {"submitted": submitted})


@login_required
@require_POST
def ai_consent(request):
    profile, preferences = _preferences(request.user)
    if profile is None:
        return JsonResponse({"ok": False, "error": "Kein Benutzerprofil vorhanden."}, status=400)

    action = (request.POST.get("action") or "accept").strip().lower()
    if action == "revoke":
        preferences["ai_third_party_consent_revoked_at"] = timezone.now().isoformat()
        message = "Die Einwilligung für die KI-Verarbeitung wurde widerrufen."
    else:
        preferences.update({
            "ai_third_party_consent_at": timezone.now().isoformat(),
            "ai_third_party_consent_version": AI_CONSENT_VERSION,
            "ai_third_party_consent_revoked_at": None,
        })
        message = "Die Einwilligung für die KI-Verarbeitung wurde gespeichert."

    profile.preferences = preferences
    profile.save(update_fields=["preferences", "updated_at"])

    wants_json = "application/json" in request.headers.get("Accept", "") or request.headers.get("X-Requested-With") == "XMLHttpRequest"
    if wants_json:
        return JsonResponse({"ok": True, "consented": has_ai_consent(request.user), "message": message})
    messages.success(request, message)
    return redirect("next-settings")
