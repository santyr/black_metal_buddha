"""Read-only import of the catalog managed in Printful."""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from io import BytesIO
from pathlib import Path
import hashlib
import re
import time
import unicodedata
from urllib.parse import unquote, urljoin, urlsplit
from uuid import uuid4

import httpx
from PIL import Image, ImageOps
from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import PrintfulCatalogState, PrintfulProduct, ProductVariant
from .settings import Settings, settings


class CatalogSyncError(ValueError):
    pass


def _id(value) -> str:
    text = str(value)
    if not text.isdigit() or int(text) <= 0:
        raise CatalogSyncError("Printful returned an invalid product or variant ID")
    return str(int(text))


def _price(value) -> int | None:
    try:
        amount = Decimal(str(value))
        cents = amount * 100
        if not amount.is_finite() or cents != cents.to_integral_value() or not 0 < cents < 2**31:
            return None
        return int(cents)
    except (InvalidOperation, ValueError, TypeError):
        return None


def _api_json(client: httpx.Client, path: str, **params) -> dict:
    for attempt in range(2):
        try:
            response = client.get("https://api.printful.com" + path, params=params)
        except httpx.HTTPError:
            raise CatalogSyncError("Printful could not be reached; the previous catalog is retained") from None
        if response.status_code == 429 and attempt == 0:
            try:
                pause = min(60, max(10, int(response.headers.get("Retry-After", "60"))))
            except ValueError:
                pause = 60
            time.sleep(pause)
            continue
        if response.status_code != 200:
            raise CatalogSyncError(f"Printful catalog request failed with HTTP {response.status_code}")
        try:
            data = response.json()
        except ValueError:
            raise CatalogSyncError("Printful returned an invalid catalog response") from None
        if not isinstance(data, dict) or data.get("code") != 200 or "result" not in data:
            raise CatalogSyncError("Printful returned an invalid catalog response")
        return data
    raise CatalogSyncError("Printful is rate limited; the previous catalog is retained")


def _product_ids(client: httpx.Client) -> list[str]:
    ids: list[str] = []
    total: int | None = None
    for _ in range(100):
        data = _api_json(client, "/store/products", limit=100, offset=len(ids))
        rows, paging = data.get("result"), data.get("paging")
        if not isinstance(rows, list) or not isinstance(paging, dict):
            raise CatalogSyncError("Printful catalog pagination is incomplete")
        count = paging.get("total")
        if type(count) is not int or count < 0 or paging.get("offset") != len(ids):
            raise CatalogSyncError("Printful catalog pagination is invalid")
        if total is not None and total != count:
            raise CatalogSyncError("Printful catalog changed during pagination; retry on the next sync")
        total = count
        for row in rows:
            if not isinstance(row, dict):
                raise CatalogSyncError("Printful returned an invalid product list")
            product_id = _id(row.get("id"))
            if product_id in ids:
                raise CatalogSyncError("Printful returned duplicate product IDs")
            ids.append(product_id)
        if len(ids) == total:
            return ids
        if not rows or len(ids) > total:
            raise CatalogSyncError("Printful catalog pagination is incomplete")
    raise CatalogSyncError("Printful catalog exceeded the supported pagination limit")


def fetch_snapshot(config: Settings = settings) -> list[dict]:
    if not config.printful_token or not config.printful_store_id:
        raise CatalogSyncError("Printful catalog access is not configured")
    headers = {
        "Authorization": "Bearer " + config.printful_token,
        "X-PF-Store-Id": config.printful_store_id,
        "User-Agent": "BlackMetalBuddha/catalog-sync",
    }
    result: list[dict] = []
    variants_seen, skus_seen = set(), set()
    with httpx.Client(headers=headers, timeout=25, follow_redirects=False) as client:
        ids = _product_ids(client)
        for product_id in ids:
            raw = _api_json(client, "/store/products/" + product_id)["result"]
            if not isinstance(raw, dict):
                raise CatalogSyncError("Printful returned invalid product details")
            product, variants = raw.get("sync_product"), raw.get("sync_variants")
            if not isinstance(product, dict) or not isinstance(variants, list):
                raise CatalogSyncError("Printful returned incomplete product details")
            if _id(product.get("id")) != product_id or product.get("variants") != len(variants):
                raise CatalogSyncError("Printful product identity or variant count does not match")
            name = str(product.get("name") or "").strip()
            if not name or len(name) > 255:
                raise CatalogSyncError("A Printful product needs a valid name")
            normalized = []
            garment = "Printful apparel"
            image = product.get("thumbnail_url") or None
            for variant in variants:
                if not isinstance(variant, dict) or _id(variant.get("sync_product_id")) != product_id:
                    raise CatalogSyncError("Printful variant belongs to an unexpected product")
                variant_id = _id(variant.get("id"))
                sku = str(variant.get("sku") or f"BMB-PF-{product_id}-{variant_id}").strip()
                if variant_id in variants_seen or not sku or len(sku) > 128 or sku in skus_seen:
                    raise CatalogSyncError("Printful has duplicate IDs/SKUs or an invalid SKU")
                variants_seen.add(variant_id)
                skus_seen.add(sku)
                size, color = str(variant.get("size") or "One size"), str(variant.get("color") or "Default")
                if len(size) > 32 or len(color) > 64:
                    raise CatalogSyncError("Printful size or color exceeds the supported field length")
                currency = str(variant.get("currency") or "USD").upper()
                if not re.fullmatch(r"[A-Z]{3}", currency):
                    raise CatalogSyncError("Printful returned an invalid currency")
                cents = _price(variant.get("retail_price")) if currency == "USD" else None
                synced = variant.get("synced") is True
                available = (synced and not variant.get("discontinued") and not variant.get("out_of_stock")
                             and variant.get("availability_status", "active") == "active")
                catalog = variant.get("product") or {}
                if isinstance(catalog, dict):
                    garment = ("Comfort Colors 1717" if catalog.get("product_id") == 586
                               else str(catalog.get("name") or garment).split(" (")[0][:255])
                if not image:
                    for file in variant.get("files") or []:
                        if isinstance(file, dict) and file.get("type") == "preview" and file.get("status") == "ok":
                            image = file.get("url") or file.get("preview_url") or None
                            if image:
                                break
                normalized.append({"id": variant_id, "sku": sku, "size": size, "color": color,
                                   "currency": currency, "price": cents, "synced": synced,
                                   "available": bool(available)})
            result.append({"id": product_id, "name": name, "garment": garment,
                           "ignored": bool(product.get("is_ignored")), "image": image,
                           "variants": normalized})
        # A product added/deleted while details were fetched must not become a partial snapshot.
        if set(_product_ids(client)) != set(ids):
            raise CatalogSyncError("Printful catalog changed during sync; retry on the next sync")
    return result


def _safe_image_url(url: str, config: Settings) -> None:
    try:
        parsed = urlsplit(url)
        own_host = urlsplit(config.public_base_url).hostname
        own = parsed.hostname == own_host and parsed.path.startswith(("/static/products/", "/static/product-scenes/", "/product-images/"))
        provider = bool(parsed.hostname and parsed.hostname.endswith(".printful.com"))
        if (parsed.scheme != "https" or parsed.username or parsed.password or parsed.port not in (None, 443)
                or not (own or provider) or ".." in unquote(parsed.path).split("/") or "\\" in unquote(parsed.path)):
            raise ValueError
    except (ValueError, TypeError):
        raise CatalogSyncError("The product mockup must use a Printful image or a storefront image URL") from None


def cache_mockup(url: str | None, previous: PrintfulProduct | None, config: Settings) -> tuple[str | None, str | None, str | None]:
    if not url:
        return None, None, None
    _safe_image_url(url, config)
    directory = Path(config.printful_catalog_image_dir)
    directory.mkdir(parents=True, exist_ok=True)
    headers = {"User-Agent": "Mozilla/5.0"}
    cached = False
    if (previous and previous.source_image_url == url and previous.image
            and re.fullmatch(r"/product-images/[a-f0-9]{64}\.webp", previous.image)):
        path = directory / previous.image.rsplit("/", 1)[1]
        if path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest() == path.stem:
            cached = True
            if previous.image_etag:
                headers["If-None-Match"] = previous.image_etag
            if previous.image_last_modified:
                headers["If-Modified-Since"] = previous.image_last_modified
    # This client deliberately has no Printful Authorization header.
    with httpx.Client(timeout=25, follow_redirects=False, headers=headers) as client:
        current = url
        content = bytearray()
        for _ in range(6):
            _safe_image_url(current, config)
            try:
                with client.stream("GET", current) as response:
                    if response.status_code == 304 and cached:
                        return previous.image, previous.image_etag, previous.image_last_modified
                    if response.status_code in (301, 302, 303, 307, 308):
                        location = response.headers.get("Location")
                        if not location:
                            raise CatalogSyncError("Mockup redirect is incomplete")
                        current = urljoin(current, location)
                        continue
                    if response.status_code != 200:
                        raise CatalogSyncError(f"Mockup download failed with HTTP {response.status_code}")
                    etag = response.headers.get("ETag")
                    modified = response.headers.get("Last-Modified")
                    if modified and len(modified) > 128:
                        modified = None
                    for chunk in response.iter_bytes():
                        content.extend(chunk)
                        if len(content) > 25 * 1024 * 1024:
                            raise CatalogSyncError("Mockup file exceeds the supported size")
                    break
            except httpx.HTTPError:
                raise CatalogSyncError("Mockup download failed; the previous catalog is retained") from None
        else:
            raise CatalogSyncError("Mockup has too many redirects")
    try:
        with Image.open(BytesIO(content)) as source:
            if source.format not in {"JPEG", "PNG", "WEBP"} or source.width * source.height > 20_000_000:
                raise CatalogSyncError("Mockup format or dimensions are unsupported")
            source.load()
            source = ImageOps.exif_transpose(source)
            mode = "RGBA" if "A" in source.getbands() else "RGB"
            image = ImageOps.pad(source.convert(mode), (900, 900), method=Image.Resampling.LANCZOS,
                                 color=(43, 43, 43, 0) if mode == "RGBA" else (43, 43, 43))
            buffer = BytesIO()
            image.save(buffer, format="WEBP", quality=92, method=6)
            data = buffer.getvalue()
    except CatalogSyncError:
        raise
    except (OSError, ValueError, Image.DecompressionBombError):
        raise CatalogSyncError("Mockup could not be decoded") from None
    digest = hashlib.sha256(data).hexdigest()
    target = directory / (digest + ".webp")
    temporary = directory / ("." + uuid4().hex + ".tmp")
    try:
        temporary.write_bytes(data)
        temporary.chmod(0o644)
        temporary.replace(target)
    finally:
        temporary.unlink(missing_ok=True)
    return "/product-images/" + target.name, etag, modified


def _slug(name: str, product_id: str, used: set[str]) -> str:
    plain = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode().lower()
    base = re.sub(r"[^a-z0-9]+", "-", plain).strip("-")[:100] or "product"
    value = base if base not in used else base + "-" + product_id
    if value in used:
        raise CatalogSyncError("A stable product URL could not be assigned")
    return value


def sync_catalog(session: Session, *, config: Settings = settings, apply: bool = True) -> dict:
    if not config.printful_catalog_sync_enabled:
        raise CatalogSyncError("Printful catalog sync is disabled")
    from .catalog import PRODUCTS
    snapshot = fetch_snapshot(config)
    previous = {p.printful_product_id: p for p in session.scalars(select(PrintfulProduct)).all()}
    old_variants = session.scalars(select(ProductVariant)).all()
    by_id = {}
    for variant in old_variants:
        if variant.printful_variant_id:
            if variant.printful_variant_id in by_id:
                raise CatalogSyncError("Local catalog has duplicate Printful variant mappings")
            by_id[variant.printful_variant_id] = variant
    known_slugs = {v.printful_product_id: v.product_slug for v in old_variants if v.printful_product_id}
    used = {p.slug for p in previous.values()}
    rank = {p.slug: i for i, p in enumerate(PRODUCTS)}
    prepared = []
    for raw in snapshot:
        old = previous.get(raw["id"])
        slug = old.slug if old else known_slugs.get(raw["id"])
        if not slug:
            slug = _slug(raw["name"], raw["id"], used)
        used.add(slug)
        image, etag, modified = cache_mockup(raw["image"], old, config) if not raw["ignored"] else (None, None, None)
        visible = bool(not raw["ignored"] and image and any(v["synced"] and v["price"] for v in raw["variants"]))
        prepared.append({**raw, "slug": slug, "cached_image": image, "etag": etag,
                         "last_modified": modified, "visible": visible})
    report = {"products": sum(p["visible"] for p in prepared),
              "variants": sum(len(p["variants"]) for p in prepared), "apply": apply}
    if not apply:
        session.rollback()
        return report
    now = datetime.now(timezone.utc)
    incoming_ids = {v["id"] for p in prepared for v in p["variants"]}
    incoming_skus = {v["sku"]: v["id"] for p in prepared for v in p["variants"]}
    # Move changed/retired SKUs out of the way before assigning a complete snapshot.
    for variant in old_variants:
        variant.catalog_visible = False
        target_id = incoming_skus.get(variant.sku)
        intended = next((v["sku"] for p in prepared for v in p["variants"] if v["id"] == variant.printful_variant_id), None)
        if (intended is not None and intended != variant.sku) or (target_id and target_id != variant.printful_variant_id):
            variant.sku = "BMB-ARCHIVED-" + str(variant.id) + "-" + uuid4().hex[:12].upper()
        if variant.printful_variant_id not in incoming_ids:
            variant.active = False
            variant.sellable = False
    session.flush()
    for product in previous.values():
        product.visible = False
    for raw in prepared:
        product = previous.get(raw["id"])
        if product is None:
            product = PrintfulProduct(printful_product_id=raw["id"], slug=raw["slug"],
                                     sort_order=rank.get(raw["slug"], 100))
            session.add(product)
        product.name, product.garment_name = raw["name"], raw["garment"]
        product.image, product.source_image_url = raw["cached_image"], raw["image"]
        product.image_etag, product.image_last_modified = raw["etag"], raw["last_modified"]
        product.visible, product.updated_at = raw["visible"], now
        for v in raw["variants"]:
            row = by_id.get(v["id"])
            if row is None:
                row = ProductVariant()
                session.add(row)
            row.product_slug, row.sku = product.slug, v["sku"]
            row.size, row.color = v["size"], v["color"]
            row.currency, row.retail_price_cents = v["currency"], v["price"]
            row.printful_product_id, row.printful_variant_id = raw["id"], v["id"]
            row.active = bool(raw["visible"] and v["available"] and v["price"])
            row.sellable = row.active
            row.catalog_visible = bool(raw["visible"] and v["synced"] and v["price"])
            row.updated_at = now
    state = session.get(PrintfulCatalogState, 1)
    if state is None:
        state = PrintfulCatalogState(id=1)
        session.add(state)
    state.store_id, state.synced_at = config.printful_store_id, now
    state.product_count, state.variant_count = report["products"], report["variants"]
    session.commit()
    return report


def require_current_catalog(session: Session, config: Settings = settings) -> None:
    if not config.printful_catalog_sync_enabled:
        return
    state = session.get(PrintfulCatalogState, 1)
    if state is None or state.store_id != config.printful_store_id:
        raise CatalogSyncError("The product catalog is temporarily unavailable")
    synced = state.synced_at
    if synced.tzinfo is None:
        synced = synced.replace(tzinfo=timezone.utc)
    if (datetime.now(timezone.utc) - synced).total_seconds() > 600:
        raise CatalogSyncError("The product catalog is temporarily unavailable; please try again shortly")
