#!/usr/bin/env python3
"""Erzeugt den Echo-OS-Bootscreen im 80er-Neon-Stil (Tron / Synthwave).

Ausgabe (Standard /usr/share/plymouth/themes/echo):
  background.png   Himmel, Sterne, Synthwave-Sonne, Drahtgitter-Berge
  grid-0..N.png    bewegtes Perspektiv-Gitter (Endlosschleife)
  logo.png         Chrom-Schriftzug "ECHO-OS" mit Neon-Glühen
  streak.png       Tron-Lichtspur, fährt über den Boden
  splash.jpg       Standbild (für Kodis Startbild)
Alle Grafiken sind auf 1280x720 ausgelegt; das Plymouth-Skript skaliert sie.
"""
import math
import os
import random
import sys

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

W, H = 1280, 720
HORIZON = 400
FRAMES = 24
OUT = sys.argv[1] if len(sys.argv) > 1 else "/usr/share/plymouth/themes/echo"
FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
FONT_MONO = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf"

CYAN = (0, 240, 255)
MAGENTA = (255, 40, 200)
PURPLE = (140, 40, 255)
SKY_TOP = (6, 0, 22)
SKY_HORIZON = (70, 0, 90)


def glow(layer, radii=(2, 6, 16), strength=(1.0, 0.9, 0.7)):
    """Neon-Glühen: mehrere unscharfe Kopien unter die scharfen Linien legen."""
    out = Image.new("RGBA", layer.size, (0, 0, 0, 0))
    for r, s in zip(radii, strength):
        blurred = layer.filter(ImageFilter.GaussianBlur(r))
        if s != 1.0:
            a = blurred.getchannel("A").point(lambda v, s=s: int(min(255, v * s)))
            blurred.putalpha(a)
        out = Image.alpha_composite(out, blurred)
    return Image.alpha_composite(out, layer)


def lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


# ------------------------------------------------------------------ Hintergrund
def background():
    img = Image.new("RGBA", (W, H), SKY_TOP + (255,))
    d = ImageDraw.Draw(img)
    for y in range(HORIZON):
        t = (y / HORIZON) ** 1.8
        d.line([(0, y), (W, y)], fill=lerp(SKY_TOP, SKY_HORIZON, t) + (255,))
    for y in range(HORIZON, H):
        t = (y - HORIZON) / (H - HORIZON)
        d.line([(0, y), (W, y)], fill=lerp((30, 0, 45), (4, 0, 12), t ** 0.6) + (255,))

    # Sterne
    rnd = random.Random(1984)
    stars = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    sd = ImageDraw.Draw(stars)
    for _ in range(260):
        x, y = rnd.randrange(W), rnd.randrange(int(HORIZON * 0.85))
        b = rnd.randrange(90, 255)
        r = 1 if rnd.random() < 0.85 else 2
        sd.ellipse([x - r, y - r, x + r, y + r], fill=(b, b, min(255, b + 30), 255))
    img = Image.alpha_composite(img, glow(stars, radii=(1, 3), strength=(0.8, 0.5)))

    # Synthwave-Sonne mit Streifen-Schnitten
    cx, cy, rad = W // 2, HORIZON - 40, 175
    sun = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    sdraw = ImageDraw.Draw(sun)
    for y in range(cy - rad, HORIZON):
        dy = y - cy
        if abs(dy) > rad:
            continue
        half = int(math.sqrt(rad * rad - dy * dy))
        t = (y - (cy - rad)) / (2 * rad)
        col = lerp((255, 236, 90), (255, 30, 160), min(1, t * 1.15))
        sdraw.line([(cx - half, y), (cx + half, y)], fill=col + (255,))
    # Streifen werden nach unten breiter
    for i in range(10):
        y0 = cy - 50 + i * 21
        gap = 2 + i * 1.6
        sdraw.rectangle([0, y0, W, y0 + gap], fill=(0, 0, 0, 0))
    sun_glow = sun.filter(ImageFilter.GaussianBlur(40))
    img = Image.alpha_composite(img, sun_glow)
    img = Image.alpha_composite(img, sun)

    # Drahtgitter-Berge links und rechts
    mountains = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    md = ImageDraw.Draw(mountains)
    rnd = random.Random(7)
    for side in (-1, 1):
        pts = []
        x = W // 2 + side * 210
        while 0 <= x <= W:
            dist = abs(x - W // 2) / (W / 2)
            peak = HORIZON - rnd.randint(25, 70) - int(60 * dist)
            pts.append((x, peak))
            x += side * rnd.randint(55, 95)
        pts = [(W // 2 + side * 170, HORIZON)] + pts + [(0 if side < 0 else W, HORIZON)]
        md.polygon(pts, fill=(18, 0, 40, 255))
        md.line(pts, fill=CYAN + (255,), width=2)
        for px, py in pts[1:-1]:          # Gitterlinien zu den Gipfeln
            md.line([(px, py), (px + side * 40, HORIZON)], fill=PURPLE + (200,), width=1)
            md.line([(px, py), (px - side * 30, HORIZON)], fill=PURPLE + (200,), width=1)
    img = Image.alpha_composite(img, glow(mountains, radii=(2, 8), strength=(0.9, 0.6)))

    # Horizontlinie
    hl = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(hl).line([(0, HORIZON), (W, HORIZON)], fill=MAGENTA + (255,), width=2)
    img = Image.alpha_composite(img, glow(hl, radii=(3, 12), strength=(1, 0.8)))
    return img


# ------------------------------------------------------------------ Gitter
GRID_H = H - HORIZON


def grid_frame(phase):
    """phase 0..1 = Bewegung um eine Gitterzeile auf den Betrachter zu."""
    layer = Image.new("RGBA", (W, GRID_H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    vx = W / 2
    # Längslinien zum Fluchtpunkt
    for i in range(-22, 23):
        x_bottom = vx + i * 120
        d.line([(vx + i * 6, 0), (x_bottom, GRID_H)], fill=MAGENTA + (255,), width=2)
    # Querlinien in Perspektive: y = k / z
    cam = 60.0
    for n in range(0, 40):
        z = (n + 1 - phase) * 1.0
        if z <= 0.05:
            continue
        y = cam * 4.2 / z
        if y > GRID_H or y < 4:
            continue
        fade = max(0.0, min(1.0, (y - 4) / 70))
        d.line([(0, y), (W, y)], fill=MAGENTA + (int(255 * fade),), width=2 if y > 40 else 1)
    layer = glow(layer, radii=(2, 7), strength=(1.0, 0.7))
    # Richtung Horizont im Dunst verschwinden lassen
    mask = Image.new("L", (W, GRID_H))
    md = ImageDraw.Draw(mask)
    for y in range(GRID_H):
        md.line([(0, y), (W, y)], fill=int(255 * min(1.0, 0.05 + (y / GRID_H) ** 0.6)))
    layer.putalpha(ImageChops.multiply(layer.getchannel("A"), mask))
    # halbe Auflösung speichern (Plymouth skaliert hoch) -> schnellerer Boot
    return layer.resize((W // 2, GRID_H // 2), Image.LANCZOS)


# ------------------------------------------------------------------ Logo
def logo():
    text = "ECHO-OS"
    font = ImageFont.truetype(FONT_BOLD, 150)
    tw = int(ImageDraw.Draw(Image.new("L", (1, 1))).textlength(text, font=font))
    pad = 60
    lw, lh = tw + pad * 2 + 80, 300
    mask = Image.new("L", (lw, lh), 0)
    ImageDraw.Draw(mask).text((pad + 40, 30), text, font=font, fill=255)
    # 80er-Kursiv: horizontal scheren
    shear = 0.22
    mask = mask.transform(mask.size, Image.AFFINE, (1, shear, -shear * lh / 2, 0, 1, 0),
                          resample=Image.BICUBIC)
    bbox = mask.getbbox()
    top, bottom = bbox[1], bbox[3]
    mid = top + (bottom - top) * 0.52

    # Chrom-Verlauf mit hartem Horizont in der Mitte
    chrome = Image.new("RGBA", (lw, lh))
    cd = ImageDraw.Draw(chrome)
    for y in range(lh):
        if y < mid:
            t = (y - top) / max(1, mid - top)
            col = lerp((255, 255, 255), (120, 220, 255), max(0, t))
        else:
            t = (y - mid) / max(1, bottom - mid)
            col = lerp((40, 0, 90), (255, 70, 210), min(1, max(0, t)))
        cd.line([(0, y), (lw, y)], fill=col + (255,))
    fill = Image.new("RGBA", (lw, lh), (0, 0, 0, 0))
    fill.paste(chrome, (0, 0), mask)

    # Neon-Kontur
    edge = mask.filter(ImageFilter.MaxFilter(7))
    outline = Image.new("RGBA", (lw, lh), (0, 0, 0, 0))
    outline.paste(Image.new("RGBA", (lw, lh), CYAN + (255,)), (0, 0), edge)
    outline = glow(outline, radii=(3, 10, 24), strength=(1, 0.9, 0.7))
    out = Image.alpha_composite(outline, fill)

    # Untertitel
    sub = "M E D I A   S Y S T E M"
    sfont = ImageFont.truetype(FONT_MONO, 26)
    sw = ImageDraw.Draw(out).textlength(sub, font=sfont)
    sx, sy = (lw - sw) / 2, bottom + 14
    shadow = Image.new("RGBA", (lw, lh), (0, 0, 0, 0))
    ImageDraw.Draw(shadow).rounded_rectangle([sx - 18, sy - 6, sx + sw + 18, sy + 36],
                                             radius=8, fill=(8, 0, 24, 200))
    out = Image.alpha_composite(out, shadow.filter(ImageFilter.GaussianBlur(4)))
    neon = Image.new("RGBA", (lw, lh), (0, 0, 0, 0))
    ImageDraw.Draw(neon).text((sx, sy), sub, font=sfont, fill=MAGENTA + (255,))
    out = Image.alpha_composite(out, glow(neon, radii=(3, 8), strength=(1, 0.8)))
    core = Image.new("RGBA", (lw, lh), (0, 0, 0, 0))
    ImageDraw.Draw(core).text((sx, sy), sub, font=sfont, fill=(255, 220, 250, 255))
    out = Image.alpha_composite(out, core)
    return out.crop(out.getbbox())


# ------------------------------------------------------------------ Lichtspur
def streak():
    sw, sh = 360, 40
    layer = Image.new("RGBA", (sw, sh), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    for x in range(sw - 30):
        a = int(255 * (x / (sw - 30)) ** 2.2)
        d.line([(x, sh // 2 - 2), (x, sh // 2 + 2)], fill=CYAN + (a,))
    d.rounded_rectangle([sw - 40, sh // 2 - 7, sw - 6, sh // 2 + 7], radius=5, fill=(220, 255, 255, 255))
    return glow(layer, radii=(2, 6, 12), strength=(1, 0.9, 0.7))


def compose(bg, grid, logo_img, streak_img=None, streak_x=0):
    frame = bg.copy()
    frame.alpha_composite(grid.resize((W, GRID_H), Image.BILINEAR), (0, HORIZON))
    frame.alpha_composite(logo_img, ((W - logo_img.width) // 2, 140))
    if streak_img is not None:
        frame.alpha_composite(streak_img, (int(streak_x), 640))
    return frame


def main():
    os.makedirs(OUT, exist_ok=True)
    bg = background()
    bg.save(os.path.join(OUT, "background.png"), optimize=True)
    grids = []
    for i in range(FRAMES):
        g = grid_frame(i / FRAMES)
        g.save(os.path.join(OUT, f"grid-{i}.png"), optimize=True)
        grids.append(g)
    lg = logo()
    lg.save(os.path.join(OUT, "logo.png"), optimize=True)
    st = streak()
    st.save(os.path.join(OUT, "streak.png"), optimize=True)
    compose(bg, grids[0], lg).convert("RGB").save(os.path.join(OUT, "splash.jpg"), quality=92)

    if os.environ.get("ECHOOS_PREVIEW"):
        frames = []
        for i in range(FRAMES * 2):
            sx = -st.width + (W + st.width * 2) * (i / (FRAMES * 2))
            frames.append(compose(bg, grids[i % FRAMES], lg, st, sx).convert("RGB"))
        frames[0].save(os.environ["ECHOOS_PREVIEW"], save_all=True, append_images=frames[1:],
                       duration=40, loop=0)
    print(f"Bootscreen erzeugt in {OUT}")


if __name__ == "__main__":
    main()
