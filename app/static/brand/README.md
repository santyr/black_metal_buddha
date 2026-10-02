# Brand Assets

## Approved artwork awaiting valid source

The intended identity is the user-approved Black Metal Buddha full lockup with
recognizable Dzogchen A, a sparse spiked halo, bone white, and restrained red.

The site uses `black-metal-buddha-wordmark.svg`, a text-only temporary fallback.
Restore the valid approved original, update `app/branding.py`, and verify image
decoding before deployment. The fallback does not replace the approved identity.

## Remote asset integrity — 2026-10-02

Remote commit `a33277d` describes its WebP and PNG as repaired, but the checked-out
files and a direct raw WebP download do not match the documented checksums.
Both files fail Pillow decoding; a valid file signature alone is insufficient.
Chromium rejects the WebP but accepts the PNG as a 900 × 900 image. The PNG
still fails strict decoding and does not match its documented checksum.

| File | Actual bytes | Actual SHA-256 |
| --- | --- | --- |
| `black-metal-buddha-logo.webp` | 14,633 | `e8e8665402681e22e1c8db72e010bafba2f93cf16b36502962c22c278b69290d` |
| `black-metal-buddha-logo-source.png` | 7,182 | `0b7a5056584d23407b83ac0f5cfc586c0fd5623fd1f2911699610c42cbd1b39e` |

The WebP RIFF header declares 90,550 bytes, exceeding the actual file length.
The PNG cannot be decoded as a complete image. These assets remain archived;
they are not used by the storefront or owner templates.

See `docs/17_BRAND_GUIDELINES.md` before creating or modifying brand artwork.
Do not introduce Christian crosses or cruciform supporting ornamentation.
