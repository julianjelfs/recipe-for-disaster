import httpx
import pytest

from app import reports, store
from app.importer import pipeline
from app.importer.pipeline import renormalise_recipe
from app.importer.validate import ValidationFailed
from tests.helpers import BBC_URL, FakeClient, add_recipe, make_recipe, step


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
