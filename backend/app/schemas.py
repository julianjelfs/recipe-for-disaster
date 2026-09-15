"""Pydantic models shared by the importer, the database layer and the API."""

from typing import Literal, get_args

from pydantic import BaseModel, ConfigDict, Field

Unit = Literal[
    "g", "kg", "ml", "l", "tsp", "tbsp",
    "pinch", "dash", "clove", "tin", "bunch", "handful", "sprig", "slice", "piece",
]
UK_UNITS: tuple[str, ...] = get_args(Unit)

Course = Literal["breakfast", "starter", "main", "side", "dessert", "baking", "snack", "drink", "sauce"]
Diet = Literal["vegetarian", "vegan", "gluten-free", "dairy-free", "nut-free"]
SearchSort = Literal["relevance", "newest", "title", "quickest", "simplest"]


# Models the LLM fills in. Every field is required (no defaults) so structured outputs
# lists it in the schema's `required`; nullable fields use `| None`.

class NormalisedIngredient(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str = Field(description="Short unique slug that steps use to refer to this ingredient, e.g. 'caster-sugar'.")
    group: str | None = Field(description="Section heading such as 'For the buttercream', or null.")
    quantity: float | None = Field(description="Amount as a decimal, or null when unspecified.")
    quantity_max: float | None = Field(description="Upper bound of a range like '5-6', otherwise null.")
    unit: Unit | None = Field(description="UK unit, or null for countable items like eggs.")
    name: str = Field(description="Ingredient as a cook would write it, e.g. 'unsalted butter'.")
    canonical_name: str = Field(description="Plain singular lower-case base ingredient for search, e.g. 'butter'.")
    preparation: str | None = Field(description="e.g. 'finely chopped', 'softened', or null.")
    optional: bool


class NormalisedStep(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str
    timer_seconds: int | None = Field(description="Wait of 2 minutes or more worth a timer, or null.")
    ingredient_keys: list[str] = Field(description="Keys of the ingredients added or used in this step.")


class NormalisedRecipe(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str
    servings: int | None
    prep_minutes: int | None
    cook_minutes: int | None
    total_minutes: int | None
    ingredients: list[NormalisedIngredient]
    steps: list[NormalisedStep]
    complexity: Literal[1, 2, 3, 4, 5]
    cuisine: str | None
    course: Course | None
    diet: list[Diet]
    equipment: list[str]
    techniques: list[str]


class RecipeEdit(NormalisedRecipe):
    """A recipe edited by hand: the shape Claude fills in, plus the fields only people set."""

    notes: str
    tags: list[str]


# API models.

class Ingredient(BaseModel):
    id: int
    position: int
    group_name: str | None
    quantity: float | None
    quantity_max: float | None
    unit: str | None
    name: str
    canonical_name: str
    preparation: str | None
    optional: bool


class Step(BaseModel):
    id: int
    position: int
    text: str
    timer_seconds: int | None
    ingredient_ids: list[int]


class Recipe(BaseModel):
    id: int
    source_url: str
    source_domain: str
    title: str
    image_url: str | None
    servings: int | None
    prep_minutes: int | None
    cook_minutes: int | None
    total_minutes: int | None
    complexity: int
    cuisine: str | None
    course: str | None
    diet: list[str]
    equipment: list[str]
    techniques: list[str]
    tags: list[str]
    notes: str
    model: str
    parse_version: int
    created_at: str
    updated_at: str
    ingredients: list[Ingredient]
    steps: list[Step]


class RecipeSummary(BaseModel):
    id: int
    title: str
    image_url: str | None
    source_domain: str
    total_minutes: int | None
    complexity: int
    cuisine: str | None
    course: str | None
    diet: list[str]
    created_at: str


class FacetValue(BaseModel):
    value: str
    count: int


class Facets(BaseModel):
    total: int
    ingredients: list[FacetValue]
    cuisines: list[FacetValue]
    courses: list[FacetValue]
    diet: list[FacetValue]
    equipment: list[FacetValue]
    techniques: list[FacetValue]
    tags: list[FacetValue]


class ImportRequest(BaseModel):
    url: str


class FlagRequest(BaseModel):
    comment: str


class FlagCreated(BaseModel):
    id: int
