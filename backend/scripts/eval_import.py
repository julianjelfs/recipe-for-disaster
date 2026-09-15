"""Run real URLs through fetch, extract and Claude, and print what comes back. Writes nothing.

Usage: uv run python scripts/eval_import.py scripts/eval_urls.txt
"""

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import anthropic  # noqa: E402

from app import config  # noqa: E402
from app.importer.extract import extract  # noqa: E402
from app.importer.fetch import canonicalise_url, fetch_html  # noqa: E402
from app.costs import cost_usd  # noqa: E402
from app.importer.normalise import NormaliseResult, normalise  # noqa: E402
from app.schemas import NormalisedRecipe  # noqa: E402


def cost(result: NormaliseResult) -> float:
    return cost_usd(config.MODEL, result.usage) or 0.0


def format_amount(quantity: float | None, quantity_max: float | None, unit: str | None) -> str:
    if quantity is None:
        return ""
    amount = f"{quantity:g}" + (f"-{quantity_max:g}" if quantity_max is not None else "")
    if unit in ("g", "kg", "ml", "l"):
        return f"{amount}{unit} "
    return f"{amount} {unit} " if unit else f"{amount} "


def print_recipe(recipe: NormalisedRecipe) -> None:
    print(
        f"     {recipe.title} | serves {recipe.servings} | {recipe.total_minutes} min"
        f" | complexity {recipe.complexity} | {recipe.course} | {recipe.cuisine} | {', '.join(recipe.diet)}"
    )
    for ingredient in recipe.ingredients:
        group = f"[{ingredient.group}] " if ingredient.group else ""
        prep = f", {ingredient.preparation}" if ingredient.preparation else ""
        amount = format_amount(ingredient.quantity, ingredient.quantity_max, ingredient.unit)
        print(f"     - {group}{amount}{ingredient.name}{prep}  ({ingredient.canonical_name})")
    for number, step in enumerate(recipe.steps, start=1):
        timer = f"  [timer {step.timer_seconds // 60}m{step.timer_seconds % 60:02d}s]" if step.timer_seconds else ""
        print(f"     {number}. {step.text}{timer}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("urls", type=Path, help="text file with one URL per line")
    args = parser.parse_args()

    urls = [line.strip() for line in args.urls.read_text().splitlines() if line.strip() and not line.startswith("#")]
    client = anthropic.Anthropic()
    total_cost = 0.0
    failures = 0

    for url in urls:
        started = time.monotonic()
        try:
            page = extract(fetch_html(canonicalise_url(url)), url)
            result = normalise(page, client, config.MODEL)
        except Exception as error:  # report every failure and carry on through the list
            failures += 1
            print(f"FAIL {url}\n     {type(error).__name__}: {error}\n")
            continue

        total_cost += cost(result)
        source = "schema.org" if page.structured is not None else "page text"
        print(f"OK   {url}  [{source}, {time.monotonic() - started:.1f}s, ${cost(result):.4f}]")
        print_recipe(result.recipe)
        print()

    print(f"{len(urls) - failures}/{len(urls)} imported, total ${total_cost:.4f}")


if __name__ == "__main__":
    main()
