#!/usr/bin/env python3
"""Baut das Kodi-Addon „Echo Streaming“ als ZIP zum Installieren in Kodi
(Android TV, Google TV, Fire TV, Handy, Windows …): Add-ons → Aus ZIP-Datei installieren.

Aufruf: python3 tools/build_kodi_addon.py [ausgabe-ordner]   (Standard: dist/)
"""
import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FS = os.path.join(ROOT, "stage-echoos/00-echoos/files/rootfs")
ADDON_ID = "plugin.program.echoos.streaming"
ADDON_SRC = os.path.join(FS, "home/echoos/.kodi/addons", ADDON_ID)
SERVICES = os.path.join(FS, "usr/share/echoos/services.json")
LIB = os.path.join(FS, "usr/local/lib/echoos")
LICENSE_NOTE = os.path.join(FS, "usr/share/doc/echoos/LIZENZEN.md")


def main():
    out_dir = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "dist"))
    os.makedirs(out_dir, exist_ok=True)
    version = re.search(r'<addon[^>]*\sversion="([^"]+)"', open(os.path.join(ADDON_SRC, "addon.xml")).read()).group(1)

    with tempfile.TemporaryDirectory() as tmp:
        dst = os.path.join(tmp, ADDON_ID)
        shutil.copytree(ADDON_SRC, dst, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        res = os.path.join(dst, "resources")
        shutil.copy(SERVICES, os.path.join(res, "services.json"))
        shutil.copy(LICENSE_NOTE, os.path.join(dst, "LIZENZEN.md"))

        # Kacheln und Symbol
        tiles = os.path.join(res, "tiles")
        env = {**os.environ, "ECHOOS_TILE_DIR": tiles, "ECHOOS_SERVICES": SERVICES}
        subprocess.run([sys.executable, os.path.join(LIB, "gen_tiles.py")], env=env, check=True,
                       stdout=subprocess.DEVNULL)
        shutil.move(os.path.join(tiles, "_addon_icon.png"), os.path.join(dst, "icon.png"))

        # Neon-Startbild (Kodi-Startbild und Hintergrund des Addons)
        boot = os.path.join(tmp, "boot")
        subprocess.run([sys.executable, os.path.join(LIB, "gen_bootscreen.py"), boot], check=True,
                       stdout=subprocess.DEVNULL)
        os.makedirs(os.path.join(res, "media"), exist_ok=True)
        shutil.copy(os.path.join(boot, "splash.jpg"), os.path.join(res, "media", "splash.jpg"))
        shutil.copy(os.path.join(boot, "splash.jpg"), os.path.join(dst, "fanart.jpg"))

        target = os.path.join(out_dir, f"{ADDON_ID}-{version}.zip")
        with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as zf:
            for folder, _, files in os.walk(dst):
                for name in sorted(files):
                    full = os.path.join(folder, name)
                    zf.write(full, os.path.relpath(full, tmp))
    print(target)


if __name__ == "__main__":
    main()
