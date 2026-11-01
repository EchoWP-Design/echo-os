#!/usr/bin/env python3
"""Rendert den Echo-OS-Bootscreen so, wie ihn das Plymouth-Skript echo.script abspielt.

Nutzt dieselben Grafiken (gen_bootscreen.py) und dieselben Formeln wie das
Skript (Skalierung, Gitterbild = tick/2 % 24, Logo-Puls, Lichtspur-Position).
Plymouth ruft die Refresh-Funktion 50x pro Sekunde auf; bei 25 fps Video
entspricht ein Videobild zwei Ticks.

Aufruf: simulate_plymouth.py <theme-ordner> <ausgabe.mp4> [Breite Höhe]
"""
import math
import os
import subprocess
import sys

from PIL import Image, ImageDraw, ImageFont

THEME, OUT = sys.argv[1], sys.argv[2]
W = int(sys.argv[3]) if len(sys.argv) > 3 else 1920
H = int(sys.argv[4]) if len(sys.argv) > 4 else 1080
FPS, SECONDS = 25, 9
SX, SY = W / 1280, H / 720
FRAMES_GRID = 24


def load(name):
    return Image.open(os.path.join(THEME, name)).convert("RGBA")


# --- wie im Skript: Bilder laden und skalieren
bg = load("background.png").resize((W, H), Image.BILINEAR)
grid = [load(f"grid-{i}.png").resize((W, int(320 * SY)), Image.BILINEAR) for i in range(FRAMES_GRID)]
logo = load("logo.png")
logo = logo.resize((int(logo.width * SX), int(logo.height * SY)), Image.BILINEAR)
streak = load("streak.png")
streak = streak.resize((int(streak.width * SX), int(streak.height * SY)), Image.BILINEAR)
splash = Image.open(os.path.join(THEME, "splash.jpg")).convert("RGBA").resize((W, H), Image.BILINEAR)
font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf", 19)

MESSAGES = [(2.0, "Dateisystem wird geprüft …"), (4.5, "Netzwerk wird gestartet …"), (6.5, "")]


def frame(tick, t):
    img = bg.copy()
    img.alpha_composite(grid[int(tick / 2) % FRAMES_GRID], (0, int(400 * SY)))
    opacity = 0.92 + 0.08 * math.sin(tick * 0.06)
    lg = logo.copy()
    lg.putalpha(lg.getchannel("A").point(lambda a: int(a * opacity)))
    img.alpha_composite(lg, (int((W - logo.width) / 2), int(140 * SY)))
    span = W + 2 * streak.width
    x = (tick * 9 * SX) % span - streak.width
    img.alpha_composite(streak, (int(x), int(640 * SY))) if x > -streak.width else None
    msg = ""
    for start, text in MESSAGES:
        if t >= start:
            msg = text
    if msg:
        d = ImageDraw.Draw(img)
        tw = d.textlength(msg, font=font)
        d.text(((W - tw) / 2, H - int(40 * SY)), msg, font=font, fill=(0, 240, 255, 255))
    return img


def main():
    ff = subprocess.Popen(["ffmpeg", "-loglevel", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24",
                           "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-c:v", "libx264",
                           "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p", OUT],
                          stdin=subprocess.PIPE)
    total = FPS * SECONDS
    for n in range(total):
        t = n / FPS
        img = frame(n * 2, t)
        # Letzte Sekunde: Übergabe an Kodi (plymouth quit --retain-splash, dann Kodi-Startbild)
        if t > SECONDS - 1.2:
            a = min(1.0, (t - (SECONDS - 1.2)) / 0.5)
            img = Image.blend(img, splash, a)
        ff.stdin.write(img.convert("RGB").tobytes())
        if n in (0, 37, 75, 150):
            img.convert("RGB").save(OUT.replace(".mp4", f"_frame{n:03d}.png"))
    ff.stdin.close()
    ff.wait()
    print("Video:", OUT)


if __name__ == "__main__":
    main()
