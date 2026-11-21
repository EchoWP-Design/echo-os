"""Echo-Startbild: legt beim Kodi-Start das Neon-Startbild von Echo-OS als Kodi-Startbild ab.

Kodi sucht sein Startbild unter special://home/media/splash.jpg. Ein eigenes Startbild
des Nutzers wird nie überschrieben: Ersetzt oder entfernt wird nur ein Bild, das dieses
Addon selbst abgelegt hat (erkannt an der gespeicherten Prüfsumme).
"""
import hashlib
import os
import shutil

import xbmcaddon
import xbmcvfs

ADDON = xbmcaddon.Addon()
SOURCE = os.path.join(xbmcvfs.translatePath(ADDON.getAddonInfo("path")), "resources", "media", "splash.jpg")
TARGET = xbmcvfs.translatePath("special://home/media/splash.jpg")
MARKER = os.path.join(xbmcvfs.translatePath(ADDON.getAddonInfo("profile")), "splash.sha256")


def sha256(path):
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def read_marker():
    try:
        with open(MARKER, encoding="utf-8") as fh:
            return fh.read().strip()
    except OSError:
        return ""


def write_marker(value):
    os.makedirs(os.path.dirname(MARKER), exist_ok=True)
    with open(MARKER, "w", encoding="utf-8") as fh:
        fh.write(value)


def ours():
    return os.path.exists(TARGET) and read_marker() and sha256(TARGET) == read_marker()


def wanted():
    try:
        return ADDON.getSettingBool("splash")
    except Exception:  # noqa: BLE001
        return True


def main():
    if not os.path.exists(SOURCE):
        return  # Echo-OS auf dem Pi bringt sein Startbild selbst mit
    if wanted():
        if not os.path.exists(TARGET) or (ours() and sha256(SOURCE) != sha256(TARGET)):
            os.makedirs(os.path.dirname(TARGET), exist_ok=True)
            shutil.copyfile(SOURCE, TARGET)
            write_marker(sha256(TARGET))
    elif ours():
        os.remove(TARGET)
        write_marker("")


if __name__ == "__main__":
    main()
