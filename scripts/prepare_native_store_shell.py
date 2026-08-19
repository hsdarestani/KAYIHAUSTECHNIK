from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NATIVE = ROOT / "native"
CONFIG = NATIVE / "capacitor.config.ts"
PACKAGE = NATIVE / "package.json"
INDEX = NATIVE / "www" / "index.html"
APP_JS = NATIVE / "www" / "app.js"
BUILD_SCRIPT = NATIVE / "scripts" / "build.mjs"


def replace_required(path: Path, old: str, new: str) -> None:
    if not path.exists():
        raise RuntimeError(f"Native release source is missing: {path.relative_to(ROOT)}")
    text = path.read_text(encoding="utf-8")
    if old in text:
        text = text.replace(old, new)
        path.write_text(text, encoding="utf-8")
    elif new not in text:
        raise RuntimeError(f"Expected native release marker is missing in {path.relative_to(ROOT)}: {old!r}")


def main() -> None:
    if not NATIVE.exists():
        raise RuntimeError("Assembled native source is missing")

    replace_required(CONFIG, "appName: 'KAYI Haustechnik'", "appName: 'A+Bau'")
    replace_required(INDEX, "<title>KAYI Haustechnik</title>", "<title>A+Bau</title>")
    replace_required(INDEX, '<div class="logo">K</div><h1>KAYI Haustechnik</h1><p>Natives Baustellen-Aufmaß</p>', '<div class="logo">A+</div><h1>A+Bau</h1><p>Baustellenmanagement wird geladen …</p>')
    replace_required(INDEX, 'src="app.js"', 'src="app.bundle.js"')

    # The original native build guard was itself pinned to the legacy visible brand.
    # Keep the integrity check, but make A+Bau the required release-shell marker.
    replace_required(BUILD_SCRIPT, "KAYI Haustechnik", "A+Bau")

    if APP_JS.exists():
        text = APP_JS.read_text(encoding="utf-8")
        text = text.replace('<div class="logo">K</div><h1>KAYI Haustechnik</h1><p>RoomPlan · LiDAR · ARCore Depth</p>', '<div class="logo">A+</div><h1>A+Bau</h1><p>Baustelle · Aufmaß · Dokumentation</p>')
        text = text.replace("KAYI Haustechnik", "A+Bau")
        APP_JS.write_text(text, encoding="utf-8")

    if PACKAGE.exists():
        package = json.loads(PACKAGE.read_text(encoding="utf-8"))
        package["version"] = "2.2.1"
        dev_dependencies = dict(package.get("devDependencies") or {})
        dev_dependencies["esbuild"] = "^0.25.0"
        package["devDependencies"] = dev_dependencies
        scripts = dict(package.get("scripts") or {})
        # build.mjs validates the source shell; esbuild then resolves @capacitor/core
        # into a browser-executable module. Delete the raw source so Capacitor cannot
        # accidentally package the broken bare import again.
        scripts["build"] = (
            "node scripts/build.mjs && "
            "esbuild www/app.js --bundle --format=esm --platform=browser --target=es2020 "
            "--outfile=www/app.bundle.js && rm www/app.js"
        )
        package["scripts"] = scripts
        PACKAGE.write_text(json.dumps(package, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    config = CONFIG.read_text(encoding="utf-8")
    if "appId: 'de.kayihaustechnik.app'" not in config or "appName: 'A+Bau'" not in config:
        raise RuntimeError("Native Capacitor identity is not the expected A+Bau store identity")

    index = INDEX.read_text(encoding="utf-8")
    if 'src="app.bundle.js"' not in index:
        raise RuntimeError("Native index does not reference the bundled startup JavaScript")

    visible_sources = "\n".join(
        p.read_text(encoding="utf-8", errors="ignore")
        for p in (INDEX, APP_JS)
        if p.exists()
    )
    if "KAYI Haustechnik" in visible_sources or "Natives Baustellen-Aufmaß" in visible_sources:
        raise RuntimeError("Legacy KAYI splash/visible product name remains in the native store shell")

    print("A+Bau native store shell prepared: A+Bau branding + esbuild startup bundle configured.")


if __name__ == "__main__":
    main()
