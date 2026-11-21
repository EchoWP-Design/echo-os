#!/usr/bin/env python3
"""Erzeugt die Grafiken der Echo-App aus den Echo-OS-Quellen (eine Quelle für alles):

  assets/services.json   Streaming-Dienste mit Android-Paketnamen
  assets/tiles/*.png     Kacheln (gen_tiles.py)
  assets/boot/*.png      Neon-Intro (gen_bootscreen.py)
Aufruf aus dem Ordner app/: python3 tool/make_assets.py
"""
import os
import shutil
import subprocess
import sys

APP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT = os.path.dirname(APP)
FS = os.path.join(ROOT, "stage-echoos/00-echoos/files/rootfs")
LIB = os.path.join(FS, "usr/local/lib/echoos")
SERVICES = os.path.join(FS, "usr/share/echoos/services.json")
ASSETS = os.path.join(APP, "assets")


def main():
    os.makedirs(ASSETS, exist_ok=True)
    shutil.copy(SERVICES, os.path.join(ASSETS, "services.json"))

    tiles = os.path.join(ASSETS, "tiles")
    shutil.rmtree(tiles, ignore_errors=True)
    env = {**os.environ, "ECHOOS_TILE_DIR": tiles, "ECHOOS_SERVICES": SERVICES}
    subprocess.run([sys.executable, os.path.join(LIB, "gen_tiles.py")], env=env, check=True)
    os.remove(os.path.join(tiles, "_addon_icon.png"))

    boot = os.path.join(ASSETS, "boot")
    shutil.rmtree(boot, ignore_errors=True)
    subprocess.run([sys.executable, os.path.join(LIB, "gen_bootscreen.py"), boot], check=True)
    for name in os.listdir(boot):
        if not name.endswith(".png"):
            os.remove(os.path.join(boot, name))

    print("Grafiken für die Echo-App erzeugt")


if __name__ == "__main__":
    main()
