from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def write(rel: str, text: str) -> None:
    (ROOT / rel).write_text(text, encoding="utf-8")


def patch_view_branding() -> None:
    path = "erp/rebuild_views.py"
    text = read(path)
    text = text.replace(
        '"""ToolTime-style customer cockpit while keeping KAYI\'s existing data model."""',
        '"""ToolTime-style customer cockpit while keeping A+Bau\'s existing data model."""',
    )
    write(path, text)


def patch_customer_template() -> None:
    path = "templates/rebuild/customer_detail.html"
    text = read(path)

    text = text.replace(
        '<div class="tt-more-head"><h2>Weitere Standorte & Kontakte</h2><a href="?add_object=1#weitere-kontakte" title="Einsatzort hinzufügen">＋</a></div>',
        '<div class="tt-more-head"><h2>Weitere Standorte & Kontakte</h2><a href="?add_object=1#weitere-kontakte" title="Objekt hinzufügen">＋ Objekt hinzufügen</a></div>',
    )
    text = text.replace(
        'Hier lassen sich zusätzliche Adressen oder Einsatzorte für diesen Kunden anlegen.',
        'Standardmäßig wird die Kundenadresse im Projekt verwendet. Zusätzliche Adressen oder Einsatzorte können hier angelegt werden.',
    )
    text = text.replace(
        '<div class="tt-section-title"><h2>Termine <span>· {{ appointments|length }}</span></h2>{% if projects %}<a class="tt-section-action" href="{% url \'next-appointment-create\' %}?project={{ projects.0.pk }}">＋ Termin</a>{% endif %}</div>',
        '<div class="tt-section-title"><h2>Termine <span>· {{ appointments|length }}</span></h2></div>',
    )

    write(path, text)


def patch_css() -> None:
    candidates = [ROOT / "static/css/kayi-readability.css", ROOT / "static/css/kayi-next.css"]
    path = next((candidate for candidate in candidates if candidate.exists()), None)
    if path is None:
        return
    text = path.read_text(encoding="utf-8")
    text = text.replace(
        '.tt-more-head>a{display:grid;place-items:center;width:30px;height:30px;border-radius:7px;color:#264d70;text-decoration:none;font-size:23px}',
        '.tt-more-head>a{display:inline-flex;align-items:center;justify-content:center;min-height:30px;padding:5px 8px;border-radius:7px;color:#264d70;text-decoration:none;font-size:11px;font-weight:700;white-space:nowrap}',
    )
    path.write_text(text, encoding="utf-8")


def guard() -> None:
    template = read("templates/rebuild/customer_detail.html")
    views = read("erp/rebuild_views.py")
    for marker in (
        "＋ Objekt hinzufügen",
        "Standardmäßig wird die Kundenadresse",
        'name="action" value="add_location"',
    ):
        if marker not in template:
            raise RuntimeError(f"Customer compatibility marker missing: {marker}")
    if "next-appointment-create" in template:
        raise RuntimeError("Customer detail reintroduced a duplicate local appointment action")
    if "KAYI's existing data model" in views:
        raise RuntimeError("Customer detail reintroduced visible legacy branding in Python strings")


def main() -> None:
    patch_view_branding()
    patch_customer_template()
    patch_css()
    guard()
    print("ToolTime customer detail regression compatibility applied.")


if __name__ == "__main__":
    main()
