from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MARKER = "A+BAU FINAL ROOM PLANNER + FIELD FLOW GUARD 2026-08-21"


def read(rel: str) -> str:
    path = ROOT / rel
    if not path.exists():
        raise RuntimeError(f"Final flow guard target missing: {rel}")
    return path.read_text(encoding="utf-8")


def write(rel: str, text: str) -> None:
    path = ROOT / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def restore_room_planner_routes() -> None:
    # Keep Room Planner Pro as the primary 3D entry point. The legacy
    # /configurator/ route remains only as a compatibility fallback.
    replacements = {
        "{% url 'configurator' %}?project={{ project.pk }}": "{% url 'next-room-planner' project.pk %}",
        '{% url "configurator" %}?project={{ project.pk }}': "{% url 'next-room-planner' project.pk %}",
        "{% url 'configurator' %}?project={{ event.project.pk }}": "{% url 'next-room-planner' event.project.pk %}",
        '{% url "configurator" %}?project={{ event.project.pk }}': "{% url 'next-room-planner' event.project.pk %}",
    }
    template_dir = ROOT / "templates" / "rebuild"
    patched = 0
    for path in template_dir.glob("*.html"):
        text = path.read_text(encoding="utf-8")
        original = text
        for old, new in replacements.items():
            text = text.replace(old, new)
        if text != original:
            path.write_text(text, encoding="utf-8")
            patched += 1

    project = read("templates/rebuild/project_detail.html")
    if "next-room-planner' project.pk" not in project and 'next-room-planner" project.pk' not in project:
        raise RuntimeError("Project detail is not connected to Room Planner Pro")
    if "configurator' %}?project={{ project.pk }}" in project or 'configurator" %}?project={{ project.pk }}' in project:
        raise RuntimeError("Project detail still points to the legacy configurator")

    appointment = read("templates/rebuild/appointment_detail.html")
    if "configurator' %}?project={{ event.project.pk }}" in appointment or 'configurator" %}?project={{ event.project.pk }}' in appointment:
        raise RuntimeError("Technician appointment still points to the legacy configurator")

    print(f"{MARKER}: restored modern 3D routes in {patched} rebuild template(s).")


def restore_project_detail_contracts() -> None:
    # Reconcile the final ToolTime visual pass with established project workflows.
    # Finance values remain office-only; technicians keep operational controls.
    rel = "templates/rebuild/project_detail.html"
    text = read(rel)

    text = text.replace("▱ Aufmaß & 3D", "▱ Raum & 3D · Aufmaß")

    text = text.replace(
        "<div><span>B&O / Versicherung</span><strong>Leistungsnachweis / Regiebericht</strong></div>",
        "<div><strong>B&O Leistungsnachweis / Regiebericht</strong><span>Versicherung</span></div>",
    )

    text = text.replace(
        '<a class="tt-pd-row" href="{% url \'next-appointment-detail\' event.pk %}">',
        '<a class="tt-pd-row" data-row-href="{% url \'next-appointment-detail\' event.pk %}" href="{% url \'next-appointment-detail\' event.pk %}">',
    )
    text = text.replace(
        '<a class="tt-pd-row" href="{% url \'next-quote-edit\' row.quote.pk %}">',
        '<a class="tt-pd-row" data-action="open-offer" data-row-href="{% url \'next-quote-edit\' row.quote.pk %}" href="{% url \'next-quote-edit\' row.quote.pk %}">',
    )
    text = text.replace(
        '<a class="tt-pd-row" href="{% url \'next-invoice-edit\' row.invoice.pk %}">',
        '<a class="tt-pd-row" data-action="open-invoice" data-row-href="{% url \'next-invoice-edit\' row.invoice.pk %}" href="{% url \'next-invoice-edit\' row.invoice.pk %}">',
    )

    # Preserve the established project-document download contract while keeping
    # the normal browser preview action available.
    text = text.replace(
        '<a class="nx-btn nx-btn-ghost" href="{{ document.file.url }}" target="_blank">Öffnen</a>',
        '<a class="nx-btn nx-btn-ghost" href="{{ document.file.url }}" target="_blank">Öffnen</a><a class="nx-btn nx-btn-ghost" href="{{ document.file.url }}" download>Herunterladen</a>',
    )

    kpi_block = '''      <div class="tt-pd-kpis">
        <section><span>Umsatz (netto)</span><strong>€{{ turnover_net|floatformat:2 }}</strong></section>
        <section><span>Ausgaben (netto)</span><strong>€{{ project_expenditure|floatformat:2 }}</strong></section>
        <section class="tt-pd-kpi-open"><span>Offener Betrag (brutto)</span><strong>€{{ open_amount|floatformat:2 }}</strong></section>
      </div>

'''
    text = text.replace(kpi_block, "", 1)

    old_tabs = '<div class="tt-pd-tabs"><button type="button" class="is-active" data-tab="overview">Übersicht</button><button type="button" data-tab="tasks">Aufgaben</button><button type="button" data-tab="documents">Dokumente</button></div>'
    new_tabs = '<div class="tt-pd-tabs"><button type="button" class="is-active" data-tab="overview">Übersicht</button><button type="button" data-tab="tasks">Aufgaben</button><button type="button" data-tab="documents">Dokumente</button>{% if not field_user %}<button type="button" data-tab="finance">Finanzen</button>{% endif %}</div>'
    if 'data-tab="finance"' not in text:
        if old_tabs not in text:
            raise RuntimeError("Project detail tab anchor changed before finance restoration")
        text = text.replace(old_tabs, new_tabs, 1)

    finance_panel = r'''
        {% if not field_user %}
        <div class="tt-pd-panel" data-tab-panel="finance">
          <section class="tt-pd-section">
            <h3>Finanzen</h3>
            <div class="tt-pd-kpis">
              <section><span>Umsatz (netto)</span><strong>€{{ turnover_net|floatformat:2 }}</strong></section>
              <section><span>Ausgaben (netto)</span><strong>€{{ project_expenditure|floatformat:2 }}</strong></section>
              <section class="tt-pd-kpi-open"><span>Offener Betrag (brutto)</span><strong>€{{ open_amount|floatformat:2 }}</strong></section>
            </div>
            <div class="tt-pd-tool-grid">
              <a href="{% url 'next-finance' %}">↗ Finanzübersicht</a>
              <a href="{% url 'next-quote-create' %}?project={{ project.pk }}">◇ Angebot erstellen</a>
              <a href="{% url 'next-invoice-create' %}?project={{ project.pk }}">€ Rechnung erstellen</a>
            </div>
          </section>
        </div>
        {% endif %}
'''
    if 'data-tab-panel="finance"' not in text:
        docs_anchor = '''        <div class="tt-pd-panel" data-tab-panel="documents">
          <section class="tt-pd-section"><h3>Dokumente</h3>{% for document in documents %}<div class="tt-pd-row"><div><strong>{{ document.title }}</strong><small>{{ document.get_category_display }} · {{ document.created_at|date:'d.m.Y H:i' }}</small></div>{% if document.file %}<a class="nx-btn nx-btn-ghost" href="{{ document.file.url }}" target="_blank">Öffnen</a><a class="nx-btn nx-btn-ghost" href="{{ document.file.url }}" download>Herunterladen</a>{% endif %}</div>{% empty %}<div class="tt-pd-empty">Noch keine Dokumente angelegt.</div>{% endfor %}</section>
        </div>
'''
        if docs_anchor not in text:
            raise RuntimeError("Project detail documents panel anchor changed before finance restoration")
        text = text.replace(docs_anchor, docs_anchor + finance_panel, 1)

    required = (
        "next-room-planner",
        "Raum & 3D",
        "Aufmaß",
        "B&O Leistungsnachweis / Regiebericht",
        'data-tab="finance"',
        'data-tab-panel="finance"',
        "data-row-href",
        'data-action="open-offer"',
        'data-action="open-invoice"',
        "Herunterladen",
    )
    missing = [marker for marker in required if marker not in text]
    if missing:
        raise RuntimeError(f"Project detail final workflow contracts missing: {missing}")

    finance_pos = text.find('data-tab-panel="finance"')
    kpi_pos = text.find("Umsatz (netto)")
    guard_pos = text.rfind("{% if not field_user %}", 0, finance_pos + 1)
    if min(finance_pos, kpi_pos, guard_pos) < 0 or not (guard_pos < finance_pos and guard_pos < kpi_pos):
        raise RuntimeError("Project-detail finance values are not protected from field users")

    write(rel, text)
    print(f"{MARKER}: restored project-detail finance/row/B&O/field contracts.")


def install_regression_test() -> None:
    write(
        "tests/test_final_room_planner_field_flow_guard.py",
        r'''from pathlib import Path

from django.test import SimpleTestCase

ROOT = Path(__file__).resolve().parents[1]


class FinalRoomPlannerAndFieldFlowGuardTests(SimpleTestCase):
    def test_project_detail_uses_room_planner_pro_not_legacy_configurator(self):
        project = (ROOT / "templates/rebuild/project_detail.html").read_text(encoding="utf-8")
        self.assertIn("next-room-planner", project)
        self.assertNotIn("{% url 'configurator' %}?project={{ project.pk }}", project)
        self.assertNotIn('{% url "configurator" %}?project={{ project.pk }}', project)

    def test_project_detail_keeps_established_workflow_contracts_and_hides_finance_from_field(self):
        project = (ROOT / "templates/rebuild/project_detail.html").read_text(encoding="utf-8")
        for marker in (
            "Raum & 3D",
            "Aufmaß",
            "B&O Leistungsnachweis / Regiebericht",
            'data-tab="finance"',
            'data-tab-panel="finance"',
            "data-row-href",
            'data-action="open-offer"',
            'data-action="open-invoice"',
            "Herunterladen",
        ):
            self.assertIn(marker, project)
        finance_pos = project.find('data-tab-panel="finance"')
        kpi_pos = project.find("Umsatz (netto)")
        guard_pos = project.rfind("{% if not field_user %}", 0, finance_pos + 1)
        self.assertGreaterEqual(finance_pos, 0)
        self.assertGreaterEqual(kpi_pos, 0)
        self.assertGreaterEqual(guard_pos, 0)
        self.assertLess(guard_pos, finance_pos)
        self.assertLess(guard_pos, kpi_pos)

    def test_room_planner_pro_runtime_and_ai_vision_are_still_installed(self):
        template = (ROOT / "templates/rebuild/room_planner.html").read_text(encoding="utf-8")
        js = (ROOT / "static/js/room-planner.js").read_text(encoding="utf-8")
        views = (ROOT / "erp/room_planner_views.py").read_text(encoding="utf-8")
        for marker in ("data-rp-canvas", "data-rp-open-vision", "data-rp-add-object"):
            self.assertIn(marker, template)
        for marker in ("KAYI_ROOM_PLANNER_PRO", "WebGLRenderer"):
            self.assertIn(marker, js)
        self.assertIn("room_vision", views)

    def test_technician_voice_ai_signature_pdf_flow_survives_final_ui_layers(self):
        appointment = (ROOT / "templates/rebuild/appointment_detail.html").read_text(encoding="utf-8")
        field_home = (ROOT / "templates/rebuild/field_home.html").read_text(encoding="utf-8")
        field_views = (ROOT / "erp/field_authorization_views.py").read_text(encoding="utf-8")
        next_js = (ROOT / "static/js/kayi-next.js").read_text(encoding="utf-8")
        field_js = (ROOT / "static/js/field-authorization.js").read_text(encoding="utf-8")

        self.assertIn("Vor Ort in einem Ablauf", field_home)
        for marker in (
            "data-field-voice",
            "data-field-record",
            "data-field-transcribe",
            "data-customer-reviewed",
            "Kundenunterschrift zum Abschluss",
            "Einsatz abschließen & PDF erstellen",
            "data-handoff-result",
        ):
            self.assertIn(marker, appointment)
        for marker in ("KAYI_FINAL_CUSTOMER_HANDOFF", "field_voice_note", "customer_reviewed"):
            self.assertIn(marker, field_views)
        for marker in ("KAYIFieldHandoff", "MediaRecorder", "data-field-voice"):
            self.assertIn(marker, next_js)
        self.assertIn("KAYIFieldHandoff?.showResult", field_js)

    def test_technician_primary_3d_link_uses_same_pro_planner(self):
        appointment = (ROOT / "templates/rebuild/appointment_detail.html").read_text(encoding="utf-8")
        self.assertNotIn("{% url 'configurator' %}?project={{ event.project.pk }}", appointment)
        self.assertNotIn('{% url "configurator" %}?project={{ event.project.pk }}', appointment)
        if "Aufmaß & 3D" in appointment or "Raum & 3D" in appointment:
            self.assertIn("next-room-planner", appointment)
''',
    )


def guard_existing_tests() -> None:
    required_tests = [
        "tests/test_room_planner_pro.py",
        "tests/test_global_ai_field_handoff.py",
        "tests/test_android_voice_capture_hotfix.py",
        "tests/test_ai_role_permissions.py",
        "tests/test_technician_project_approval_flow.py",
        "tests/test_tooltime_appointment_field_bridge_contract.py",
        "tests/test_tooltime_appointment_process_parity.py",
    ]
    missing = [rel for rel in required_tests if not (ROOT / rel).exists()]
    if missing:
        raise RuntimeError(f"Critical regression suites disappeared from final assembly: {missing}")

    smoke = read("scripts/production_browser_smoke.py")
    for marker in (
        "KAYI Room Planner Pro browser smoke",
        "run_field_surface",
        "technician root did not redirect to /field/",
        "global KAYI KI assistant",
    ):
        if marker not in smoke:
            raise RuntimeError(f"Production browser smoke lost critical coverage: {marker}")


def main() -> None:
    restore_room_planner_routes()
    restore_project_detail_contracts()
    install_regression_test()
    guard_existing_tests()
    test_source = read("tests/test_final_room_planner_field_flow_guard.py")
    compile(test_source, str(ROOT / "tests/test_final_room_planner_field_flow_guard.py"), "exec")
    print(f"{MARKER}: Room Planner Pro, technician voice/KI/signature/PDF and regression coverage preserved.")


if __name__ == "__main__":
    main()
