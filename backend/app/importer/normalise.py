"""Turn extracted page data into a concise UK recipe with one Claude call (plus one retry)."""

import json
from dataclasses import dataclass

import anthropic

from app import config
from app.importer.extract import Extract
from app.importer.validate import ValidationFailed, validate
from app.schemas import NormalisedRecipe

MAX_ATTEMPTS = 2

SYSTEM_PROMPT = """\
You turn scraped recipe data into a clean, concise recipe for a UK home cook.

# Ingredients
- One entry per ingredient, in the original order. Put section headings in `group` \
(e.g. "For the buttercream"). Drop "Note 3" references, substitution asides and chat.
- `key` is a short unique slug for the ingredient, such as "caster-sugar". When an ingredient \
appears twice, give the second a suffix ("butter-2"). Steps refer to ingredients by key.
- Split combined lines: "2 large eggs plus 1 egg yolk" becomes 2 "large eggs" and 1 "egg yolk".
- Always keep the count of countable items: "4 large eggs" is quantity 4, unit null, name "large eggs".
- Units: g, kg, ml, l, tsp, tbsp, and for things that aren't weighed: pinch, dash, clove, \
tin, bunch, handful, sprig, slice, piece. Countable items ("1 onion") have unit null. \
Something counted in a word not on this list (stems, sticks, leaves, sheets) also has unit null, \
with the word kept in the name: "5-6 stems choy sum" is quantity 5, quantity_max 6, name "stems choy sum".
- Sizes stay in the name: "a 5cm piece of ginger" is quantity 1, unit null, name "5cm piece fresh ginger".
- Keep tsp and tbsp amounts as they are, even when the source adds grams: "1 tsp (5g) salt" is 1 tsp.
- Amounts already in g, kg, ml or l: copy them exactly. Never recalculate them.
- Convert cups, ounces, pounds, fluid ounces and sticks. Weigh dry ingredients and fats in g; \
measure liquids in ml. Round to the nearest 5 above 20 and to the nearest 1 below.
  - 1 cup of liquid = 240 ml. 1 fl oz = 30 ml. 1 oz = 28 g. 1 lb = 450 g. 1 stick of butter = 115 g.
  - 1 cup of: plain or self-raising flour 125 g; caster or granulated sugar 200 g; brown sugar 200 g; \
icing sugar 120 g; butter 225 g; rolled oats 90 g; uncooked rice 185 g; grated cheese 100 g; \
chopped nuts 120 g; cocoa powder 85 g; honey or syrup 340 g; chocolate chips 170 g; \
breadcrumbs 60 g; frozen peas 140 g; chopped vegetables or mushrooms 150 g; bean sprouts 100 g. \
Multiply by the number of cups. Leafy greens or herbs measured in cups become handfuls.
  - "Salt to taste" and similar: quantity null, unit null.
- `name` is the ingredient and its descriptors only ("unsalted butter", "large eggs"). \
How it is prepared goes in `preparation` ("finely chopped", "softened") and never in `name`.
- `canonical_name` is the plain singular base ingredient, lower case, used for search: \
"unsalted butter" -> "butter", "large eggs" -> "egg", "golden caster sugar" -> "caster sugar", \
"garlic cloves" -> "garlic", "boneless chicken thighs" -> "chicken thigh".
- Fractions become decimals (½ -> 0.5).
- `optional` is true only when the source says the ingredient is optional.

# British English
Use British names and spelling in ingredient names, canonical names and steps.
- Ingredients: coriander (not cilantro), spring onion (scallion), courgette (zucchini), \
aubergine (eggplant), plain flour (all-purpose flour), wholemeal flour (whole wheat flour), \
cornflour (cornstarch), bicarbonate of soda (baking soda), double cream (heavy cream), \
caster sugar (superfine sugar), icing sugar (powdered sugar), beef mince (ground beef), \
pork mince (ground pork), red pepper (bell pepper), prawns (shrimp), chilli flakes (red pepper flakes), \
tomato purée (tomato paste), chopped tomatoes (crushed or diced canned tomatoes), passata (tomato sauce), \
stock (broth), onion (yellow onion), spring greens or kale (collard greens), \
sausage meat (bulk sausage), plain chocolate (semisweet chocolate), rapeseed or vegetable oil (canola oil), \
yoghurt (yogurt).
- Kitchen words: frying pan (skillet), casserole dish (Dutch oven), baking paper (parchment paper), \
cling film (plastic wrap), foil (aluminum foil), grill (broil), hob (stovetop), loaf tin (loaf pan), \
cake tin (cake pan), baking tray (baking sheet or sheet pan), kitchen paper (paper towels), \
skewer (toothpick, when testing a bake), oil or butter (nonstick spray).

# Steps
- Short imperative sentences. Keep what the cook needs: temperatures, tin sizes, timings and cues \
like "until golden". Drop tips, stories, video references, links, "Note" references, storage advice, \
and quantities that just repeat the ingredient list.
- Each step covers one stage of work. Split long steps, merge trivial ones.
- Give one method. Drop alternative methods (stovetop, slow cooker, air fryer, bread machine versions) \
unless the page offers nothing else.
- Oven temperatures in Celsius with fan and gas, e.g. "Heat the oven to 180C (160C fan, gas 4)".
- Never write cups, ounces, pounds or Fahrenheit in a step. Convert them like ingredients, \
or leave the amount out when the ingredient list already has it.
- Give tin, pan, dish and tray sizes in inches, the way UK bakers buy them: "20cm round tin" -> \
"8in round tin", "30 x 20cm roasting tin" -> "12 x 8in roasting tin", "8x4 inch loaf pan" -> \
"8 x 4in loaf tin". Other sizes, such as "cut into 2cm pieces", stay in cm.
- `timer_seconds` is an unattended wait of 2 minutes or more: baking, simmering, resting, rising, chilling. \
For a range use the lower end, when the cook should first check ("bake for 20-25 mins" -> 1200). \
Null for hands-on work such as creaming, kneading, whisking or stir-frying.
- `ingredient_keys` lists the key of every ingredient added or used in that step.

# Metadata
- Times in minutes, null when unknown. `total_minutes` includes resting and marinating.
- `servings`: portions, or pieces for baking. Null when unknown.
- `complexity`: 1 assembly only (salads, sandwiches); 2 simple one-pan cooking; \
3 several components or standard techniques (roux, kneading bread); \
4 demanding technique or tight timing (tempering chocolate, soufflé, laminated dough); \
5 professional level, multi-day, or many components.
- `diet`: only labels the recipe actually meets.
- `equipment`: notable items beyond basic pans, bowls and knives ("stand mixer", "8in sandwich tins", "wok").
- `techniques`: short lower-case labels ("stir-frying", "creaming", "braising").
"""


class NormaliseError(Exception):
    pass


@dataclass
class Usage:
    """Tokens used by every Claude call for one import or re-read, retries and failed attempts included."""

    calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cache_creation_input_tokens: int = 0
    cache_read_input_tokens: int = 0

    def add(self, api_usage) -> None:
        self.calls += 1
        self.input_tokens += api_usage.input_tokens or 0
        self.output_tokens += api_usage.output_tokens or 0
        self.cache_creation_input_tokens += getattr(api_usage, "cache_creation_input_tokens", 0) or 0
        self.cache_read_input_tokens += getattr(api_usage, "cache_read_input_tokens", 0) or 0


@dataclass(frozen=True)
class NormaliseResult:
    recipe: NormalisedRecipe
    usage: Usage


def normalise(
    extract: Extract,
    client: anthropic.Anthropic,
    model: str = config.MODEL,
    usage: Usage | None = None,
) -> NormaliseResult:
    """Ask Claude for a NormalisedRecipe. On validation failure, retry once with the errors.

    Each call's tokens are added to `usage` straight away, so a caller that passes one in
    still has the counts when this raises.
    """
    usage = usage if usage is not None else Usage()
    messages: list[dict] = [{"role": "user", "content": _user_content(extract)}]
    for attempt in range(1, MAX_ATTEMPTS + 1):
        response = client.messages.parse(
            model=model,
            max_tokens=16000,
            system=[{"type": "text", "text": SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}}],
            messages=messages,
            output_format=NormalisedRecipe,
        )
        usage.add(response.usage)
        if response.stop_reason != "end_turn" or response.parsed_output is None:
            raise NormaliseError(f"Claude stopped ({response.stop_reason}) before returning a recipe.")
        try:
            return NormaliseResult(validate(response.parsed_output), usage)
        except ValidationFailed as failure:
            if attempt == MAX_ATTEMPTS:
                raise
            feedback = "\n".join(f"- {error}" for error in failure.errors)
            messages = messages + [
                {"role": "assistant", "content": response.parsed_output.model_dump_json()},
                {"role": "user", "content": f"That recipe failed validation:\n{feedback}\nReturn the whole corrected recipe."},
            ]
    raise AssertionError("unreachable")


def _user_content(extract: Extract) -> str:
    if extract.structured is not None:
        return "Scraped recipe data (JSON):\n" + json.dumps(extract.structured, ensure_ascii=False, indent=1)
    return (
        "This page had no structured recipe data. Its main text follows; find the recipe in it.\n\n"
        + (extract.text or "")
    )
