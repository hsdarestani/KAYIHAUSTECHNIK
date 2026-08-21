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

    # Appointment creation is an office-only workflow. The general production
    # smoke can be authenticated as a field/demo user, so verify this one page
    # in a separate temporary Office session. The account is deleted in finally
    # and production permissions for the original session are never changed.
    smoke_rel = "scripts/production_browser_smoke.py"
    smoke = module.read(smoke_rel)
    old_smoke = r'''            # A+BAU TOOLTIME APPOINTMENT PROCESS BROWSER SMOKE
            response = page.goto(urljoin(base_url, "appointments/new/"), wait_until="domcontentloaded", timeout=30_000)
            if response is None or response.status >= 500:
                fail(f"appointment parity create returned {response.status if response else 'no response'}")
            body = page.locator("body").inner_text()
            for label in ("Terminname", "Mitarbeiter hinzufügen", "Leistungsgruppe hinzufügen", "Position hinzufügen", "Arbeitsbericht"):
                if label not in body:
                    fail(f"appointment parity is missing {label!r}")
            if page.locator('[data-service-editor]').count() != 1:
                fail("appointment service editor is missing")
'''
    new_smoke = r'''            # A+BAU TOOLTIME APPOINTMENT PROCESS BROWSER SMOKE
            from erp.models import Organization, UserProfile
            smoke_org = Organization.objects.filter(settings__is_demo=True).order_by("pk").first() or Organization.objects.order_by("pk").first()
            if smoke_org is None:
                fail("appointment parity smoke could not resolve an organization")
            smoke_username = f"appointment-office-smoke-{secrets.token_hex(5)}"
            smoke_password = secrets.token_urlsafe(24)
            SmokeUser = get_user_model()
            smoke_office_user = SmokeUser.objects.create_user(
                username=smoke_username,
                password=smoke_password,
                email=f"{smoke_username}@example.invalid",
            )
            smoke_profile, _ = UserProfile.objects.get_or_create(user=smoke_office_user)
            smoke_profile.organization = smoke_org
            smoke_profile.role = UserProfile.Role.OFFICE
            smoke_profile.is_mobile_worker = False
            smoke_profile.save()
            office_context = None
            try:
                office_context = browser.new_context(locale="de-DE", viewport={"width": 1440, "height": 1000})
                office_page = office_context.new_page()
                login_response = office_page.goto(urljoin(base_url, "login/"), wait_until="domcontentloaded", timeout=30_000)
                if login_response is None or login_response.status >= 500:
                    fail(f"appointment parity office login returned {login_response.status if login_response else 'no response'}")
                office_page.fill('input[name="username"]', smoke_username)
                office_page.fill('input[name="password"]', smoke_password)
                with office_page.expect_navigation(wait_until="domcontentloaded", timeout=30_000):
                    office_page.click('button[type="submit"], button.btn-primary')
                if "/login/" in office_page.url:
                    fail("appointment parity office login did not establish a session")
                response = office_page.goto(urljoin(base_url, "appointments/new/"), wait_until="domcontentloaded", timeout=30_000)
                if response is None or response.status >= 500:
                    fail(f"appointment parity create returned {response.status if response else 'no response'}")
                if "/login/" in office_page.url:
                    fail("appointment parity office smoke unexpectedly redirected to login")
                body = office_page.locator("body").inner_text()
                for label in ("Terminname", "Mitarbeiter hinzufügen", "Leistungsgruppe hinzufügen", "Position hinzufügen", "Arbeitsbericht"):
                    if label not in body:
                        fail(f"appointment parity is missing {label!r}")
                if office_page.locator('[data-service-editor]').count() != 1:
                    fail("appointment service editor is missing")
            finally:
                if office_context is not None:
                    office_context.close()
                smoke_office_user.delete()
'''
    if "smoke_username = f\"appointment-office-smoke-" not in smoke:
        if old_smoke not in smoke:
            raise RuntimeError("Appointment final closeout: appointment browser smoke anchor fehlt")
        smoke = smoke.replace(old_smoke, new_smoke, 1)
    module.write(smoke_rel, smoke)
    compile(smoke, str(ROOT / smoke_rel), "exec")

    for marker in (
        "Nach dem Speichern",
        "data-field-services",
        "next-appointment-to-quote",
        "next-appointment-to-invoice",
    ):
        haystack = form if marker == "Nach dem Speichern" else detail if marker == "data-field-services" else urls
        if marker not in haystack:
            raise RuntimeError(f"Appointment final closeout guard missing: {marker}")
    for marker in (
        'smoke_username = f"appointment-office-smoke-',
        "UserProfile.Role.OFFICE",
        "smoke_office_user.delete()",
    ):
        if marker not in smoke:
            raise RuntimeError(f"Appointment final closeout browser guard missing: {marker}")
    print(f"{MARKER}: final template balance, hand-off routes and isolated Office appointment browser smoke restored.")
