#!/usr/bin/env python3
"""Erzeugt schlichte Kacheln (Farbe + Name) für jede Streaming-App.
Bewusst ohne Original-Logos – nur Name und Farbe."""
import json
import os

from PIL import Image, ImageDraw, ImageFont

SERVICES = "/usr/share/echoos/services.json"
OUT = os.environ.get("ECHOOS_TILE_DIR", "/usr/share/echoos/tiles")
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
W, H = 512, 512


def hex_rgb(value):
    value = value.lstrip("#")
    return tuple(int(value[i:i + 2], 16) for i in (0, 2, 4))


def fit_font(draw, text, max_width):
    size = 96
    while size > 24:
        font = ImageFont.truetype(FONT, size)
        if draw.textlength(text, font=font) <= max_width:
            return font
        size -= 4
    return ImageFont.truetype(FONT, size)


def tile(name, color, path):
    base = hex_rgb(color)
    img = Image.new("RGB", (W, H), base)
    draw = ImageDraw.Draw(img)
    # leichter Verlauf nach unten
    for y in range(H):
        f = 1 - 0.35 * (y / H)
        draw.line([(0, y), (W, y)], fill=tuple(int(c * f) for c in base))
    words = name.split()
    lines = [name] if len(words) == 1 or len(name) <= 10 else [" ".join(words[:-1]), words[-1]]
    fonts = [fit_font(draw, line, W - 80) for line in lines]
    heights = [f.getbbox(line)[3] - f.getbbox(line)[1] for f, line in zip(fonts, lines)]
    y = (H - sum(heights) - 20 * (len(lines) - 1)) / 2
    for line, font, h in zip(lines, fonts, heights):
        x = (W - draw.textlength(line, font=font)) / 2
        draw.text((x, y - font.getbbox(line)[1]), line, font=font, fill="white")
        y += h + 20
    img.save(path, optimize=True)


def main():
    os.makedirs(OUT, exist_ok=True)
    with open(SERVICES, encoding="utf-8") as fh:
        services = json.load(fh)
    for svc in services:
        tile(svc["name"], svc.get("color", "#333333"), os.path.join(OUT, f"{svc['id']}.png"))
    tile("Streaming", "#2a6df4", os.path.join(OUT, "_addon_icon.png"))
    print(f"{len(services)} Kacheln in {OUT}")


if __name__ == "__main__":
    main()
