from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
IMPL = ROOT / "scripts" / "install_owner_pricing_commercial_ai_safety.py"
LEGACY_SCOPE_FILES = (
    ROOT / "erp" / "ai_scope_catalog.py",
    ROOT / "erp" / "ai_scope_planner.py",
)


def _current_runtime_price_library() -> None:
    """Expose the already-supported Price Library in the current rebuild Settings UI.

    The current assembled runtime already has the production Price Library and its
    upload workflow. The older PR106 installer targets retired scope-planner files,
    so on this runtime we only bridge the existing Price Library into the newer
    Settings surface instead of replaying obsolete source patches.
    """
    price_template = ROOT / "templates" / "erp" / "price_library.html"
    settings_template = ROOT / "templates" / "rebuild" / "settings.html"

    if not price_template.exists():
        raise RuntimeError("Current Price Library template is missing")
    price_text = price_template.read_text(encoding="utf-8")
    if "Preisliste importieren" not in price_text:
        raise RuntimeError("Current Price Library no longer exposes the import workflow")

    route_found = False
    for path in (ROOT / "erp").rglob("*.py"):
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        if "price-library" in text:
            route_found = True
            break
    if not route_found:
        raise RuntimeError("Current Price Library route is missing")

    if not settings_template.exists():
        raise RuntimeError("Rebuild Settings template is missing")
    settings = settings_template.read_text(encoding="utf-8")
    marker = "CURRENT_PRICE_LIBRARY_SETTINGS_BRIDGE_20260818"
    if marker not in settings:
        card = f'''\n<!-- {marker} -->\n<section class="nx-card nx-card-pad" style="margin-top:16px">\n  <div class="nx-card-head" style="padding:0">\n    <div>\n      <div class="nx-kicker">Kalkulation</div>\n      <h2>Eigene Preislisten</h2>\n      <p>Firmenpreislisten importieren, durchsuchen und für Kalkulation, Angebote und Rechnungen verwenden.</p>\n    </div>\n    <a class="nx-btn nx-btn-primary" href="{{% url 'price-library' %}}">Preislisten verwalten →</a>\n  </div>\n</section>\n'''
        if "{% endblock %}" not in settings:
            raise RuntimeError("Rebuild Settings endblock anchor changed")
        settings = settings.replace("{% endblock %}", card + "{% endblock %}", 1)
        settings_template.write_text(settings, encoding="utf-8")

    verify = settings_template.read_text(encoding="utf-8")
    if marker not in verify or "{% url 'price-library' %}" not in verify:
        raise RuntimeError("Price Library Settings bridge was not installed")
    print("A+Bau current Price Library exposed in rebuild Settings; existing import workflow reused.")


def _legacy_owner_workflow() -> None:
    spec = importlib.util.spec_from_file_location("ab_owner_workflow_impl", IMPL)
    if spec is None or spec.loader is None:
        raise RuntimeError("Could not load owner workflow installer")
    impl = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(impl)
    impl.main()


if all(path.exists() for path in LEGACY_SCOPE_FILES):
    _legacy_owner_workflow()
else:
    _current_runtime_price_library()
