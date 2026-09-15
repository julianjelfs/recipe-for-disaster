import re
import sqlite3

import pytest

from app.importer.validate import ValidationFailed, fahrenheit_to_celsius, tidy_name, validate
from app.schemas import UK_UNITS, NormalisedIngredient
from tests.helpers import ingredient, make_recipe, step

FAHRENHEIT_IN_TEXT = re.compile(r"\d\s*(?:°|º|degrees?\s*)?F\b", re.IGNORECASE)


def _ingredient_with_unit(unit: str) -> NormalisedIngredient:
    # model_construct skips the Literal check, the way a model ignoring its schema would.
    return NormalisedIngredient.model_construct(
        key="plain-flour", group=None, quantity=1.0, quantity_max=None, unit=unit, name="flour",
        canonical_name="plain flour", preparation=None, optional=False,
    )


def test_inv1_units_are_uk_validator_rejects_us_units():
    """Invariant 1: every stored ingredient unit is in the allowed UK unit set or null."""
    for unit in ("cup", "oz", "lb", "stick"):
        recipe = make_recipe(ingredients=[_ingredient_with_unit(unit)], steps=[step("Mix.", ["plain-flour"])])
        with pytest.raises(ValidationFailed) as failure:
            validate(recipe)
        assert any(repr(unit) in error for error in failure.value.errors)


def test_inv1_units_are_uk_database_accepts_only_uk_units(conn):
    """Invariant 1: the ingredients.unit CHECK matches app.schemas.UK_UNITS exactly."""
    with conn:
        recipe_id = conn.execute(
            "INSERT INTO recipes (source_url, source_domain, title, complexity, model, parse_version)"
            " VALUES ('https://x.example/', 'x.example', 'x', 1, 'm', 1)"
        ).lastrowid
    insert = "INSERT INTO ingredients (recipe_id, position, unit, name, canonical_name) VALUES (?, 0, ?, 'x', 'x')"
    for unit in (*UK_UNITS, None):
        with conn:
            conn.execute(insert, (recipe_id, unit))
    with pytest.raises(sqlite3.IntegrityError), conn:
        conn.execute(insert, (recipe_id, "cup"))


def test_inv3_recipe_needs_ingredients_and_steps():
    """Invariant 3: every stored recipe has at least one ingredient and at least one step."""
    with pytest.raises(ValidationFailed) as failure:
        validate(make_recipe(ingredients=[], steps=[]))
    assert "The recipe has no ingredients." in failure.value.errors
    assert "The recipe has no steps." in failure.value.errors


def test_steps_must_refer_to_known_ingredient_keys():
    with pytest.raises(ValidationFailed) as failure:
        validate(make_recipe(steps=[step("Mix.", ["butter", "margarine"])]))
    assert "['margarine']" in failure.value.errors[0]


def test_ingredient_keys_must_be_unique():
    butter = ingredient("unsalted butter", "butter", 100, "g")
    with pytest.raises(ValidationFailed) as failure:
        validate(make_recipe(ingredients=[butter, butter], steps=[step("Melt.", ["butter"])]))
    assert "['butter']" in failure.value.errors[0]


def test_step_keys_are_deduplicated_in_ingredient_order():
    cleaned = validate(make_recipe(steps=[step("Beat.", ["egg", "caster-sugar", "egg"])]))
    assert cleaned.steps[0].ingredient_keys == ["caster-sugar", "egg"]


@pytest.mark.parametrize(
    ("name", "preparation", "expected"),
    [
        ("unsalted butter, softened", "softened", ("unsalted butter", "softened")),
        ("mashed bananas", "mashed", ("mashed bananas", None)),
        ("chopped pecans or walnuts", "chopped", ("chopped pecans or walnuts", None)),
        ("onion", "finely chopped", ("onion", "finely chopped")),
        ("onion", None, ("onion", None)),
    ],
)
def test_preparation_is_not_shown_twice(name, preparation, expected):
    assert tidy_name(name, preparation) == expected


def test_validate_tidies_names():
    recipe = make_recipe(
        ingredients=[ingredient("unsalted butter, softened", "butter", 200, "g", preparation="softened")],
        steps=[step("Beat the butter.", ["butter"])],
    )
    assert validate(recipe).ingredients[0].name == "unsalted butter"


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Heat oven to 180C/350F.", "Heat oven to 180C."),
        ("Heat oven to 220°C (425°F).", "Heat oven to 220°C."),
        ("Bake at 350°F for 30 minutes.", "Bake at 175C for 30 minutes."),
        ("Preheat to 400 degrees F.", "Preheat to 205C."),
        ("Add 2 tbsp flour and 150 fl oz milk.", "Add 2 tbsp flour and 150 fl oz milk."),
    ],
)
def test_inv10_fahrenheit_is_converted(raw, expected):
    """Invariant 10: no temperature in stored step text is in °F."""
    assert fahrenheit_to_celsius(raw) == expected


def test_inv10_validate_removes_fahrenheit_from_steps():
    """Invariant 10: no temperature in stored step text is in °F."""
    recipe = make_recipe(steps=[step("Heat the oven to 350F.", []), step("Bake at 200C/400F until golden.", ["egg"])])
    cleaned = validate(recipe)
    assert not any(FAHRENHEIT_IN_TEXT.search(s.text) for s in cleaned.steps)


@pytest.mark.parametrize(
    ("text", "measure"),
    [
        ("Measure out 1 3/4 cups of mashed banana.", "4 cups"),
        ("Add 8 oz of cheese.", "8 oz"),
        ("Use a 2 lb loaf tin.", "2 lb"),
        ("Melt 1 stick of butter.", "1 stick of butter"),
        ("Pour in ½ cup of milk.", "½ cup"),
        ('Shape the dough into an 8" log.', '8"'),
        ("Place in a lightly greased 8½ × 4½ inch loaf pan.", "½ inch"),
    ],
)
def test_inv11_steps_have_no_us_measures(text, measure):
    """Invariant 11: no stored step text mentions cups, ounces, pounds or inches."""
    with pytest.raises(ValidationFailed) as failure:
        validate(make_recipe(steps=[step(text, [])]))
    assert repr(measure) in failure.value.errors[0]


def test_inv11_words_containing_measures_are_allowed():
    """Invariant 11: the check doesn't trip on ordinary words like 'cupboard'."""
    validate(make_recipe(steps=[step("Store in a cupboard for 2 days, or 3 cupcakes' worth of tins.", [])]))


def test_inv15_size_in_name_is_not_stored_as_a_weight():
    """Invariant 15: no ingredient whose name gives a size in cm or mm is stored with that size as its weight or volume."""
    recipe = make_recipe(
        ingredients=[
            # Report #2, as Claude returned it on re-read: 5g of a 5cm piece.
            ingredient("5cm piece fresh ginger", "ginger", 5, "g", key="ginger"),
            ingredient("5cm piece fresh ginger", "ginger", 1, None, key="ginger-2"),
            ingredient("2cm cubes cold butter", "butter", 100, "g"),
            ingredient("5mm slices courgette", "courgette", 5, "piece"),
        ],
        steps=[step("Grate the ginger.", ["ginger", "ginger-2", "butter", "courgette"])],
    )
    cleaned = validate(recipe)
    assert [(i.quantity, i.unit) for i in cleaned.ingredients] == [(1.0, None), (1.0, None), (100.0, "g"), (5.0, "piece")]
