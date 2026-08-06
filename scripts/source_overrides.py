from pathlib import Path
import base64
import gzip
import hashlib
import re
import shutil
import subprocess


def replace_exact(path: str, old: str, new: str) -> None:
    target = Path(path)
    text = target.read_text(encoding="utf-8")
    if new in text:
        return
    if old not in text:
        raise RuntimeError(f"Expected source fragment not found in {path}")
    target.write_text(text.replace(old, new), encoding="utf-8")


def replace_regex(path: str, pattern: str, replacement: str) -> None:
    target = Path(path)
    text = target.read_text(encoding="utf-8")
    if replacement in text:
        return
    updated, count = re.subn(pattern, replacement, text)
    if count != 1:
        raise RuntimeError(f"Expected one source fragment in {path}, found {count}")
    target.write_text(updated, encoding="utf-8")


def _remove_patch_additions(patch_bytes: bytes) -> None:
    """Remove files introduced by a patch so source assembly is repeatable.

    Text and binary Git patches do not always contain ``--- /dev/null``. Track
    each ``diff --git`` target and its ``new file mode`` marker instead.
    """
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
        return
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
    subprocess.run(
        ["git", "apply", "--whitespace=nowarn", str(patch_path)],
        check=True,
    )


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

apply_verified_patch(
    "scripts/v2_patch",
    "1d6f4e344288e13d6a8eed74d3fc15d45f62b01516beda57baf38c6df7581381",
    "kayi-v2.patch",
    "KAYI v2",
)

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

apply_verified_patch(
    "scripts/ui_parity_patch",
    "0deef073f4f15b1296dec3f651dffdef5341b2d49fb9c5799d5109264eedc195",
    "kayi-ui-parity-room-measurement.patch",
    "KAYI UI parity",
)
apply_verified_patch(
    "scripts/ui_parity_additions",
    "5030cb29157c85f6f9adb2334da4e5d68b786bcbf3c824f04b3b934913eca618",
    "kayi-ui-additions.patch",
    "KAYI UI additions",
)
apply_verified_patch(
    "scripts/workflow_patch",
    "bc8d471e29167f9dd0961b225fdc6cc2a92193967bc0f97c84689a27daf43c1d",
    "kayi-operational-workflow.patch",
    "KAYI operational workflow",
)
apply_verified_patch(
    "scripts/workflow_fix_patch",
    "006bd6da3685306be71d3aa65cefe0c55bd07b4da5340f4ab9cc2b8993de8b9a",
    "kayi-operational-workflow-fix.patch",
    "KAYI operational workflow fix",
)
apply_verified_patch(
    "scripts/workflow_migration_fix_patch",
    "447b62935fe5a0cc3e1f2d8d92c245cc111684e9d79ec6e812e8299b38406530",
    "kayi-workflow-migration-fix.patch",
    "KAYI workflow migration fix",
)
apply_verified_patch(
    "scripts/native_room_scanner_patch",
    "253f05e187a789d8fe59d6a4680e9fa32aae41b27cb3b3d7399fdf24e4766a48",
    "kayi-native-room-scanner.patch",
    "KAYI native room scanner",
)
# Keeps the original native USDZ/OBJ scan immutable while adding editable,
# versioned parametric geometry. Every changed measurement returns to review.
apply_verified_patch(
    "scripts/simplified_room_editor_patch",
    "df8796d5c3ba78236e9a7191b8c2014230973a72976c9e7a2cf3c619d58bc7ff",
    "kayi-simplified-room-editor.patch",
    "KAYI simplified room scan editor",
)
apply_verified_patch(
    "scripts/project_wizard_ai_patch",
    "c7b34e9dbd8efa2ca4d30ffc09c038307d4a96c874384a0038493e3f60502197",
    "kayi-project-wizard-ai.patch",
    "KAYI AI service picker",
)

# Android's java.nio.file.Files implementation does not expose Java 11's
# readString/writeString helpers. Use Java 7 byte APIs so the ARCore plugin
# compiles on Android while preserving UTF-8 payloads.
replace_regex(
    "native/plugins/kayi-room-scanner/android/src/main/java/de/kayihaustechnik/scanner/ArCoreRoomScanActivity.java",
    r"Files\.writeString\(\s*payloadFile\.toPath\(\)\s*,\s*payload\.toString\(2\)\s*\)".replace("\\\\", "\\"),
    "Files.write(payloadFile.toPath(),payload.toString(2).getBytes(java.nio.charset.StandardCharsets.UTF_8))",
)
replace_regex(
    "native/plugins/kayi-room-scanner/android/src/main/java/de/kayihaustechnik/scanner/ArCoreRoomScanActivity.java",
    r"Files\.writeString\(\s*metaFile\.toPath\(\)\s*,\s*meta\.toString\(2\)\s*\)".replace("\\\\", "\\"),
    "Files.write(metaFile.toPath(),meta.toString(2).getBytes(java.nio.charset.StandardCharsets.UTF_8))",
)
replace_regex(
    "native/plugins/kayi-room-scanner/android/src/main/java/de/kayihaustechnik/scanner/KayiRoomScannerPlugin.java",
    r"Files\.readString\(\s*new File\(scan\.payloadPath\)\.toPath\(\)\s*\)".replace("\\\\", "\\"),
    "new String(Files.readAllBytes(new File(scan.payloadPath).toPath()),java.nio.charset.StandardCharsets.UTF_8)",
)
replace_regex(
    "native/plugins/kayi-room-scanner/android/src/main/java/de/kayihaustechnik/scanner/KayiRoomScannerPlugin.java",
    r"Files\.readString\(\s*meta\.toPath\(\)\s*\)".replace("\\\\", "\\"),
    "new String(Files.readAllBytes(meta.toPath()),java.nio.charset.StandardCharsets.UTF_8)",
)
