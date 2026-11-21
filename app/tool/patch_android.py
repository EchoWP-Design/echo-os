#!/usr/bin/env python3
"""Passt das von `flutter create` erzeugte Android-Projekt an (läuft in CI, aus app/):

* Manifest: Internet, Heimnetz per HTTP (Pi), Fire-TV-/Android-TV-Start (Leanback),
  Banner, App-Name, Sichtbarkeit der installierten Apps
* MainActivity: Apps auflisten, starten, App-Store öffnen, Fernseher erkennen
* Symbol und Banner aus tool/out (make_assets.py)
* Signatur: android/key.properties + android/app/echo.jks (aus GitHub-Secrets)
"""
import os
import re
import shutil
import sys

from PIL import Image

APP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AND = os.path.join(APP, "android")
MAIN = os.path.join(AND, "app/src/main")
PACKAGE = "de.echowp.echo_app"


def fail(msg):
    print("patch_android: " + msg, file=sys.stderr)
    sys.exit(1)


def patch_manifest():
    path = os.path.join(MAIN, "AndroidManifest.xml")
    s = open(path, encoding="utf-8").read()
    head = (
        '    <uses-permission android:name="android.permission.INTERNET"/>\n'
        '    <uses-feature android:name="android.software.leanback" android:required="false"/>\n'
        '    <uses-feature android:name="android.hardware.touchscreen" android:required="false"/>\n'
    )
    if "android.permission.INTERNET" not in s:
        s = s.replace("    <application", head + "    <application", 1)
    s = re.sub(r'android:label="[^"]*"', 'android:label="Echo"', s, count=1)
    if "android:banner" not in s:
        s = s.replace("<application", '<application\n        android:banner="@drawable/banner"\n'
                      '        android:usesCleartextTraffic="true"', 1)
    launcher = '<category android:name="android.intent.category.LAUNCHER"/>'
    if launcher not in s:
        fail("LAUNCHER-Kategorie im Manifest nicht gefunden")
    if "LEANBACK_LAUNCHER" not in s:
        s = s.replace(launcher, launcher + '\n                <category android:name="android.intent.category.LEANBACK_LAUNCHER"/>', 1)
    queries = (
        '        <intent>\n            <action android:name="android.intent.action.MAIN"/>\n'
        '            <category android:name="android.intent.category.LAUNCHER"/>\n        </intent>\n'
        '        <intent>\n            <action android:name="android.intent.action.MAIN"/>\n'
        '            <category android:name="android.intent.category.LEANBACK_LAUNCHER"/>\n        </intent>\n'
    )
    if "category.LEANBACK_LAUNCHER\"/>\n        </intent>" in s:
        pass  # schon angepasst
    elif "<queries>" in s:
        s = s.replace("<queries>", "<queries>\n" + queries, 1)
    else:
        s = s.replace("</manifest>", "    <queries>\n" + queries + "    </queries>\n</manifest>", 1)
    open(path, "w", encoding="utf-8").write(s)


MAIN_ACTIVITY = """package %s

import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import io.flutter.embedding.android.FlutterActivity
import io.flutter.embedding.engine.FlutterEngine
import io.flutter.plugin.common.MethodChannel

class MainActivity : FlutterActivity() {
    override fun configureFlutterEngine(flutterEngine: FlutterEngine) {
        super.configureFlutterEngine(flutterEngine)
        MethodChannel(flutterEngine.dartExecutor.binaryMessenger, "echoos/apps").setMethodCallHandler { call, result ->
            when (call.method) {
                "installed" -> result.success(installed())
                "launch" -> result.success(launch(call.argument<String>("package") ?: ""))
                "store" -> result.success(store(call.argument<String>("package") ?: ""))
                "isTv" -> result.success(
                    packageManager.hasSystemFeature(PackageManager.FEATURE_LEANBACK) ||
                        packageManager.hasSystemFeature("amazon.hardware.fire_tv")
                )
                else -> result.notImplemented()
            }
        }
    }

    private fun installed(): Map<String, String> {
        val pm = packageManager
        val out = HashMap<String, String>()
        for (category in listOf(Intent.CATEGORY_LAUNCHER, Intent.CATEGORY_LEANBACK_LAUNCHER)) {
            val intent = Intent(Intent.ACTION_MAIN).addCategory(category)
            for (info in pm.queryIntentActivities(intent, 0)) {
                out[info.activityInfo.packageName] = info.loadLabel(pm).toString()
            }
        }
        return out
    }

    private fun launch(pkg: String): Boolean {
        if (pkg.isEmpty()) return false
        val pm = packageManager
        val intent = pm.getLeanbackLaunchIntentForPackage(pkg) ?: pm.getLaunchIntentForPackage(pkg) ?: return false
        intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        return try {
            startActivity(intent)
            true
        } catch (e: Exception) {
            false
        }
    }

    // Fire TV: Amazon Appstore; sonst Google Play
    private fun store(pkg: String): Boolean {
        if (pkg.isEmpty()) return false
        for (uri in listOf("amzn://apps/android?p=$pkg", "market://details?id=$pkg")) {
            try {
                startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(uri)).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
                return true
            } catch (e: Exception) {
            }
        }
        return false
    }
}
""" % PACKAGE


def patch_activity():
    kt = os.path.join(MAIN, "kotlin", *PACKAGE.split("."), "MainActivity.kt")
    if not os.path.exists(kt):
        found = [os.path.join(d, f) for d, _, fs in os.walk(os.path.join(MAIN, "kotlin")) for f in fs if f == "MainActivity.kt"]
        if not found:
            fail("MainActivity.kt nicht gefunden")
        kt = found[0]
    open(kt, "w", encoding="utf-8").write(MAIN_ACTIVITY)


def patch_images():
    res = os.path.join(MAIN, "res")
    icon = Image.open(os.path.join(APP, "tool/out/icon.png")).convert("RGB")
    for folder, size in {"mdpi": 48, "hdpi": 72, "xhdpi": 96, "xxhdpi": 144, "xxxhdpi": 192}.items():
        d = os.path.join(res, f"mipmap-{folder}")
        os.makedirs(d, exist_ok=True)
        icon.resize((size, size), Image.LANCZOS).save(os.path.join(d, "ic_launcher.png"))
    d = os.path.join(res, "drawable")
    os.makedirs(d, exist_ok=True)
    shutil.copy(os.path.join(APP, "tool/out/banner.png"), os.path.join(d, "banner.png"))


SIGNING = """
    signingConfigs {
        create("echo") {
            val props = java.util.Properties()
            val f = rootProject.file("key.properties")
            if (f.exists()) f.inputStream().use { props.load(it) }
            storeFile = file(props.getProperty("storeFile") ?: "echo.jks")
            storePassword = props.getProperty("storePassword")
            keyAlias = props.getProperty("keyAlias")
            keyPassword = props.getProperty("keyPassword")
        }
    }
"""


def patch_gradle():
    path = os.path.join(AND, "app/build.gradle.kts")
    if not os.path.exists(path):
        fail("build.gradle.kts nicht gefunden (ältere Flutter-Version?)")
    s = open(path, encoding="utf-8").read()
    if 'create("echo")' not in s:
        s = s.replace("    buildTypes {", SIGNING + "\n    buildTypes {", 1)
    if 'signingConfigs.getByName("debug")' not in s and 'signingConfigs.getByName("echo")' not in s:
        fail("Signatur-Zeile im Release-Build nicht gefunden")
    s = s.replace('signingConfigs.getByName("debug")', 'signingConfigs.getByName("echo")')
    # Fire OS 7 = Android 9 (API 28); Flutter verlangt ohnehin mindestens 21/24
    s = re.sub(r"minSdk = [^\n]+", "minSdk = 24", s, count=1)
    open(path, "w", encoding="utf-8").write(s)


def main():
    if not os.path.isdir(MAIN):
        fail("android/ fehlt – vorher `flutter create --platforms=android` ausführen")
    patch_manifest()
    patch_activity()
    patch_images()
    patch_gradle()
    print("Android-Projekt für Fire TV angepasst")


if __name__ == "__main__":
    main()
