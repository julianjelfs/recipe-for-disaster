import sqlite3

import pytest

from app.importer.normalise import SYSTEM_PROMPT
from app.importer.pipeline import import_url
from app.importer.validate import ValidationFailed
from tests.helpers import BBC_URL, FakeClient, fetch_fixture, make_recipe, step

RECIPE_TABLES = ("recipes", "ingredients", "steps", "step_ingredients", "tags")


def count_rows(conn: sqlite3.Connection, table: str) -> int:
    return conn.execute(f"SELECT count(*) FROM {table}").fetchone()[0]


def broken_recipe():
    return make_recipe(steps=[step("Mix.", ['nope'])])


def test_import_stores_normalised_recipe(conn):
    client = FakeClient(make_recipe())
    recipe, created = import_url(conn, BBC_URL, client, fetch_fixture("bbcgoodfood.html"))

    assert created
    assert recipe.source_domain == "bbcgoodfood.com"
    assert [i.canonical_name for i in recipe.ingredients] == ["caster sugar", "butter", "egg", "self-raising flour"]
    assert recipe.steps[1].ingredient_ids == [i.id for i in recipe.ingredients]
    assert recipe.steps[2].timer_seconds == 1200
    assert recipe.diet == ["vegetarian"] and recipe.techniques == ["creaming"]
    call = client.messages.calls[0]
    assert call["system"][0]["text"] == SYSTEM_PROMPT
    assert "For the buttercream" in call["messages"][0]["content"]


def test_inv2_same_url_imports_once(conn):
    """Invariant 2: importing the same URL twice returns the existing recipe and creates no new row."""
    fetched: list[str] = []
    client = FakeClient(make_recipe())
    fetch = fetch_fixture("bbcgoodfood.html", fetched)

    first, created = import_url(conn, BBC_URL + "?utm_source=newsletter#method", client, fetch)
    second, created_again = import_url(conn, BBC_URL.replace("www.bbcgoodfood", "WWW.BBCGOODFOOD"), client, fetch)

    assert created and not created_again
    assert first.id == second.id
    assert len(fetched) == 1
    assert len(client.messages.calls) == 1
    assert count_rows(conn, "recipes") == 1


def test_inv3_stored_recipe_has_ingredients_and_steps(conn):
    """Invariant 3: every stored recipe has at least one ingredient and at least one step."""
    import_url(conn, BBC_URL, FakeClient(make_recipe()), fetch_fixture("bbcgoodfood.html"))
    empty = conn.execute(
        """
        SELECT count(*) FROM recipes r
        WHERE NOT EXISTS (SELECT 1 FROM ingredients WHERE recipe_id = r.id)
           OR NOT EXISTS (SELECT 1 FROM steps WHERE recipe_id = r.id)
        """
    ).fetchone()[0]
    assert empty == 0


def test_inv4_step_ingredients_belong_to_same_recipe(conn):
    """Invariant 4: every step_ingredients row references an ingredient belonging to the same recipe."""
    fetch = fetch_fixture("bbcgoodfood.html")
    cake, _ = import_url(conn, BBC_URL, FakeClient(make_recipe()), fetch)
    other, _ = import_url(conn, "https://example.com/other-cake", FakeClient(make_recipe()), fetch)

    mismatched = conn.execute(
        """
        SELECT count(*) FROM step_ingredients si
        JOIN steps s ON s.id = si.step_id
        JOIN ingredients i ON i.id = si.ingredient_id
        WHERE s.recipe_id != i.recipe_id
        """
    ).fetchone()[0]
    assert mismatched == 0

    with pytest.raises(sqlite3.IntegrityError), conn:
        conn.execute(
            "INSERT INTO step_ingredients (step_id, ingredient_id) VALUES (?, ?)",
            (cake.steps[0].id, other.ingredients[0].id),
        )


def test_inv6_validation_failure_is_retried_with_errors(conn):
    """Invariant 6 (retry half): the first validation failure is sent back to Claude once."""
    client = FakeClient(broken_recipe(), make_recipe())
    recipe, created = import_url(conn, BBC_URL, client, fetch_fixture("bbcgoodfood.html"))

    assert created and recipe.steps
    assert len(client.messages.calls) == 2
    retry_messages = client.messages.calls[1]["messages"]
    assert [m["role"] for m in retry_messages] == ["user", "assistant", "user"]
    assert "['nope']" in retry_messages[-1]["content"]
    assert len(client.messages.calls[0]["messages"]) == 1


def test_inv6_second_validation_failure_writes_nothing(conn):
    """Invariant 6: a validation failure after one retry raises and writes no recipe data."""
    client = FakeClient(broken_recipe(), broken_recipe())
    with pytest.raises(ValidationFailed):
        import_url(conn, BBC_URL, client, fetch_fixture("bbcgoodfood.html"))

    assert len(client.messages.calls) == 2
    assert {table: count_rows(conn, table) for table in RECIPE_TABLES} == dict.fromkeys(RECIPE_TABLES, 0)


def test_api_import_then_dedupe_then_read(api):
    http = api(FakeClient(make_recipe()))

    created = http.post("/api/import", json={"url": BBC_URL})
    assert created.status_code == 201
    recipe_id = created.json()["id"]

    again = http.post("/api/import", json={"url": BBC_URL + "#comments"})
    assert again.status_code == 200
    assert again.json()["id"] == recipe_id

    read = http.get(f"/api/recipes/{recipe_id}")
    assert read.status_code == 200
    assert read.json()["title"] == "Easy chocolate cake"
    assert http.get("/api/recipes/9999").status_code == 404


def test_inv6_api_returns_422_and_writes_nothing(api, conn):
    """Invariant 6: a validation failure after one retry returns 422 and writes no recipe data."""
    http = api(FakeClient(broken_recipe(), broken_recipe()))

    response = http.post("/api/import", json={"url": BBC_URL})

    assert response.status_code == 422
    assert any("['nope']" in error for error in response.json()["detail"]["errors"])
    assert {table: count_rows(conn, table) for table in RECIPE_TABLES} == dict.fromkeys(RECIPE_TABLES, 0)


def test_api_rejects_bad_url(api):
    http = api(FakeClient())
    response = http.post("/api/import", json={"url": "not a url"})
    assert response.status_code == 422
    assert "Not a web URL" in response.json()["detail"]["message"]
