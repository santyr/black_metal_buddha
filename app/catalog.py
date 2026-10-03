from dataclasses import dataclass, replace


@dataclass(frozen=True)
class Product:
    slug: str
    name: str
    subtitle: str
    summary: str
    description: str
    image: str
    image_alt: str
    sku: str
    series: str = "Core Collection"
    launch_price_cents: int | None = None
    launch_price_max_cents: int | None = None
    garment_name: str = "Comfort Colors 1717"
    sizes: tuple[str, ...] = ("S", "M", "L", "XL", "2XL")

    @property
    def zoom_image(self) -> str:
        import re
        if self.image and re.fullmatch(r"/product-images/[a-f0-9]{64}\.webp", self.image):
            return self.image.removesuffix(".webp") + ".detail.webp"
        return self.image

    @property
    def size_display(self) -> str:
        return ", ".join(self.sizes)

    @property
    def size_range(self) -> str:
        if self.sizes == ("S", "M", "L", "XL", "2XL"):
            return "S–XXL"
        return f"{self.sizes[0]}–{self.sizes[-1]}" if len(self.sizes) > 1 else self.size_display

    @property
    def variable_price(self) -> bool:
        return bool(self.launch_price_max_cents and self.launch_price_max_cents != self.launch_price_cents)

    @property
    def launch_price_display(self) -> str:
        return "$" + format(self.launch_price_cents / 100, ".2f") if self.launch_price_cents else ""


PRODUCTS = (
    Product(
        slug="lotus-of-the-void",
        name="Lotus of the Void",
        subtitle="No Self. No Fear.",
        summary="A skeletal meditation on non-self, mortality, and the stillness inside the void.",
        description=(
            "Lotus of the Void places a skeletal contemplative figure beneath an eclipse halo, "
            "framed by ravens, smoke, and a thorned lotus. The piece joins black-metal visual "
            "language with themes of impermanence and non-self."
        ),
        image="/static/products/lotus-of-the-void.webp",
        image_alt="Lotus of the Void printed on a black T-shirt against the Black Metal Buddha ash-charcoal background.",
        sku="BMB-LOTUS",
        launch_price_cents=3500,
    ),
    Product(
        slug="dharma-of-decay",
        name="Dharma of Decay",
        subtitle="All Things Pass.",
        summary="A mountain stupa, ravens, candles, and a bone-wheel reminder that every form changes.",
        description=(
            "Dharma of Decay centers a weathered stupa beneath a bone-and-thorn wheel, with ravens, "
            "candles, mist, and a muted red lunar accent. Its theme is simple: all conditioned things "
            "change, and every form passes."
        ),
        image="/static/products/dharma-of-decay.webp",
        image_alt="Dharma of Decay printed on a black T-shirt against the Black Metal Buddha ash-charcoal background.",
        sku="BMB-DHARMA",
        launch_price_cents=3500,
    ),
    Product(
        slug="meditate-on-death",
        name="Meditate on Death",
        subtitle="Emptiness Is Freedom.",
        summary="A stark memento mori built around meditation, prayer beads, lotus petals, and a blood-red sun.",
        description=(
            "Meditate on Death is a memento mori rendered as ritual apparel: a skeletal monk, prayer "
            "beads, lotus petals, smoke, and a distressed red sun. The design points toward mortality "
            "as a contemplative subject rather than spectacle."
        ),
        image="/static/products/meditate-on-death.webp",
        image_alt="Meditate on Death printed on a black T-shirt against the Black Metal Buddha ash-charcoal background.",
        sku="BMB-MEDITATE",
        launch_price_cents=3500,
    ),
    Product(
        slug="longchenpa-rest-in-illusion",
        name="Longchenpa — Rest in Illusion",
        subtitle="Rest in Illusion.",
        summary=(
            "A wrathful vision of Longchenpa surrounded by reflections, dissolving appearances, "
            "and dreamlike forms inspired by the contemplative theme of resting in illusion."
        ),
        description=(
            "Longchenpa — Rest in Illusion is Black Metal Buddha's lineage-series interpretation "
            "of the great Dzogchen master in a fierce visionary form. Mirrored lotus forms, "
            "phantom faces, moon reflections, dissolving landscapes, smoke, and a blood-red eclipse "
            "frame the central figure as reminders that appearances can be vivid without being solid. "
            "The design draws its theme from contemplative teachings on illusion while remaining an "
            "original artistic interpretation rather than a traditional iconographic depiction."
        ),
        image="/static/products/longchenpa-rest-in-illusion.webp",
        image_alt=(
            "Longchenpa — Rest in Illusion printed on a black T-shirt against the "
            "Black Metal Buddha ash-charcoal background."
        ),
        sku="BMB-LONGCHENPA",
        launch_price_cents=3500,
        series="Lineage Series",
    ),
)

PRODUCT_BY_SLUG = {product.slug: product for product in PRODUCTS}

# Provider-managed collaboration; this story is used only after Printful import.
PRODUCT_BY_SLUG["awaken-the-herd-lightning-goats-black-metal-buddha"] = Product(
    slug="awaken-the-herd-lightning-goats-black-metal-buddha",
    name="Awaken the Herd — Lightning Goats × Black Metal Buddha",
    subtitle="Awaken the Herd.",
    summary="Lightning Goats × Black Metal Buddha collaboration in bone and ritual red.",
    description=(
        "Awaken the Herd is a Lightning Goats × Black Metal Buddha collaboration. "
        "The front graphic reads LIGHTNING GOATS / AWAKEN THE HERD in bone and "
        "ritual red on black Comfort Colors 1717. Back and sleeves are blank."
    ),
    image="/static/products/lightning-goats-awaken-the-herd.webp",
    image_alt="Awaken the Herd on a black Comfort Colors 1717 T-shirt against the charcoal background.",
    sku="BMB-LGAWAKEN",
    series="Lightning Goats Series",
    sizes=("S", "M", "L", "XL", "2XL", "3XL", "4XL"),
)



def get_products(session=None) -> tuple[Product, ...]:
    from sqlalchemy import select
    from .db import SessionLocal
    from .models import PrintfulCatalogState, PrintfulProduct, ProductVariant
    from .settings import settings
    if not settings.printful_catalog_sync_enabled:
        return PRODUCTS
    if session is None:
        with SessionLocal() as owned:
            return get_products(owned)
    if session.get(PrintfulCatalogState, 1) is None:
        return PRODUCTS
    records = session.scalars(select(PrintfulProduct).where(PrintfulProduct.visible.is_(True))
                              .order_by(PrintfulProduct.sort_order, PrintfulProduct.name)).all()
    variants = session.scalars(select(ProductVariant).where(ProductVariant.catalog_visible.is_(True))).all()
    size_order = {name: i for i, name in enumerate(("XXS", "XS", "S", "M", "L", "XL", "2XL", "3XL", "4XL", "5XL", "6XL"))}
    products = []
    for record in records:
        current = [v for v in variants if v.product_slug == record.slug and v.retail_price_cents]
        prices = [v.retail_price_cents for v in current]
        sizes = tuple(sorted({v.size for v in current}, key=lambda s: (size_order.get(s, 100), s)))
        curated = PRODUCT_BY_SLUG.get(record.slug)
        product = curated or Product(
            slug=record.slug, name=record.name, subtitle=record.garment_name,
            summary=f"{record.name} on {record.garment_name}.",
            description=f"{record.name} is printed on {record.garment_name}. Choose from the available sizes and colors.",
            image=record.image, image_alt=f"{record.name} product mockup.",
            sku="BMB-PF-" + record.printful_product_id,
        )
        products.append(replace(product, name=record.name, image=record.image,
                                image_alt=f"{record.name} on {record.garment_name}.",
                                garment_name=record.garment_name, sizes=sizes,
                                launch_price_cents=min(prices) if prices else None,
                                launch_price_max_cents=max(prices) if prices else None))
    return tuple(products)


def products_by_slug(session=None) -> dict[str, Product]:
    return {product.slug: product for product in get_products(session)}


def get_product(slug: str, session=None) -> Product | None:
    return products_by_slug(session).get(slug)


def catalog_overview(products: tuple[Product, ...]) -> str:
    if not products:
        return "New products are coming soon."
    garment_names = {p.garment_name for p in products}
    ranges = {p.size_range for p in products}
    prices = [value for p in products for value in (p.launch_price_cents, p.launch_price_max_cents) if value]
    details = []
    if len(garment_names) == 1:
        details.append(next(iter(garment_names)))
    if len(ranges) == 1:
        details.append(next(iter(ranges)))
    if prices:
        low, high = min(prices), max(prices)
        amount = f"${low / 100:.2f}" if low == high else f"${low / 100:.2f}–${high / 100:.2f}"
        details.append(amount + " plus shipping")
    return " · ".join(details) + "." if details else "See current sizes and prices in the shop."
