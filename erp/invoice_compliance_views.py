from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods, require_POST

from . import models as m
from .rebuild_views import _is_field_user, _org
from .services.invoice_compliance_service import ComplianceError, create_cancellation, create_correction, get_compliance


def _office(request):
    if _is_field_user(request):
        messages.error(request, "Rechnungs-Compliance ist nur für Büro/Buchhaltung verfügbar.")
        return False
    return True


@login_required
@require_http_methods(["GET", "POST"])
def compliance_settings(request):
    if not _office(request): return redirect("next-dashboard")
    org = _org(request)
    settings = dict(org.settings or {})
    legal = dict(settings.get("invoice_legal") or {})
    if request.method == "POST":
        fields = ("legal_form", "street", "house_number", "postal_code", "city", "country", "website", "tax_number", "vat_id", "register", "register_number", "register_court", "managing_director", "bic", "bank_name")
        for field in fields: legal[field] = (request.POST.get(field) or "").strip()
        settings["invoice_legal"] = legal
        settings["invoice_currency"] = (request.POST.get("invoice_currency") or "EUR").strip().upper()[:3]
        settings["invoice_number_prefix"] = (request.POST.get("invoice_number_prefix") or "RE").strip()[:20]
        settings["invoice_number_digits"] = max(3, min(int(request.POST.get("invoice_number_digits") or 5), 12))
        settings["invoice_number_start"] = max(1, int(request.POST.get("invoice_number_start") or 1))
        settings["einvoice_transition_end"] = (request.POST.get("einvoice_transition_end") or "2026-12-31").strip()
        settings["invoice_tax_reason"] = (request.POST.get("invoice_tax_reason") or "").strip()
        org.settings = settings
        org.legal_name = (request.POST.get("legal_name") or org.legal_name or org.name).strip()
        org.email = (request.POST.get("email") or org.email or "").strip()
        org.phone = (request.POST.get("phone") or org.phone or "").strip()
        org.address = (request.POST.get("address") or org.address or "").strip()
        org.tax_id = legal.get("tax_number") or legal.get("vat_id") or org.tax_id
        org.iban = (request.POST.get("iban") or org.iban or "").strip()
        org.save()
        messages.success(request, "Rechnungs- und Unternehmensdaten gespeichert.")
        return redirect("invoice-compliance-settings")
    return render(request, "rebuild/invoice_compliance_settings.html", {"org": org, "legal": legal, "settings": settings, "validator_configured": bool(__import__('os').environ.get('XRECHNUNG_VALIDATOR_URL'))})


@login_required
@require_POST
def correction_create(request, pk):
    if not _office(request): return redirect("next-dashboard")
    org = _org(request); original = get_object_or_404(m.Invoice, organization=org, pk=pk)
    try: draft = create_correction(original, user=request.user)
    except ComplianceError as exc:
        messages.error(request, str(exc)); return redirect("next-invoice-edit", pk=pk)
    messages.success(request, f"Korrekturentwurf zu {original.number} erstellt.")
    return redirect("next-invoice-edit", pk=draft.pk)


@login_required
@require_POST
def cancellation_create(request, pk):
    if not _office(request): return redirect("next-dashboard")
    org = _org(request); original = get_object_or_404(m.Invoice, organization=org, pk=pk)
    try: cancellation, record = create_cancellation(original, user=request.user, request=request)
    except ComplianceError as exc:
        messages.error(request, str(exc)); return redirect("next-invoice-edit", pk=pk)
    messages.success(request, f"Storno {record.final_number} wurde revisionsorientiert erstellt.")
    return redirect("next-invoice-edit", pk=cancellation.pk)


@login_required
def frozen_pdf(request, pk):
    if not _office(request): return redirect("next-dashboard")
    org = _org(request); invoice = get_object_or_404(m.Invoice, organization=org, pk=pk); record = get_compliance(invoice)
    if not record or not record.original_pdf_document_id: raise Http404
    return FileResponse(record.original_pdf_document.file.open("rb"), content_type="application/pdf", filename=f"rechnung-{record.final_number}.pdf")


@login_required
def frozen_xml(request, pk):
    if not _office(request): return redirect("next-dashboard")
    org = _org(request); invoice = get_object_or_404(m.Invoice, organization=org, pk=pk); record = get_compliance(invoice)
    if not record or not record.original_xml_document_id: raise Http404
    return FileResponse(record.original_xml_document.file.open("rb"), content_type="application/xml", filename=f"xrechnung-{record.final_number}.xml")
