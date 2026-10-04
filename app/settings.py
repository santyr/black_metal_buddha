from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


def _bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    app_env: str
    public_base_url: str
    database_url: str
    phase1_api_enabled: bool
    square_environment: str
    square_api_version: str
    square_access_token: str | None
    square_location_id: str | None
    square_webhook_signature_key: str | None
    square_webhook_notification_url: str | None
    printful_token: str | None
    printful_store_id: str | None
    printful_mode: str
    printful_webhook_secret_key: str | None
    printful_webhook_public_key: str | None
    phase0_5_approved: bool
    email_mode: str
    smtp_host: str | None
    smtp_port: int
    smtp_username: str | None
    smtp_password: str | None
    email_from: str | None
    printful_confirm_enabled: bool = False
    app_secret_key: str | None = None
    admin_username: str | None = None
    admin_password: str | None = None
    admin_refunds_enabled: bool = False
    admin_cancel_fulfillment_enabled: bool = False
    owner_console_enabled: bool = False
    production_checkout_enabled: bool = False
    production_canary_approved: bool = False
    production_catalog_approved: bool = False
    production_catalog_fingerprint: str | None = None
    production_canary_mode: bool = False
    support_email: str | None = None
    printful_catalog_sync_enabled: bool = False
    printful_catalog_image_dir: str = str(Path(__file__).resolve().parents[1] / ".runtime" / "product-images")
    paypal_environment: str = "sandbox"
    paypal_client_id: str | None = None
    paypal_client_secret: str | None = field(default=None, repr=False)
    paypal_merchant_id: str | None = None
    paypal_webhook_id: str | None = None
    paypal_webhook_notification_url: str | None = None
    checkout_tax_mode: str = "disabled"
    checkout_tax_policy_approved: bool = False
    paypal_production_canary_approved: bool = False

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            app_env=os.getenv("APP_ENV", "development"),
            public_base_url=os.getenv("PUBLIC_BASE_URL", "https://blackmetalbuddha.com").rstrip("/"),
            database_url=os.getenv("DATABASE_URL", "sqlite:///./black_metal_buddha.db"),
            phase1_api_enabled=_bool("PHASE1_API_ENABLED", False),
            square_environment=os.getenv("SQUARE_ENVIRONMENT", "sandbox").lower(),
            square_api_version=os.getenv("SQUARE_API_VERSION", "2026-09-16"),
            square_access_token=os.getenv("SQUARE_ACCESS_TOKEN"),
            square_location_id=os.getenv("SQUARE_LOCATION_ID"),
            square_webhook_signature_key=os.getenv("SQUARE_WEBHOOK_SIGNATURE_KEY"),
            square_webhook_notification_url=os.getenv("SQUARE_WEBHOOK_NOTIFICATION_URL"),
            printful_token=os.getenv("PRINTFUL_TOKEN"),
            printful_store_id=os.getenv("PRINTFUL_STORE_ID"),
            printful_mode=os.getenv("PRINTFUL_MODE", "disabled").lower(),
            printful_webhook_secret_key=os.getenv("PRINTFUL_WEBHOOK_SECRET_KEY"),
            printful_webhook_public_key=os.getenv("PRINTFUL_WEBHOOK_PUBLIC_KEY"),
            phase0_5_approved=_bool("PHASE0_5_APPROVED", False),
            email_mode=os.getenv("EMAIL_MODE", "disabled").lower(),
            smtp_host=os.getenv("SMTP_HOST"),
            smtp_port=int(os.getenv("SMTP_PORT", "587")),
            smtp_username=os.getenv("SMTP_USERNAME"),
            smtp_password=os.getenv("SMTP_PASSWORD"),
            email_from=os.getenv("EMAIL_FROM"),
            printful_confirm_enabled=_bool("PRINTFUL_CONFIRM_ENABLED", False),
            app_secret_key=os.getenv("APP_SECRET_KEY"),
            admin_username=os.getenv("ADMIN_USERNAME"),
            admin_password=os.getenv("ADMIN_PASSWORD"),
            admin_refunds_enabled=_bool("ADMIN_REFUNDS_ENABLED", False),
            admin_cancel_fulfillment_enabled=_bool("ADMIN_CANCEL_FULFILLMENT_ENABLED", False),
            owner_console_enabled=_bool("OWNER_CONSOLE_ENABLED", False),
            production_checkout_enabled=_bool("PRODUCTION_CHECKOUT_ENABLED", False),
            production_canary_approved=_bool("PRODUCTION_CANARY_APPROVED", False),
            production_catalog_approved=_bool("PRODUCTION_CATALOG_APPROVED", False),
            production_catalog_fingerprint=os.getenv("PRODUCTION_CATALOG_FINGERPRINT"),
            production_canary_mode=_bool("PRODUCTION_CANARY_MODE", False),
            support_email=os.getenv("SUPPORT_EMAIL"),
            printful_catalog_sync_enabled=_bool("PRINTFUL_CATALOG_SYNC_ENABLED", False),
            printful_catalog_image_dir=os.getenv("PRINTFUL_CATALOG_IMAGE_DIR") or
                str(Path(__file__).resolve().parents[1] / ".runtime" / "product-images"),
            paypal_environment=os.getenv("PAYPAL_ENVIRONMENT", "sandbox").lower(),
            paypal_client_id=os.getenv("PAYPAL_CLIENT_ID"),
            paypal_client_secret=os.getenv("PAYPAL_CLIENT_SECRET"),
            paypal_merchant_id=os.getenv("PAYPAL_MERCHANT_ID"),
            paypal_webhook_id=os.getenv("PAYPAL_WEBHOOK_ID"),
            paypal_webhook_notification_url=os.getenv("PAYPAL_WEBHOOK_NOTIFICATION_URL"),
            checkout_tax_mode=os.getenv("CHECKOUT_TAX_MODE", "disabled").lower(),
            checkout_tax_policy_approved=_bool("CHECKOUT_TAX_POLICY_APPROVED", False),
            paypal_production_canary_approved=_bool("PAYPAL_PRODUCTION_CANARY_APPROVED", False),
        )

    @property
    def paypal_api_base(self) -> str:
        hosts = {"sandbox": "https://api-m.sandbox.paypal.com",
                 "production": "https://api-m.paypal.com"}
        if self.paypal_environment not in hosts:
            raise ValueError("PAYPAL_ENVIRONMENT must be sandbox or production")
        return hosts[self.paypal_environment]

    @property
    def square_api_base(self) -> str:
        if self.square_environment == "production":
            return "https://connect.squareup.com"
        return "https://connect.squareupsandbox.com"

    @property
    def admin_enabled(self) -> bool:
        return bool(self.admin_username and self.admin_password and self.app_secret_key)

    def validate_safety(self) -> None:
        self.paypal_api_base  # Reject typos instead of silently selecting a payment environment.
        if self.checkout_tax_mode not in {"disabled", "printful_quote"}:
            raise ValueError("CHECKOUT_TAX_MODE must be disabled or printful_quote")
        if self.printful_catalog_sync_enabled and (not self.printful_token or not self.printful_store_id):
            raise ValueError("Printful catalog sync requires a token and store ID")
        if self.printful_mode not in {"disabled", "draft", "production"}:
            raise ValueError("PRINTFUL_MODE must be disabled, draft, or production")
        if self.email_mode not in {"disabled", "console", "smtp"}:
            raise ValueError("EMAIL_MODE must be disabled, console, or smtp")
        if self.email_mode == "smtp" and (not self.smtp_host or not self.email_from):
            raise ValueError("SMTP_HOST and EMAIL_FROM are required when EMAIL_MODE=smtp")

        any_admin = bool(self.admin_username or self.admin_password or self.app_secret_key)
        if any_admin and not self.admin_enabled:
            raise ValueError(
                "ADMIN_USERNAME, ADMIN_PASSWORD, and APP_SECRET_KEY must be configured together"
            )

        if self.printful_mode == "production":
            if not self.phase0_5_approved:
                raise ValueError("Production Printful fulfillment requires PHASE0_5_APPROVED=true")
            if not self.printful_confirm_enabled:
                raise ValueError("Production Printful fulfillment requires PRINTFUL_CONFIRM_ENABLED=true")

        if self.app_env == "production" and self.phase1_api_enabled:
            missing: list[str] = []
            if not self.production_checkout_enabled:
                missing.append("PRODUCTION_CHECKOUT_ENABLED")
            if not self.phase0_5_approved:
                missing.append("PHASE0_5_APPROVED")
            if not self.paypal_production_canary_approved:
                missing.append("PAYPAL_PRODUCTION_CANARY_APPROVED")
            if not self.production_catalog_approved:
                missing.append("PRODUCTION_CATALOG_APPROVED")
            if not self.production_catalog_fingerprint:
                missing.append("PRODUCTION_CATALOG_FINGERPRINT")
            missing.extend(self._paypal_live_prerequisites())
            if self.printful_mode != "production":
                missing.append("PRINTFUL_MODE=production")
            if not self.printful_confirm_enabled:
                missing.append("PRINTFUL_CONFIRM_ENABLED")
            if self.email_mode != "smtp":
                missing.append("EMAIL_MODE=smtp")
            if self.database_url.startswith("sqlite"):
                missing.append("PostgreSQL DATABASE_URL")
            if not self.admin_enabled:
                missing.append("admin credentials + APP_SECRET_KEY")
            if not self.support_email:
                missing.append("SUPPORT_EMAIL")
            if not self.printful_token:
                missing.append("PRINTFUL_TOKEN")
            if not self.printful_store_id:
                missing.append("PRINTFUL_STORE_ID")
            if not self.printful_webhook_secret_key:
                missing.append("PRINTFUL_WEBHOOK_SECRET_KEY")
            if missing:
                raise ValueError(
                    "Production checkout prerequisites are not satisfied: "
                    + ", ".join(missing)
                )


    def validate_canary_safety(self) -> None:
        missing: list[str] = []
        if self.app_env != "production":
            missing.append("APP_ENV=production")
        if self.phase1_api_enabled:
            missing.append("PHASE1_API_ENABLED=false")
        if self.production_checkout_enabled:
            missing.append("PRODUCTION_CHECKOUT_ENABLED=false")
        if not self.production_canary_mode:
            missing.append("PRODUCTION_CANARY_MODE=true")
        if not self.phase0_5_approved:
            missing.append("PHASE0_5_APPROVED=true")
        if not self.production_catalog_approved:
            missing.append("PRODUCTION_CATALOG_APPROVED=true")
        if not self.production_catalog_fingerprint:
            missing.append("PRODUCTION_CATALOG_FINGERPRINT")
        missing.extend(self._paypal_live_prerequisites())
        if self.printful_mode != "production":
            missing.append("PRINTFUL_MODE=production")
        if not self.printful_confirm_enabled:
            missing.append("PRINTFUL_CONFIRM_ENABLED=true")
        if self.email_mode != "smtp":
            missing.append("EMAIL_MODE=smtp")
        if self.database_url.startswith("sqlite"):
            missing.append("PostgreSQL DATABASE_URL")
        if not self.printful_token or not self.printful_store_id:
            missing.append("live Printful credentials")
        if not self.printful_webhook_secret_key:
            missing.append("PRINTFUL_WEBHOOK_SECRET_KEY")
        if not self.smtp_host or not self.email_from:
            missing.append("working SMTP configuration")
        if not self.admin_enabled:
            missing.append("admin credentials + APP_SECRET_KEY")
        if not self.support_email:
            missing.append("SUPPORT_EMAIL")
        if missing:
            raise ValueError("Production canary prerequisites are not satisfied: " + ", ".join(missing))

    def _paypal_live_prerequisites(self) -> list[str]:
        missing = []
        if self.paypal_environment != "production":
            missing.append("PAYPAL_ENVIRONMENT=production")
        for name in ("paypal_client_id", "paypal_client_secret", "paypal_merchant_id", "paypal_webhook_id"):
            if not getattr(self, name):
                missing.append(name.upper())
        expected = f"{self.public_base_url}/api/phase1/webhooks/paypal"
        if not self.public_base_url.startswith("https://") or self.paypal_webhook_notification_url != expected:
            missing.append(f"PAYPAL_WEBHOOK_NOTIFICATION_URL={expected}")
        if self.checkout_tax_mode != "printful_quote":
            missing.append("CHECKOUT_TAX_MODE=printful_quote")
        if not self.checkout_tax_policy_approved:
            missing.append("CHECKOUT_TAX_POLICY_APPROVED")
        return missing


settings = Settings.from_env()
settings.validate_safety()
