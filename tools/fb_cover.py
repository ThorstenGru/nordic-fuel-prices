"""Draws the Facebook Page cover (1640x624) so that nothing important is cut on a phone.

Mobile crops the cover to about 16:9 (the middle ~1110 px of 1640) and the profile picture covers the bottom centre. So everything sits in x 330-1310 and y < 400.
Static text only (no live prices that would go stale).

    python tools/fb_cover.py [OUT.png]      # default docs/facebook/cover.png
"""
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

W, H = 1640, 624
BG, TOP, FG, GREEN, DIM, CHIP = (14, 26, 41), (11, 148, 112), (247, 250, 252), (94, 234, 212), (150, 165, 185), (31, 52, 78)
FONTS = ["C:/Windows/Fonts/arialbd.ttf", "C:/Windows/Fonts/arial.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"]


def font(size, bold=True):
    for p in FONTS[0::2] if bold else FONTS[1::2]:
        if Path(p).exists():
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def draw(out: Path) -> None:
    im = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(im)
    d.rectangle((0, 0, W, 14), fill=TOP)
    cx = W // 2
    d.text((cx, 120), "Euro Fuel Prices", font=font(104), fill=FG, anchor="mm")
    d.text((cx, 215), "Live fuel prices across Europe", font=font(44, False), fill=GREEN, anchor="mm")
    d.text((cx, 272), "Free map  ·  no account  ·  no ads", font=font(34, False), fill=DIM, anchor="mm")
    codes = ["SE", "NO", "DK", "FI", "DE", "AT", "CH", "PL", "FR", "ES", "IT", "NL"]
    f, pad, gap = font(28), 16, 10
    widths = [d.textlength(c, font=f) + 2 * pad for c in codes]
    x = cx - (sum(widths) + gap * (len(codes) - 1)) / 2
    for c, w in zip(codes, widths):
        d.rounded_rectangle((x, 330, x + w, 384), 14, fill=CHIP)
        d.text((x + w / 2, 357), c, font=f, fill=FG, anchor="mm")
        x += w + gap
    out.parent.mkdir(parents=True, exist_ok=True)
    im.save(out)


if __name__ == "__main__":
    draw(Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parent.parent / "docs" / "facebook" / "cover.png")
