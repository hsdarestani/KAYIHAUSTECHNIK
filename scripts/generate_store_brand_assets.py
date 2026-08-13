#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
STORE = ROOT / "store" / "generated"
SOURCE_ICON = ROOT / "branding" / "fav.png"

BG = (13, 14, 16, 255)
INK = (246, 243, 235, 255)
GOLD = (201, 161, 59, 255)
SOFT_GOLD = (235, 213, 151, 255)
MUTED = (166, 168, 173, 255)
WHITE = (255, 255, 255, 255)


def font(size: int, bold: bool = False):
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf" if bold else "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/Library/Fonts/Arial Bold.ttf" if bold else "/Library/Fonts/Arial.ttf",
    ]
    for candidate in candidates:
        p = Path(candidate)
        if p.exists():
            return ImageFont.truetype(str(p), size=size)
    return ImageFont.load_default()


def _source() -> Image.Image:
    if not SOURCE_ICON.exists():
        raise RuntimeError(f"A+Bau source icon is missing: {SOURCE_ICON}")
    with Image.open(SOURCE_ICON) as image:
        return image.convert("RGBA").copy()


def _square_source(size: int, *, transparent_padding: bool = False) -> Image.Image:
    src = _source()
    if transparent_padding:
        canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        inner = max(1, round(size * 0.78))
        resized = src.resize((inner, inner), Image.Resampling.LANCZOS)
        canvas.alpha_composite(resized, ((size - inner) // 2, (size - inner) // 2))
        return canvas
    # App Store icons must be opaque. Composite any transparency onto the brand dark background.
    src = src.resize((size, size), Image.Resampling.LANCZOS)
    canvas = Image.new("RGBA", (size, size), BG)
    canvas.alpha_composite(src)
    return canvas


def icon(size: int, destination: Path, transparent: bool = False):
    base = _square_source(size, transparent_padding=transparent)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.suffix.lower() == ".jpg":
        base.convert("RGB").save(destination, quality=95)
    else:
        if not transparent:
            base = base.convert("RGB")
        base.save(destination, optimize=True)


def feature_graphic(destination: Path):
    image = Image.new("RGB", (1024, 500), BG[:3])
    d = ImageDraw.Draw(image)
    # soft gold ambient shapes
    d.ellipse((720, -180, 1160, 260), fill=(42, 35, 21))
    d.rounded_rectangle((54, 54, 392, 446), radius=54, fill=(21, 22, 24), outline=(75, 62, 31), width=2)
    app_icon = _square_source(286).convert("RGB")
    image.paste(app_icon, (80, 107))
    d.text((440, 112), "A+Bau", font=font(58, True), fill=INK[:3])
    d.text((440, 202), "Alles organisiert. Alles im Griff.", font=font(27, True), fill=SOFT_GOLD[:3])
    d.text((440, 258), "Von der Baustelle bis zur Rechnung.", font=font(24), fill=MUTED[:3])
    d.text((440, 334), "Aufträge · Termine · Doku · Aufmaß · Finanzen", font=font(20), fill=INK[:3])
    destination.parent.mkdir(parents=True, exist_ok=True)
    image.save(destination, optimize=True)


def android_launcher(native: Path) -> bool:
    res = native / "android" / "app" / "src" / "main" / "res"
    if not res.exists():
        return False
    densities = {"mdpi": 48, "hdpi": 72, "xhdpi": 96, "xxhdpi": 144, "xxxhdpi": 192}
    for density, size in densities.items():
        folder = res / f"mipmap-{density}"
        folder.mkdir(parents=True, exist_ok=True)
        for name in ("ic_launcher.png", "ic_launcher_round.png"):
            icon(size, folder / name)
        foreground = folder / "ic_launcher_foreground.png"
        if foreground.exists():
            icon(size, foreground, transparent=True)
    for folder in res.glob("mipmap-*"):
        mono = folder / "ic_launcher_monochrome.png"
        if mono.exists():
            # Keep a safe padded mark for adaptive/monochrome-compatible slots.
            icon(Image.open(mono).size[0], mono, transparent=True)
    return True


def ios_app_icon(native: Path) -> bool:
    appicon = native / "ios" / "App" / "App" / "Assets.xcassets" / "AppIcon.appiconset"
    contents = appicon / "Contents.json"
    if not contents.exists():
        return False
    data = json.loads(contents.read_text(encoding="utf-8"))
    generated = set()
    for entry in data.get("images", []):
        filename = entry.get("filename")
        if not filename:
            idiom = entry.get("idiom", "universal").replace("-", "_")
            size_label = entry.get("size", "1024x1024").replace(".", "_")
            scale_label = entry.get("scale", "1x")
            filename = f"ABau-{idiom}-{size_label}-{scale_label}.png"
            entry["filename"] = filename
        raw = entry.get("size", "1024x1024").split("x")[0]
        scale = int(entry.get("scale", "1x").rstrip("x"))
        pixels = max(1, round(float(raw) * scale))
        if entry.get("idiom") == "ios-marketing":
            pixels = 1024
        icon(pixels, appicon / filename)
        generated.add(filename)
    contents.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    if not generated:
        icon(1024, appicon / "AppIcon-512@2x.png")
    return True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--native", action="store_true", help="replace launcher icons for whichever native platform has already been generated")
    args = parser.parse_args()

    STORE.mkdir(parents=True, exist_ok=True)
    icon(512, STORE / "google-play-icon-512.png")
    icon(1024, STORE / "app-store-icon-1024.png")
    feature_graphic(STORE / "google-play-feature-graphic-1024x500.png")

    generated = []
    if args.native:
        if android_launcher(ROOT / "native"):
            generated.append("Android")
        if ios_app_icon(ROOT / "native"):
            generated.append("iOS")
        if not generated:
            raise RuntimeError("No generated Android or iOS project was found for native launcher assets")

    suffix = f"; native: {', '.join(generated)}" if generated else ""
    print(f"A+Bau store brand assets generated from branding/fav.png in {STORE}{suffix}")


if __name__ == "__main__":
    main()
