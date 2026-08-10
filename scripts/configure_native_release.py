#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import plistlib
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NATIVE = ROOT / "native"
DESUGAR_DEP = "coreLibraryDesugaring 'com.android.tools:desugar_jdk_libs:2.0.3'"


def _enable_android_desugaring(path: Path) -> None:
    if not path.exists():
        raise RuntimeError(f"Android Gradle file missing: {path}")
    text = path.read_text(encoding="utf-8")
    if "coreLibraryDesugaringEnabled true" not in text:
        compile_options = re.search(r"compileOptions\s*\{", text)
        if compile_options:
            pos = compile_options.end()
            text = text[:pos] + "\n        coreLibraryDesugaringEnabled true" + text[pos:]
        else:
            android_block = re.search(r"android\s*\{", text)
            if not android_block:
                raise RuntimeError(f"Could not find android block in {path}")
            pos = android_block.end()
            text = text[:pos] + "\n    compileOptions {\n        coreLibraryDesugaringEnabled true\n        sourceCompatibility JavaVersion.VERSION_1_8\n        targetCompatibility JavaVersion.VERSION_1_8\n    }" + text[pos:]
    if DESUGAR_DEP not in text:
        # Library Gradle files commonly have a buildscript.dependencies block
        # before the actual module dependencies. coreLibraryDesugaring belongs to
        # the Android module configuration, so use the final dependencies block.
        dependencies = list(re.finditer(r"(?m)^\s*dependencies\s*\{", text))
        if dependencies:
            pos = dependencies[-1].end()
            text = text[:pos] + f"\n    {DESUGAR_DEP}" + text[pos:]
        else:
            text += f"\n\ndependencies {{\n    {DESUGAR_DEP}\n}}\n"
    path.write_text(text, encoding="utf-8")


def android(version: str, build: str) -> None:
    app_gradle = NATIVE / "android" / "app" / "build.gradle"
    scanner_gradle = NATIVE / "plugins" / "kayi-room-scanner" / "android" / "build.gradle"
    manifest = NATIVE / "android" / "app" / "src" / "main" / "AndroidManifest.xml"
    if not app_gradle.exists() or not manifest.exists():
        raise SystemExit("Android project is not generated. Run `npx cap add android && npx cap sync android` first.")

    # java.time is used by the ARCore scanner while KAYI intentionally keeps
    # Android 7+ support (minSdk 24). Enable official core-library desugaring in
    # both the app and the library module so isolated library lint also sees it.
    _enable_android_desugaring(app_gradle)
    _enable_android_desugaring(scanner_gradle)

    text = app_gradle.read_text(encoding="utf-8")
    text = re.sub(r"versionCode\s+\d+", f"versionCode {int(build)}", text, count=1)
    text = re.sub(r'versionName\s+"[^"]+"', f'versionName "{version}"', text, count=1)

    keystore = os.environ.get("KAYI_ANDROID_KEYSTORE", "").strip()
    if keystore and Path(keystore).exists() and "KAYI_RELEASE_SIGNING" not in text:
        signing = '''\n    // KAYI_RELEASE_SIGNING - values are supplied only by the protected CI environment.\n    signingConfigs {\n        release {\n            storeFile file(System.getenv("KAYI_ANDROID_KEYSTORE"))\n            storePassword System.getenv("KAYI_ANDROID_KEYSTORE_PASSWORD")\n            keyAlias System.getenv("KAYI_ANDROID_KEY_ALIAS")\n            keyPassword System.getenv("KAYI_ANDROID_KEY_PASSWORD")\n        }\n    }\n'''
        text = text.replace("    buildTypes {", signing + "    buildTypes {", 1)
        release_marker = "        release {"
        text = text.replace(release_marker, release_marker + "\n            signingConfig signingConfigs.release", 1)
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
    print(f"Android release configured: {version} ({build}); Java API desugaring enabled for app and room scanner")


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
