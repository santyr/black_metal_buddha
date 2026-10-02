from __future__ import annotations

import json
import os
import secrets
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.exception_handlers import http_exception_handler
from fastapi.responses import JSONResponse, PlainTextResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.exceptions import HTTPException as StarletteHTTPException

from .admin import router as admin_router
from .branding import LOGO_PATH, LOGO_TYPE
from .api_phase1 import router as phase1_router
from .catalog import catalog_overview, get_products
from .catalog_ops import assert_production_catalog
from .db import SessionLocal, init_db
from .orders import get_order
from .models import PrintfulCatalogState, ProductVariant
from sqlalchemy import select
from .rate_limit import limiter
from .settings import settings as phase1_settings
from .storefront import price_floor_by_product, sellable_catalog, sellable_variants_for_product

ROOT = Path(__file__).resolve().parents[1]
BASE_URL = os.getenv("PUBLIC_BASE_URL", "https://blackmetalbuddha.com").rstrip("/")
SITE_NAME = "Black Metal Buddha"
DEFAULT_DESCRIPTION = (
    "Black Metal Buddha creates dark ritual apparel inspired by impermanence, mortality, "
    "non-self, and contemplative Buddhist themes."
)


@asynccontextmanager
async def lifespan(_: FastAPI):
    # Production schema changes are applied with Alembic. Development and tests
    # may auto-create the current schema for convenience.
    if phase1_settings.app_env != "production":
        init_db()
    elif phase1_settings.phase1_api_enabled:
        with SessionLocal() as session:
            if phase1_settings.printful_catalog_sync_enabled:
                state = session.get(PrintfulCatalogState, 1)
                if state is None or state.store_id != phase1_settings.printful_store_id:
                    raise RuntimeError("The approved Printful catalog has not been imported")
            else:
                assert_production_catalog(session, phase1_settings.production_catalog_fingerprint)
    yield


app = FastAPI(
    title=SITE_NAME,
    docs_url=None if os.getenv("APP_ENV") == "production" else "/docs",
    redoc_url=None,
    lifespan=lifespan,
)

app.mount("/static", StaticFiles(directory=ROOT / "app" / "static"), name="static")
app.mount("/product-images", StaticFiles(directory=phase1_settings.printful_catalog_image_dir,
                                        check_dir=False), name="product-images")
app.mount(
    "/prints",
    StaticFiles(directory=ROOT / "black_metal_buddhist_prints" / "05_original_mockups"),
    name="prints",
)
app.mount(
    "/print-assets",
    StaticFiles(directory=ROOT / "black_metal_buddhist_prints"),
    name="print-assets",
)

templates = Jinja2Templates(directory=ROOT / "app" / "templates")
app.include_router(phase1_router)
app.include_router(admin_router)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    nonce = secrets.token_urlsafe(18)
    request.state.csp_nonce = nonce
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "img-src 'self' data:; "
        "style-src 'self'; "
        f"script-src 'self' 'nonce-{nonce}'; "
        "connect-src 'self'; "
        "base-uri 'self'; frame-ancestors 'none'; form-action 'self'"
    )

    sensitive_prefixes = ("/admin", "/checkout", "/orders/", "/api/")
    if request.url.path.startswith(sensitive_prefixes):
        response.headers["Cache-Control"] = "no-store, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["X-Robots-Tag"] = "noindex, nofollow"

    return response


def page_context(request: Request, **kwargs):
    products = kwargs.pop("products", None)
    if products is None:
        products = get_products()
    return {
        "request": request,
        "site_name": SITE_NAME,
        "base_url": BASE_URL,
        "logo_path": LOGO_PATH,
        "logo_type": LOGO_TYPE,
        "default_description": DEFAULT_DESCRIPTION,
        "products": products,
        "catalog_overview": catalog_overview(products),
        "phase1_enabled": phase1_settings.phase1_api_enabled,
        "support_email": phase1_settings.support_email,
        **kwargs,
    }


def storefront_price_floors() -> dict[str, int]:
    if not phase1_settings.phase1_api_enabled:
        return {}
    with SessionLocal() as session:
        return price_floor_by_product(session)


@app.exception_handler(StarletteHTTPException)
async def http_error_page(request: Request, exc: StarletteHTTPException):
    if request.url.path.startswith("/api/"):
        return await http_exception_handler(request, exc)
    if exc.status_code == 404:
        return templates.TemplateResponse(
            request,
            "404.html",
            page_context(
                request,
                title="Page Not Found | Black Metal Buddha",
                description="The requested Black Metal Buddha page could not be found.",
                canonical=f"{BASE_URL}{request.url.path}",
                robots="noindex,nofollow",
            ),
            status_code=404,
            headers=exc.headers,
        )
    return PlainTextResponse(str(exc.detail), status_code=exc.status_code, headers=exc.headers)


@app.get("/healthz", response_class=PlainTextResponse, include_in_schema=False)
def healthz() -> str:
    return "ok"


@app.get("/", include_in_schema=False)
def home(request: Request):
    structured_data = {
        "@context": "https://schema.org",
        "@graph": [
            {
                "@type": "Organization",
                "@id": f"{BASE_URL}/#organization",
                "name": SITE_NAME,
                "url": f"{BASE_URL}/",
                "logo": f"{BASE_URL}{LOGO_PATH}",
                "description": DEFAULT_DESCRIPTION,
            },
            {
                "@type": "WebSite",
                "@id": f"{BASE_URL}/#website",
                "url": f"{BASE_URL}/",
                "name": SITE_NAME,
                "publisher": {"@id": f"{BASE_URL}/#organization"},
                "description": DEFAULT_DESCRIPTION,
            },
        ],
    }
    return templates.TemplateResponse(
        request,
        "home.html",
        page_context(
            request,
            title="Black Metal Buddha | Ritual Apparel for a Fleeting World",
            description=DEFAULT_DESCRIPTION,
            canonical=f"{BASE_URL}/",
            structured_data=json.dumps(structured_data),
            price_floors=storefront_price_floors(),
        ),
    )


@app.get("/shop", include_in_schema=False)
def shop(request: Request):
    return templates.TemplateResponse(
        request,
        "shop.html",
        page_context(
            request,
            title="Shop Black Metal Buddha | Dark Buddhist-Inspired Apparel",
            description="Explore the current Black Metal Buddha collection, sizes, and prices.",
            canonical=f"{BASE_URL}/shop",
            price_floors=storefront_price_floors(),
        ),
    )


@app.get("/products/{slug}", include_in_schema=False)
def product_detail(request: Request, slug: str):
    products = get_products()
    product = next((item for item in products if item.slug == slug), None)
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found")

    variants = []
    if phase1_settings.phase1_api_enabled:
        with SessionLocal() as session:
            variants = sellable_variants_for_product(session, slug)

    product_schema: dict = {
        "@context": "https://schema.org",
        "@type": "Product",
        "name": product.name,
        "description": product.description,
        "sku": product.sku,
        "brand": {"@type": "Brand", "name": SITE_NAME},
        "category": product.series,
        "image": [f"{BASE_URL}{product.image}"],
        "url": f"{BASE_URL}/products/{product.slug}",
    }
    if variants:
        prices = [item.retail_price_cents for item in variants]
        product_schema["offers"] = {
            "@type": "AggregateOffer",
            "priceCurrency": variants[0].currency,
            "lowPrice": format(min(prices) / 100, ".2f"),
            "highPrice": format(max(prices) / 100, ".2f"),
            "offerCount": len(variants),
            "availability": "https://schema.org/InStock",
        }

    return templates.TemplateResponse(
        request,
        "product.html",
        page_context(
            request,
            product=product,
            products=products,
            variants=variants,
            title=f"{product.name} | Black Metal Buddha",
            description=product.summary,
            canonical=f"{BASE_URL}/products/{product.slug}",
            structured_data=json.dumps(product_schema).replace("<", "\\u003c").replace("&", "\\u0026"),
        ),
    )


@app.get("/about", include_in_schema=False)
def about(request: Request):
    return templates.TemplateResponse(
        request,
        "about.html",
        page_context(
            request,
            title="About Black Metal Buddha | Art, Impermanence, and Ritual Apparel",
            description=(
                "About Black Metal Buddha, an independent apparel project exploring impermanence, "
                "mortality, non-self, and contemplative symbolism through black-metal visual language."
            ),
            canonical=f"{BASE_URL}/about",
        ),
    )


@app.get("/faq", include_in_schema=False)
def faq(request: Request):
    return templates.TemplateResponse(
        request,
        "faq.html",
        page_context(
            request,
            title="FAQ | Black Metal Buddha",
            description="Answers about Black Metal Buddha products, printing, shipping, and launch status.",
            canonical=f"{BASE_URL}/faq",
        ),
    )


@app.get("/cart", include_in_schema=False)
def cart(request: Request):
    return templates.TemplateResponse(
        request,
        "cart.html",
        page_context(
            request,
            title="Cart | Black Metal Buddha",
            description="Black Metal Buddha shopping cart.",
            canonical=f"{BASE_URL}/cart",
            robots="noindex,nofollow",
        ),
    )


@app.get("/checkout", include_in_schema=False)
def checkout(request: Request):
    if not phase1_settings.phase1_api_enabled:
        raise HTTPException(status_code=404, detail="Checkout unavailable")
    with SessionLocal() as session:
        has_variants = bool(sellable_catalog(session))
    if not has_variants:
        raise HTTPException(status_code=404, detail="Checkout unavailable")

    return templates.TemplateResponse(
        request,
        "checkout.html",
        page_context(
            request,
            title="Checkout | Black Metal Buddha",
            description="Secure Black Metal Buddha checkout.",
            canonical=f"{BASE_URL}/checkout",
            robots="noindex,nofollow",
        ),
    )


@app.get("/orders/{order_number}", include_in_schema=False)
def order_status(request: Request, order_number: str):
    with SessionLocal() as session:
        order = get_order(session, order_number)
        if order is None:
            raise HTTPException(status_code=404, detail="Order not found")
        if not phase1_settings.phase1_api_enabled and not order.is_canary:
            raise HTTPException(status_code=404, detail="Order status unavailable")

        if order.refund_state == "COMPLETED":
            heading = "Your payment has been refunded."
            message = "Your full refund is complete."
        elif order.fulfillment_state == "RETURNED":
            heading = "A shipment was returned."
            message = "This shipment needs attention. Please contact us so we can resolve it."
        elif order.fulfillment_state == "CANCELED":
            heading = "Fulfillment was canceled."
            message = "Please contact us if you need help with this order or its refund."
        elif order.order_state == "FULFILLMENT_FAILED":
            heading = "Your order needs attention."
            message = "Payment was received, but fulfillment encountered a problem. Please contact us."
        elif order.order_state == "FULFILLMENT_HOLD":
            heading = "Your order is on hold."
            message = "Payment was received. Fulfillment is paused while an issue is resolved."
        elif order.order_state == "PAID":
            heading = "Payment received."
            message = "Your payment is confirmed. Fulfillment is queued."
        elif order.order_state in {"FULFILLMENT_SUBMITTED", "IN_PRODUCTION"}:
            heading = "Your order is being prepared."
            message = "Payment is confirmed and fulfillment is in progress."
        elif order.order_state == "PARTIALLY_SHIPPED":
            heading = "Part of your order has shipped."
            message = "One or more shipments are on the way. Remaining items will follow."
        elif order.order_state == "SHIPPED":
            heading = "Your order has shipped."
            message = "All items have been shipped. Tracking details appear below when available."
        elif order.order_state == "PAYMENT_FAILED":
            heading = "Payment was not completed."
            message = "No fulfillment will occur for this order."
        else:
            heading = "Payment pending."
            message = "If you just completed Square checkout, this page will update after payment confirmation."

        return templates.TemplateResponse(
            request,
            "order_status.html",
            page_context(
                request,
                order=order,
                status_heading=heading,
                status_message=message,
                title=f"Order {order.order_number} | Black Metal Buddha",
                description="Black Metal Buddha order status.",
                canonical=f"{BASE_URL}/orders/{order.order_number}",
                robots="noindex,nofollow",
            ),
        )


@app.get("/contact", include_in_schema=False)
def contact(request: Request):
    return templates.TemplateResponse(
        request,
        "contact.html",
        page_context(
            request,
            title="Contact | Black Metal Buddha",
            description="Contact Black Metal Buddha for order, product, shipping, or privacy support.",
            canonical=f"{BASE_URL}/contact",
        ),
    )


@app.get("/terms", include_in_schema=False)
def terms(request: Request):
    return templates.TemplateResponse(
        request,
        "terms.html",
        page_context(
            request,
            title="Terms of Sale | Black Metal Buddha",
            description="Black Metal Buddha terms of sale for made-to-order merchandise.",
            canonical=f"{BASE_URL}/terms",
        ),
    )


@app.get("/shipping-returns", include_in_schema=False)
def shipping_returns(request: Request):
    return templates.TemplateResponse(
        request,
        "shipping_returns.html",
        page_context(
            request,
            title="Shipping & Returns | Black Metal Buddha",
            description="Black Metal Buddha shipping and returns information.",
            canonical=f"{BASE_URL}/shipping-returns",
        ),
    )


@app.get("/privacy", include_in_schema=False)
def privacy(request: Request):
    return templates.TemplateResponse(
        request,
        "privacy.html",
        page_context(
            request,
            title="Privacy | Black Metal Buddha",
            description="Black Metal Buddha privacy information.",
            canonical=f"{BASE_URL}/privacy",
        ),
    )


@app.get("/robots.txt", response_class=PlainTextResponse, include_in_schema=False)
def robots() -> str:
    return (
        "User-agent: *\n"
        "Allow: /\n"
        "Disallow: /cart\n"
        "Disallow: /checkout\n"
        "Disallow: /orders/\n"
        "Disallow: /admin\n"
        "Disallow: /api/\n"
        f"Sitemap: {BASE_URL}/sitemap.xml\n"
    )


@app.get("/sitemap.xml", include_in_schema=False)
def sitemap() -> Response:
    paths = ["/", "/shop", "/about", "/faq", "/contact", "/terms", "/shipping-returns", "/privacy"]
    paths.extend(f"/products/{product.slug}" for product in get_products())
    urls = "".join(f"<url><loc>{BASE_URL}{path}</loc></url>" for path in paths)
    xml = f'<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{urls}</urlset>'
    return Response(content=xml, media_type="application/xml")


@app.get("/catalog.json", include_in_schema=False)
def public_catalog() -> JSONResponse:
    with SessionLocal() as session:
        products = get_products(session)
        variants = session.scalars(select(ProductVariant)).all()
        data = []
        for product in products:
            current = [v for v in variants if v.product_slug == product.slug and
                       (v.catalog_visible if phase1_settings.printful_catalog_sync_enabled else v.active)]
            data.append({"slug": product.slug, "name": product.name, "image": product.image,
                         "variants": [{"sku": v.sku, "variantId": v.printful_variant_id,
                                       "size": v.size, "color": v.color,
                                       "priceCents": v.retail_price_cents, "currency": v.currency,
                                       "available": bool(v.active and v.sellable)} for v in current]})
    return JSONResponse({"products": data}, headers={"Cache-Control": "no-store"})
