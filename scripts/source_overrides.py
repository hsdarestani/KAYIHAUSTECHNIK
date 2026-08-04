from pathlib import Path


def replace_exact(path: str, old: str, new: str) -> None:
    target = Path(path)
    text = target.read_text(encoding="utf-8")
    if new in text:
        return
    if old not in text:
        raise RuntimeError(f"Expected source fragment not found in {path}")
    target.write_text(text.replace(old, new), encoding="utf-8")


replace_exact(
    "erp/models.py",
    '    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="objects")\n'
    '    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name="objects")',
    '    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="object_locations")\n'
    '    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name="object_locations")',
)

replace_exact(
    "Dockerfile",
    "COPY . .\nRUN useradd --create-home --uid 10001 appuser",
    "COPY . .\nRUN python manage.py makemigrations erp --noinput\nRUN useradd --create-home --uid 10001 appuser",
)


# Apply the verified KAYI v2 feature patch after the immutable base source is assembled.
import base64
import gzip
import hashlib
import subprocess

PATCH_SHA256 = "1d6f4e344288e13d6a8eed74d3fc15d45f62b01516beda57baf38c6df7581381"
patch_parts = sorted(Path("scripts/v2_patch").glob("part*"))
if patch_parts:
    payload = base64.b64decode(
        "".join(part.read_text(encoding="utf-8").strip() for part in patch_parts),
        validate=True,
    )
    if hashlib.sha256(payload).hexdigest() != PATCH_SHA256:
        raise RuntimeError("KAYI v2 patch integrity check failed")
    patch_path = Path("/tmp/kayi-v2.patch")
    patch_path.write_bytes(gzip.decompress(payload))
    subprocess.run(
        ["git", "apply", "--whitespace=nowarn", str(patch_path)],
        check=True,
    )

# Keep sensitive pricing payload outside the public source tree while installing
# its importer and tests into the assembled Django application.
reference_command = Path("scripts/reference_seed/import_normalized_prices.py")
if reference_command.exists():
    target = Path("erp/management/commands/import_normalized_prices.py")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(reference_command.read_text(encoding="utf-8"), encoding="utf-8")
reference_test = Path("scripts/reference_seed/test_normalized_prices.py")
if reference_test.exists():
    target = Path("tests/test_normalized_prices.py")
    target.write_text(reference_test.read_text(encoding="utf-8"), encoding="utf-8")
