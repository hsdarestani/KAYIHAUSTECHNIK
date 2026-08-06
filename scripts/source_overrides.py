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

# Install the production price-library command and its integrity tests only after
# the application source and v2 domain models have been assembled.
reference_command = Path("scripts/reference_seed/import_normalized_prices.py")
if reference_command.exists():
    target = Path("erp/management/commands/import_normalized_prices.py")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(reference_command.read_text(encoding="utf-8"), encoding="utf-8")

reference_test = Path("scripts/reference_seed/test_normalized_prices.py")
if reference_test.exists():
    target = Path("tests/test_normalized_prices.py")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(reference_test.read_text(encoding="utf-8"), encoding="utf-8")

# Apply the verified graphical parity and camera-assisted room measurement release.
UI_PARITY_PATCH_SHA256 = "0deef073f4f15b1296dec3f651dffdef5341b2d49fb9c5799d5109264eedc195"
ui_patch_parts = sorted(Path("scripts/ui_parity_patch").glob("part*"))
if ui_patch_parts:
    ui_payload = base64.b64decode(
        "".join(part.read_text(encoding="utf-8").strip() for part in ui_patch_parts),
        validate=True,
    )
    if hashlib.sha256(ui_payload).hexdigest() != UI_PARITY_PATCH_SHA256:
        raise RuntimeError("KAYI UI parity patch integrity check failed")
    ui_patch_path = Path("/tmp/kayi-ui-parity-room-measurement.patch")
    ui_patch_path.write_bytes(gzip.decompress(ui_payload))
    subprocess.run(
        ["git", "apply", "--whitespace=nowarn", str(ui_patch_path)],
        check=True,
    )

# Add the new migration and graphical templates that are not part of the immutable base tree.
UI_ADDITIONS_PATCH_SHA256 = "5030cb29157c85f6f9adb2334da4e5d68b786bcbf3c824f04b3b934913eca618"
ui_addition_parts = sorted(Path("scripts/ui_parity_additions").glob("part*"))
if ui_addition_parts:
    addition_payload = base64.b64decode(
        "".join(part.read_text(encoding="utf-8").strip() for part in ui_addition_parts),
        validate=True,
    )
    if hashlib.sha256(addition_payload).hexdigest() != UI_ADDITIONS_PATCH_SHA256:
        raise RuntimeError("KAYI UI additions patch integrity check failed")
    additions_patch_path = Path("/tmp/kayi-ui-additions.patch")
    additions_patch_path.write_bytes(gzip.decompress(addition_payload))
    subprocess.run(
        ["git", "apply", "--whitespace=nowarn", str(additions_patch_path)],
        check=True,
    )

# Apply meeting-tested operational workflow release.
WORKFLOW_PATCH_SHA256 = "bc8d471e29167f9dd0961b225fdc6cc2a92193967bc0f97c84689a27daf43c1d"
workflow_patch_parts = sorted(Path("scripts/workflow_patch").glob("part*"))
if workflow_patch_parts:
    workflow_payload = base64.b64decode(
        "".join(part.read_text(encoding="utf-8").strip() for part in workflow_patch_parts),
        validate=True,
    )
    if hashlib.sha256(workflow_payload).hexdigest() != WORKFLOW_PATCH_SHA256:
        raise RuntimeError("KAYI operational workflow patch integrity check failed")
    workflow_patch_path = Path("/tmp/kayi-operational-workflow.patch")
    workflow_patch_path.write_bytes(gzip.decompress(workflow_payload))
    subprocess.run(
        ["git", "apply", "--whitespace=nowarn", str(workflow_patch_path)],
        check=True,
    )

# Apply compatibility fixes found by the full release regression suite.
WORKFLOW_FIX_PATCH_SHA256 = "006bd6da3685306be71d3aa65cefe0c55bd07b4da5340f4ab9cc2b8993de8b9a"
workflow_fix_parts = sorted(Path("scripts/workflow_fix_patch").glob("part*"))
if workflow_fix_parts:
    workflow_fix_payload = base64.b64decode(
        "".join(part.read_text(encoding="utf-8").strip() for part in workflow_fix_parts),
        validate=True,
    )
    if hashlib.sha256(workflow_fix_payload).hexdigest() != WORKFLOW_FIX_PATCH_SHA256:
        raise RuntimeError("KAYI operational workflow fix patch integrity check failed")
    workflow_fix_path = Path("/tmp/kayi-operational-workflow-fix.patch")
    workflow_fix_path.write_bytes(gzip.decompress(workflow_fix_payload))
    subprocess.run(
        ["git", "apply", "--whitespace=nowarn", str(workflow_fix_path)],
        check=True,
    )

# Backfill unique public share tokens safely for existing production price sources.
WORKFLOW_MIGRATION_FIX_PATCH_SHA256 = "447b62935fe5a0cc3e1f2d8d92c245cc111684e9d79ec6e812e8299b38406530"
workflow_migration_fix_parts = sorted(Path("scripts/workflow_migration_fix_patch").glob("part*"))
if workflow_migration_fix_parts:
    workflow_migration_fix_payload = base64.b64decode(
        "".join(part.read_text(encoding="utf-8").strip() for part in workflow_migration_fix_parts),
        validate=True,
    )
    if hashlib.sha256(workflow_migration_fix_payload).hexdigest() != WORKFLOW_MIGRATION_FIX_PATCH_SHA256:
        raise RuntimeError("KAYI workflow migration fix patch integrity check failed")
    workflow_migration_fix_path = Path("/tmp/kayi-workflow-migration-fix.patch")
    workflow_migration_fix_path.write_bytes(gzip.decompress(workflow_migration_fix_payload))
    subprocess.run(
        ["git", "apply", "--whitespace=nowarn", str(workflow_migration_fix_path)],
        check=True,
    )
