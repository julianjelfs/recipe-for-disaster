import sqlite3

import pytest

from app import costs, reports, store
from app.importer.create import CREATE_PROMPT, invent_recipe
from app.importer.normalise import RULES, SYSTEM_PROMPT
from app.importer.pipeline import create_recipe, renormalise_recipe
from app.importer.validate import ValidationFailed
from tests.helpers import BBC_URL, FakeClient, add_recipe, make_recipe, step

BRIEF = "something warming with butternut squash and chorizo, for 4, under an hour"


def test_the_two_prompts_share_one_copy_of_the_rules():
    """Editing the rules for one path but not the other is the drift this guards against."""
    assert SYSTEM_PROMPT.endswith(RULES)
    assert CREATE_PROMPT.endswith(RULES)
    assert SYSTEM_PROMPT != CREATE_PROMPT


def test_creating_stores_the_recipe_and_the_brief(conn):
    recipe = create_recipe(conn, BRIEF, FakeClient(make_recipe(title="Squash and chorizo stew")))

    assert recipe.title == "Squash and chorizo stew"
    assert (recipe.origin, recipe.prompt) == ("created", BRIEF)
    assert recipe.source_url is None and recipe.source_domain is None and recipe.image_url is None
    assert [i.canonical_name for i in recipe.ingredients] == ["caster sugar", "butter", "egg", "self-raising flour"]
    assert invent_recipe.__module__ == "app.importer.create"


def test_inv21_every_recipe_is_imported_or_created(conn):
    """Invariant 21: a recipe is imported (URL, no prompt) or created (prompt, no URL), never a mixture."""
    imported = add_recipe(conn, BBC_URL)
    created = create_recipe(conn, BRIEF, FakeClient(make_recipe()))
    rows = conn.execute("SELECT origin, source_url, prompt FROM recipes ORDER BY id").fetchall()
    assert [(r["origin"], r["source_url"] is None, r["prompt"] is None) for r in rows] == [
        ("imported", False, True),
        ("created", True, False),
    ]
    assert (imported.origin, created.origin) == ("imported", "created")

    columns = "source_url, source_domain, origin, prompt, title, complexity, model, parse_version"
    for values in (
        # Created, but with a URL and no brief.
        ("https://x.example/", "x.example", "created", None, "x", 1, "m", 1),
        # Imported, but with a brief and no URL.
        (None, None, "imported", "invent me a cake", "x", 1, "m", 1),
        # Neither.
        (None, None, "created", None, "x", 1, "m", 1),
    ):
        with pytest.raises(sqlite3.IntegrityError), conn:
            conn.execute(f"INSERT INTO recipes ({columns}) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", values)


def test_inv22_created_recipe_is_stored_like_an_imported_one(conn):
    """Invariant 22: creation writes the same tables, the same content and one search index row."""
    imported = add_recipe(conn, BBC_URL)
    created = create_recipe(conn, BRIEF, FakeClient(make_recipe()))

    def content(recipe_id: int) -> dict:
        return {
            table: conn.execute(f"SELECT count(*) FROM {table} WHERE recipe_id = ?", (recipe_id,)).fetchone()[0]
            for table in ("ingredients", "steps", "tags", "recipe_search")
        }

    assert content(created.id) == content(imported.id)
    assert conn.execute(
        "SELECT count(*) FROM step_ingredients si JOIN steps s ON s.id = si.step_id WHERE s.recipe_id = ?",
        (created.id,),
    ).fetchone()[0] == 4
    assert [(s.text, s.timer_seconds) for s in created.steps] == [(s.text, s.timer_seconds) for s in imported.steps]


def test_created_recipes_are_searchable_and_deletable(conn):
    created = create_recipe(conn, BRIEF, FakeClient(make_recipe(title="Squash stew")))
    from app import search

    assert [r.id for r in search.search_recipes(conn, q="squash").recipes] == [created.id]
    assert [r.origin for r in search.search_recipes(conn).recipes] == ["created"]
    assert store.delete_recipe(conn, created.id)
    assert conn.execute("SELECT count(*) FROM recipe_search").fetchone()[0] == 0


def test_created_recipes_can_be_flagged(conn):
    """The flag path used to require a source URL, so this would have been a 500."""
    created = create_recipe(conn, BRIEF, FakeClient(make_recipe()))
    report_id = reports.flag_recipe(conn, created.id, "The chorizo never gets browned")
    report = reports.get_report(conn, report_id)
    assert report["source_url"] is None
    assert report["comment"] == "The chorizo never gets browned"


def test_inv18_creation_records_its_cost(conn):
    """Invariant 18: every import, creation or re-read records its tokens and cost."""
    created = create_recipe(conn, BRIEF, FakeClient(make_recipe()))
    [row] = conn.execute("SELECT * FROM claude_usage").fetchall()
    assert (row["purpose"], row["recipe_id"], row["succeeded"], row["source_url"]) == ("create", created.id, 1, None)
    assert (row["calls"], row["input_tokens"], row["output_tokens"]) == (1, 1000, 500)
    assert costs.spending(conn).creations == 1


def test_a_failed_creation_is_recorded_and_stores_nothing(conn):
    broken = make_recipe(steps=[step("Mix.", ["nope"])])
    with pytest.raises(ValidationFailed):
        create_recipe(conn, BRIEF, FakeClient(broken, broken))

    assert conn.execute("SELECT count(*) FROM recipes").fetchone()[0] == 0
    [usage] = conn.execute("SELECT * FROM claude_usage").fetchall()
    assert (usage["purpose"], usage["succeeded"], usage["calls"]) == ("create", 0, 2)
    [report] = reports.list_reports(conn)
    assert report["kind"] == "failed"
    assert report["comment"] == BRIEF
    assert report["source_url"] is None


def test_inv22_try_again_reinvents_from_the_saved_brief(conn, monkeypatch):
    """Invariant 22: re-reading a created recipe reuses its brief, fetches nothing, and keeps notes and tags."""
    created = create_recipe(conn, BRIEF, FakeClient(make_recipe(title="First attempt")))
    store.replace_recipe(conn, created.id, make_recipe(title="First attempt"), notes="Needs more chilli", custom_tags=["midweek"])

    import httpx

    from app.importer import pipeline

    def no_network(*args, **kwargs):
        raise AssertionError("re-reading a created recipe must not fetch anything")

    monkeypatch.setattr(httpx, "get", no_network)
    monkeypatch.setattr(pipeline, "fetch_html", no_network)

    client = FakeClient(make_recipe(title="Second attempt"))
    again = renormalise_recipe(conn, created.id, client)

    assert again.title == "Second attempt"
    assert (again.origin, again.prompt) == ("created", BRIEF)
    assert again.notes == "Needs more chilli" and again.tags == ["midweek"]
    assert client.messages.calls[0]["messages"][0]["content"] == f"Brief: {BRIEF}"
    assert conn.execute("SELECT count(*) FROM claude_usage WHERE purpose = 'renormalise'").fetchone()[0] == 1
