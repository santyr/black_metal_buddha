from __future__ import annotations

import argparse
import os
import time
from io import BytesIO
from pathlib import Path
from urllib.parse import urlparse

import httpx
from PIL import Image, ImageOps

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "app" / "static" / "products"

API_BASE = "https://api.printful.com"
CATALOG_PRODUCT_ID = 586  # Comfort Colors 1717
DEFAULT_COLOR = "Black"
DEFAULT_SIZE = "M"
STORE_BG = (43, 43, 43)  # Black Metal Buddha Ash Charcoal
OUTPUT_SIZE = (900, 900)

ART_FILES = {
    "lotus-of-the-void": "lotus_of_the_void_two_ink_12x16_300dpi.png",
    "dharma-of-decay": "dharma_of_decay_two_ink_12x16_300dpi.png",
    "meditate-on-death": "meditate_on_death_two_ink_12x16_300dpi.png",
    "longchenpa-rest-in-illusion": "longchenpa_rest_in_illusion_two_ink_12x16_300dpi.png",
}


class PrintfulMockupError(RuntimeError):
    pass


def _headers(token: str, store_id: str | None) -> dict[str, str]:
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "User-Agent": "BlackMetalBuddha/printful-mockups",
    }
    if store_id:
        headers["X-PF-Store-Id"] = store_id
    return headers


def _result(response: httpx.Response) -> dict:
    response.raise_for_status()
    data = response.json()
    result = data.get("result")
    if not isinstance(result, dict):
        raise PrintfulMockupError(f"Unexpected Printful response: {data!r}")
    return result


def _catalog_variant_id(client: httpx.Client, *, color: str, size: str) -> int:
    result = _result(client.get(f"{API_BASE}/products/{CATALOG_PRODUCT_ID}"))
    variants = result.get("variants")
    if not isinstance(variants, list):
        raise PrintfulMockupError("Printful catalog response did not include variants")

    wanted_color = color.strip().casefold()
    wanted_size = size.strip().casefold()
    for variant in variants:
        if not isinstance(variant, dict):
            continue
        if str(variant.get("color", "")).strip().casefold() != wanted_color:
            continue
        if str(variant.get("size", "")).strip().casefold() != wanted_size:
            continue
        variant_id = variant.get("id")
        if isinstance(variant_id, int) and variant_id > 0:
            return variant_id

    available = sorted({
        (str(v.get("color", "")), str(v.get("size", "")))
        for v in variants if isinstance(v, dict)
    })
    raise PrintfulMockupError(
        f"No Printful catalog variant for color={color!r}, size={size!r}; "
        f"catalog returned {len(available)} color/size combinations"
    )


def _public_art_url(slug: str, *, repo: str, ref: str) -> str:
    filename = ART_FILES[slug]
    return (
        f"https://raw.githubusercontent.com/{repo}/{ref}/"
        "black_metal_buddhist_prints/03_two_ink_png/"
        f"{filename}"
    )


def _available_mockup_styles(client: httpx.Client) -> tuple[set[str], set[str]]:
    result = _result(
        client.get(
            f"{API_BASE}/mockup-generator/printfiles/{CATALOG_PRODUCT_ID}",
            params={"technique": "DTG"},
        )
    )
    groups = result.get("option_groups") or []
    options = result.get("options") or []

    def names(values) -> set[str]:
        found: set[str] = set()
        if not isinstance(values, list):
            return found
        for value in values:
            if isinstance(value, str):
                found.add(value)
            elif isinstance(value, dict):
                for key in ("name", "title", "id", "value"):
                    item = value.get(key)
                    if isinstance(item, str) and item:
                        found.add(item)
        return found

    return names(groups), names(options)


def _create_task(
    client: httpx.Client,
    *,
    variant_id: int,
    image_url: str,
    option_group: str | None,
    option: str | None,
    lifelike: bool,
) -> dict:
    payload: dict = {
        "variant_ids": [variant_id],
        "format": "png",
        "width": 2000,
        "files": [
            {
                "placement": "front",
                "image_url": image_url,
            }
        ],
    }
    if lifelike:
        payload["product_options"] = {"lifelike": True}
    if option_group:
        payload["option_groups"] = [option_group]
    if option:
        payload["options"] = [option]

    return _result(
        client.post(
            f"{API_BASE}/mockup-generator/create-task/{CATALOG_PRODUCT_ID}",
            json=payload,
        )
    )


def _wait_for_task(
    client: httpx.Client,
    task: dict,
    *,
    timeout_sec: int = 180,
    poll_sec: int = 10,
) -> dict:
    task_key = task.get("task_key")
    if not isinstance(task_key, str) or not task_key:
        raise PrintfulMockupError(f"Printful did not return a task key: {task!r}")

    started = time.monotonic()
    current = task
    first_poll = True

    while True:
        status = str(current.get("status", "")).lower()
        if status == "completed":
            return current
        if status == "failed":
            raise PrintfulMockupError(
                f"Printful mockup task failed: {current.get('error') or current!r}"
            )
        if time.monotonic() - started >= timeout_sec:
            raise PrintfulMockupError(
                f"Timed out waiting for Printful mockup task {task_key}"
            )

        # Printful asks clients not to request the first result before 10 seconds.
        time.sleep(max(10 if first_poll else poll_sec, 1))
        first_poll = False
        current = _result(
            client.get(
                f"{API_BASE}/mockup-generator/task",
                params={"task_key": task_key},
            )
        )


def _choose_mockup_url(
    result: dict,
    *,
    option_group: str | None,
    option: str | None,
) -> str:
    mockups = result.get("mockups")
    if not isinstance(mockups, list):
        raise PrintfulMockupError(f"Completed task has no mockups: {result!r}")

    front = [
        item for item in mockups
        if isinstance(item, dict) and item.get("placement") == "front"
    ] or [item for item in mockups if isinstance(item, dict)]

    # If a particular Printful style was requested, prefer the matching extra.
    for item in front:
        extras = item.get("extra") or []
        if not isinstance(extras, list):
            continue
        for extra in extras:
            if not isinstance(extra, dict):
                continue
            group_ok = not option_group or extra.get("option_group") == option_group
            option_ok = not option or extra.get("option") == option
            url = extra.get("url")
            if group_ok and option_ok and isinstance(url, str) and url:
                return url

    # Product-only Flat/Front is preferred when it is among returned extras.
    for item in front:
        extras = item.get("extra") or []
        if not isinstance(extras, list):
            continue
        for extra in extras:
            if not isinstance(extra, dict):
                continue
            if extra.get("option_group") == "Flat" and extra.get("option") == "Front":
                url = extra.get("url")
                if isinstance(url, str) and url:
                    return url

    for item in front:
        url = item.get("mockup_url")
        if isinstance(url, str) and url:
            return url

    raise PrintfulMockupError(f"No usable front mockup URL in task: {result!r}")


def _store_mockup(client: httpx.Client, url: str, destination: Path) -> None:
    parsed = urlparse(url)
    if parsed.scheme != "https":
        raise PrintfulMockupError(f"Refusing non-HTTPS mockup URL: {url}")

    response = client.get(url)
    response.raise_for_status()
    if len(response.content) > 25 * 1024 * 1024:
        raise PrintfulMockupError("Printful mockup download exceeded 25 MiB")

    try:
        source = Image.open(BytesIO(response.content)).convert("RGBA")
        source.load()
    except Exception as exc:
        raise PrintfulMockupError(f"Printful returned an invalid mockup image: {url}") from exc

    # Printful PNG mockups can have transparency. Preserve the real garment and
    # render it over the storefront's established Ash Charcoal background.
    source.thumbnail(OUTPUT_SIZE, Image.Resampling.LANCZOS)
    canvas = Image.new("RGBA", OUTPUT_SIZE, (*STORE_BG, 255))
    x = (OUTPUT_SIZE[0] - source.width) // 2
    y = (OUTPUT_SIZE[1] - source.height) // 2
    canvas.alpha_composite(source, (x, y))

    destination.parent.mkdir(parents=True, exist_ok=True)
    canvas.convert("RGB").save(destination, "WEBP", quality=92, method=6)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate production storefront mockups with Printful's native Mockup Generator."
    )
    parser.add_argument("--color", default=DEFAULT_COLOR)
    parser.add_argument("--size", default=DEFAULT_SIZE)
    parser.add_argument(
        "--repo",
        default=os.getenv("BMB_MOCKUP_ART_REPO", "santyr/black_metal_buddha"),
        help="Public GitHub repository hosting the approved print masters.",
    )
    parser.add_argument(
        "--ref",
        default=os.getenv("BMB_MOCKUP_ART_REF", "main"),
        help="Git ref used in public raw artwork URLs; pin this to a commit in CI.",
    )
    parser.add_argument(
        "--option-group",
        default=os.getenv("PRINTFUL_MOCKUP_OPTION_GROUP", "Flat"),
        help="Printful mockup style group. Use an empty string to accept Printful's default.",
    )
    parser.add_argument(
        "--option",
        default=os.getenv("PRINTFUL_MOCKUP_OPTION", "Front"),
        help="Printful mockup style option. Use an empty string to accept Printful's default.",
    )
    parser.add_argument("--no-lifelike", action="store_true")
    args = parser.parse_args()

    token = os.getenv("PRINTFUL_TOKEN")
    if not token:
        raise SystemExit(
            "PRINTFUL_TOKEN is required. The native mockup workflow intentionally "
            "does not fall back to fabricated garment imagery."
        )
    store_id = os.getenv("PRINTFUL_STORE_ID") or None
    option_group = args.option_group.strip() or None
    option = args.option.strip() or None

    with httpx.Client(
        headers=_headers(token, store_id),
        timeout=httpx.Timeout(60.0, connect=20.0),
        follow_redirects=True,
    ) as client:
        variant_id = _catalog_variant_id(client, color=args.color, size=args.size)
        print(
            f"Printful catalog product {CATALOG_PRODUCT_ID}: "
            f"{args.color} {args.size} -> variant {variant_id}"
        )

        available_groups, available_options = _available_mockup_styles(client)
        if option_group and available_groups and option_group not in available_groups:
            print(
                f"Printful style group {option_group!r} is not available; "
                "letting Printful choose its default group"
            )
            option_group = None
        if option and available_options and option not in available_options:
            print(
                f"Printful style option {option!r} is not available; "
                "letting Printful choose its default option"
            )
            option = None

        submit_interval = float(
            os.getenv("PRINTFUL_MOCKUP_SUBMIT_INTERVAL_SEC", "31")
        )
        last_submit = 0.0

        for slug in ART_FILES:
            elapsed = time.monotonic() - last_submit
            if last_submit and elapsed < submit_interval:
                time.sleep(submit_interval - elapsed)
            image_url = _public_art_url(slug, repo=args.repo, ref=args.ref)
            task = _create_task(
                client,
                variant_id=variant_id,
                image_url=image_url,
                option_group=option_group,
                option=option,
                lifelike=not args.no_lifelike,
            )
            last_submit = time.monotonic()
            result = _wait_for_task(client, task)
            mockup_url = _choose_mockup_url(
                result,
                option_group=option_group,
                option=option,
            )
            destination = OUT / f"{slug}.webp"
            _store_mockup(client, mockup_url, destination)
            with Image.open(destination) as check:
                check.load()
                print(
                    f"{slug}: native Printful mockup -> {destination.relative_to(ROOT)} "
                    f"{check.size[0]}x{check.size[1]}"
                )


if __name__ == "__main__":
    main()
