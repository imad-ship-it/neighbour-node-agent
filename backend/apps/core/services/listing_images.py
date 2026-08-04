"""Images for seeded listings.

The problem this solves: `seed_data` used to set every listing's `image` to one
hardcoded path, `listings/2026/07/drill.jpg`. `ImageField` stores a *path*, and
`bulk_create` never checks that anything is there — so the rows looked correct in
the database and rendered as broken thumbnails in the browser. `media/` is
gitignored, so the file was absent on every clone and in every container. 43 of
51 listings were affected.

The fix is to generate a real image file per listing at seed time and save it
through the `ImageField`, so the bytes land on the media volume wherever the seed
happens to run. No binary in git, no network call, works offline on every fresh
`docker compose up`.

Two deliberate choices:

- **Drawn cards, not stock photos.** Seed data is fake, and a card that says
  "Cordless Drill / tools" is honest about that in a way a downloaded product
  shot is not. It also sidesteps committing third-party images to a public repo.
- **Real photos win when they exist.** Drop `<noun>.jpg` into `backend/seed_images/`
  — `drill.jpg`, `kayak.jpg` — and it is used instead, no code change. That keeps
  the upgrade path open without paying for it now.

Nothing here runs in the request path; it is seed-time only.
"""

from __future__ import annotations

import io
import textwrap
from pathlib import Path

from django.conf import settings
from django.core.files.base import ContentFile
from PIL import Image, ImageDraw, ImageFont

# Where a real photo can be dropped in to override the generated card. Keyed on
# the lowercase item noun, so `drill.jpg` covers every listing whose title ends
# in "Drill".
SEED_IMAGE_DIR = Path(settings.BASE_DIR) / "seed_images"
PHOTO_SUFFIXES = (".jpg", ".jpeg", ".png", ".webp")

CARD_SIZE = (800, 600)

# One colour per category, dark enough that near-white text sits comfortably on
# it at thumbnail size. Distinct hues so a grid of cards reads as varied rather
# than as one repeated tile.
CATEGORY_COLOURS = {
    "tools": (63, 74, 90),
    "appliances": (31, 95, 91),
    "electronics": (59, 63, 122),
    "furniture": (107, 74, 52),
    "sporting_goods": (47, 107, 63),
    "other": (74, 74, 82),
}
FALLBACK_COLOUR = CATEGORY_COLOURS["other"]

TEXT = (245, 245, 247)
MUTED = (255, 255, 255, 150)


def _font(size: int) -> ImageFont.FreeTypeFont:
    """Pillow's own scalable font.

    `python:3.14-slim` ships no font files at all — `/usr/share/fonts` is empty —
    so `truetype("DejaVuSans.ttf")` raises in the container while working fine on
    a developer laptop. `load_default(size=...)` (Pillow >= 10.1) returns a real
    FreeType font bundled with Pillow itself, which is the only option here that
    does not need an apt layer.
    """
    try:
        return ImageFont.load_default(size=size)
    except TypeError:  # Pillow < 10.1: bitmap default, fixed size, still legible
        return ImageFont.load_default()


def _photo_override(title: str) -> bytes | None:
    """Return real photo bytes if someone has supplied one for this item noun."""
    if not SEED_IMAGE_DIR.is_dir():
        return None
    # Titles are "<adjective> <Noun>", so the last word is the item.
    noun = title.strip().split()[-1].lower() if title.strip() else ""
    if not noun:
        return None
    for suffix in PHOTO_SUFFIXES:
        candidate = SEED_IMAGE_DIR / f"{noun}{suffix}"
        if candidate.is_file():
            return candidate.read_bytes()
    return None


def _draw_card(title: str, category: str) -> bytes:
    """A flat colour card carrying the item name and its category."""
    colour = CATEGORY_COLOURS.get(category, FALLBACK_COLOUR)
    image = Image.new("RGB", CARD_SIZE, colour)
    draw = ImageDraw.Draw(image, "RGBA")
    width, height = CARD_SIZE

    # A slightly darker footer band, so the category label reads as a caption
    # rather than as more title.
    band_top = int(height * 0.78)
    draw.rectangle([0, band_top, width, height], fill=(0, 0, 0, 60))

    # Thin inset border — stops the card looking like a failed image fill.
    draw.rectangle(
        [12, 12, width - 13, height - 13], outline=(255, 255, 255, 40), width=2
    )

    # Wrap to at most three lines, shrinking the type if the title is long, so a
    # "Professional DSLR Camera" fits without overflowing the card.
    for size, wrap_at in ((72, 14), (60, 17), (48, 22), (38, 28)):
        lines = textwrap.wrap(title, width=wrap_at) or [title]
        if len(lines) <= 3:
            break
    font = _font(size)

    line_height = size + 12
    block_height = line_height * len(lines)
    y = (band_top - block_height) // 2

    for line in lines:
        box = draw.textbbox((0, 0), line, font=font)
        draw.text(((width - (box[2] - box[0])) // 2, y), line, font=font, fill=TEXT)
        y += line_height

    label = category.replace("_", " ").upper()
    label_font = _font(26)
    box = draw.textbbox((0, 0), label, font=label_font)
    draw.text(
        (
            (width - (box[2] - box[0])) // 2,
            band_top + (height - band_top - 26) // 2 - 6,
        ),
        label,
        font=label_font,
        fill=MUTED,
    )

    buffer = io.BytesIO()
    # JPEG, not PNG: a flat card compresses to a few KB, and 46 of them on the
    # media volume should not be megabytes.
    image.save(buffer, format="JPEG", quality=82, optimize=True)
    return buffer.getvalue()


def image_for(title: str, category: str) -> ContentFile:
    """The image to attach to a seeded listing, as a saveable file.

    Deterministic: the same title and category always produce the same bytes, so
    re-seeding does not churn the media volume.
    """
    photo = _photo_override(title)
    if photo is not None:
        return ContentFile(photo, name=f"{title.strip().split()[-1].lower()}.jpg")
    slug = "".join(c if c.isalnum() else "-" for c in title.lower()).strip("-")
    return ContentFile(_draw_card(title, category), name=f"seed-{slug}.jpg")
