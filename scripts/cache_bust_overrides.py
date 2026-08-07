from pathlib import Path
import base64
import gzip
import hashlib
import re
import shutil
import subprocess


VERSION = "20260807-1200"
CACHE_NAME = "kayi-shell-v13-20260807"


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
