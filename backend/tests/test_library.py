import httpx
import pytest

from app import reports, search, store
from app.importer import pipeline
from app.importer.pipeline import renormalise_recipe
from app.importer.validate import ValidationFailed
from tests.helpers import BBC_URL, FakeClient, add_recipe, ingredient, make_recipe, step


def ids(conn, **filters) -> list[int]:
    return [recipe.id for recipe in search.search_recipes(conn, **filters)]


def library(conn):
    pie = add_recipe(
        conn, "https://example.com/leek-bacon-pie",
        title="Leek and bacon pie", total_minutes=90, complexity=3, course="main", cuisine="British", diet=[],
        ingredients=[ingredient("leeks", "leek", 2, None), ingredient("smoked streaky bacon", "bacon", 200, "g")],
        steps=[step("Fry the bacon, then add the leeks.", ["leek", "bacon"])],
    )
    soup = add_recipe(
        conn, "https://example.com/leek-potato-soup",
        title="Leek and potato soup", total_minutes=40, complexity=1, course="starter", cuisine="French",
        diet=["vegetarian"],
        ingredients=[ingredient("leeks", "leek", 3, None), ingredient("floury potatoes", "potato", 500, "g")],
        steps=[step("Simmer the leeks and potatoes in stock until soft.", ["leek", "potato"])],
    )
    sandwich = add_recipe(
        conn, "https://example.com/bacon-sandwich",
        title="Bacon sandwich", total_minutes=None, complexity=1, course="breakfast", cuisine=None, diet=[],
        ingredients=[ingredient("back bacon", "bacon", 4, "slice"), ingredient("white bread", "bread", 2, "slice")],
        steps=[step("Grill the bacon and put it between the bread.", ["bacon", "bread"])],
    )
    return pie, soup, sandwich


def index_rows(conn, recipe_id: int):
    return conn.execute("SELECT title, notes FROM recipe_search WHERE recipe_id = ?", (recipe_id,)).fetchall()


def test_inv7_has_requires_every_ingredient(conn):
    """Invariant 7: has=a,b returns only recipes with an ingredient matching a and one matching b."""
    pie, soup, sandwich = library(conn)
    assert ids(conn, has=["leek", "bacon"]) == [pie.id]
    assert set(ids(conn, has=["leek"])) == {pie.id, soup.id}
    assert set(ids(conn, has=["bacon"])) == {pie.id, sandwich.id}
    assert ids(conn, has=["leek", "bacon", "potato"]) == []


def test_inv7_has_matches_plurals_and_whole_words(conn):
    """Invariant 7: an ingredient matches when its canonical name contains the word, singular or plural."""
    pie, soup, _ = library(conn)
    thighs = add_recipe(
        conn, "https://example.com/roast-thighs",
        ingredients=[ingredient("boneless chicken thighs", "chicken thigh", 6, None)],
        steps=[step("Roast.", ["chicken-thigh"])],
    )
    assert set(ids(conn, has=["Leeks"])) == {pie.id, soup.id}
    assert ids(conn, has=["potatoes"]) == [soup.id]
    assert ids(conn, has=["chicken"]) == [thighs.id]
    assert ids(conn, has=["chicken thighs"]) == [thighs.id]
    assert ids(conn, has=["bac"]) == []


def test_text_search_covers_titles_ingredients_steps_and_prefixes(conn):
    pie, soup, _ = library(conn)
    assert ids(conn, q="pie") == [pie.id]
    assert ids(conn, q="simmer stock") == [soup.id]
    assert ids(conn, q="floury") == [soup.id]
    assert set(ids(conn, q="lee")) == {pie.id, soup.id}
    assert ids(conn, q="lasagne") == []


def test_filters_and_sorting(conn):
    pie, soup, sandwich = library(conn)
    assert ids(conn, max_total=60) == [soup.id]
    assert set(ids(conn, max_complexity=1)) == {soup.id, sandwich.id}
    assert ids(conn, course="breakfast") == [sandwich.id]
    assert ids(conn, cuisine="french") == [soup.id]
    assert ids(conn, tags=["Vegetarian"]) == [soup.id]
    assert ids(conn) == [sandwich.id, soup.id, pie.id]
    assert ids(conn, sort="title") == [sandwich.id, pie.id, soup.id]
    assert ids(conn, sort="quickest") == [soup.id, pie.id, sandwich.id]
    assert ids(conn, sort="simplest") == [soup.id, sandwich.id, pie.id]


def test_facets_count_recipes(conn):
    library(conn)
    facets = search.facets(conn)
    assert facets.total == 3
    assert {v.value: v.count for v in facets.ingredients} == {"leek": 2, "bacon": 2, "potato": 1, "bread": 1}
    assert {v.value: v.count for v in facets.courses} == {"main": 1, "starter": 1, "breakfast": 1}
    assert [v.value for v in facets.diet] == ["vegetarian"]


def test_inv14_search_index_follows_every_change(conn):
    """Invariant 14: each recipe has exactly one search index row matching its current content; a deleted recipe has none."""
    recipe = add_recipe(conn, BBC_URL, title="Plain cake")
    assert [row["title"] for row in index_rows(conn, recipe.id)] == ["Plain cake"]

    store.replace_recipe(conn, recipe.id, make_recipe(title="Lemon cake"), notes="Family favourite")
    [row] = index_rows(conn, recipe.id)
    assert (row["title"], row["notes"]) == ("Lemon cake", "Family favourite")
    assert ids(conn, q="favourite") == [recipe.id]

    renormalise_recipe(conn, recipe.id, FakeClient(make_recipe(title="Renamed cake")))
    assert [row["title"] for row in index_rows(conn, recipe.id)] == ["Renamed cake"]

    assert store.delete_recipe(conn, recipe.id)
    assert index_rows(conn, recipe.id) == []
    assert ids(conn, q="cake") == []


def test_inv5_renormalise_uses_saved_page_data_without_fetching(conn, monkeypatch):
    """Invariant 5: renormalise from stored raw data produces a recipe without any network fetch of the source URL."""
    recipe = add_recipe(conn, BBC_URL)
    store.replace_recipe(conn, recipe.id, make_recipe(), notes="Use dark chocolate", custom_tags=["birthday"])

    def no_network(*args, **kwargs):
        raise AssertionError("renormalise must not fetch the page")

    monkeypatch.setattr(httpx, "get", no_network)
    monkeypatch.setattr(pipeline, "fetch_html", no_network)

    client = FakeClient(make_recipe(title="Chocolate cake, read again"))
    updated = renormalise_recipe(conn, recipe.id, client)

    assert updated.id == recipe.id
    assert updated.title == "Chocolate cake, read again"
    assert updated.notes == "Use dark chocolate"
    assert updated.tags == ["birthday"]
    assert "For the buttercream" in client.messages.calls[0]["messages"][0]["content"]


def test_failed_renormalise_leaves_recipe_alone_and_is_recorded(conn):
    recipe = add_recipe(conn, BBC_URL)
    broken = make_recipe(title="Broken", steps=[step("Mix.", ["nope"])])

    with pytest.raises(ValidationFailed):
        renormalise_recipe(conn, recipe.id, FakeClient(broken, broken))

    assert store.get_recipe(conn, recipe.id).title == "Easy chocolate cake"
    [report] = reports.list_reports(conn)
    assert report["kind"] == "failed" and report["source_url"] == BBC_URL


def edit_payload(**overrides) -> dict:
    return make_recipe(**overrides).model_dump() | {"notes": "", "tags": []}


def test_api_search_and_facets(api, conn):
    library(conn)
    http = api(FakeClient())
    assert [r["title"] for r in http.get("/api/recipes", params={"has": "leek, bacon"}).json()] == ["Leek and bacon pie"]
    [soup] = http.get("/api/recipes", params={"q": "soup", "max_total": 60}).json()
    assert soup["diet"] == ["vegetarian"]
    assert http.get("/api/recipes", params={"tag": "vegetarian", "sort": "title"}).json()[0]["title"] == "Leek and potato soup"
    assert http.get("/api/facets").json()["total"] == 3


def test_api_edit_recipe(api, conn):
    recipe = add_recipe(conn, BBC_URL)
    http = api(FakeClient())
    payload = edit_payload(title="Better cake") | {"notes": "Halve the sugar", "tags": ["Birthday", " birthday "]}
    payload["steps"][0]["text"] = "Heat the oven to 350F."

    response = http.put(f"/api/recipes/{recipe.id}", json=payload)

    assert response.status_code == 200
    body = response.json()
    assert body["title"] == "Better cake"
    assert body["notes"] == "Halve the sugar"
    assert body["tags"] == ["birthday"]
    assert body["steps"][0]["text"] == "Heat the oven to 175C."
    assert body["created_at"] == recipe.created_at


def test_api_edit_is_validated_like_an_import(api, conn):
    recipe = add_recipe(conn, BBC_URL)
    http = api(FakeClient())

    cups = edit_payload()
    cups["ingredients"][0]["unit"] = "cup"
    assert http.put(f"/api/recipes/{recipe.id}", json=cups).status_code == 422

    no_steps = http.put(f"/api/recipes/{recipe.id}", json=edit_payload(steps=[]))
    assert no_steps.status_code == 422
    assert "The recipe has no steps." in no_steps.json()["detail"]["errors"]

    assert http.put("/api/recipes/999", json=edit_payload()).status_code == 404
    assert store.get_recipe(conn, recipe.id).title == "Easy chocolate cake"


def test_api_renormalise_and_delete(api, conn):
    recipe = add_recipe(conn, BBC_URL)
    http = api(FakeClient(make_recipe(title="Read again")))

    assert http.post(f"/api/recipes/{recipe.id}/renormalise").json()["title"] == "Read again"
    assert http.post("/api/recipes/999/renormalise").status_code == 404

    assert http.delete(f"/api/recipes/{recipe.id}").status_code == 204
    assert http.get(f"/api/recipes/{recipe.id}").status_code == 404
    assert http.delete(f"/api/recipes/{recipe.id}").status_code == 404
