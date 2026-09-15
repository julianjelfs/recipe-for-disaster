import pytest
from fastapi.testclient import TestClient

from app import db
from app.main import app, get_client, get_conn, get_fetcher
from tests.helpers import FakeClient, fetch_fixture


@pytest.fixture
def conn(tmp_path):
    connection = db.connect(tmp_path / "test.db")
    db.migrate(connection)
    yield connection
    connection.close()


@pytest.fixture
def api(conn):
    """Build a TestClient wired to the test database, a fake Claude client and a saved page."""

    def make(client: FakeClient, fixture: str = "bbcgoodfood.html") -> TestClient:
        app.dependency_overrides[get_conn] = lambda: conn
        app.dependency_overrides[get_client] = lambda: client
        app.dependency_overrides[get_fetcher] = lambda: fetch_fixture(fixture)
        return TestClient(app)

    yield make
    app.dependency_overrides.clear()
