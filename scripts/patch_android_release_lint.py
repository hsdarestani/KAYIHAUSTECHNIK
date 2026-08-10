from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCANNER = ROOT / "native" / "plugins" / "kayi-room-scanner" / "android" / "src" / "main" / "java" / "de" / "kayihaustechnik" / "scanner" / "ArCoreRoomScanActivity.java"

if SCANNER.exists():
    text = SCANNER.read_text(encoding="utf-8")
    text = text.replace(
        "instruction.setTypeface(null,1);",
        "instruction.setTypeface(null,android.graphics.Typeface.BOLD);",
    )
    if "instruction.setTypeface(null,1);" in text:
        raise RuntimeError("Android scanner still uses a raw Typeface style constant")
    if "instruction.setTypeface(null,android.graphics.Typeface.BOLD);" not in text:
        raise RuntimeError("Android scanner Typeface lint fix could not be verified")
    SCANNER.write_text(text, encoding="utf-8")

print("KAYI Android scanner release-lint constants verified.")
