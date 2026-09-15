"""Find recipes by text, ingredients and filters, and count what the library holds."""

import re
import sqlite3
from collections.abc import Iterable

from app.schemas import Facets, FacetValue, RecipeSummary, SearchSort

# An ingredient whose canonical name contains the phrase as whole words ("chicken" in "chicken thigh").
# The phrase is passed twice: as typed, and with each word made singular.
_HAS_INGREDIENT = """
    EXISTS (
        SELECT 1 FROM ingredients i
        WHERE i.recipe_id = r.id
          AND (instr(' ' || i.canonical_name || ' ', ' ' || ? || ' ') > 0
               OR instr(' ' || i.canonical_name || ' ', ' ' || ? || ' ') > 0)
    )
"""

# bm25 weights, in recipe_search column order: recipe_id, title, ingredients, steps, tags, notes, meta.
_RELEVANCE = "bm25(recipe_search, 0, 10, 5, 1, 3, 2, 3)"

_ORDER_BY = {
    "newest": "r.created_at DESC, r.id DESC",
    "title": "r.title COLLATE NOCASE, r.id",
    "quickest": "r.total_minutes IS NULL, r.total_minutes, r.title COLLATE NOCASE",
    "simplest": "r.complexity, r.total_minutes IS NULL, r.total_minutes, r.title COLLATE NOCASE",
}


def singular(word: str) -> str:
    """Rough English singular, enough to match "leeks" to "leek" and "tomatoes" to "tomato"."""
    if len(word) > 3 and word.endswith("ies"):
        return word[:-3] + "y"
    if len(word) > 3 and word.endswith("oes"):
        return word[:-2]
    if len(word) > 3 and word.endswith("s") and not word.endswith("ss"):
        return word[:-1]
    return word


def search_recipes(
    conn: sqlite3.Connection,
    *,
    q: str | None = None,
    has: Iterable[str] = (),
    max_total: int | None = None,
    max_complexity: int | None = None,
    cuisine: str | None = None,
    course: str | None = None,
    tags: Iterable[str] = (),
    sort: SearchSort | None = None,
    limit: int = 500,
) -> list[RecipeSummary]:
    joins: list[str] = []
    where: list[str] = []
    params: list[object] = []

    match = _match_expression(q or "")
    if match:
        joins.append("JOIN recipe_search ON recipe_search.recipe_id = r.id")
        where.append("recipe_search MATCH ?")
        params.append(match)

    for name in has:
        phrase = " ".join(name.lower().split())
        if phrase:
            where.append(_HAS_INGREDIENT)
            params += [phrase, " ".join(singular(word) for word in phrase.split())]

    if max_total is not None:
        where.append("r.total_minutes <= ?")
        params.append(max_total)
    if max_complexity is not None:
        where.append("r.complexity <= ?")
        params.append(max_complexity)
    if cuisine:
        where.append("r.cuisine = ? COLLATE NOCASE")
        params.append(cuisine)
    if course:
        where.append("r.course = ?")
        params.append(course)
    for tag in tags:
        if tag.strip():
            where.append("EXISTS (SELECT 1 FROM tags t WHERE t.recipe_id = r.id AND t.value = ?)")
            params.append(tag.strip().lower())

    sort = sort or ("relevance" if match else "newest")
    order = _RELEVANCE if sort == "relevance" and match else _ORDER_BY.get(sort, _ORDER_BY["newest"])

    rows = conn.execute(
        f"""
        SELECT r.id, r.title, r.image_url, r.source_domain, r.total_minutes, r.complexity,
               r.cuisine, r.course, r.created_at
        FROM recipes r {" ".join(joins)}
        {"WHERE " + " AND ".join(where) if where else ""}
        ORDER BY {order}
        LIMIT ?
        """,
        [*params, limit],
    ).fetchall()

    diet: dict[int, list[str]] = {}
    ids = [row["id"] for row in rows]
    if ids:
        placeholders = ", ".join("?" * len(ids))
        for tag in conn.execute(
            f"SELECT recipe_id, value FROM tags WHERE kind = 'diet' AND recipe_id IN ({placeholders}) ORDER BY value",
            ids,
        ):
            diet.setdefault(tag["recipe_id"], []).append(tag["value"])

    return [RecipeSummary.model_validate({**dict(row), "diet": diet.get(row["id"], [])}) for row in rows]


def facets(conn: sqlite3.Connection) -> Facets:
    def values(sql: str) -> list[FacetValue]:
        return [FacetValue(value=row[0], count=row[1]) for row in conn.execute(sql)]

    tags: dict[str, list[FacetValue]] = {}
    for row in conn.execute(
        "SELECT kind, value, count(DISTINCT recipe_id) AS n FROM tags GROUP BY kind, value ORDER BY n DESC, value"
    ):
        tags.setdefault(row["kind"], []).append(FacetValue(value=row["value"], count=row["n"]))

    return Facets(
        total=conn.execute("SELECT count(*) FROM recipes").fetchone()[0],
        ingredients=values(
            "SELECT canonical_name, count(DISTINCT recipe_id) AS n FROM ingredients"
            " GROUP BY canonical_name ORDER BY n DESC, canonical_name"
        ),
        cuisines=values(
            "SELECT cuisine, count(*) AS n FROM recipes WHERE cuisine IS NOT NULL"
            " GROUP BY cuisine COLLATE NOCASE ORDER BY n DESC, cuisine"
        ),
        courses=values(
            "SELECT course, count(*) AS n FROM recipes WHERE course IS NOT NULL GROUP BY course ORDER BY n DESC, course"
        ),
        diet=tags.get("diet", []),
        equipment=tags.get("equipment", []),
        techniques=tags.get("technique", []),
        tags=tags.get("custom", []),
    )


def _match_expression(q: str) -> str | None:
    """Every word must match, each as a prefix: "choc cake" -> '"choc"* "cake"*'."""
    words = re.findall(r"\w+", q.lower())
    return " ".join(f'"{word}"*' for word in words) or None
