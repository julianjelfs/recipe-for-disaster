"""Read and write recipes in SQLite."""

import json
import sqlite3
from collections.abc import Iterable
from urllib.parse import urlsplit

from app.importer.extract import Extract
from app.schemas import Ingredient, NormalisedRecipe, Recipe, Step

# NormalisedRecipe list field -> tags.kind. Tags of kind 'custom' are the ones people add.
TAG_FIELDS = {"diet": "diet", "equipment": "equipment", "techniques": "technique"}

# One recipe's search index row. migrations/003_search.sql builds the same columns.
_INDEX_ROW = """
    SELECT
        r.id,
        r.title,
        coalesce((SELECT group_concat(i.name || ' ' || i.canonical_name, ' ') FROM ingredients i WHERE i.recipe_id = r.id), ''),
        coalesce((SELECT group_concat(s.text, ' ') FROM steps s WHERE s.recipe_id = r.id), ''),
        coalesce((SELECT group_concat(t.value, ' ') FROM tags t WHERE t.recipe_id = r.id), ''),
        r.notes,
        coalesce(r.cuisine, '') || ' ' || coalesce(r.course, '')
    FROM recipes r
    WHERE r.id = ?
"""


def find_recipe_id(conn: sqlite3.Connection, source_url: str) -> int | None:
    row = conn.execute("SELECT id FROM recipes WHERE source_url = ?", (source_url,)).fetchone()
    return row["id"] if row else None


def get_raw(conn: sqlite3.Connection, recipe_id: int) -> sqlite3.Row | None:
    return conn.execute("SELECT source_url, raw_extract, raw_text FROM recipes WHERE id = ?", (recipe_id,)).fetchone()


def insert_recipe(
    conn: sqlite3.Connection,
    *,
    source_url: str,
    recipe: NormalisedRecipe,
    extract: Extract,
    model: str,
    parse_version: int,
) -> int:
    with conn:
        cursor = conn.execute(
            """
            INSERT INTO recipes (
                source_url, source_domain, title, image_url, servings,
                prep_minutes, cook_minutes, total_minutes, complexity, cuisine, course,
                raw_extract, raw_text, model, parse_version
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                source_url,
                urlsplit(source_url).netloc.removeprefix("www."),
                recipe.title,
                extract.image_url,
                recipe.servings,
                recipe.prep_minutes,
                recipe.cook_minutes,
                recipe.total_minutes,
                recipe.complexity,
                recipe.cuisine,
                recipe.course,
                json.dumps(extract.structured, ensure_ascii=False) if extract.structured is not None else None,
                extract.text,
                model,
                parse_version,
            ),
        )
        recipe_id = cursor.lastrowid
        _insert_content(conn, recipe_id, recipe)
        _reindex(conn, recipe_id)
    return recipe_id


def replace_recipe(
    conn: sqlite3.Connection,
    recipe_id: int,
    recipe: NormalisedRecipe,
    *,
    model: str | None = None,
    parse_version: int | None = None,
    notes: str | None = None,
    custom_tags: Iterable[str] | None = None,
) -> bool:
    """Swap in new recipe content, keeping the source, the raw page data and created_at.

    Arguments left as None keep their stored values. Returns False if there is no such recipe.
    """
    with conn:
        cursor = conn.execute(
            """
            UPDATE recipes SET
                title = ?, servings = ?, prep_minutes = ?, cook_minutes = ?, total_minutes = ?,
                complexity = ?, cuisine = ?, course = ?,
                notes = coalesce(?, notes),
                model = coalesce(?, model),
                parse_version = coalesce(?, parse_version),
                updated_at = datetime('now')
            WHERE id = ?
            """,
            (
                recipe.title, recipe.servings, recipe.prep_minutes, recipe.cook_minutes, recipe.total_minutes,
                recipe.complexity, recipe.cuisine, recipe.course, notes, model, parse_version, recipe_id,
            ),
        )
        if cursor.rowcount == 0:
            return False
        # Deleting steps and ingredients cascades to step_ingredients.
        conn.execute("DELETE FROM steps WHERE recipe_id = ?", (recipe_id,))
        conn.execute("DELETE FROM ingredients WHERE recipe_id = ?", (recipe_id,))
        if custom_tags is None:
            conn.execute("DELETE FROM tags WHERE recipe_id = ? AND kind != 'custom'", (recipe_id,))
        else:
            conn.execute("DELETE FROM tags WHERE recipe_id = ?", (recipe_id,))
            _insert_tags(conn, recipe_id, [("custom", tag) for tag in custom_tags])
        _insert_content(conn, recipe_id, recipe)
        _reindex(conn, recipe_id)
    return True


def delete_recipe(conn: sqlite3.Connection, recipe_id: int) -> bool:
    with conn:
        conn.execute("DELETE FROM recipe_search WHERE recipe_id = ?", (recipe_id,))
        return conn.execute("DELETE FROM recipes WHERE id = ?", (recipe_id,)).rowcount == 1


def _insert_content(conn: sqlite3.Connection, recipe_id: int, recipe: NormalisedRecipe) -> None:
    ingredient_ids: dict[str, int] = {}
    for position, ingredient in enumerate(recipe.ingredients):
        cursor = conn.execute(
            """
            INSERT INTO ingredients (
                recipe_id, position, group_name, quantity, quantity_max, unit,
                name, canonical_name, preparation, optional
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                recipe_id, position, ingredient.group, ingredient.quantity, ingredient.quantity_max,
                ingredient.unit, ingredient.name, ingredient.canonical_name, ingredient.preparation,
                ingredient.optional,
            ),
        )
        ingredient_ids[ingredient.key] = cursor.lastrowid

    for position, step in enumerate(recipe.steps):
        cursor = conn.execute(
            "INSERT INTO steps (recipe_id, position, text, timer_seconds) VALUES (?, ?, ?, ?)",
            (recipe_id, position, step.text, step.timer_seconds),
        )
        conn.executemany(
            "INSERT INTO step_ingredients (step_id, ingredient_id) VALUES (?, ?)",
            [(cursor.lastrowid, ingredient_ids[key]) for key in step.ingredient_keys],
        )

    _insert_tags(
        conn,
        recipe_id,
        [(kind, value) for field, kind in TAG_FIELDS.items() for value in getattr(recipe, field)],
    )


def _insert_tags(conn: sqlite3.Connection, recipe_id: int, tags: Iterable[tuple[str, str]]) -> None:
    cleaned = sorted({(kind, value.strip().lower()) for kind, value in tags if value.strip()})
    conn.executemany(
        "INSERT INTO tags (recipe_id, kind, value) VALUES (?, ?, ?)",
        [(recipe_id, kind, value) for kind, value in cleaned],
    )


def _reindex(conn: sqlite3.Connection, recipe_id: int) -> None:
    conn.execute("DELETE FROM recipe_search WHERE recipe_id = ?", (recipe_id,))
    conn.execute(
        f"INSERT INTO recipe_search (recipe_id, title, ingredients, steps, tags, notes, meta) {_INDEX_ROW}",
        (recipe_id,),
    )


def get_recipe(conn: sqlite3.Connection, recipe_id: int) -> Recipe | None:
    row = conn.execute("SELECT * FROM recipes WHERE id = ?", (recipe_id,)).fetchone()
    if row is None:
        return None

    ingredients = [
        Ingredient.model_validate(dict(r))
        for r in conn.execute("SELECT * FROM ingredients WHERE recipe_id = ? ORDER BY position", (recipe_id,))
    ]

    ingredient_ids_by_step: dict[int, list[int]] = {}
    for link in conn.execute(
        """
        SELECT si.step_id, si.ingredient_id
        FROM step_ingredients si
        JOIN steps s ON s.id = si.step_id
        JOIN ingredients i ON i.id = si.ingredient_id
        WHERE s.recipe_id = ?
        ORDER BY i.position
        """,
        (recipe_id,),
    ):
        ingredient_ids_by_step.setdefault(link["step_id"], []).append(link["ingredient_id"])

    steps = [
        Step.model_validate({**dict(r), "ingredient_ids": ingredient_ids_by_step.get(r["id"], [])})
        for r in conn.execute("SELECT * FROM steps WHERE recipe_id = ? ORDER BY position", (recipe_id,))
    ]

    tags: dict[str, list[str]] = {"diet": [], "equipment": [], "technique": [], "custom": []}
    for tag in conn.execute("SELECT kind, value FROM tags WHERE recipe_id = ? ORDER BY value", (recipe_id,)):
        tags[tag["kind"]].append(tag["value"])

    return Recipe.model_validate(
        {
            **dict(row),
            "ingredients": ingredients,
            "steps": steps,
            "diet": tags["diet"],
            "equipment": tags["equipment"],
            "techniques": tags["technique"],
            "tags": tags["custom"],
        }
    )
