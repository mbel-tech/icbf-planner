# -*- coding: utf-8 -*-
"""Generate the PWA icons for the ICBF planner site (teal ground, white fish).

Icons are drawn rather than sourced so they stay crisp at every size and need no
font/emoji rendering (which is unreliable across machines).

Run:  python icbf_icons.py
"""
from pathlib import Path
from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
OUT = HERE / "docs" / "icons"

TEAL = (14, 124, 134)      # --teal from the app
WHITE = (255, 255, 255)


def fish(d, cx, cy, w, h, fill):
    """A simple, legible fish silhouette centred on (cx, cy)."""
    body = [cx - w * 0.50, cy - h * 0.50, cx + w * 0.22, cy + h * 0.50]
    d.ellipse(body, fill=fill)
    # tail
    d.polygon([(cx + w * 0.16, cy),
               (cx + w * 0.50, cy - h * 0.38),
               (cx + w * 0.50, cy + h * 0.38)], fill=fill)
    # eye (punched out of the body)
    r = h * 0.075
    ex, ey = cx - w * 0.30, cy - h * 0.12
    d.ellipse([ex - r, ey - r, ex + r, ey + r], fill=TEAL)


def rounded_icon(size, pad_ratio, radius_ratio, maskable):
    img = Image.new("RGB", (size, size), TEAL)
    d = ImageDraw.Draw(img)
    if not maskable:
        # rounded-square plate on transparent-ish ground reads better as an app tile
        r = int(size * radius_ratio)
        plate = Image.new("RGB", (size, size), TEAL)
        img = plate
        d = ImageDraw.Draw(img)
    inset = size * pad_ratio
    fish(d, size / 2, size / 2, size - 2 * inset, (size - 2 * inset) * 0.62, WHITE)
    return img


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    # maskable icons need the art inside a ~80% safe zone (corners get cropped)
    rounded_icon(192, 0.26, 0.22, True).save(OUT / "icon-192.png")
    rounded_icon(512, 0.26, 0.22, True).save(OUT / "icon-512.png")
    # apple touch icon is never masked -> art can breathe a little more
    rounded_icon(180, 0.20, 0.22, False).save(OUT / "apple-touch-icon.png")
    # favicon
    rounded_icon(64, 0.16, 0.22, False).save(OUT / "favicon-64.png")
    for p in sorted(OUT.iterdir()):
        print("wrote", p.relative_to(HERE), p.stat().st_size, "bytes")


if __name__ == "__main__":
    main()
