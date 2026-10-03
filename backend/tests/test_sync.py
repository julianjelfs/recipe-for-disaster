import pytest

from app import store, sync
from app.importer.pipeline import renormalise_recipe
from tests.helpers import BBC_URL, FakeClient, add_created_recipe, add_recipe, make_recipe


def epoch(conn) -> int:
    return conn.execute("PRAGMA user_version").fetchone()[0]


def since(conn, revision: int):
    return sync.changes_since(conn, revision, epoch(conn))


def changed_ids(response) -> list[int]:
    return [recipe.id for recipe in response.changed]


def test_inv28_every_write_path_is_reported_as_changed(conn):
    """Invariant 28: syncing from revision r returns every recipe added or changed after r, and no other."""
    pie = add_recipe(conn, BBC_URL, title="Leek pie")
    soup = add_created_recipe(conn, title="Leek soup")
    start = since(conn, 0).revision

    assert since(conn, start).changed == []

    store.replace_recipe(conn, pie.id, make_recipe(title="Leek and cheese pie"), notes="More cheese")
    after_edit = since(conn, start)
    assert changed_ids(after_edit) == [pie.id]
    assert after_edit.changed[0].title == "Leek and cheese pie"

    renormalise_recipe(conn, soup.id, FakeClient(make_recipe(title="Leek soup, read again")))
    after_reread = since(conn, after_edit.revision)
    assert changed_ids(after_reread) == [soup.id]

    newer = add_created_recipe(conn, title="Squash stew")
    assert changed_ids(since(conn, after_reread.revision)) == [newer.id]


@pytest.mark.parametrize(
    "sql",
    [
        "UPDATE ingredients SET name = 'baby leeks' WHERE recipe_id = {id}",
        "DELETE FROM ingredients WHERE id = (SELECT max(id) FROM ingredients WHERE recipe_id = {id})",
        "UPDATE steps SET text = 'Stir.' WHERE recipe_id = {id}",
        "INSERT INTO tags (recipe_id, kind, value) VALUES ({id}, 'custom', 'weeknight')",
        "DELETE FROM step_ingredients WHERE step_id IN (SELECT id FROM steps WHERE recipe_id = {id})",
    ],
)
def test_inv28_a_change_to_a_recipes_parts_changes_the_recipe(conn, sql):
    """Invariant 28: the database stamps the change itself, so no write path can forget to."""
    pie = add_recipe(conn, BBC_URL, title="Leek pie")
    other = add_created_recipe(conn, title="Leek soup")
    start = since(conn, 0).revision

    with conn:
        conn.execute(sql.format(id=pie.id))

    assert changed_ids(since(conn, start)) == [pie.id]
    assert other.id not in changed_ids(since(conn, start))


def test_inv29_deleted_recipes_are_reported(conn):
    """Invariant 29: syncing from revision r reports every recipe deleted after r."""
    pie = add_recipe(conn, BBC_URL, title="Leek pie")
    soup = add_created_recipe(conn, title="Leek soup")
    start = since(conn, 0).revision

    assert store.delete_recipe(conn, soup.id)

    response = since(conn, start)
    assert response.deleted == [soup.id]
    assert response.changed == []
    assert since(conn, response.revision).deleted == []
    assert store.get_recipe(conn, pie.id) is not None


def test_inv29_a_reused_id_is_not_reported_deleted(conn):
    """Invariant 29: SQLite gives a new recipe the highest id once it is free. That recipe exists, so it isn't deleted."""
    add_recipe(conn, BBC_URL, title="Leek pie")
    soup = add_created_recipe(conn, title="Leek soup")
    start = since(conn, 0).revision

    store.delete_recipe(conn, soup.id)
    stew = add_created_recipe(conn, title="Squash stew")
    assert stew.id == soup.id

    response = since(conn, start)
    assert response.deleted == []
    assert changed_ids(response) == [stew.id]
    assert response.changed[0].title == "Squash stew"


def test_inv30_a_fresh_device_gets_the_whole_library(conn):
    """Invariant 30: a sync from 0 returns every recipe, marked full."""
    pie = add_recipe(conn, BBC_URL, title="Leek pie")
    soup = add_created_recipe(conn, title="Leek soup")
    store.delete_recipe(conn, soup.id)

    response = sync.changes_since(conn, 0, None)

    assert response.full
    assert changed_ids(response) == [pie.id]
    assert response.deleted == []
    assert response.changed[0] == store.get_recipe(conn, pie.id)


@pytest.mark.parametrize("ahead_by", [1, 100])
def test_inv30_a_copy_ahead_of_the_server_starts_again(conn, ahead_by):
    """Invariant 30: after the Pi is restored from a backup, a device's revision may be ahead of it."""
    add_recipe(conn, BBC_URL)
    revision = since(conn, 0).revision

    response = since(conn, revision + ahead_by)

    assert response.full
    assert len(response.changed) == 1


def test_inv30_a_copy_from_another_epoch_starts_again(conn):
    """Invariant 30: a migration may change recipes without the triggers seeing it, so it voids every copy."""
    add_recipe(conn, BBC_URL)
    revision = since(conn, 0).revision

    response = sync.changes_since(conn, revision, epoch(conn) - 1)

    assert response.full
    assert len(response.changed) == 1


def test_api_sync(api, conn):
    pie = add_recipe(conn, BBC_URL, title="Leek pie")
    http = api(FakeClient(make_recipe()))

    first = http.get("/api/sync").json()
    assert first["full"] and [r["id"] for r in first["changed"]] == [pie.id]
    assert first["changed"][0] == http.get(f"/api/recipes/{pie.id}").json()

    assert http.delete(f"/api/recipes/{pie.id}").status_code == 204
    second = http.get("/api/sync", params={"since": first["revision"], "epoch": first["epoch"]}).json()
    assert not second["full"]
    assert (second["changed"], second["deleted"]) == ([], [pie.id])
    assert second["revision"] > first["revision"]
