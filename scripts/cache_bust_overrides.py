from pathlib import Path
import base64
import gzip
import hashlib
import re
import shutil
import subprocess


VERSION = "20260807-0245"
CACHE_NAME = "kayi-shell-v11-20260807"


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


# One source-aware patch completes the B&O workflow end to end: the selected
# insurance price list powers the project wizard and the central Angebot &
# Kalkulation workspace, while AI can only select authoritative database items.
apply_verified_patch(
    "scripts/offer_workspace_patch",
    "84180dd5b9c2c0688882e989bd4cbbe2fc364593032a39c8e0dcfb85d71407d9",
    "kayi-offer-workspace.patch",
    "KAYI Angebot & Kalkulation workspace",
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
# project wizard shell from the browser cache.
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
