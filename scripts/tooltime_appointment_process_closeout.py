from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MARKER = "A+BAU TOOLTIME APPOINTMENT FINAL CLOSEOUT 2026-08-21"


def run(module) -> None:
    # The signed Field-Authorization template keeps its phone controls on one
    # line, while the older appointment template used a newline. The original
    # compatibility patch could therefore open an event.project conditional
    # without installing its customer fallback/endif. Undo only that half-patch.
    detail_rel = "templates/rebuild/appointment_detail.html"
    detail = module.read(detail_rel)
    opened_phone = "{% if event.project %}{% with phone=event.project.customer.mobile|default:event.project.customer.phone %}"
    balanced_else = "{% endwith %}{% else %}{% with phone=event.customer.mobile|default:event.customer.phone %}"
    if opened_phone in detail and balanced_else not in detail:
        detail = detail.replace(
            opened_phone,
            "{% with phone=event.project.customer.mobile|default:event.project.customer.phone %}",
            1,
        )
    if opened_phone in detail and balanced_else not in detail:
        raise RuntimeError("Appointment final closeout: unbalanced phone conditional remains")
    module.write(detail_rel, detail)

    # Preserve the legacy Phase-10 accessibility/semantics contract while the
    # placeholder card has become a real service editor.
    form_rel = "templates/rebuild/appointment_form.html"
    form = module.read(form_rel)
    service_card = '<section class="tt-appt-card tt-appt-services-editor" data-service-editor>'
    service_card_labeled = '<section class="tt-appt-card tt-appt-services-editor" data-service-editor aria-label="Nach dem Speichern">'
    if "Nach dem Speichern" not in form:
        if service_card not in form:
            raise RuntimeError("Appointment final closeout: service editor card fehlt")
        form = form.replace(service_card, service_card_labeled, 1)
    module.write(form_rel, form)

    # Ensure the two appointment hand-off endpoints are present in the final
    # URL table. An earlier tuple construction used adjacent string literals,
    # so its membership guard could accidentally test only the first character.
    urls_rel = "erp/rebuild_urls.py"
    urls = module.read(urls_rel)
    anchor = '    path("appointments/<int:pk>/edit/", views.appointment_edit, name="next-appointment-edit"),\n'
    route_quote = '    path("appointments/<int:pk>/angebot/", views.appointment_to_quote, name="next-appointment-to-quote"),\n'
    route_invoice = '    path("appointments/<int:pk>/rechnung/", views.appointment_to_invoice, name="next-appointment-to-invoice"),\n'
    missing = ""
    if route_quote not in urls:
        missing += route_quote
    if route_invoice not in urls:
        missing += route_invoice
    if missing:
        if anchor not in urls:
            raise RuntimeError("Appointment final closeout: appointment edit URL anchor fehlt")
        urls = urls.replace(anchor, anchor + missing, 1)
    module.write(urls_rel, urls)
    compile(urls, str(ROOT / urls_rel), "exec")

    for marker in (
        "Nach dem Speichern",
        "data-field-services",
        "next-appointment-to-quote",
        "next-appointment-to-invoice",
    ):
        haystack = form if marker == "Nach dem Speichern" else detail if marker == "data-field-services" else urls
        if marker not in haystack:
            raise RuntimeError(f"Appointment final closeout guard missing: {marker}")
    print(f"{MARKER}: final template balance, legacy semantics and Termin→Angebot/Rechnung routes restored.")
