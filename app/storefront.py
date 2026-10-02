from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from .catalog import get_product, products_by_slug
from .models import ProductVariant


SIZE_ORDER = {
    "XS": 0,
    "S": 1,
    "M": 2,
    "L": 3,
    "XL": 4,
    "2XL": 5,
    "XXL": 5,
    "3XL": 6,
    "XXXL": 6,
    "4XL": 7,
    "5XL": 8,
}


@dataclass(frozen=True)
class StorefrontVariant:
    sku: str
    product_slug: str
    product_name: str
    size: str
    color: str
    currency: str
    retail_price_cents: int
    printful_variant_id: str | None = None

    @property
    def price_display(self) -> str:
        return "$" + format(self.retail_price_cents / 100, ".2f")


def sellable_variants_for_product(session: Session, product_slug: str) -> list[StorefrontVariant]:
    product = get_product(product_slug, session)
    if product is None:
        return []

    rows = session.scalars(
        select(ProductVariant).where(
            ProductVariant.product_slug == product_slug,
            ProductVariant.active.is_(True),
            ProductVariant.sellable.is_(True),
            ProductVariant.retail_price_cents.is_not(None),
        )
    ).all()

    variants = [
        StorefrontVariant(
            sku=row.sku,
            product_slug=row.product_slug,
            product_name=product.name,
            size=row.size,
            color=row.color,
            currency=row.currency,
            retail_price_cents=int(row.retail_price_cents or 0),
            printful_variant_id=row.printful_variant_id,
        )
        for row in rows
    ]
    return sorted(
        variants,
        key=lambda item: (
            item.color.lower(),
            SIZE_ORDER.get(item.size.upper(), 100),
            item.size,
            item.sku,
        ),
    )


def sellable_catalog(session: Session) -> list[StorefrontVariant]:
    result: list[StorefrontVariant] = []
    for product_slug in products_by_slug(session):
        result.extend(sellable_variants_for_product(session, product_slug))
    return result


def price_floor_by_product(session: Session) -> dict[str, int]:
    floors: dict[str, int] = {}
    for item in sellable_catalog(session):
        current = floors.get(item.product_slug)
        if current is None or item.retail_price_cents < current:
            floors[item.product_slug] = item.retail_price_cents
    return floors
