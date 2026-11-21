"""Echo-App – App-Symbol (Variante B, Fernbedienung) und Fire-TV-Banner.
Bauweise wie EchoWP-Mail/Newsflash: rundes Elefanten-Logo, Produktzeichen am Echo-Bogen.
Braucht: cairosvg, Pillow, Schrift Inter Display Black. Ergebnisse liegen fertig im Repo,
neu erzeugen nur bei Designänderungen: python3 generator-echo-app.py
"""
import math
from io import BytesIO

import cairosvg
from PIL import Image, ImageDraw, ImageFont

K, Y = "#0A0A0A", "#FFD400"
FONT = "/usr/share/fonts/opentype/inter/InterDisplay-Black.otf"


def elefant(col):
    return f'''<g fill="none" stroke="{col}" stroke-width="26" stroke-linecap="round" stroke-linejoin="round">
<path d="M104 62 C 60 34, 18 80, 34 130 C 44 160, 74 170, 98 150"/>
<path d="M104 62 C 132 40, 176 50, 182 92 C 186 120, 172 140, 160 160 C 150 178, 156 198, 176 196 C 192 194, 198 178, 194 164"/>
<path d="M216 180 A 32 32 0 0 0 220 138" stroke-width="18"/>
</g><circle cx="150" cy="90" r="13" fill="{col}"/>'''


def fernbedienung(f, ink):
    return f'''<g transform="translate(232 214) rotate(-18)">
<rect x="-24" y="-44" width="48" height="88" rx="14" fill="{f}" stroke="{ink}" stroke-width="12"/>
<circle cx="0" cy="-16" r="12" fill="none" stroke="{ink}" stroke-width="7"/>
<circle cx="0" cy="-16" r="3.5" fill="{ink}"/>
<rect x="-10" y="8" width="20" height="7" rx="3.5" fill="{ink}"/>
<rect x="-10" y="22" width="20" height="7" rx="3.5" fill="{ink}"/>
</g>'''


def motiv(col, bgcol, scale):
    return f'<g transform="translate(512 512) scale({scale}) translate(-142 -140)">{elefant(col)}{fernbedienung(col, bgcol)}</g>'


def svg(inner):
    return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1024 1024" width="1024" height="1024">{inner}</svg>'


def render(s, size=1024):
    return Image.open(BytesIO(cairosvg.svg2png(bytestring=s.encode(), output_width=size, output_height=size))).convert("RGBA")


def make_banner(W, H):
    """Elefant + Wortmarke „Echo“ mit Block „App“ (Inter Display Black), zentriert auf Schwarz."""
    S = W / 320
    banner = Image.new("RGBA", (W, H), K)
    icon = render(svg(motiv(Y, K, 2.55)), 1024)
    icon = icon.crop(icon.getbbox())
    ih = int(180 * S * 0.56)
    icon = icon.resize((int(icon.width * ih / icon.height), ih), Image.LANCZOS)
    d = ImageDraw.Draw(banner)
    font = ImageFont.truetype(FONT, int(40 * S))
    sfont = ImageFont.truetype(FONT, int(20 * S))
    bb = d.textbbox((0, 0), "Echo", font=font)
    sb = d.textbbox((0, 0), "App", font=sfont)
    pad, gap1, gap2 = int(5 * S), int(10 * S), int(5 * S)
    block_w = (sb[2] - sb[0]) + 2 * pad
    total = icon.width + gap1 + (bb[2] - bb[0]) + gap2 + block_w
    x0 = (W - total) // 2
    banner.alpha_composite(icon, (x0, (H - ih) // 2))
    x = x0 + icon.width + gap1
    y = (H - (bb[3] - bb[1])) // 2 - bb[1]
    d.text((x, y), "Echo", font=font, fill=Y)
    x2 = x + (bb[2] - bb[0]) + gap2
    bh = (sb[3] - sb[1]) + 2 * pad
    by = y + bb[3] - bh
    d.rounded_rectangle((x2, by, x2 + block_w, by + bh), radius=int(6 * S), fill=Y)
    d.text((x2 + pad - sb[0], by + pad - sb[1]), "App", font=sfont, fill=K)
    return banner


files = {
    "echo-app_symbol_rund": svg(f'<circle cx="512" cy="512" r="512" fill="{K}"/>' + motiv(Y, K, 2.55)),
    "echo-app_android-vordergrund": svg(motiv(Y, K, 1.70)),
}
m_white = motiv("white", "black", 1.70)
files["echo-app_android-monochrom"] = svg(
    f'<defs><mask id="m">{m_white}</mask></defs><rect width="1024" height="1024" fill="#000" mask="url(#m)"/>')
for name, s in files.items():
    open(f"{name}.svg", "w").write(s)
    render(s).save(f"{name}_1024.png")
render(svg(f'<rect width="1024" height="1024" fill="{K}"/>' + motiv(Y, K, 2.3)), 512).save("echo-app_store_512.png")
# Fernseher (Fire TV/Android TV): quadratisches Symbol mit dem Banner-Motiv. Fire TV zeigt für
# Apps außerhalb des Amazon Appstore kein Banner, nur das Symbol (Fire OS 7 vergrößert zudem
# Adaptive Icons zu stark) – daher steckt das Banner im quadratischen TV-Symbol.
tv_banner = make_banner(1024, 576)
tv_img = Image.new("RGBA", (1024, 1024), K)
tv_img.alpha_composite(tv_banner, (0, (1024 - 576) // 2))
tv_img.convert("RGB").save("echo-app_tv-symbol_1024.png")

banner = make_banner(320 * 4, 180 * 4)
banner.resize((320, 180), Image.LANCZOS).convert("RGB").save("echo-app_tv-banner_320x180.png")

# Vorschau: runde/abgerundete Maske, 48 px, Banner
fg = Image.open("echo-app_android-vordergrund_1024.png")
adaptive = Image.alpha_composite(Image.new("RGBA", (1024, 1024), K), fg)
c = int(1024 * 18 / 108)
adaptive = adaptive.crop((c, c, 1024 - c, 1024 - c)).resize((1024, 1024), Image.LANCZOS)


def masked(img, shape):
    m = Image.new("L", img.size, 0)
    dd = ImageDraw.Draw(m)
    if shape == "rund":
        dd.ellipse((0, 0, 1023, 1023), fill=255)
    else:
        dd.rounded_rectangle((0, 0, 1023, 1023), radius=230, fill=255)
    out = Image.new("RGBA", img.size, (0, 0, 0, 0))
    out.paste(img, (0, 0), m)
    return out


sheet = Image.new("RGBA", (1700, 420), "#808080")
for i, t in enumerate([masked(adaptive, "rund"), masked(adaptive, "eckig"),
                       adaptive.resize((48, 48), Image.LANCZOS).resize((320, 320), Image.NEAREST)]):
    sheet.alpha_composite(t.resize((320, 320), Image.LANCZOS), (40 + i * 360, 50))
sheet.alpha_composite(Image.open("echo-app_tv-banner_320x180.png").convert("RGBA").resize((560, 315), Image.LANCZOS), (1110, 52))
sheet.convert("RGB").save("00_uebersicht-launcher.png")

px = fg.load()
worst = max((math.hypot(x - 512, y - 512) for y in range(0, 1024, 2) for x in range(0, 1024, 2) if px[x, y][3] > 20), default=0)
print(f"max. Radius Vordergrund: {worst:.0f} px (Grenze 300)")
