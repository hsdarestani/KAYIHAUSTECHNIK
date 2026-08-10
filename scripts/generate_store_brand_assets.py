#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
STORE = ROOT / "store" / "generated"

BG = (244, 242, 255, 255)
INK = (27, 28, 38, 255)
PURPLE = (105, 85, 226, 255)
SOFT = (225, 220, 255, 255)
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


def sparkle(draw: ImageDraw.ImageDraw, cx: float, cy: float, radius: float, fill=PURPLE):
    # KAYI's simple four-point vision mark; symmetrical and legible at launcher sizes.
    points = [
        (cx, cy - radius),
        (cx + radius * 0.23, cy - radius * 0.23),
        (cx + radius, cy),
        (cx + radius * 0.23, cy + radius * 0.23),
        (cx, cy + radius),
        (cx - radius * 0.23, cy + radius * 0.23),
        (cx - radius, cy),
        (cx - radius * 0.23, cy - radius * 0.23),
    ]
    draw.polygon(points, fill=fill)


def icon(size: int, destination: Path, transparent: bool = False):
    base = Image.new("RGBA", (size, size), (0, 0, 0, 0) if transparent else BG)
    d = ImageDraw.Draw(base)
    pad = int(size * 0.16)
    if transparent:
        d.rounded_rectangle((pad, pad, size - pad, size - pad), radius=int(size * 0.15), fill=BG)
    # soft halo helps the mark survive masks without looking like a copied store glyph.
    halo = int(size * 0.18)
    d.ellipse((size // 2 - halo, size // 2 - halo, size // 2 + halo, size // 2 + halo), fill=SOFT)
    sparkle(d, size / 2, size / 2, size * 0.205)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.suffix.lower() == ".jpg":
        base.convert("RGB").save(destination, quality=95)
    else:
        base.save(destination, optimize=True)


def feature_graphic(destination: Path):
    image = Image.new("RGB", (1024, 500), BG[:3])
    d = ImageDraw.Draw(image)
    d.rounded_rectangle((72, 86, 300, 414), radius=54, fill=WHITE[:3])
    d.ellipse((130, 144, 242, 256), fill=SOFT[:3])
    sparkle(d, 186, 200, 66, fill=PURPLE[:3])
    d.text((350, 135), "KAYI Haustechnik", font=font(52, True), fill=INK[:3])
    d.text((350, 220), "Aufträge · Doku · 3D-Aufmaß", font=font(29, False), fill=INK[:3])
    d.text((350, 278), "Büro und Baustelle in einem Ablauf", font=font(23, False), fill=(77, 78, 90))
    destination.parent.mkdir(parents=True, exist_ok=True)
    image.save(destination, optimize=True)


def android_launcher(native: Path):
    res = native / "android" / "app" / "src" / "main" / "res"
    densities = {"mdpi": 48, "hdpi": 72, "xhdpi": 96, "xxhdpi": 144, "xxxhdpi": 192}
    for density, size in densities.items():
        folder = res / f"mipmap-{density}"
        for name in ("ic_launcher.png", "ic_launcher_round.png"):
            icon(size, folder / name)
        # Capacitor templates may reference a separate adaptive foreground.
        if (folder / "ic_launcher_foreground.png").exists():
            icon(size, folder / "ic_launcher_foreground.png", transparent=True)

    # Android 13+ themed icon when adaptive launcher XML uses a monochrome layer.
    for folder in res.glob("mipmap-*"):
        mono = folder / "ic_launcher_monochrome.png"
        if mono.exists():
            icon(Image.open(mono).size[0], mono, transparent=True)


def ios_app_icon(native: Path):
    appicon = native / "ios" / "App" / "App" / "Assets.xcassets" / "AppIcon.appiconset"
    contents = appicon / "Contents.json"
    if not contents.exists():
        raise RuntimeError(f"Missing iOS AppIcon catalog: {contents}")
    data = json.loads(contents.read_text(encoding="utf-8"))
    generated = set()
    for entry in data.get("images", []):
        filename = entry.get("filename")
        if not filename:
            # Xcode 26 templates can omit filenames. Give deterministic names.
            idiom = entry.get("idiom", "universal").replace("-", "_")
            size_label = entry.get("size", "1024x1024").replace(".", "_").replace("x", "x")
            scale_label = entry.get("scale", "1x")
            filename = f"KAYI-{idiom}-{size_label}-{scale_label}.png"
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


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--native", action="store_true", help="also replace generated Android/iOS launcher icons")
    args = parser.parse_args()

    STORE.mkdir(parents=True, exist_ok=True)
    icon(512, STORE / "google-play-icon-512.png")
    icon(1024, STORE / "app-store-icon-1024.png")
    feature_graphic(STORE / "google-play-feature-graphic-1024x500.png")

    if args.native:
        android_launcher(ROOT / "native")
        ios_app_icon(ROOT / "native")

    print(f"KAYI store brand assets generated in {STORE}")


if __name__ == "__main__":
    main()
