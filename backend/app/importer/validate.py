"""Checks on LLM output that don't rely on the model following instructions."""

import re

from app.schemas import UK_UNITS, NormalisedIngredient, NormalisedRecipe


class ValidationFailed(Exception):
    def __init__(self, errors: list[str]):
        super().__init__("; ".join(errors))
        self.errors = errors


_FAHRENHEIT = re.compile(
    r"(?P<sep>\s*[/(]\s*)?(?P<deg>\d{2,3})\s*(?:°|º|degrees?\s*)?F(?:ahrenheit)?\b(?P<close>\))?",
    re.IGNORECASE,
)
_ENDS_WITH_CELSIUS = re.compile(r"\d\s*(?:°|º|degrees?\s*)?C(?:elsius)?(?:\s*fan)?\s*$", re.IGNORECASE)
# An amount followed by a US measure: "1 3/4 cups", "8 oz", "2 lbs", "1 stick of butter", "8 inch", '8"'.
_US_MEASURE = re.compile(
    r"(?:\d|½|¼|¾|⅓|⅔)\s*"
    r"(?:(?:cups?|fl\.?\s*oz|oz|ounces?|lbs?|pounds?|inch(?:es)?|sticks? of butter)\b|[\"″])",
    re.IGNORECASE,
)
# A size given in the ingredient name: "5cm piece fresh ginger".
_SIZE_IN_NAME = re.compile(r"(\d+(?:\.\d+)?)\s*(?:cm|mm)\b", re.IGNORECASE)
_WEIGHT_AND_VOLUME_UNITS = {"g", "kg", "ml", "l"}


def fahrenheit_to_celsius(text: str) -> str:
    """Drop °F that repeats an adjacent °C value ("180C/350F"), convert any other °F to °C."""

    def replace(match: re.Match[str]) -> str:
        if match.group("sep") and _ENDS_WITH_CELSIUS.search(text[: match.start()]):
            return ""
        celsius = round((int(match.group("deg")) - 32) * 5 / 9 / 5) * 5
        return f"{match.group('sep') or ''}{celsius}C{match.group('close') or ''}"

    return _FAHRENHEIT.sub(replace, text)


def tidy_name(name: str, preparation: str | None) -> tuple[str, str | None]:
    """Stop the preparation showing twice when the name already carries it.

    "unsalted butter, softened" + "softened" -> "unsalted butter" + "softened"
    "mashed bananas" + "mashed" -> "mashed bananas" + None
    """
    name = name.strip()
    if not preparation:
        return name, None
    suffix = f", {preparation}"
    if name.lower().endswith(suffix.lower()):
        return name[: -len(suffix)], preparation
    if re.search(rf"\b{re.escape(preparation)}\b", name, re.IGNORECASE):
        return name, None
    return name, preparation


def size_is_not_amount(ingredient: NormalisedIngredient) -> NormalisedIngredient:
    """Undo a size read as a weight: 5g of "5cm piece fresh ginger" becomes 1 of it.

    The model made this mistake on report #2 even when given "1 × 5cm piece of fresh ginger".
    """
    match = _SIZE_IN_NAME.search(ingredient.name)
    if (
        match
        and ingredient.unit in _WEIGHT_AND_VOLUME_UNITS
        and ingredient.quantity == float(match.group(1))
        and ingredient.quantity_max is None
    ):
        return ingredient.model_copy(update={"quantity": 1.0, "unit": None})
    return ingredient


def validate(recipe: NormalisedRecipe) -> NormalisedRecipe:
    """Return a cleaned copy of the recipe, or raise ValidationFailed listing every problem."""
    errors: list[str] = []
    if not recipe.ingredients:
        errors.append("The recipe has no ingredients.")
    if not recipe.steps:
        errors.append("The recipe has no steps.")

    keys = [ingredient.key for ingredient in recipe.ingredients]
    repeated = sorted({key for key in keys if keys.count(key) > 1})
    if repeated:
        errors.append(f"Ingredient keys must be unique; these appear more than once: {repeated}.")

    for index, ingredient in enumerate(recipe.ingredients):
        label = f"Ingredient {index} ({ingredient.name!r})"
        if not ingredient.key.strip():
            errors.append(f"{label} has an empty key.")
        if ingredient.unit is not None and ingredient.unit not in UK_UNITS:
            errors.append(f"{label} uses unit {ingredient.unit!r}. Allowed units: {', '.join(UK_UNITS)}, or null.")
        if ingredient.quantity is not None and ingredient.quantity <= 0:
            errors.append(f"{label} has quantity {ingredient.quantity}; quantities must be positive or null.")
        if ingredient.quantity_max is not None and (
            ingredient.quantity is None or ingredient.quantity_max < ingredient.quantity
        ):
            errors.append(f"{label} has quantity_max {ingredient.quantity_max} without a smaller quantity.")
        if not ingredient.name.strip() or not ingredient.canonical_name.strip():
            errors.append(f"{label} needs a name and a canonical_name.")

    known_keys = set(keys)
    for number, step in enumerate(recipe.steps, start=1):
        unknown = [key for key in step.ingredient_keys if key not in known_keys]
        if unknown:
            errors.append(f"Step {number} refers to unknown ingredient keys {unknown}.")
        if step.timer_seconds is not None and step.timer_seconds <= 0:
            errors.append(f"Step {number} has timer_seconds {step.timer_seconds}; use a positive number or null.")
        if not step.text.strip():
            errors.append(f"Step {number} has no text.")
        us_measure = _US_MEASURE.search(step.text)
        if us_measure:
            errors.append(
                f"Step {number} uses a US measure ({us_measure.group(0)!r}). "
                "Convert it to metric or leave the amount out."
            )

    if errors:
        raise ValidationFailed(errors)

    ingredients = []
    for ingredient in recipe.ingredients:
        name, preparation = tidy_name(ingredient.name, ingredient.preparation)
        tidied = ingredient.model_copy(
            update={
                "key": ingredient.key.strip(),
                "name": name,
                "preparation": preparation,
                "canonical_name": ingredient.canonical_name.strip().lower(),
            }
        )
        ingredients.append(size_is_not_amount(tidied))
    steps = [
        step.model_copy(
            update={
                "text": fahrenheit_to_celsius(step.text.strip()),
                # Deduplicated, in ingredient-list order.
                "ingredient_keys": [key for key in keys if key in set(step.ingredient_keys)],
            }
        )
        for step in recipe.steps
    ]
    return recipe.model_copy(update={"ingredients": ingredients, "steps": steps})
