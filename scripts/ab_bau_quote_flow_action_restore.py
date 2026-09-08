from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MARKER = "A+BAU QUOTE FLOW ACTION RESTORE 2026-09-08"
VIEW_REL = "erp/tooltime_parity_views.py"
TEMPLATE_REL = "templates/rebuild/quote_detail.html"
CSS_REL = "static/css/tooltime-quote-detail.css"
TEST_REL = "tests/test_ab_bau_quote_flow_action_restore.py"


def read(rel: str) -> str:
    path = ROOT / rel
    if not path.exists():
        raise RuntimeError(f"Quote flow restore target missing: {rel}")
    return path.read_text(encoding="utf-8")


def write(rel: str, text: str) -> None:
    path = ROOT / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def patch_quote_detail_context() -> None:
    text = read(VIEW_REL)
    if f"# {MARKER}" not in text:
        old = '    return render(request, "rebuild/quote_detail.html", _quote_detail_context(quote, meta))\n'
        new = f'''    # {MARKER}\n    context = _quote_detail_context(quote, meta)\n    order_confirmation = None\n    for candidate in m.Document.objects.filter(\n        organization=org,\n        project=quote.project,\n        category="contract",\n    ).order_by("-pk")[:50]:\n        metadata = candidate.metadata or {{}}\n        if metadata.get("kind") == "order_confirmation" and str(metadata.get("quote_id")) == str(quote.pk):\n            order_confirmation = candidate\n            break\n    context["order_confirmation"] = order_confirmation\n    context["existing_invoice"] = m.Invoice.objects.filter(organization=org, quote=quote).order_by("pk").first()\n    return render(request, "rebuild/quote_detail.html", context)\n'''
        if old not in text:
            raise RuntimeError("Quote detail render anchor missing")
        text = text.replace(old, new, 1)

    # The first click should create the confirmation and immediately return to the
    # accepted quote so the next lifecycle action becomes visible. Existing callers
    # keep the historical create-and-download behaviour unless they opt into return=1.
    redirect_marker = 'request.GET.get("return") == "1"'
    if redirect_marker not in text:
        old = '        if created:\n            messages.success(request, "Auftragsbestätigung wurde erstellt und revisionssicher im Projekt gespeichert.")\n'
        new = old + '            if request.GET.get("return") == "1":\n                return redirect("next-quote-edit", pk=quote.pk)\n'
        if old not in text:
            raise RuntimeError("Order-confirmation creation success anchor missing")
        text = text.replace(old, new, 1)

    write(VIEW_REL, text)
    compile(text, str(ROOT / VIEW_REL), "exec")


def patch_quote_detail_template() -> None:
    text = read(TEMPLATE_REL)

    old_head = '''    <div class="ttqd-head-actions"><a class="nx-btn" href="{% url 'next-quote-pdf' quote.pk %}">PDF herunterladen</a>{% if quote.status != 'accepted' %}<form method="post" action="{% url 'next-quote-status' quote.pk %}">{% csrf_token %}<button class="nx-btn nx-btn-accent" name="action" value="accepted">Als angenommen markieren</button></form>{% endif %}</div>'''
    new_head = '''    <div class="ttqd-head-actions" data-quote-flow-actions>
      <a class="nx-btn" href="{% url 'next-quote-pdf' quote.pk %}">PDF herunterladen</a>
      {% if quote.status == 'accepted' %}
        {% if order_confirmation %}
          <form method="post" action="{% url 'next-quote-order-confirmation' quote.pk %}" data-quote-flow-order-confirmation>{% csrf_token %}<button class="nx-btn" type="submit">Auftragsbestätigung herunterladen</button></form>
          <form method="post" action="{% url 'next-quote-to-invoice' quote.pk %}" data-quote-flow-invoice>{% csrf_token %}<button class="nx-btn nx-btn-accent" type="submit">{% if existing_invoice %}Rechnung öffnen{% else %}In Rechnung übernehmen{% endif %}</button></form>
        {% else %}
          <form method="post" action="{% url 'next-quote-order-confirmation' quote.pk %}?return=1" data-quote-flow-order-confirmation>{% csrf_token %}<button class="nx-btn nx-btn-accent" type="submit">Auftragsbestätigung erstellen</button></form>
        {% endif %}
      {% else %}
        <form method="post" action="{% url 'next-quote-status' quote.pk %}">{% csrf_token %}<button class="nx-btn nx-btn-accent" name="action" value="accepted">Als angenommen markieren</button></form>
      {% endif %}
    </div>'''
    if 'data-quote-flow-actions' not in text:
        if old_head not in text:
            raise RuntimeError("Quote detail header action anchor missing")
        text = text.replace(old_head, new_head, 1)

    old_actions = '''      <section class="ttqd-card"><span class="ttqd-eyebrow">Aktionen</span><div class="ttqd-action-stack">{% if quote.status != 'accepted' and quote.status != 'rejected' %}<form method="post" action="{% url 'next-quote-status' quote.pk %}">{% csrf_token %}<button class="nx-btn" name="action" value="rejected">Als abgelehnt markieren</button></form>{% endif %}{% if quote.status == 'rejected' %}<form method="post" action="{% url 'next-quote-status' quote.pk %}">{% csrf_token %}<button class="nx-btn" name="action" value="pending">Status zurücksetzen</button></form>{% endif %}<form method="post" action="{% url 'next-quote-to-invoice' quote.pk %}">{% csrf_token %}<button class="nx-btn nx-btn-accent" type="submit">In Rechnung übernehmen</button></form></div></section>'''
    new_actions = '''      <section class="ttqd-card"><span class="ttqd-eyebrow">Aktionen</span><div class="ttqd-action-stack" data-quote-flow-sidebar>
        {% if quote.status == 'accepted' %}
          {% if order_confirmation %}
            <div class="ttqd-flow-state"><strong>Auftragsbestätigung erstellt</strong><span>Der Auftrag ist bestätigt. Als Nächstes kann die Rechnung erstellt werden.</span></div>
            <form method="post" action="{% url 'next-quote-order-confirmation' quote.pk %}" data-quote-flow-order-confirmation>{% csrf_token %}<button class="nx-btn" type="submit">Auftragsbestätigung herunterladen</button></form>
            <form method="post" action="{% url 'next-quote-to-invoice' quote.pk %}" data-quote-flow-invoice>{% csrf_token %}<button class="nx-btn nx-btn-accent" type="submit">{% if existing_invoice %}Rechnung öffnen{% else %}In Rechnung übernehmen{% endif %}</button></form>
          {% else %}
            <div class="ttqd-flow-state"><strong>Nächster Schritt: Auftragsbestätigung</strong><span>Nach der Annahme muss zuerst die Auftragsbestätigung erstellt werden. Danach wird die Rechnungsaktion freigeschaltet.</span></div>
            <form method="post" action="{% url 'next-quote-order-confirmation' quote.pk %}?return=1" data-quote-flow-order-confirmation>{% csrf_token %}<button class="nx-btn nx-btn-accent" type="submit">Auftragsbestätigung erstellen</button></form>
          {% endif %}
        {% else %}
          {% if quote.status != 'rejected' %}<form method="post" action="{% url 'next-quote-status' quote.pk %}">{% csrf_token %}<button class="nx-btn" name="action" value="rejected">Als abgelehnt markieren</button></form>{% endif %}
          {% if quote.status == 'rejected' %}<form method="post" action="{% url 'next-quote-status' quote.pk %}">{% csrf_token %}<button class="nx-btn" name="action" value="pending">Status zurücksetzen</button></form>{% endif %}
        {% endif %}
      </div></section>'''
    if 'data-quote-flow-sidebar' not in text:
        if old_actions not in text:
            raise RuntimeError("Quote detail sidebar action anchor missing")
        text = text.replace(old_actions, new_actions, 1)

    write(TEMPLATE_REL, text)


def patch_css() -> None:
    text = read(CSS_REL)
    if ".ttqd-flow-state" not in text:
        text += r'''
/* A+BAU QUOTE FLOW ACTION RESTORE 2026-09-08 */
.ttqd-flow-state{display:grid;gap:4px;padding:11px 12px;border:1px solid #e4ddcc;border-radius:10px;background:#fbf7ed;color:#4c463b}
.ttqd-flow-state strong{font-size:12px;color:#2f2a21}
.ttqd-flow-state span{font-size:12px;line-height:1.45;color:#756b5b}
'''
    write(CSS_REL, text)


def install_test() -> None:
    write(TEST_REL, f'''from pathlib import Path\nfrom django.test import SimpleTestCase\n\nROOT = Path(__file__).resolve().parents[1]\n\n\nclass ABauQuoteFlowActionRestoreTests(SimpleTestCase):\n    def test_postdraft_context_exposes_order_confirmation_and_invoice_state(self):\n        views = (ROOT / "{VIEW_REL}").read_text(encoding="utf-8")\n        for marker in (\n            "{MARKER}",\n            'context["order_confirmation"]',\n            'context["existing_invoice"]',\n            'metadata.get("kind") == "order_confirmation"',\n            'request.GET.get("return") == "1"',\n        ):\n            self.assertIn(marker, views)\n\n    def test_accepted_quote_exposes_confirmation_before_invoice(self):\n        detail = (ROOT / "{TEMPLATE_REL}").read_text(encoding="utf-8")\n        for marker in (\n            "data-quote-flow-actions",\n            "data-quote-flow-sidebar",\n            "next-quote-order-confirmation",\n            "Auftragsbestätigung erstellen",\n            "Auftragsbestätigung herunterladen",\n            "Nächster Schritt: Auftragsbestätigung",\n            "Rechnung öffnen",\n            "In Rechnung übernehmen",\n            "{{% if order_confirmation %}}",\n        ):\n            self.assertIn(marker, detail)\n        self.assertIn("?return=1", detail)\n\n    def test_invoice_action_stays_server_backed_and_conditionally_unlocked(self):\n        detail = (ROOT / "{TEMPLATE_REL}").read_text(encoding="utf-8")\n        self.assertIn("next-quote-to-invoice", detail)\n        self.assertIn("data-quote-flow-invoice", detail)\n        self.assertIn("{{% if existing_invoice %}}Rechnung öffnen{{% else %}}In Rechnung übernehmen{{% endif %}}", detail)\n\n    def test_flow_hint_is_styled(self):\n        css = (ROOT / "{CSS_REL}").read_text(encoding="utf-8")\n        self.assertIn(".ttqd-flow-state", css)\n''')


def guard() -> None:
    views = read(VIEW_REL)
    detail = read(TEMPLATE_REL)
    css = read(CSS_REL)
    for marker in (
        MARKER,
        'context["order_confirmation"]',
        'context["existing_invoice"]',
        'request.GET.get("return") == "1"',
    ):
        if marker not in views:
            raise RuntimeError(f"Quote flow view guard failed: {marker}")
    for marker in (
        "data-quote-flow-actions",
        "data-quote-flow-sidebar",
        "next-quote-order-confirmation",
        "Auftragsbestätigung erstellen",
        "Auftragsbestätigung herunterladen",
        "data-quote-flow-invoice",
        "?return=1",
    ):
        if marker not in detail:
            raise RuntimeError(f"Quote flow template guard failed: {marker}")
    if ".ttqd-flow-state" not in css:
        raise RuntimeError("Quote flow CSS guard failed")


def main() -> None:
    patch_quote_detail_context()
    patch_quote_detail_template()
    patch_css()
    install_test()
    guard()
    print(f"{MARKER}: accepted quotes now lead clearly through Auftragsbestätigung to Rechnung.")


if __name__ == "__main__":
    main()
