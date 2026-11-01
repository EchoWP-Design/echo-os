"""Kodi-Addon: zeigt die Streaming-Apps als Kacheln und startet sie."""
import json
import subprocess
import sys
from urllib.parse import parse_qs

import xbmc
import xbmcgui
import xbmcplugin

SERVICES_FILE = "/usr/share/echoos/services.json"
TILES = "/usr/share/echoos/tiles"

BASE = sys.argv[0]
HANDLE = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].lstrip("-").isdigit() else -1
ARGS = parse_qs(sys.argv[2][1:]) if len(sys.argv) > 2 else {}


def load_services():
    with open(SERVICES_FILE, encoding="utf-8") as fh:
        return json.load(fh)


def widevine_ready():
    try:
        out = subprocess.run(["dpkg-query", "-W", "-f=${Status}", "libwidevinecdm0"],
                             capture_output=True, text=True, timeout=5).stdout
        return "install ok installed" in out
    except Exception:  # noqa: BLE001
        return False


def launch(service_id):
    services = {s["id"]: s for s in load_services()}
    svc = services.get(service_id)
    if not svc:
        xbmcgui.Dialog().notification("Streaming", "Unbekannter Dienst", xbmcgui.NOTIFICATION_ERROR)
        return
    if svc.get("drm") and not widevine_ready():
        xbmcgui.Dialog().notification(
            svc["name"], "Das DRM-Modul wird nach dem ersten Start noch installiert. Bitte in ein paar Minuten erneut versuchen.",
            xbmcgui.NOTIFICATION_WARNING, 8000)
        return
    xbmcgui.Dialog().notification(
        svc["name"], "Wird gestartet … Zurück mit Home oder Zurück lange drücken",
        f"{TILES}/{svc['id']}.png", 4000)
    xbmc.sleep(500)
    # Startet den Browser-Dienst; systemd beendet Kodi automatisch und
    # startet es danach wieder (Conflicts= / ExecStopPost=).
    subprocess.Popen(["systemctl", "start", "--no-block", f"echoos-browser@{svc['id']}.service"])


def list_services():
    xbmcplugin.setContent(HANDLE, "videos")
    for svc in load_services():
        item = xbmcgui.ListItem(label=svc["name"])
        tile = f"{TILES}/{svc['id']}.png"
        item.setArt({"thumb": tile, "icon": tile, "poster": tile, "fanart": tile})
        url = f"{BASE}?launch={svc['id']}"
        xbmcplugin.addDirectoryItem(HANDLE, url, item, isFolder=False)
    xbmcplugin.endOfDirectory(HANDLE)
    # Kachelansicht (Estuary "Wall") statt Textliste
    xbmc.executebuiltin("Container.SetViewMode(500)")


if "launch" in ARGS:
    launch(ARGS["launch"][0])
else:
    list_services()
