"""Kodi-Addon „Echo Streaming“: Streaming-Dienste als Kacheln.

- Echo-OS (Raspberry Pi): startet den Dienst im Vollbild-Browser.
- Kodi auf Android (TV, Fire TV, Handy): startet die installierte App des Dienstes,
  sonst öffnet es die App im App-Store des Geräts.
"""
import json
import os
import subprocess
import sys
from urllib.parse import parse_qs

import xbmc
import xbmcaddon
import xbmcgui
import xbmcplugin

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "resources", "lib"))
import echostream as es  # noqa: E402

ADDON = xbmcaddon.Addon()
BASE = sys.argv[0]
HANDLE = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].lstrip("-").isdigit() else -1
ARGS = parse_qs(sys.argv[2][1:]) if len(sys.argv) > 2 else {}
ON_ANDROID = xbmc.getCondVisibility("System.Platform.Android")
DEVICE_TYPES = {0: "auto", 1: "tv", 2: "mobile"}


def setting_int(key, default=0):
    try:
        return ADDON.getSettingInt(key)
    except Exception:  # noqa: BLE001
        return default


def setting_bool(key, default=False):
    try:
        return ADDON.getSettingBool(key)
    except Exception:  # noqa: BLE001
        return default


def installed_apps():
    request = {"jsonrpc": "2.0", "id": 1, "method": "Files.GetDirectory",
               "params": {"directory": "androidapp://sources/apps/", "media": "files"}}
    try:
        return es.parse_installed(json.loads(xbmc.executeJSONRPC(json.dumps(request))))
    except Exception:  # noqa: BLE001
        return {}


def notify(title, message, icon=xbmcgui.NOTIFICATION_INFO, ms=5000):
    xbmcgui.Dialog().notification(title, message, icon, ms)


# ---------------------------------------------------------------- Android
def launch_android(svc):
    apps = installed_apps()
    tv = es.is_tv(apps, DEVICE_TYPES.get(setting_int("devicetype"), "auto"))
    pkg = es.find_package(svc, apps, tv)
    if pkg:
        notify(svc["name"], "Wird gestartet …", es.tile_path(svc["id"]), 3000)
        xbmc.executebuiltin(es.launch_command(pkg))
        return
    store = es.store_command(svc, apps, tv)
    if store:
        notify(svc["name"], "Noch nicht installiert – der App-Store wird geöffnet.",
               es.tile_path(svc["id"]), 5000)
        xbmc.executebuiltin(store)
    else:
        notify(svc["name"], "Nicht installiert. Bitte die App im App-Store deines Geräts installieren.",
               xbmcgui.NOTIFICATION_WARNING, 8000)


# ---------------------------------------------------------------- Echo-OS (Pi)
def widevine_ready():
    try:
        out = subprocess.run(["dpkg-query", "-W", "-f=${Status}", "libwidevinecdm0"],
                             capture_output=True, text=True, timeout=5).stdout
        return "install ok installed" in out
    except Exception:  # noqa: BLE001
        return False


def launch_echoos(svc):
    if svc.get("drm") and not widevine_ready():
        notify(svc["name"], "Das DRM-Modul wird nach dem ersten Start noch installiert. "
               "Bitte in ein paar Minuten erneut versuchen.", xbmcgui.NOTIFICATION_WARNING, 8000)
        return
    notify(svc["name"], "Wird gestartet … Zurück mit Home oder Zurück lange drücken",
           es.tile_path(svc["id"]), 4000)
    xbmc.sleep(500)
    # Startet den Browser-Dienst; systemd beendet Kodi und startet es danach wieder.
    subprocess.Popen(["systemctl", "start", "--no-block", f"echoos-browser@{svc['id']}.service"])


# ---------------------------------------------------------------- Ansicht
def launch(service_id):
    svc = {s["id"]: s for s in es.load_services()}.get(service_id)
    if not svc:
        notify("Streaming", "Unbekannter Dienst", xbmcgui.NOTIFICATION_ERROR)
        return
    if ON_ANDROID:
        launch_android(svc)
    else:
        launch_echoos(svc)


def list_services():
    xbmcplugin.setContent(HANDLE, "videos")
    apps, tv = {}, False
    if ON_ANDROID:
        apps = installed_apps()
        tv = es.is_tv(apps, DEVICE_TYPES.get(setting_int("devicetype"), "auto"))
    only_installed = setting_bool("onlyinstalled")
    for svc in es.load_services():
        label = svc["name"]
        if ON_ANDROID and not es.find_package(svc, apps, tv):
            if only_installed:
                continue
            label = f"{svc['name']} · installieren"
        item = xbmcgui.ListItem(label=label)
        tile = es.tile_path(svc["id"])
        item.setArt({"thumb": tile, "icon": tile, "poster": tile, "fanart": tile})
        xbmcplugin.addDirectoryItem(HANDLE, f"{BASE}?launch={svc['id']}", item, isFolder=False)
    xbmcplugin.endOfDirectory(HANDLE)
    # Kachelansicht (Estuary „Wall“) statt Textliste
    xbmc.executebuiltin("Container.SetViewMode(500)")


if "launch" in ARGS:
    launch(ARGS["launch"][0])
else:
    list_services()
