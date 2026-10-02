from dataclasses import dataclass


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
        image="/prints/lotus_of_the_void_REFERENCE_ONLY.jpg",
        image_alt="Black T-shirt mockup for Lotus of the Void, featuring a skeletal meditating figure and red eclipse halo.",
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
        image="/prints/dharma_of_decay_REFERENCE_ONLY.jpg",
        image_alt="Black T-shirt mockup for Dharma of Decay, featuring a mountain stupa, ravens, candles, and red lunar accent.",
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
        image="/prints/meditate_on_death_REFERENCE_ONLY.jpg",
        image_alt="Black T-shirt mockup for Meditate on Death, featuring a skeletal monk, prayer beads, lotus petals, and red sun.",
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
        image="/print-assets/02_two_ink_vector/longchenpa_rest_in_illusion_two_ink.svg",
        image_alt=(
            "Two-ink Black Metal Buddha artwork for Longchenpa — Rest in Illusion, "
            "featuring a wrathful seated master, eclipse halo, phantom reflections, lotus imagery, "
            "and bone-white and ritual-red details."
        ),
        sku="BMB-LONGCHENPA",
        launch_price_cents=3500,
        series="Lineage Series",
    ),
)

PRODUCT_BY_SLUG = {product.slug: product for product in PRODUCTS}
