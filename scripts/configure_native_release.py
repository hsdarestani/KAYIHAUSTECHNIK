#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import plistlib
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NATIVE = ROOT / "native"


def android(version: str, build: str) -> None:
    app_gradle = NATIVE / "android" / "app" / "build.gradle"
    manifest = NATIVE / "android" / "app" / "src" / "main" / "AndroidManifest.xml"
    if not app_gradle.exists() or not manifest.exists():
        raise SystemExit("Android project is not generated. Run `npx cap add android && npx cap sync android` first.")

    text = app_gradle.read_text(encoding="utf-8")
    text = re.sub(r"versionCode\s+\d+", f"versionCode {int(build)}", text, count=1)
    text = re.sub(r'versionName\s+"[^"]+"', f'versionName "{version}"', text, count=1)

    keystore = os.environ.get("KAYI_ANDROID_KEYSTORE", "").strip()
    if keystore and Path(keystore).exists() and "KAYI_RELEASE_SIGNING" not in text:
        signing = '''
    // KAYI_RELEASE_SIGNING - values are supplied only by the protected CI environment.
    signingConfigs {
        release {
            storeFile file(System.getenv("KAYI_ANDROID_KEYSTORE"))
            storePassword System.getenv("KAYI_ANDROID_KEYSTORE_PASSWORD")
            keyAlias System.getenv("KAYI_ANDROID_KEY_ALIAS")
            keyPassword System.getenv("KAYI_ANDROID_KEY_PASSWORD")
        }
    }
'''
        text = text.replace("    buildTypes {", signing + "    buildTypes {", 1)
        text = text.replace("        release {", "        release {\n            signingConfig signingConfigs.release", 1)
    app_gradle.write_text(text, encoding="utf-8")

    mtext = manifest.read_text(encoding="utf-8")
    if "android.permission.RECORD_AUDIO" not in mtext:
        mtext = mtext.replace(
            '<uses-permission android:name="android.permission.INTERNET" />',
            '<uses-permission android:name="android.permission.INTERNET" />\n    <uses-permission android:name="android.permission.RECORD_AUDIO" />',
            1,
        )
    if "android.hardware.microphone" not in mtext:
        mtext = mtext.replace("<application", '<uses-feature android:name="android.hardware.microphone" android:required="false" />\n\n    <application', 1)
    if "android:usesCleartextTraffic" not in mtext:
        mtext = mtext.replace("<application", '<application android:usesCleartextTraffic="false"', 1)
    manifest.write_text(mtext, encoding="utf-8")
    print(f"Android release configured: {version} ({build}); cleartext disabled and optional microphone declared")


def _add_privacy_manifest_to_xcode(project: Path) -> None:
    text = project.read_text(encoding="utf-8")
    if "PrivacyInfo.xcprivacy in Resources" in text:
        return
    build_id = "4B53544F5245505249563031"
    ref_id = "4B53544F5245505249563032"
    text = text.replace(
        "/* Begin PBXBuildFile section */",
        f"/* Begin PBXBuildFile section */\n\t\t{build_id} /* PrivacyInfo.xcprivacy in Resources */ = {{isa = PBXBuildFile; fileRef = {ref_id} /* PrivacyInfo.xcprivacy */; }};",
        1,
    )
    text = text.replace(
        "/* Begin PBXFileReference section */",
        f"/* Begin PBXFileReference section */\n\t\t{ref_id} /* PrivacyInfo.xcprivacy */ = {{isa = PBXFileReference; lastKnownFileType = text.xml; path = PrivacyInfo.xcprivacy; sourceTree = \"<group>\"; }};",
        1,
    )
    info_ref = re.search(r"(?m)^\s*([A-F0-9]{24}) /\* Info\.plist \*/ = \{isa = PBXFileReference;", text)
    if info_ref:
        child_marker = f"\t\t\t\t{info_ref.group(1)} /* Info.plist */,{chr(10)}"
        if child_marker in text:
            text = text.replace(child_marker, child_marker + f"\t\t\t\t{ref_id} /* PrivacyInfo.xcprivacy */,\n", 1)
    resources = re.search(r"(?s)(/\* Begin PBXResourcesBuildPhase section \*/.*?files = \(\n)(.*?)(\n\s*\);)", text)
    if not resources:
        raise RuntimeError("Could not locate Xcode Resources build phase for PrivacyInfo.xcprivacy")
    insertion = f"\t\t\t\t{build_id} /* PrivacyInfo.xcprivacy in Resources */,\n"
    text = text[:resources.start(2)] + insertion + text[resources.start(2):]
    project.write_text(text, encoding="utf-8")


def _privacy_type(name: str) -> dict[str, object]:
    return {
        "NSPrivacyCollectedDataType": name,
        "NSPrivacyCollectedDataTypeLinked": True,
        "NSPrivacyCollectedDataTypeTracking": False,
        "NSPrivacyCollectedDataTypePurposes": ["NSPrivacyCollectedDataTypePurposeAppFunctionality"],
    }


def ios(version: str, build: str) -> None:
    app_dir = NATIVE / "ios" / "App" / "App"
    plist = app_dir / "Info.plist"
    project = NATIVE / "ios" / "App" / "App.xcodeproj" / "project.pbxproj"
    package = NATIVE / "ios" / "App" / "CapApp-SPM" / "Package.swift"
    if not plist.exists() or not project.exists():
        raise SystemExit("iOS project is not generated. Run `npx cap add ios && npx cap sync ios` first.")

    with plist.open("rb") as fh:
        info = plistlib.load(fh)
    info.update({
        "NSCameraUsageDescription": "KAYI benötigt die Kamera nur, wenn du Fotos aufnimmst oder einen Raumscan aktiv startest.",
        "NSMicrophoneUsageDescription": "KAYI benötigt das Mikrofon nur, wenn du eine Sprachnotiz oder einen Arbeitsbericht aktiv aufnimmst.",
        "ITSAppUsesNonExemptEncryption": False,
    })
    with plist.open("wb") as fh:
        plistlib.dump(info, fh, sort_keys=False)

    collected = [
        "NSPrivacyCollectedDataTypeName",
        "NSPrivacyCollectedDataTypeEmailAddress",
        "NSPrivacyCollectedDataTypePhoneNumber",
        "NSPrivacyCollectedDataTypePhysicalAddress",
        "NSPrivacyCollectedDataTypePaymentInfo",
        "NSPrivacyCollectedDataTypeOtherFinancialInfo",
        "NSPrivacyCollectedDataTypeEmailsOrTextMessages",
        "NSPrivacyCollectedDataTypePhotosorVideos",
        "NSPrivacyCollectedDataTypeAudioData",
        "NSPrivacyCollectedDataTypeOtherUserContent",
        "NSPrivacyCollectedDataTypeUserID",
        "NSPrivacyCollectedDataTypeProductInteraction",
        "NSPrivacyCollectedDataTypeEnvironmentScanning",
    ]
    privacy = {
        "NSPrivacyTracking": False,
        "NSPrivacyTrackingDomains": [],
        "NSPrivacyCollectedDataTypes": [_privacy_type(item) for item in collected],
        "NSPrivacyAccessedAPITypes": [],
    }
    privacy_path = app_dir / "PrivacyInfo.xcprivacy"
    with privacy_path.open("wb") as fh:
        plistlib.dump(privacy, fh, sort_keys=False)

    text = project.read_text(encoding="utf-8")
    text = re.sub(r"MARKETING_VERSION = [^;]+;", f"MARKETING_VERSION = {version};", text)
    text = re.sub(r"CURRENT_PROJECT_VERSION = [^;]+;", f"CURRENT_PROJECT_VERSION = {build};", text)
    text = re.sub(r"IPHONEOS_DEPLOYMENT_TARGET = [^;]+;", "IPHONEOS_DEPLOYMENT_TARGET = 16.0;", text)
    project.write_text(text, encoding="utf-8")
    _add_privacy_manifest_to_xcode(project)

    if package.exists():
        ptext = package.read_text(encoding="utf-8")
        ptext = re.sub(r"\.iOS\(\.v\d+\)", ".iOS(.v16)", ptext)
        package.write_text(ptext, encoding="utf-8")
    print(f"iOS release configured: {version} ({build}), minimum iOS 16.0")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("platform", choices=("android", "ios"))
    parser.add_argument("--version", default=os.environ.get("KAYI_APP_VERSION", "2.2.0"))
    parser.add_argument("--build", default=os.environ.get("KAYI_BUILD_NUMBER", "22001"))
    args = parser.parse_args()
    if args.platform == "android":
        android(args.version, args.build)
    else:
        ios(args.version, args.build)


if __name__ == "__main__":
    main()
