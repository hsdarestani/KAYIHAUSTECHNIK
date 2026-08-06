from pathlib import Path
import base64
import gzip
import hashlib
import re
import shutil
import subprocess


VERSION = "20260806-1930"
CACHE_NAME = "kayi-shell-v7-20260806"


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


def replace_regex(path: str, pattern: str, replacement: str) -> None:
    target = Path(path)
    text = target.read_text(encoding="utf-8")
    if replacement in text:
        return
    updated, count = re.subn(pattern, replacement, text, count=1)
    if count != 1:
        raise RuntimeError(f"Expected one cache-busting source fragment in {path}, found {count}")
    target.write_text(updated, encoding="utf-8")


# Apply the final source-aware B&O pricing integration after all historical
# source patches, then rotate the web/PWA assets that expose the new picker.
apply_verified_patch(
    "scripts/bando_price_source_patch",
    "fa6895dc1434eb6abe9ff47b9269b869aee56d1d37e1688d971de2671d79dc00",
    "kayi-bando-price-source.patch",
    "KAYI B&O price source wizard",
)

# The project wizard HTML was updated while browsers and the PWA worker still
# served an older app.css/app.js. Give every release asset a new URL so the
# matching CSS and JavaScript are loaded with the new markup immediately.
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

# Force the browser to check the new worker script instead of reusing the
# previously cached registration. updateViaCache=none is important on iOS PWA.
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
