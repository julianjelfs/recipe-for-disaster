import base64

import pytest

from app import config, store
from app.importer.pipeline import import_photos, import_url, renormalise_recipe
from app.importer.validate import ValidationFailed
from tests.helpers import BBC_URL, FakeClient, fetch_fixture, make_recipe, step

# Enough of each format for the signature check. Claude never sees them: the client is fake.
PAGE_ONE = b"\xff\xd8\xff\xe0" + b"first page" * 20
PAGE_TWO = b"\x89PNG\r\n\x1a\n" + b"second page" * 20


def upload(*photos: tuple[str, bytes]) -> dict:
    return {"photos": [{"media_type": t, "data": base64.b64encode(d).decode()} for t, d in photos]}


def images_sent(client: FakeClient, call: int = 0) -> list[tuple[str, bytes]]:
    content = client.messages.calls[call]["messages"][0]["content"]
    return [
        (block["source"]["media_type"], base64.b64decode(block["source"]["data"]))
        for block in content
        if block["type"] == "image"
    ]


def test_inv32_a_photographed_recipe_keeps_its_photos_in_order(api, conn):
    """Invariant 32: a photographed recipe keeps every photo it was read from, in page order."""
    client = FakeClient(make_recipe(title="Quick puttanesca spaghetti"))
    http = api(client)

    response = http.post("/api/photo", json=upload(("image/jpeg", PAGE_ONE), ("image/png", PAGE_TWO)))

    assert response.status_code == 201
    recipe = response.json()
    assert (recipe["origin"], recipe["source_url"], recipe["prompt"]) == ("photographed", None, None)
    assert len(recipe["photo_ids"]) == 2
    assert recipe["image_url"] == f"/api/photos/{recipe['photo_ids'][0]}"
    for photo_id, (media_type, data) in zip(recipe["photo_ids"], [("image/jpeg", PAGE_ONE), ("image/png", PAGE_TWO)]):
        photo = http.get(f"/api/photos/{photo_id}")
        assert (photo.status_code, photo.headers["content-type"], photo.content) == (200, media_type, data)
        assert "immutable" in photo.headers["cache-control"]

    assert images_sent(client) == [("image/jpeg", PAGE_ONE), ("image/png", PAGE_TWO)]
    call = client.messages.calls[0]
    assert (call["model"], call["output_config"]) == (config.PHOTO_MODEL, {"effort": config.PHOTO_EFFORT})
    assert http.get("/api/sync").json()["changed"][0]["photo_ids"] == recipe["photo_ids"]


def test_inv32_try_again_rereads_the_stored_photos(conn):
    """Invariant 32: "try again" on a photographed recipe reads its stored photos, with no new picture."""
    recipe = import_photos(conn, [("image/jpeg", PAGE_ONE), ("image/png", PAGE_TWO)], FakeClient(make_recipe(title="First read")))
    client = FakeClient(make_recipe(title="Second read"))

    again = renormalise_recipe(conn, recipe.id, client)

    assert again.title == "Second read"
    assert again.photo_ids == recipe.photo_ids
    assert images_sent(client) == [("image/jpeg", PAGE_ONE), ("image/png", PAGE_TWO)]
    assert client.messages.calls[0]["model"] == config.PHOTO_MODEL


def test_deleting_a_photographed_recipe_deletes_its_photos(api, conn):
    recipe = import_photos(conn, [("image/jpeg", PAGE_ONE)], FakeClient(make_recipe()))
    http = api(FakeClient())

    assert http.delete(f"/api/recipes/{recipe.id}").status_code == 204
    assert http.get(f"/api/photos/{recipe.photo_ids[0]}").status_code == 404
    assert conn.execute("SELECT count(*) FROM recipe_photos").fetchone()[0] == 0


def test_photo_ids_are_never_reused(conn):
    """The phone caches /api/photos/{id} for good, so a new photo must never take an old id."""
    first = import_photos(conn, [("image/jpeg", PAGE_ONE)], FakeClient(make_recipe()))
    store.delete_recipe(conn, first.id)
    second = import_photos(conn, [("image/jpeg", PAGE_ONE)], FakeClient(make_recipe()))
    assert second.photo_ids[0] > first.photo_ids[0]


@pytest.mark.parametrize(
    ("body", "message"),
    [
        (upload(), "between 1 and 4"),
        (upload(*[("image/jpeg", PAGE_ONE)] * 5), "between 1 and 4"),
        ({"photos": [{"media_type": "image/jpeg", "data": "not base64!"}]}, "isn't valid base64"),
        (upload(("image/jpeg", b"\xff\xd8\xff" + b"x" * 3_750_000)), "under 3.5 MB"),
        (upload(("image/jpeg", PAGE_TWO)), "isn't a JPEG"),
        (upload(("image/png", PAGE_ONE)), "isn't a PNG"),
    ],
)
def test_inv33_bad_uploads_are_refused_before_calling_claude(api, conn, body, message):
    """Invariant 33: only 1 to 4 JPEG, PNG or WebP photos of at most 3.5 MB each reach Claude."""
    client = FakeClient(make_recipe())
    response = api(client).post("/api/photo", json=body)

    assert response.status_code == 422
    assert message in response.json()["detail"]["message"]
    assert client.messages.calls == []
    assert conn.execute("SELECT count(*) FROM recipes").fetchone()[0] == 0


def test_inv33_other_formats_are_refused(api, conn):
    """Invariant 33: HEIC and the like never reach Claude, which can't read them."""
    client = FakeClient(make_recipe())
    response = api(client).post("/api/photo", json=upload(("image/heic", PAGE_ONE)))
    assert response.status_code == 422
    assert client.messages.calls == []


def test_inv18_photo_import_records_its_cost(conn):
    """Invariant 18: a photo import records its usage against the photo model, as purpose "photo"."""
    recipe = import_photos(conn, [("image/jpeg", PAGE_ONE)], FakeClient(make_recipe()))

    [row] = conn.execute("SELECT * FROM claude_usage").fetchall()
    assert (row["purpose"], row["recipe_id"], row["succeeded"], row["model"]) == ("photo", recipe.id, 1, config.PHOTO_MODEL)
    # Sonnet 5.5 list prices: 1000 in at $2/M, 500 out at $10/M.
    assert row["cost_usd"] == pytest.approx(0.007)


def test_a_failed_photo_import_is_recorded_and_stores_nothing(conn):
    broken = make_recipe(steps=[step("Mix.", ["nope"])])
    with pytest.raises(ValidationFailed):
        import_photos(conn, [("image/jpeg", PAGE_ONE)], FakeClient(broken, broken))

    assert conn.execute("SELECT count(*) FROM recipes").fetchone()[0] == 0
    assert conn.execute("SELECT count(*) FROM recipe_photos").fetchone()[0] == 0
    [report] = conn.execute("SELECT kind, comment FROM import_reports").fetchall()
    assert report["kind"] == "failed" and "photo" in report["comment"]
    [usage] = conn.execute("SELECT purpose, succeeded, calls FROM claude_usage").fetchall()
    assert tuple(usage) == ("photo", 0, 2)


def test_url_imports_send_no_effort(conn):
    """Haiku 4.5 rejects the effort setting, so only the photo path may send it."""
    client = FakeClient(make_recipe())
    import_url(conn, BBC_URL, client, fetch_fixture("bbcgoodfood.html"))
    assert "output_config" not in client.messages.calls[0]
