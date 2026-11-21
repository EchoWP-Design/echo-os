#!/usr/bin/env python3
"""Erzeugt die Grafiken der Echo-App aus den Echo-OS-Quellen (eine Quelle für alles):

  assets/services.json   Streaming-Dienste mit Android-Paketnamen
  assets/tiles/*.png     Kacheln (gen_tiles.py)
  assets/boot/*.png      Neon-Intro (gen_bootscreen.py)
  tool/out/icon.png      App-Symbol 512x512
  tool/out/banner.png    Fire-TV-/Android-TV-Banner 320x180
Aufruf aus dem Ordner app/: python3 tool/make_assets.py
"""
import os
import shutil
import subprocess
import sys

from PIL import Image, ImageDraw, ImageFilter, ImageFont

APP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT = os.path.dirname(APP)
FS = os.path.join(ROOT, "stage-echoos/00-echoos/files/rootfs")
LIB = os.path.join(FS, "usr/local/lib/echoos")
SERVICES = os.path.join(FS, "usr/share/echoos/services.json")
ASSETS = os.path.join(APP, "assets")
OUT = os.path.join(APP, "tool/out")
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
CYAN, MAGENTA = (0, 240, 255), (255, 40, 200)


def neon_text(size, text, font_size, pos=None):
    img = Image.new("RGBA", size, (7, 0, 26, 255))
    d = ImageDraw.Draw(img)
    # Synthwave-Gitter unten
    w, h = size
    hz = int(h * 0.62)
    for i in range(-12, 13):
        d.line([(w / 2 + i * w * 0.02, hz), (w / 2 + i * w * 0.18, h)], fill=MAGENTA + (150,), width=max(1, w // 160))
    for k in range(1, 7):
        y = hz + (h - hz) * (k / 6) ** 1.8
        d.line([(0, y), (w, y)], fill=MAGENTA + (150,), width=max(1, w // 160))
    font = ImageFont.truetype(FONT, font_size)
    tw = d.textlength(text, font=font)
    x, y = pos or ((w - tw) / 2, h * 0.18)
    layer = Image.new("RGBA", size, (0, 0, 0, 0))
    ImageDraw.Draw(layer).text((x, y), text, font=font, fill=CYAN + (255,))
    glow = layer.filter(ImageFilter.GaussianBlur(max(2, w // 60)))
    img = Image.alpha_composite(img, glow)
    img = Image.alpha_composite(img, glow)
    core = Image.new("RGBA", size, (0, 0, 0, 0))
    ImageDraw.Draw(core).text((x, y), text, font=font, fill=(235, 255, 255, 255))
    return Image.alpha_composite(img, core).convert("RGB")


def main():
    os.makedirs(ASSETS, exist_ok=True)
    os.makedirs(OUT, exist_ok=True)
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

    neon_text((512, 512), "E", 330, pos=(150, 40)).save(os.path.join(OUT, "icon.png"))
    neon_text((320, 180), "ECHO", 64).save(os.path.join(OUT, "banner.png"))
    print("Grafiken für die Echo-App erzeugt")


if __name__ == "__main__":
    main()
