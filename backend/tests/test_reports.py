import json

import pytest

from app import reports
from app.importer.fetch import FetchError, InvalidUrl
from app.importer.pipeline import import_url
from app.importer.validate import ValidationFailed
from tests.helpers import BBC_URL, FakeClient, fetch_fixture, make_recipe, step


def test_inv12_flag_keeps_recipe_as_it_was(conn):
    """Invariant 12: a flag keeps the recipe as it was when flagged, even after the recipe is edited or deleted."""
    recipe, _ = import_url(conn, BBC_URL, FakeClient(make_recipe()), fetch_fixture("bbcgoodfood.html"))
    report_id = reports.flag_recipe(conn, recipe.id, "Eggs are missing")

    with conn:
        conn.execute("UPDATE recipes SET title = 'Edited title' WHERE id = ?", (recipe.id,))
    assert json.loads(reports.get_report(conn, report_id)["recipe_snapshot"])["title"] == "Easy chocolate cake"

    with conn:
        conn.execute("DELETE FROM recipes WHERE id = ?", (recipe.id,))
    report = reports.get_report(conn, report_id)
    snapshot = json.loads(report["recipe_snapshot"])
    assert report["kind"] == "flagged"
    assert report["recipe_id"] is None
    assert report["comment"] == "Eggs are missing"
    assert snapshot["title"] == "Easy chocolate cake"
    assert [i["name"] for i in snapshot["ingredients"]][2] == "large eggs"
    assert "For the buttercream" in report["raw_extract"]


def test_flag_unknown_recipe_returns_none(conn):
    assert reports.flag_recipe(conn, 12345, "?") is None
    assert reports.list_reports(conn) == []


def test_inv13_validation_failure_is_recorded(conn):
    """Invariant 13: an import that fails after its URL is accepted is recorded with the URL, error and extracted data."""
    broken = make_recipe(steps=[step("Mix.", ["nope"])])
    with pytest.raises(ValidationFailed):
        import_url(conn, BBC_URL, FakeClient(broken, broken), fetch_fixture("bbcgoodfood.html"))

    [report] = reports.list_reports(conn)
    assert report["kind"] == "failed"
    assert report["source_url"] == BBC_URL
    assert "['nope']" in report["error"]
    assert "For the buttercream" in report["raw_extract"]
    assert report["recipe_id"] is None


def test_inv13_fetch_failure_is_recorded(conn):
    """Invariant 13: a blocked fetch is recorded with the URL and error, and no extracted data."""

    def blocked(url: str) -> str:
        raise FetchError(f"{url} returned HTTP 403. The site blocks automated fetches.")

    with pytest.raises(FetchError):
        import_url(conn, BBC_URL, FakeClient(), blocked)

    [report] = reports.list_reports(conn)
    assert "HTTP 403" in report["error"]
    assert report["raw_extract"] is None and report["raw_text"] is None


def test_bad_url_is_not_recorded(conn):
    with pytest.raises(InvalidUrl):
        import_url(conn, "not a url", FakeClient(), fetch_fixture("bbcgoodfood.html"))
    assert reports.list_reports(conn) == []


def test_resolved_reports_leave_the_open_list(conn):
    recipe, _ = import_url(conn, BBC_URL, FakeClient(make_recipe()), fetch_fixture("bbcgoodfood.html"))
    report_id = reports.flag_recipe(conn, recipe.id, "Timer on step 3 is wrong")

    assert reports.resolve_report(conn, report_id, "Prompt now uses the lower end of time ranges")
    assert not reports.resolve_report(conn, report_id, "twice")

    assert reports.list_reports(conn) == []
    [resolved] = reports.list_reports(conn, include_resolved=True)
    assert resolved["resolution"] == "Prompt now uses the lower end of time ranges"


def test_api_flag_recipe(api, conn):
    http = api(FakeClient(make_recipe()))
    recipe_id = http.post("/api/import", json={"url": BBC_URL}).json()["id"]

    assert http.post(f"/api/recipes/{recipe_id}/flags", json={"comment": "   "}).status_code == 422
    assert http.post("/api/recipes/999/flags", json={"comment": "Wrong"}).status_code == 404

    created = http.post(f"/api/recipes/{recipe_id}/flags", json={"comment": " Flour should be 250g "})
    assert created.status_code == 201
    assert reports.get_report(conn, created.json()["id"])["comment"] == "Flour should be 250g"
