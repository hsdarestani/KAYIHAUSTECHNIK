from pathlib import Path
import base64
import gzip
import hashlib
import re
import shutil
import subprocess


VERSION = "20260807-1745"
CACHE_NAME = "kayi-shell-v16-20260807"


def _remove_patch_additions(patch_bytes: bytes) -> None:
    current_target: Path | None = None
    additions: list[Path] = []
    for line in patch_bytes.decode("utf-8", errors="replace").splitlines():
        if line.startswith("diff --git a/") and " b/" in line:
            current_target = Path(line.split(" b/", 1)[1])
        elif line.startswith("new file mode ") and current_target is not None:
            additions.append(current_target)
    for target in additions:
        if target.is_symlink() or target.is_file():
            target.unlink()
        elif target.is_dir():
            shutil.rmtree(target)


def apply_verified_patch(directory: str, expected_sha256: str, temp_name: str, label: str) -> None:
    parts = sorted(Path(directory).glob("part*"))
    if not parts:
        raise RuntimeError(f"{label} patch parts are missing")
    payload = base64.b64decode(
        "".join(part.read_text(encoding="utf-8").strip() for part in parts),
        validate=True,
    )
    actual = hashlib.sha256(payload).hexdigest()
    if actual != expected_sha256:
        raise RuntimeError(f"{label} patch integrity check failed: {actual}")
    patch_bytes = gzip.decompress(payload)
    _remove_patch_additions(patch_bytes)
    patch_path = Path("/tmp") / temp_name
    patch_path.write_bytes(patch_bytes)
    subprocess.run(["git", "apply", "--whitespace=nowarn", str(patch_path)], check=True)


def replace_regex(path: str, pattern: str, replacement: str, *, optional: bool = False) -> None:
    target = Path(path)
    if not target.exists():
        if optional:
            return
        raise RuntimeError(f"Cache-busting target does not exist: {path}")
    text = target.read_text(encoding="utf-8")
    if replacement in text:
        return
    updated, count = re.subn(pattern, replacement, text, count=1)
    if count != 1:
        if optional:
            return
        raise RuntimeError(f"Expected one cache-busting source fragment in {path}, found {count}")
    target.write_text(updated, encoding="utf-8")


def replace_text(path: str, old: str, new: str, *, optional: bool = False) -> None:
    target = Path(path)
    if not target.exists():
        if optional:
            return
        raise RuntimeError(f"Text replacement target does not exist: {path}")
    text = target.read_text(encoding="utf-8")
    if new in text:
        return
    if old not in text:
        if optional:
            return
        raise RuntimeError(f"Expected source fragment not found in {path}: {old[:80]!r}")
    target.write_text(text.replace(old, new, 1), encoding="utf-8")


def improve_readability(path: str) -> None:
    """Raise tiny UI copy to a readable floor without enlarging major headings."""
    target = Path(path)
    text = target.read_text(encoding="utf-8")

    def font_floor(match: re.Match[str]) -> str:
        size = float(match.group(1))
        if size < 12:
            return "font-size:12px"
        return match.group(0)

    updated = re.sub(r"font-size:(\d+(?:\.\d+)?)px", font_floor, text)
    updated = re.sub(r"(body\{[^{}]*?font-size:)14px", r"\g<1>15px", updated, count=1)
    updated = re.sub(r"(\.btn\{[^{}]*?font-size:)13px", r"\g<1>14px", updated, count=1)

    # Keep genuinely dense calendar/mobile labels compact, but still substantially
    # larger than the old 7-9 px values.
    updated += (
        "\n/* App-wide readability pass */\n"
        ".mobile-nav a,.calendar-event small,.month-event,.time-axis>div:not(.calendar-corner),"
        ".bar-group>small{font-size:11px}\n"
        ".form-control,input,select,textarea{line-height:1.45}\n"
    )
    target.write_text(updated, encoding="utf-8")


# The source-aware patch fixes app navigation, onboarding, German 3D AI parsing,
# commercial price-list selection, authoritative non-zero B&O prices and the
# compact Angebot & Kalkulation workspace.
apply_verified_patch(
    "scripts/offer_workspace_patch",
    "c0deadf1bfce45824bb0bc0295a4cf1558bd7d41edb863c9f86e1a8fc13fc651",
    "kayi-app-ux-pricing.patch",
    "KAYI app UX and pricing",
)

# Keep the web project's URL names distinct from DRF's generated API routes so
# every in-app project link resolves to /projects/<id>/ rather than the browser API.
apply_verified_patch(
    "scripts/app_ux_pricing_fix_patch",
    "8eacfc7daadda6ffe959a2671df552c5ba9152520251c5fe97df487851ed8f78",
    "kayi-app-ux-pricing-fix.patch",
    "KAYI project route fix",
)

# Refine the live project flow after the pricing data is present: render true
# front-wall openings in 3D, resolve wizard totals against the selected
# commercial price source, expose quote PDFs directly, and replace the crowded
# price-library side rails with a compact top selector and full-width results.
apply_verified_patch(
    "scripts/angebot_prices_3d_patch",
    "fed44d6fe2c16ee4ae590f172e821fce2802d7be11509b41df1b9863cb2cc444",
    "kayi-angebot-prices-3d.patch",
    "KAYI Angebot, prices and 3D refinement",
)
apply_verified_patch(
    "scripts/angebot_prices_3d_test_fix_patch",
    "6ff42e96db83e511e597a5e4773fa6364c5e08df322d18b03a0554941c4bd163",
    "kayi-angebot-prices-3d-test-fix.patch",
    "KAYI Angebot PDF regression test fix",
)

# Step 5 now loads the real positions of the selected commercial price list
# instead of generic zero-priced catalog placeholders. This patch also adds an
# idempotent customer-register importer that matches existing customers by K-Nr.
apply_verified_patch(
    "scripts/wizard_live_prices_customer_import_patch",
    "24fddb1c5baad12e9d41a9d7b037e8d7f943d384fda57a015e7cbe9ac63d9245",
    "kayi-wizard-live-prices-customer-import.patch",
    "KAYI wizard live prices and customer import",
)

# Keep every AI surface operational when a configured model requires
# account verification, and make frontend failures proxy-safe.
apply_verified_patch(
    "scripts/ai_provider_resilience_patch",
    "1d09e3ee28a843282f642561bab3641a760a372f5f939e0dc2e902b01813e57e",
    "kayi-ai-provider-resilience.patch",
    "KAYI AI provider resilience",
)

# Readability is deliberately enforced after all feature patches so every app
# surface, including newer wizard/AI controls, inherits the same minimum text size.
improve_readability("static/css/app.css")

# Normalize the compact 3D summary. Model normalization stores Decimal values as
# strings such as "60.000"; showing those raw looks like sixty-thousand in German.
replace_text(
    "static/js/app.js",
    'const decimal = new Intl.NumberFormat("de-DE", {minimumFractionDigits: 2, maximumFractionDigits: 2});',
    'const decimal = new Intl.NumberFormat("de-DE", {minimumFractionDigits: 2, maximumFractionDigits: 2});\n  const compactNumber = new Intl.NumberFormat("de-DE", {maximumFractionDigits: 2});',
)
replace_text(
    "static/js/app.js",
    "setText('[data-model-summary]', `${state.openings.length} Öffnungen · ${state.objects.filter((item) => item.enabled !== false).length} Objekte · ${state.materials.tile_width_cm} × ${state.materials.tile_height_cm} cm`);",
    "setText('[data-model-summary]', `${state.openings.length} Öffnungen · ${state.objects.filter((item) => item.enabled !== false).length} Objekte · ${compactNumber.format(numberValue(state.materials.tile_width_cm))} × ${compactNumber.format(numberValue(state.materials.tile_height_cm))} cm`);",
)

# Defensive German labels in case an older wizard fragment is ever reintroduced.
replace_text(
    "templates/erp/project_wizard.html",
    "✦ Automatically analyze photos",
    "✦ Fotos automatisch auswerten",
    optional=True,
)
replace_text(
    "templates/erp/project_wizard.html",
    "✦ Adapt model with AI",
    "✦ Modell mit KI anpassen",
    optional=True,
)

# Every release asset receives a new URL so matching markup, CSS and JavaScript
# are loaded immediately in browsers and installed PWAs.
replace_regex(
    "templates/erp/base.html",
    r'href="\{% static \'css/app\.css\' %\}(?:\?v=[^"]*)?"',
    f'href="{{% static \'css/app.css\' %}}?v={VERSION}"',
)
replace_regex(
    "templates/erp/base.html",
    r'src="\{% static \'js/app\.js\' %\}(?:\?v=[^"]*)?"',
    f'src="{{% static \'js/app.js\' %}}?v={VERSION}"',
)
replace_regex(
    "templates/erp/quote_sign.html",
    r'href="\{% static \'css/app\.css\' %\}(?:\?v=[^"]*)?"',
    f'href="{{% static \'css/app.css\' %}}?v={VERSION}"',
    optional=True,
)

# Force iOS and Android PWAs to revalidate the worker instead of reusing an old
# app shell from the browser cache.
replace_regex(
    "static/js/app.js",
    r'navigator\.serviceWorker\.register\("/sw\.js(?:\?v=[^"]*)?",\s*\{[^}]*scope:\s*"/"[^}]*\}\)\.catch\(\(\)\s*=>\s*\{\}\)',
    f'navigator.serviceWorker.register("/sw.js?v={VERSION}", {{scope: "/", updateViaCache: "none"}}).then((registration) => registration.update()).catch(() => {{}})',
)

replace_regex(
    "static/js/sw.js",
    r'const CACHE = "[^"]+";',
    f'const CACHE = "{CACHE_NAME}";',
)
replace_regex(
    "static/js/sw.js",
    r'const ASSETS = \[[^\n]+\];',
    f'const ASSETS = ["/static/css/app.css?v={VERSION}", "/static/js/app.js?v={VERSION}", "/static/manifest.webmanifest", "/privacy/", "/terms/"];',
)
