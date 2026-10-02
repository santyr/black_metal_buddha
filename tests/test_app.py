import hashlib
import struct

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health():
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.text == "ok"


def test_home_has_seo_products_and_branding():
    response = client.get("/")
    assert response.status_code == 200
    assert "<title>Black Metal Buddha" in response.text
    assert 'rel="canonical"' in response.text
    assert "/static/brand/black-metal-buddha-logo.webp" in response.text
    assert '"@type": "Organization"' in response.text
    assert '"@type": "WebSite"' in response.text
    assert '"logo": "https://blackmetalbuddha.com/static/brand/black-metal-buddha-logo.webp"' in response.text
    assert "Lotus of the Void" in response.text
    assert "Dharma of Decay" in response.text
    assert "Meditate on Death" in response.text
    assert "Longchenpa — Rest in Illusion" in response.text


def test_logo_asset_is_complete_and_valid_webp_container():
    response = client.get("/static/brand/black-metal-buddha-logo.webp")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("image/webp")

    data = response.content
    assert len(data) == 13334
    assert data[:4] == b"RIFF"
    assert data[8:12] == b"WEBP"
    assert struct.unpack("<I", data[4:8])[0] + 8 == len(data)
    assert hashlib.sha256(data).hexdigest() == (
        "6e73625e42533c906a777b18056b98a34e84697983ee181f6f395d4427c4614a"
    )


def test_product_schema():
    response = client.get("/products/lotus-of-the-void")
    assert response.status_code == 200
    assert 'application/ld+json' in response.text
    assert '"@type": "Product"' in response.text
    assert "Checkout is intentionally disabled" in response.text


def test_branded_404_is_noindex():
    response = client.get("/products/does-not-exist")
    assert response.status_code == 404
    assert "Nothing remains here." in response.text
    assert 'content="noindex,nofollow"' in response.text


def test_robots_and_sitemap():
    robots = client.get("/robots.txt")
    assert robots.status_code == 200
    assert "Disallow: /cart" in robots.text
    sitemap = client.get("/sitemap.xml")
    assert sitemap.status_code == 200
    assert "/products/meditate-on-death" in sitemap.text
    assert "/products/longchenpa-rest-in-illusion" in sitemap.text


def test_security_headers():
    response = client.get("/")
    assert response.headers["x-content-type-options"] == "nosniff"
    assert "script-src 'self' 'nonce-" in response.headers["content-security-policy"]
    assert 'nonce="' in response.text


def test_checkout_is_hidden_while_phase1_disabled():
    response = client.get("/checkout")
    assert response.status_code == 404


def test_robots_blocks_transactional_utility_paths():
    response = client.get("/robots.txt")
    assert "Disallow: /checkout" in response.text
    assert "Disallow: /orders/" in response.text
    assert "Disallow: /admin" in response.text
    assert "Disallow: /api/" in response.text


def test_admin_is_hidden_when_not_configured():
    response = client.get("/admin")
    assert response.status_code == 404


def test_contact_page_and_sitemap_entry():
    response = client.get("/contact")
    assert response.status_code == 200
    assert "Reach Black Metal Buddha" in response.text
    sitemap = client.get("/sitemap.xml")
    assert "/contact" in sitemap.text


def test_sensitive_routes_are_no_store_and_noindex():
    response = client.get("/checkout")
    assert response.headers["cache-control"] == "no-store, max-age=0"
    assert response.headers["x-robots-tag"] == "noindex, nofollow"

    response = client.get("/admin")
    assert response.headers["cache-control"] == "no-store, max-age=0"
    assert response.headers["x-robots-tag"] == "noindex, nofollow"


def test_terms_page_and_sitemap_entry():
    response = client.get("/terms")
    assert response.status_code == 200
    assert "Terms of Sale" in response.text
    sitemap = client.get("/sitemap.xml")
    assert "/terms" in sitemap.text


def test_longchenpa_product_is_in_catalog_and_print_asset_is_served():
    page = client.get("/products/longchenpa-rest-in-illusion")
    assert page.status_code == 200
    assert "Longchenpa — Rest in Illusion" in page.text
    assert "Rest in Illusion." in page.text
    assert "LINEAGE SERIES" in page.text
    assert "/static/products/longchenpa-rest-in-illusion.webp" in page.text

    art = client.get("/static/products/longchenpa-rest-in-illusion.webp")
    assert art.status_code == 200
    assert art.headers["content-type"].startswith("image/webp")


def test_mockup_restyled_home_structure():
    response = client.get("/")
    assert response.status_code == 200
    assert 'class="masthead shell"' in response.text
    assert 'class="nav-rule"' in response.text
    assert 'class="hero-frame"' in response.text
    assert 'class="collection-band"' in response.text
    assert 'class="manifesto shell"' in response.text
    assert "/static/brand/black-metal-buddha-logo.webp" in response.text


def test_mockup_restyled_shop_and_product_structure():
    shop = client.get("/shop")
    assert shop.status_code == 200
    assert 'class="page-hero shell editorial-hero"' in shop.text
    assert 'class="product-grid product-grid-shop"' in shop.text

    product = client.get("/products/lotus-of-the-void")
    assert product.status_code == 200
    assert 'class="product-image-frame"' in product.text
    assert 'class="product-notes-band"' in product.text


def test_all_products_use_generated_tshirt_mockups():
    slugs = [
        "lotus-of-the-void",
        "dharma-of-decay",
        "meditate-on-death",
        "longchenpa-rest-in-illusion",
    ]
    for slug in slugs:
        path = f"/static/products/{slug}.webp"
        page = client.get(f"/products/{slug}")
        assert page.status_code == 200
        assert path in page.text

        image = client.get(path)
        assert image.status_code == 200
        assert image.headers["content-type"].startswith("image/webp")
        assert image.content[:4] == b"RIFF"
        assert image.content[8:12] == b"WEBP"
        assert struct.unpack("<I", image.content[4:8])[0] + 8 == len(image.content)
