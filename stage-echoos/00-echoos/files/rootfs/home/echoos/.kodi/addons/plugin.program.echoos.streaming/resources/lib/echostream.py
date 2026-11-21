"""Echo-Streaming: gemeinsame Logik für das Kodi-Addon (Echo-OS und Kodi auf Android).

Ohne Kodi-Abhängigkeiten, damit sie sich ohne Kodi testen lässt.
"""
import json
import os
import re

ADDON_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SYSTEM_SERVICES = os.environ.get("ECHOOS_SERVICES", "/usr/share/echoos/services.json")  # Echo-OS (Pi)
SYSTEM_TILES = os.environ.get("ECHOOS_TILES", "/usr/share/echoos/tiles")

PLAY_STORE = "com.android.vending"
AMAZON_STORE = "com.amazon.venezia"

# Pakete, die es nur auf Fernsehgeräten gibt (Android TV, Google TV, Fire TV).
# Ist eines davon installiert, gilt das Gerät als Fernseher.
TV_MARKERS = {
    "com.google.android.youtube.tv", "com.amazon.firetv.youtube", "com.netflix.ninja",
    "com.amazon.amazonvideo.livingroom", "com.google.android.tvlauncher",
    "com.google.android.apps.tv.launcherx", "com.google.android.leanbacklauncher",
    "com.amazon.tv.launcher",
}


def services_path():
    bundled = os.path.join(ADDON_DIR, "resources", "services.json")
    return bundled if os.path.exists(bundled) else SYSTEM_SERVICES


def load_services():
    with open(services_path(), encoding="utf-8") as fh:
        return json.load(fh)


def tile_path(service_id):
    bundled = os.path.join(ADDON_DIR, "resources", "tiles", f"{service_id}.png")
    return bundled if os.path.exists(bundled) else f"{SYSTEM_TILES}/{service_id}.png"


def normalize(text):
    text = text.lower().replace("+", "plus")
    return re.sub(r"[^a-z0-9]", "", text)


def parse_installed(rpc_result):
    """Antwort von Files.GetDirectory(androidapp://sources/apps/) -> {Paketname: Anzeigename}."""
    files = ((rpc_result or {}).get("result") or {}).get("files") or []
    apps = {}
    for item in files:
        path = (item.get("file") or "").rstrip("/")
        pkg = path.rsplit("/", 1)[-1]
        if pkg:
            apps[pkg] = item.get("label") or pkg
    return apps


def is_tv(installed, device_type="auto"):
    if device_type == "tv":
        return True
    if device_type == "mobile":
        return False
    return any(pkg in installed for pkg in TV_MARKERS)


def candidates(service, tv):
    android = service.get("android") or {}
    first, second = ("tv", "mobile") if tv else ("mobile", "tv")
    seen, out = set(), []
    for pkg in (android.get(first) or []) + (android.get(second) or []):
        if pkg not in seen:
            seen.add(pkg)
            out.append(pkg)
    return out


def find_package(service, installed, tv):
    """Paket der installierten App zum Dienst – erst über bekannte Paketnamen, dann über den Namen."""
    for pkg in candidates(service, tv):
        if pkg in installed:
            return pkg
    names = {normalize(service["name"])} | {normalize(n) for n in service.get("labels", [])}
    for pkg, label in sorted(installed.items()):
        if normalize(label) in names:
            return pkg
    return None


def store_command(service, installed, tv):
    """Kodi-Befehl, der die App im App-Store des Geräts öffnet – oder None ohne Store."""
    android = service.get("android") or {}
    preferred = (android.get("tv" if tv else "mobile") or candidates(service, tv) or [None])[0]
    if not preferred:
        return None
    if PLAY_STORE in installed:
        return (f"StartAndroidActivity({PLAY_STORE},android.intent.action.VIEW,,"
                f"market://details?id={preferred})")
    if AMAZON_STORE in installed:
        return (f"StartAndroidActivity({AMAZON_STORE},android.intent.action.VIEW,,"
                f"amzn://apps/android?p={preferred})")
    return None


def launch_command(package):
    return f"StartAndroidActivity({package})"
