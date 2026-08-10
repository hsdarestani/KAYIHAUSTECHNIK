from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "native" / "plugins" / "kayi-room-scanner" / "android"
MANIFEST = PLUGIN / "src" / "main" / "AndroidManifest.xml"
SCANNER = PLUGIN / "src" / "main" / "java" / "de" / "kayihaustechnik" / "scanner" / "ArCoreRoomScanActivity.java"
ANDROID_NS = "http://schemas.android.com/apk/res/android"
NAME = f"{{{ANDROID_NS}}}name"
VALUE = f"{{{ANDROID_NS}}}value"
REQUIRED = f"{{{ANDROID_NS}}}required"
ET.register_namespace("android", ANDROID_NS)

if not MANIFEST.exists() or not SCANNER.exists():
    raise RuntimeError("KAYI ARCore plugin sources are missing")

tree = ET.parse(MANIFEST)
root = tree.getroot()
application = root.find("application")
if application is None:
    raise RuntimeError("KAYI ARCore plugin manifest has no application element")

# KAYI remains usable without a native AR scan, so Play must not filter out
# non-ARCore devices. Remove the AR-required feature gate and declare ARCore as
# an optional enhancement instead.
for feature in list(root.findall("uses-feature")):
    if feature.get(NAME) == "android.hardware.camera.ar":
        root.remove(feature)

metadata = None
for item in application.findall("meta-data"):
    if item.get(NAME) == "com.google.ar.core":
        metadata = item
        break
if metadata is None:
    metadata = ET.SubElement(application, "meta-data")
    metadata.set(NAME, "com.google.ar.core")
metadata.set(VALUE, "optional")

# Camera itself is also optional for the rest of the ERP application. The scan
# flow requests it only when the user launches that feature.
for feature in root.findall("uses-feature"):
    if feature.get(NAME) == "android.hardware.camera":
        feature.set(REQUIRED, "false")

tree.write(MANIFEST, encoding="utf-8", xml_declaration=True)

scanner = SCANNER.read_text(encoding="utf-8")
if "ArCoreApk" not in scanner:
    raise RuntimeError(
        "ARCore is optional in Play but the native scanner does not contain an ArCoreApk availability/install check"
    )

check = ET.parse(MANIFEST).getroot()
app = check.find("application")
values = {
    item.get(VALUE)
    for item in (app.findall("meta-data") if app is not None else [])
    if item.get(NAME) == "com.google.ar.core"
}
if values != {"optional"}:
    raise RuntimeError(f"ARCore optional manifest contract failed: {values}")
if any(item.get(NAME) == "android.hardware.camera.ar" for item in check.findall("uses-feature")):
    raise RuntimeError("AR Required camera feature is still present")

print("KAYI ARCore is Play-optional and native availability/install handling is present.")
