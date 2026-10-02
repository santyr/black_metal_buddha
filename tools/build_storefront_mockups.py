from __future__ import annotations

import hashlib
import random
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parents[1]
PRINTS = ROOT / "black_metal_buddhist_prints"
OUT = ROOT / "app" / "static" / "products"

CANVAS = 1200
BACKGROUND = (43, 43, 43)  # Brand Ash Charcoal #2B2B2B
SHIRT_BASE = (8, 8, 8)
SHIRT_HIGHLIGHT = (20, 20, 20)
SHIRT_SHADOW = (2, 2, 2)

# Until a final Printful blank/variant is frozen, mockups use the conservative
# smaller-garment large-front reference described by Printful: ~11.5 x 13.8 in.
# The visual chest box below preserves that 5:6-ish proportion and keeps all
# critical text/details well inside the garment.
REFERENCE_PRINT_IN = (11.5, 13.8)
PRINT_BOX = (392, 275, 808, 774)  # 416 x 499 px, 0.834 ratio

PRODUCTS = {
    "lotus-of-the-void": PRINTS / "03_two_ink_png" / "lotus_of_the_void_two_ink_12x16_300dpi.png",
    "dharma-of-decay": PRINTS / "03_two_ink_png" / "dharma_of_decay_two_ink_12x16_300dpi.png",
    "meditate-on-death": PRINTS / "03_two_ink_png" / "meditate_on_death_two_ink_12x16_300dpi.png",
    "longchenpa-rest-in-illusion": PRINTS / "03_two_ink_png" / "longchenpa_rest_in_illusion_two_ink_12x16_300dpi.png",
}


def _noise(size: tuple[int, int], seed: int, amplitude: int = 10) -> Image.Image:
    rnd = random.Random(seed)
    pixels = bytearray(size[0] * size[1])
    for i in range(len(pixels)):
        pixels[i] = max(0, min(255, 128 + rnd.randint(-amplitude, amplitude)))
    return Image.frombytes("L", size, bytes(pixels))


def _background() -> Image.Image:
    image = Image.new("RGB", (CANVAS, CANVAS), BACKGROUND)
    # Subtle vignette and stone/fabric texture, intentionally brand-neutral.
    vignette = Image.new("L", (CANVAS, CANVAS), 0)
    draw = ImageDraw.Draw(vignette)
    for radius in range(830, 190, -12):
        value = int(210 * (1 - (radius - 190) / 640))
        box = (CANVAS // 2 - radius, CANVAS // 2 - radius,
               CANVAS // 2 + radius, CANVAS // 2 + radius)
        draw.ellipse(box, fill=max(0, min(210, value)))
    vignette = vignette.filter(ImageFilter.GaussianBlur(70))
    glow = Image.new("RGB", image.size, (26, 26, 26))
    image = Image.composite(glow, image, vignette)

    noise = _noise(image.size, seed=1717, amplitude=13).filter(ImageFilter.GaussianBlur(.35))
    texture = Image.merge("RGB", (noise, noise, noise))
    image = Image.blend(image, texture, .075)
    return image


def _shirt_mask() -> Image.Image:
    mask = Image.new("L", (CANVAS, CANVAS), 0)
    d = ImageDraw.Draw(mask)
    # Classic black tee silhouette. Torso width/height approximates a relaxed
    # unisex blank while sleeves keep the mockup visually consistent.
    points = [
        (404, 176), (326, 218), (181, 337), (245, 467),
        (344, 410), (350, 1040), (850, 1040), (856, 410),
        (955, 467), (1019, 337), (874, 218), (796, 176),
        (706, 148), (494, 148),
    ]
    d.polygon(points, fill=255)
    # Shoulder rounding / torso fill.
    d.rounded_rectangle((342, 180, 858, 1042), radius=52, fill=255)
    return mask.filter(ImageFilter.GaussianBlur(.7))


def _shirt_layer(mask: Image.Image) -> Image.Image:
    # Soft shadow below/around shirt.
    shadow_mask = mask.filter(ImageFilter.GaussianBlur(28))
    shadow = Image.new("RGBA", (CANVAS, CANVAS), (0, 0, 0, 175))
    shadow.putalpha(shadow_mask)

    base = Image.new("RGBA", (CANVAS, CANVAS), (*SHIRT_BASE, 255))
    base.putalpha(mask)

    # Broad fabric highlight through the center of the torso.
    grad = Image.new("L", (CANVAS, CANVAS), 0)
    gp = grad.load()
    for y in range(CANVAS):
        for x in range(CANVAS):
            dx = abs(x - CANVAS / 2) / 340
            dy = abs(y - 560) / 650
            v = int(max(0, 46 * (1 - min(1, dx * .85 + dy * .18))))
            gp[x, y] = v
    highlight = Image.new("RGBA", (CANVAS, CANVAS), (*SHIRT_HIGHLIGHT, 255))
    highlight.putalpha(ImageChops.multiply(mask, grad))

    fabric = _noise((CANVAS, CANVAS), seed=3001, amplitude=18).filter(ImageFilter.GaussianBlur(.4))
    fabric_rgba = Image.new("RGBA", (CANVAS, CANVAS), (255, 255, 255, 0))
    fabric_rgba.putalpha(ImageChops.multiply(mask, fabric.point(lambda p: max(0, p - 104))))

    composite = Image.new("RGBA", (CANVAS, CANVAS), (0, 0, 0, 0))
    composite.alpha_composite(shadow)
    composite.alpha_composite(base)
    composite.alpha_composite(highlight)
    composite.alpha_composite(fabric_rgba)
    return composite


def _collar_and_seams(canvas: Image.Image) -> None:
    d = ImageDraw.Draw(canvas)
    # Collar hole and ribbing.
    d.ellipse((477, 132, 723, 262), fill=(3, 3, 3, 255), outline=(33, 33, 33, 255), width=11)
    d.arc((493, 148, 707, 246), 10, 170, fill=(47, 47, 47, 255), width=3)
    # Sleeve and hem seams.
    seam = (33, 33, 33, 210)
    d.line((205, 375, 337, 447), fill=seam, width=4)
    d.line((995, 375, 863, 447), fill=seam, width=4)
    d.line((365, 1015, 835, 1015), fill=seam, width=4)


def _trim_art(image: Image.Image) -> Image.Image:
    image = image.convert("RGBA")
    bbox = image.getchannel("A").getbbox()
    if not bbox:
        raise RuntimeError("print master is fully transparent")
    return image.crop(bbox)


def _place_art(canvas: Image.Image, art: Image.Image) -> None:
    x0, y0, x1, y1 = PRINT_BOX
    box_w, box_h = x1 - x0, y1 - y0
    art = _trim_art(art)
    scale = min(box_w / art.width, box_h / art.height)
    size = (max(1, round(art.width * scale)), max(1, round(art.height * scale)))
    art = art.resize(size, Image.Resampling.LANCZOS)

    # A tiny fabric interaction keeps the design from looking pasted on.
    alpha = art.getchannel("A")
    weave = _noise(size, seed=666, amplitude=5)
    alpha = ImageChops.multiply(alpha, weave.point(lambda p: min(255, 240 + (p - 128) // 3)))
    art.putalpha(alpha)

    px = x0 + (box_w - size[0]) // 2
    py = y0 + (box_h - size[1]) // 2
    canvas.alpha_composite(art, (px, py))


def build(slug: str, source: Path) -> Path:
    if not source.exists():
        raise FileNotFoundError(source)

    background = _background().convert("RGBA")
    shirt_mask = _shirt_mask()
    background.alpha_composite(_shirt_layer(shirt_mask))
    _collar_and_seams(background)
    _place_art(background, Image.open(source))

    # Final shadow under hem.
    d = ImageDraw.Draw(background)
    d.ellipse((330, 1018, 870, 1080), fill=(0, 0, 0, 42))

    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / f"{slug}.webp"
    background.convert("RGB").resize((900, 900), Image.Resampling.LANCZOS).save(
        path, "WEBP", quality=88, method=6
    )
    return path


def main() -> None:
    print(f"Mockup reference print area: {REFERENCE_PRINT_IN[0]} x {REFERENCE_PRINT_IN[1]} in")
    for slug, source in PRODUCTS.items():
        path = build(slug, source)
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        with Image.open(path) as check:
            check.load()
            print(slug, check.size, len(path.read_bytes()), digest)


if __name__ == "__main__":
    main()
