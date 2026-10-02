from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class AddressIn(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    name: str = Field(min_length=1, max_length=200)
    email: str = Field(min_length=3, max_length=320)
    phone: str | None = Field(default=None, max_length=18)
    address1: str = Field(min_length=1, max_length=255)
    address2: str | None = Field(default=None, max_length=255)
    city: str = Field(min_length=1, max_length=128)
    state: str = Field(min_length=1, max_length=128)
    postal_code: str = Field(min_length=1, max_length=32)
    country_code: str = Field(default="US", min_length=2, max_length=2)

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        if value.count("@") != 1 or any(character.isspace() for character in value):
            raise ValueError("A valid email address is required")
        local, domain = value.split("@")
        if not local or not domain or domain.startswith(".") or domain.endswith("."):
            raise ValueError("A valid email address is required")
        return value

    @model_validator(mode="after")
    def normalize_address(self):
        self.country_code = self.country_code.upper()
        self.state = self.state.upper()
        if self.country_code in {"US", "CA"} and len(self.state) != 2:
            raise ValueError("US and Canadian addresses require a 2-letter state/province code")
        if self.country_code == "AU" and not (2 <= len(self.state) <= 3):
            raise ValueError("Australian addresses require a state/territory code")
        return self


class OrderLineIn(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    sku: str = Field(min_length=1, max_length=128)
    quantity: int = Field(ge=1, le=10)
    printful_variant_id: str | None = Field(default=None, min_length=1, max_length=128)


class CreateOrderIn(BaseModel):
    recipient: AddressIn
    items: list[OrderLineIn] = Field(min_length=1, max_length=20)

    @model_validator(mode="after")
    def reject_duplicate_skus(self):
        if len({item.sku for item in self.items}) != len(self.items):
            raise ValueError("Each SKU must appear once; use its quantity field")
        return self


class OrderOut(BaseModel):
    order_number: str
    order_state: str
    payment_state: str
    fulfillment_state: str
    currency: str
    subtotal_cents: int
    discount_cents: int
    shipping_cents: int
    shipping_method: str | None = None
    tax_cents: int
    total_cents: int
    refunded_cents: int = 0
    refund_state: str = "NONE"
    square_checkout_url: str | None = None


class ShippingRateOut(BaseModel):
    shipping: str
    name: str
    rate_cents: int
    currency: str
    min_delivery_days: int | None = None
    max_delivery_days: int | None = None


class SelectShippingIn(BaseModel):
    shipping: str = Field(min_length=1, max_length=64)


class RefundRequestIn(BaseModel):
    amount_cents: int | None = Field(default=None, ge=1)
    reason: str = Field(default="Customer refund", min_length=1, max_length=192)


class CatalogVariantOut(BaseModel):
    sku: str
    product_slug: str
    product_name: str
    size: str
    color: str
    currency: str
    retail_price_cents: int
