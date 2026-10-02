from __future__ import annotations

from io import BytesIO
from pathlib import Path

import cairosvg
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
BASE_SVG = ROOT / "tools" / "mockup_assets" / "black-shirt-charcoal.svg"
OUT_DIR = ROOT / "app" / "static" / "products"

PRODUCTS = {
    "lotus-of-the-void": ROOT / "black_metal_buddhist_prints" / "01_transparent_png" / "lotus_of_the_void_12x16_300dpi.png",
    "dharma-of-decay": ROOT / "black_metal_buddhist_prints" / "01_transparent_png" / "dharma_of_decay_12x16_300dpi.png",
    "meditate-on-death": ROOT / "black_metal_buddhist_prints" / "01_transparent_png" / "meditate_on_death_12x16_300dpi.png",
    "longchenpa-rest-in-illusion": ROOT / "black_metal_buddhist_prints" / "01_transparent_png" / "longchenpa_rest_in_illusion_12x16_300dpi.png",
}

# The production art is 3600 x 4800 at 300 DPI: an actual 12 x 16 inch file.
# Printful currently offers up to 15 x 18 inches for large_front on select DTG
# shirts, but product/size support varies and smaller variants can be
# downscaled. The marketing mockup therefore shows the art at its actual
# 12 x 16 inch footprint rather than visually inflating it to the maximum area.
#
# On this generic adult-shirt drawing the body is calibrated as roughly 22 in
# wide at chest, so 12 in maps to about 235 px. Height follows the 3:4 ratio.
PRINT_WIDTH = 235
PRINT_HEIGHT = 313
PRINT_LEFT = (640 - PRINT_WIDTH) // 2
PRINT_TOP = 140


def render_base() -> Image.Image:
    raw = cairosvg.svg2png(bytestring=BASE_SVG.read_bytes(), output_width=640, output_height=640)
    return Image.open(BytesIO(raw)).convert("RGBA")


def make_mockup(slug: str, print_file: Path) -> Path:
    base = render_base()
    artwork = Image.open(print_file).convert("RGBA")
    if artwork.size != (3600, 4800):
        raise RuntimeError(f"{print_file}: expected 3600x4800, got {artwork.size}")

    artwork = artwork.resize((PRINT_WIDTH, PRINT_HEIGHT), Image.Resampling.LANCZOS)

    # A black garment receives a white DTG underbase, so keep the bone/red
    # artwork substantially opaque. A tiny opacity reduction lets the mockup
    # retain enough fabric character without misrepresenting print color.
    alpha = artwork.getchannel("A").point(lambda p: round(p * 0.97))
    artwork.putalpha(alpha)
    base.alpha_composite(artwork, (PRINT_LEFT, PRINT_TOP))

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / f"{slug}.webp"
    base.convert("RGB").save(out, "WEBP", quality=84, method=6)
    return out


def main() -> None:
    outputs = [make_mockup(slug, path) for slug, path in PRODUCTS.items()]
    for path in outputs:
        with Image.open(path) as image:
            image.load()
            assert image.size == (640, 640)
            assert image.format == "WEBP"
        print(path.relative_to(ROOT), path.stat().st_size)


if __name__ == "__main__":
    main()
