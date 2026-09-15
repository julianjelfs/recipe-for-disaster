"""Pull recipe data out of a page: schema.org data via recipe-scrapers, else the page's main text."""

import json
import re
from dataclasses import dataclass
from typing import Any

import trafilatura
from recipe_scrapers import scrape_html

STRUCTURED_FIELDS = (
    "title", "description", "yields", "prep_time", "cook_time", "total_time",
    "ingredient_groups", "instructions_list", "cuisine", "category",
    "dietary_restrictions", "equipment", "keywords", "image",
)
# Pages shorter than this after boilerplate removal don't contain a usable recipe.
MIN_TEXT_CHARS = 200

# "2 cups (250g) flour", "1 and 1/2 cups (345g) bananas", "1/2 cup (8 Tbsp; 113g) butter":
# a leading US amount followed by the metric amount in brackets.
_US_AMOUNT_WITH_METRIC = re.compile(
    r"^[\d\s/.½¼¾⅓⅔⅛]+(?:and\s+[\d/½¼¾⅓⅔⅛]+\s*)?"
    r"(?:cups?|oz|ounces?|lbs?|pounds?|sticks?|pints?|quarts?)\b\s*"
    r"\((?:[^()]*?;\s*)?(?P<amount>\d+(?:\.\d+)?)\s*(?P<unit>g|kg|ml|l)\s*\)\s*",
    re.IGNORECASE,
)

# "5cm piece of ginger", "2.5 cm chunk ginger": a size where the count would normally be.
_SIZE_FIRST = re.compile(
    r"^(?P<size>\d+(?:\.\d+)?\s*(?:cm|mm|inch(?:es)?|in\b|\"))\s*(?P<rest>(?:piece|chunk|knob|stick|length|strip)\b.*)$",
    re.IGNORECASE,
)


class ExtractError(Exception):
    pass


@dataclass(frozen=True)
class Extract:
    """Raw material for normalisation. Exactly one of structured or text is set."""

    structured: dict[str, Any] | None
    text: str | None

    @property
    def image_url(self) -> str | None:
        return (self.structured or {}).get("image")


def prefer_metric(line: str) -> str:
    """Replace a leading US amount with the metric amount the page gives alongside it.

    Done in code because the model sometimes miscalculates from the cup amount instead of
    copying the grams (it turned "2 cups (250g) flour" into 125g).
    """
    match = _US_AMOUNT_WITH_METRIC.match(line)
    if not match:
        return line
    return f"{match.group('amount')}{match.group('unit').lower()} {line[match.end():]}"


def count_sized_pieces(line: str) -> str:
    """Put a count in front of a leading size: "5cm piece of ginger" -> "1 × 5cm piece of ginger".

    Done in code because the model read the size as the amount and stored "5g ginger".
    """
    match = _SIZE_FIRST.match(line.strip())
    if not match:
        return line
    return f"1 × {match.group('size')} {match.group('rest')}"


def clean_ingredient_line(line: str) -> str:
    return count_sized_pieces(prefer_metric(line))


def extract(html: str, url: str) -> Extract:
    structured = _structured(html, url)
    if structured is not None:
        return Extract(structured=structured, text=None)
    text = trafilatura.extract(html, url=url, include_comments=False, favor_recall=True)
    if not text or len(text) < MIN_TEXT_CHARS:
        raise ExtractError("No recipe found on the page.")
    return Extract(structured=None, text=text)


def restore(raw_extract: str | None, raw_text: str | None) -> Extract:
    """Rebuild an Extract from the page data stored at import, applying today's ingredient line clean-ups."""
    if raw_extract:
        structured = json.loads(raw_extract)
        structured["ingredient_groups"] = [
            {**group, "ingredients": [clean_ingredient_line(line) for line in group["ingredients"]]}
            for group in structured.get("ingredient_groups", [])
        ]
        return Extract(structured=structured, text=None)
    if raw_text:
        return Extract(structured=None, text=raw_text)
    raise ExtractError("There is no saved page data to read the recipe from.")


def _structured(html: str, url: str) -> dict[str, Any] | None:
    try:
        scraper = scrape_html(html, org_url=url, supported_only=False)
    except Exception:
        # recipe-scrapers raises assorted exception types when a page has no schema.org recipe.
        return None
    data: dict[str, Any] = {}
    for field in STRUCTURED_FIELDS:
        try:
            value = getattr(scraper, field)()
        except Exception:
            # Each field accessor raises its own error type when that field is missing.
            continue
        if field == "ingredient_groups":
            value = [
                {"purpose": group.purpose, "ingredients": [clean_ingredient_line(line) for line in group.ingredients]}
                for group in value
            ]
        if value not in (None, "", [], {}):
            data[field] = value
    has_ingredients = any(group["ingredients"] for group in data.get("ingredient_groups", []))
    if not has_ingredients or not data.get("instructions_list"):
        return None
    return data
