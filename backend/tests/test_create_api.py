import pytest

from app import costs
from tests.helpers import FakeClient, make_recipe, step

BRIEF = "a quick midweek pasta with anchovies"


def test_api_create_returns_the_new_recipe(api, conn):
    http = api(FakeClient(make_recipe(title="Anchovy and garlic spaghetti")))

    response = http.post("/api/create", json={"brief": f"  {BRIEF}  "})

    assert response.status_code == 201
    body = response.json()
    assert body["title"] == "Anchovy and garlic spaghetti"
    assert body["origin"] == "created"
    assert body["prompt"] == BRIEF
    assert body["source_url"] is None and body["source_domain"] is None

    listed = http.get("/api/recipes").json()["recipes"]
    assert [(r["title"], r["origin"], r["source_domain"]) for r in listed] == [
        ("Anchovy and garlic spaghetti", "created", None)
    ]
    assert costs.spending(conn).creations == 1


def test_api_create_needs_a_brief_of_sensible_length(api, conn):
    http = api(FakeClient(make_recipe()))

    empty = http.post("/api/create", json={"brief": "   "})
    assert empty.status_code == 422
    assert "invent" in empty.json()["detail"]["message"]

    long = http.post("/api/create", json={"brief": "x" * 501})
    assert long.status_code == 422
    assert "501 characters" in long.json()["detail"]["message"]

    assert conn.execute("SELECT count(*) FROM recipes").fetchone()[0] == 0
    assert conn.execute("SELECT count(*) FROM claude_usage").fetchone()[0] == 0


def test_api_create_reports_a_recipe_that_fails_validation(api, conn):
    broken = make_recipe(steps=[step("Mix.", ["nope"])])
    http = api(FakeClient(broken, broken))

    response = http.post("/api/create", json={"brief": BRIEF})

    assert response.status_code == 422
    assert any("['nope']" in error for error in response.json()["detail"]["errors"])
    assert conn.execute("SELECT count(*) FROM recipes").fetchone()[0] == 0


def test_api_create_makes_a_new_recipe_every_time(api):
    http = api(FakeClient(make_recipe(), make_recipe()))

    first = http.post("/api/create", json={"brief": BRIEF})
    second = http.post("/api/create", json={"brief": BRIEF})

    assert first.status_code == second.status_code == 201
    assert first.json()["id"] != second.json()["id"]


@pytest.mark.parametrize("path", ["/api/create"])
def test_api_create_rejects_a_missing_brief(api, path):
    http = api(FakeClient())
    assert http.post(path, json={}).status_code == 422
