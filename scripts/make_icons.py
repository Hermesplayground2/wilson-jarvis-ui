#!/usr/bin/env python3
"""Generate the PWA icon set for the Jarvis dashboard.

manifest.json referenced icon-192.png / icon-512.png, but only the .svg versions
existed -- so the icons 404'd and Android refused to offer "Install app".

Produces, next to this script:
    icon-192.png, icon-512.png                    purpose "any" (rounded plate)
    icon-maskable-192.png, icon-maskable-512.png  purpose "maskable" (full bleed,
                                                  glyph inside the safe zone)

Run:  python scripts/make_icons.py
"""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
BG = (5, 13, 20)
FG = (123, 226, 255)

FONTS = [
    "C:/Windows/Fonts/segoeuib.ttf",
    "C:/Windows/Fonts/arialbd.ttf",
    "C:/Windows/Fonts/calibrib.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
]


def load_font(px: int):
    for path in FONTS:
        if Path(path).exists():
            try:
                return ImageFont.truetype(path, px)
            except Exception:
                continue
    return ImageFont.load_default()


def draw_icon(size: int, maskable: bool) -> Image.Image:
    """maskable=True fills the whole canvas: Android crops it to its own shape, so
    the glyph must sit inside the inner 80% safe zone."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    if maskable:
        d.rectangle([0, 0, size, size], fill=BG)
        glyph_ratio = 0.46          # stays inside the safe zone
    else:
        radius = round(size * 32 / 192)
        d.rounded_rectangle([0, 0, size - 1, size - 1], radius=radius, fill=BG)
        glyph_ratio = 0.50

    font = load_font(round(size * glyph_ratio))
    box = d.textbbox((0, 0), "W", font=font)
    w, h = box[2] - box[0], box[3] - box[1]
    d.text(((size - w) / 2 - box[0], (size - h) / 2 - box[1]), "W", font=font, fill=FG)
    return img


def main() -> int:
    made = []
    for size in (192, 512):
        for maskable, name in ((False, "icon-%d.png"), (True, "icon-maskable-%d.png")):
            img = draw_icon(size, maskable)
            out = ROOT / (name % size)
            img.save(out, "PNG", optimize=True)
            made.append("%s (%d bytes)" % (out.name, out.stat().st_size))
    for m in made:
        print("  " + m)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
