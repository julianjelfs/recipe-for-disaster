"""Invent a recipe from a short brief, in the same shape an import produces."""

import anthropic

from app import config
from app.importer.normalise import RULES, NormaliseResult, Usage, ask

_CREATE_INTRO = """\
You invent recipes for a UK home cook, from a short brief.

Write one recipe that genuinely works: quantities and ratios that hold together, real timings, and
a method someone can follow in a home kitchen. Meet whatever the brief asks for (servings, time,
diet, ingredients it names) and choose sensible values for anything it leaves out. Use ingredients
a UK supermarket stocks. Give it a plain descriptive title, and don't credit it to a chef,
a restaurant or a publication: it is yours.

"""

CREATE_PROMPT = _CREATE_INTRO + RULES


def invent_recipe(
    brief: str,
    client: anthropic.Anthropic,
    model: str = config.MODEL,
    usage: Usage | None = None,
) -> NormaliseResult:
    return ask(CREATE_PROMPT, f"Brief: {brief.strip()}", client, model, usage)
