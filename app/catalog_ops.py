from __future__ import annotations

import hashlib
import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from .catalog import products_by_slug
from .models import ProductVariant


def catalog_manifest(session: Session, *, sellable_only: bool = False) -> dict:
    query = select(ProductVariant).order_by(ProductVariant.sku)
    if sellable_only:
        query = query.where(
            ProductVariant.active.is_(True),
            ProductVariant.sellable.is_(True),
        )

    variants = session.scalars(query).all()
    return {
        "version": 1,
        "currency": "USD",
        "variants": [
            {
                "product_slug": item.product_slug,
                "sku": item.sku,
                "size": item.size,
                "color": item.color,
                "retail_price_cents": item.retail_price_cents,
                "active": item.active,
                "sellable": item.sellable,
                "printful_product_id": item.printful_product_id,
                "printful_variant_id": item.printful_variant_id,
            }
            for item in variants
        ],
    }


def catalog_fingerprint(session: Session) -> str:
    manifest = catalog_manifest(session, sellable_only=True)
    payload = json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(payload).hexdigest()


def catalog_errors(session: Session) -> list[str]:
    known_products = products_by_slug(session)
    errors: list[str] = []
    variants = session.scalars(select(ProductVariant).order_by(ProductVariant.sku)).all()
    sellable_by_product: dict[str, int] = {slug: 0 for slug in known_products}

    seen_skus: set[str] = set()
    for item in variants:
        if item.sku in seen_skus:
            errors.append(f"Duplicate SKU: {item.sku}")
        seen_skus.add(item.sku)

        if (item.active or item.sellable) and item.product_slug not in known_products:
            errors.append(f"{item.sku}: unknown product slug {item.product_slug}")
        if item.currency != "USD":
            errors.append(f"{item.sku}: launch catalog currency must be USD")

        if item.sellable:
            sellable_by_product[item.product_slug] = sellable_by_product.get(item.product_slug, 0) + 1
            if not item.active:
                errors.append(f"{item.sku}: sellable but inactive")
            if item.retail_price_cents is None or item.retail_price_cents <= 0:
                errors.append(f"{item.sku}: sellable without positive retail price")
            if not item.printful_product_id:
                errors.append(f"{item.sku}: sellable without Printful product ID")
            if not item.printful_variant_id:
                errors.append(f"{item.sku}: sellable without Printful variant ID")

    for product_slug, count in sellable_by_product.items():
        if count == 0:
            errors.append(f"{product_slug}: no sellable launch variant")

    return errors


def assert_production_catalog(session: Session, expected_fingerprint: str | None) -> str:
    errors = catalog_errors(session)
    if errors:
        raise RuntimeError("Production catalog invalid: " + "; ".join(errors))

    actual = catalog_fingerprint(session)
    if not expected_fingerprint:
        raise RuntimeError("PRODUCTION_CATALOG_FINGERPRINT is not configured")
    if actual != expected_fingerprint.strip().lower():
        raise RuntimeError(
            "Production catalog fingerprint mismatch: "
            f"expected {expected_fingerprint}, got {actual}"
        )
    return actual


def import_catalog_manifest(
    session: Session,
    manifest: dict,
    *,
    apply: bool,
) -> dict:
    known_products = products_by_slug(session)
    if manifest.get("version") != 1:
        raise ValueError("Unsupported catalog manifest version")
    if manifest.get("currency") != "USD":
        raise ValueError("Catalog manifest currency must be USD")

    changes: list[dict] = []
    for raw in manifest.get("variants") or []:
        product_slug = str(raw.get("product_slug") or "")
        sku = str(raw.get("sku") or "").upper()
        if product_slug not in known_products:
            raise ValueError(f"Unknown product slug: {product_slug}")
        if not sku:
            raise ValueError("Every variant requires a SKU")

        item = session.scalar(select(ProductVariant).where(ProductVariant.sku == sku))
        created = item is None
        if item is None:
            item = ProductVariant(product_slug=product_slug, sku=sku)

        item.product_slug = product_slug
        item.size = str(raw.get("size") or "").upper()
        item.color = str(raw.get("color") or "Black")
        item.currency = "USD"
        item.retail_price_cents = (
            int(raw["retail_price_cents"])
            if raw.get("retail_price_cents") is not None
            else None
        )
        item.active = bool(raw.get("active", False))
        item.sellable = bool(raw.get("sellable", False))
        item.printful_product_id = str(raw.get("printful_product_id") or "") or None
        item.printful_variant_id = str(raw.get("printful_variant_id") or "") or None

        if item.sellable and (
            not item.active
            or not item.retail_price_cents
            or not item.printful_product_id
            or not item.printful_variant_id
        ):
            raise ValueError(f"{sku}: invalid sellable variant")

        changes.append({"sku": sku, "created": created})
        if apply:
            session.add(item)

    if apply:
        session.flush()
        errors = catalog_errors(session)
        if errors:
            session.rollback()
            raise ValueError("Imported catalog is invalid: " + "; ".join(errors))
        session.commit()
    else:
        session.rollback()
    return {"changes": changes, "count": len(changes)}
