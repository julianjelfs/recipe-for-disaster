import pytest

from tests.helpers import FakeClient, add_created_recipe, add_recipe, make_recipe


def test_offline_copy_holds_every_recipe_in_full_and_the_facets(api, conn):
    """The phone's saved copy must answer a recipe page exactly as GET /api/recipes/{id} would."""
    pie = add_recipe(conn, "https://example.com/pie", title="Leek pie", diet=[])
    soup = add_created_recipe(conn, title="Leek soup", diet=["vegetarian"])
    http = api(FakeClient(make_recipe()))

    body = http.get("/api/offline").json()

    assert [recipe["id"] for recipe in body["recipes"]] == [pie.id, soup.id]
    for recipe in body["recipes"]:
        assert recipe == http.get(f"/api/recipes/{recipe['id']}").json()
    assert body["facets"] == http.get("/api/facets").json()


def test_offline_copy_of_an_empty_library(api):
    body = api(FakeClient(make_recipe())).get("/api/offline").json()

    assert body["recipes"] == []
    assert body["facets"]["total"] == 0


@pytest.mark.parametrize("sent", ['{etag}', 'W/{etag}', '"{bare}-zstd"', 'W/"{bare}-gzip"', '"other", {etag}'])
def test_unchanged_library_answers_304(api, conn, sent):
    """A phone that already has the current copy downloads nothing, however Caddy dressed the ETag up."""
    add_recipe(conn, "https://example.com/pie", title="Leek pie")
    http = api(FakeClient(make_recipe()))
    etag = http.get("/api/offline").headers["etag"]

    response = http.get("/api/offline", headers={"If-None-Match": sent.format(etag=etag, bare=etag.strip('"'))})

    assert response.status_code == 304
    assert response.content == b""


def test_any_change_to_the_library_changes_the_etag(api, conn):
    """Adding, editing or deleting a recipe must make phones download the copy again."""
    http = api(FakeClient(make_recipe()))
    empty = http.get("/api/offline").headers["etag"]
    pie = add_recipe(conn, "https://example.com/pie", title="Leek pie")
    added = http.get("/api/offline").headers["etag"]

    edit = http.get(f"/api/recipes/{pie.id}").json()
    edited_body = {
        **{k: edit[k] for k in ("title", "servings", "prep_minutes", "cook_minutes", "total_minutes",
                                "complexity", "cuisine", "course", "diet", "equipment", "techniques", "tags")},
        "title": "Leek and cheese pie",
        "notes": "More cheese.",
        "ingredients": [
            {"key": f"i{i['id']}", "group": i["group_name"], **{k: i[k] for k in (
                "quantity", "quantity_max", "unit", "name", "canonical_name", "preparation", "optional")}}
            for i in edit["ingredients"]
        ],
        "steps": [{"text": s["text"], "timer_seconds": s["timer_seconds"],
                   "ingredient_keys": [f"i{n}" for n in s["ingredient_ids"]]} for s in edit["steps"]],
    }
    assert http.put(f"/api/recipes/{pie.id}", json=edited_body).status_code == 200
    edited = http.get("/api/offline").headers["etag"]

    assert http.delete(f"/api/recipes/{pie.id}").status_code == 204
    deleted = http.get("/api/offline").headers["etag"]

    assert len({empty, added, edited}) == 3
    assert deleted == empty
    assert http.get("/api/offline", headers={"If-None-Match": added}).status_code == 200
