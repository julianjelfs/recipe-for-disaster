import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.ui import UiFiles


@pytest.fixture
def http(tmp_path):
    (tmp_path / "index.html").write_text("<!doctype html><title>app</title>")
    (tmp_path / "robots.txt").write_text("User-agent: *")
    immutable = tmp_path / "_app" / "immutable"
    immutable.mkdir(parents=True)
    (immutable / "entry.abc123.js").write_text("console.log('hi')")

    app = FastAPI()

    @app.get("/api/health")
    def health():
        return {"status": "ok"}

    app.mount("/", UiFiles(directory=tmp_path), name="ui")
    return TestClient(app)


def test_inv16_client_routes_get_the_app(http):
    """Invariant 16: any non-API path that isn't a file returns the app's index.html."""
    for path in ("/", "/r/12", "/r/12/cook?step=3", "/add?url=https://example.com"):
        response = http.get(path)
        assert response.status_code == 200, path
        assert "<title>app</title>" in response.text, path
        assert response.headers["cache-control"] == "no-cache", path


def test_inv16_api_paths_never_get_the_app(http):
    """Invariant 16: paths under /api never return index.html; unknown ones 404."""
    assert http.get("/api/health").json() == {"status": "ok"}
    for path in ("/api", "/api/nope", "/api/recipes/1/nope"):
        response = http.get(path)
        assert response.status_code == 404, path
        assert "<title>app</title>" not in response.text, path


def test_only_fingerprinted_files_are_cached_forever(http):
    assert http.get("/_app/immutable/entry.abc123.js").headers["cache-control"] == "public, max-age=31536000, immutable"
    assert http.get("/robots.txt").headers["cache-control"] == "no-cache"
