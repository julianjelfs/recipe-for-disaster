"""Shared test data and a fake Anthropic client."""

import sqlite3
from pathlib import Path
from types import SimpleNamespace

from app.importer.pipeline import import_url
from app.schemas import NormalisedIngredient, NormalisedRecipe, NormalisedStep, Recipe

FIXTURES = Path(__file__).parent / "fixtures"
BBC_URL = "https://www.bbcgoodfood.com/recipes/easy-chocolate-cake"


def fixture_html(name: str) -> str:
    return (FIXTURES / name).read_text()


def ingredient(name: str, canonical_name: str, quantity: float | None, unit: str | None, **overrides) -> NormalisedIngredient:
    fields = dict(
        key=canonical_name.replace(" ", "-"), group=None, quantity=quantity, quantity_max=None, unit=unit,
        name=name, canonical_name=canonical_name, preparation=None, optional=False,
    )
    return NormalisedIngredient(**(fields | overrides))


def step(text: str, ingredient_keys: list[str], timer_seconds: int | None = None) -> NormalisedStep:
    return NormalisedStep(text=text, timer_seconds=timer_seconds, ingredient_keys=ingredient_keys)


def make_recipe(**overrides) -> NormalisedRecipe:
    recipe = NormalisedRecipe(
        title="Easy chocolate cake",
        servings=12,
        prep_minutes=25,
        cook_minutes=20,
        total_minutes=45,
        ingredients=[
            ingredient("golden caster sugar", "caster sugar", 200, "g"),
            ingredient("unsalted butter", "butter", 200, "g", preparation="softened"),
            ingredient("large eggs", "egg", 4, None),
            ingredient("self-raising flour", "self-raising flour", 200, "g"),
        ],
        steps=[
            step("Heat the oven to 190C (170C fan, gas 5). Butter and line two 20cm sandwich tins.", []),
            step("Beat the sugar, butter, eggs and flour until pale.", ["caster-sugar", "butter", "egg", "self-raising-flour"]),
            step("Divide between the tins and bake until a skewer comes out clean.", [], timer_seconds=1200),
        ],
        complexity=2,
        cuisine="British",
        course="baking",
        diet=["vegetarian"],
        equipment=["20cm sandwich tins"],
        techniques=["creaming"],
    )
    return recipe.model_copy(update=overrides)


class FakeMessages:
    def __init__(self, outputs):
        self._outputs = list(outputs)
        self.calls: list[dict] = []

    def parse(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(
            parsed_output=self._outputs.pop(0),
            stop_reason="end_turn",
            usage=SimpleNamespace(input_tokens=1000, output_tokens=500),
        )


class FakeClient:
    """Stands in for anthropic.Anthropic. Each messages.parse() call returns the next canned recipe."""

    def __init__(self, *outputs: NormalisedRecipe):
        self.messages = FakeMessages(outputs)


def fetch_fixture(name: str, fetched: list[str] | None = None):
    def fetch(url: str) -> str:
        if fetched is not None:
            fetched.append(url)
        return fixture_html(name)

    return fetch


def add_recipe(conn: sqlite3.Connection, url: str, **overrides) -> Recipe:
    """Import make_recipe(**overrides) as if Claude had returned it for the BBC Good Food fixture page."""
    recipe, _ = import_url(conn, url, FakeClient(make_recipe(**overrides)), fetch_fixture("bbcgoodfood.html"))
    return recipe
