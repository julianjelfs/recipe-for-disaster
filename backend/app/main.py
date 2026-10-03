"""FastAPI app. JSON API under /api, and the built frontend everywhere else."""

import base64
import binascii
import os
import sqlite3
from collections.abc import Callable, Iterator
from contextlib import asynccontextmanager, contextmanager
from functools import lru_cache

import anthropic
from fastapi import Depends, FastAPI, HTTPException, Query, Response

from app import config, db, reports, store, sync
from app.importer.extract import ExtractError
from app.importer.fetch import FetchError, InvalidUrl, fetch_html
from app.importer.normalise import NormaliseError
from app.importer.pipeline import create_recipe, import_photos, import_url, renormalise_recipe
from app.importer.validate import ValidationFailed, validate
from app.schemas import (
    CreateRequest,
    FlagCreated,
    FlagRequest,
    ImportRequest,
    PhotoRequest,
    Recipe,
    RecipeEdit,
    SyncResponse,
)
from app.ui import UiFiles

# Long enough for a detailed brief, short enough that nobody pastes an essay into a Claude call.
MAX_BRIEF = 500
# A recipe rarely runs past two pages; four leaves room for a photo of each half of a spread.
MAX_PHOTOS = 4
# Claude takes images up to 5 MB, counted as base64, which is 4/3 of the bytes. The app shrinks
# photos to a few hundred kilobytes before sending, so only a photo sent some other way gets near.
MAX_PHOTO_BYTES = 3_750_000
# How each accepted format starts, so a mislabelled or broken upload fails here, not at Claude.
_PHOTO_SIGNATURES = {"image/jpeg": (b"\xff\xd8\xff",), "image/png": (b"\x89PNG\r\n\x1a\n",), "image/webp": (b"RIFF",)}


@asynccontextmanager
async def lifespan(_app: FastAPI):
    conn = db.connect(config.DB_PATH)
    try:
        db.migrate(conn)
    finally:
        conn.close()
    yield


app = FastAPI(title="Recipe for Disaster", lifespan=lifespan)


def get_conn() -> Iterator[sqlite3.Connection]:
    conn = db.connect(config.DB_PATH)
    try:
        yield conn
    finally:
        conn.close()


@lru_cache
def _anthropic_client() -> anthropic.Anthropic:
    return anthropic.Anthropic()


def get_client() -> anthropic.Anthropic:
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise api_error(503, "ANTHROPIC_API_KEY is not set. Add it to backend/.env and restart the server.")
    return _anthropic_client()


def get_fetcher() -> Callable[[str], str]:
    return fetch_html


def api_error(status: int, message: str, errors: list[str] | None = None) -> HTTPException:
    return HTTPException(status, {"message": message, "errors": errors or []})


@contextmanager
def importer_errors() -> Iterator[None]:
    """Turn importer and Claude API failures into API errors."""
    try:
        yield
    except (InvalidUrl, ExtractError) as error:
        raise api_error(422, str(error)) from error
    except ValidationFailed as error:
        raise api_error(422, "Claude's version of the recipe failed validation twice.", error.errors) from error
    except (FetchError, NormaliseError) as error:
        raise api_error(502, str(error)) from error
    except anthropic.AuthenticationError as error:
        raise api_error(503, "Anthropic rejected the API key in backend/.env.") from error
    except (anthropic.APIStatusError, anthropic.APIConnectionError) as error:
        raise api_error(502, f"Claude API error: {error}") from error


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/import", response_model=Recipe)
def import_recipe(
    body: ImportRequest,
    response: Response,
    conn: sqlite3.Connection = Depends(get_conn),
    client: anthropic.Anthropic = Depends(get_client),
    fetch: Callable[[str], str] = Depends(get_fetcher),
) -> Recipe:
    with importer_errors():
        recipe, created = import_url(conn, body.url, client, fetch)
    response.status_code = 201 if created else 200
    return recipe


@app.post("/api/create", status_code=201, response_model=Recipe)
def create_from_brief(
    body: CreateRequest,
    conn: sqlite3.Connection = Depends(get_conn),
    client: anthropic.Anthropic = Depends(get_client),
) -> Recipe:
    """Invent a recipe from a brief. Two identical briefs make two recipes; there is nothing to dedupe."""
    brief = body.brief.strip()
    if not brief:
        raise api_error(422, "Say what you fancy and Claude will invent a recipe for it.")
    if len(brief) > MAX_BRIEF:
        raise api_error(422, f"That brief is {len(brief)} characters. Keep it under {MAX_BRIEF}.")
    with importer_errors():
        return create_recipe(conn, brief, client)


@app.post("/api/photo", status_code=201, response_model=Recipe)
def import_from_photos(
    body: PhotoRequest,
    conn: sqlite3.Connection = Depends(get_conn),
    client: anthropic.Anthropic = Depends(get_client),
) -> Recipe:
    """Read a recipe from photos of a recipe book page, in page order."""
    if not 1 <= len(body.photos) <= MAX_PHOTOS:
        raise api_error(422, f"Send between 1 and {MAX_PHOTOS} photos of the recipe.")
    photos: list[tuple[str, bytes]] = []
    for number, photo in enumerate(body.photos, start=1):
        try:
            data = base64.b64decode(photo.data, validate=True)
        except binascii.Error as error:
            raise api_error(422, f"Photo {number} isn't valid base64.") from error
        if len(data) > MAX_PHOTO_BYTES:
            raise api_error(422, f"Photo {number} is {len(data) // 1_000_000} MB. Keep each photo under 3.5 MB.")
        if not data.startswith(_PHOTO_SIGNATURES[photo.media_type]):
            raise api_error(422, f"Photo {number} isn't a {photo.media_type.removeprefix('image/').upper()} image.")
        photos.append((photo.media_type, data))
    with importer_errors():
        return import_photos(conn, photos, client)


@app.get("/api/photos/{photo_id}")
def read_photo(photo_id: int, conn: sqlite3.Connection = Depends(get_conn)) -> Response:
    """A stored page photo. Photo ids are never reused, so the phone may keep it for good."""
    photo = store.get_photo(conn, photo_id)
    if photo is None:
        raise api_error(404, "Photo not found.")
    media_type, data = photo
    return Response(data, media_type=media_type, headers={"Cache-Control": "public, max-age=31536000, immutable"})


@app.get("/api/sync", response_model=SyncResponse)
def sync_library(
    since: int = Query(0, ge=0),
    epoch: int | None = None,
    conn: sqlite3.Connection = Depends(get_conn),
) -> SyncResponse:
    """What changed since revision `since`. With since=0 (a new device) it is the whole library."""
    return sync.changes_since(conn, since, epoch)


@app.get("/api/recipes/{recipe_id}", response_model=Recipe)
def read_recipe(recipe_id: int, conn: sqlite3.Connection = Depends(get_conn)) -> Recipe:
    recipe = store.get_recipe(conn, recipe_id)
    if recipe is None:
        raise api_error(404, "Recipe not found.")
    return recipe


@app.put("/api/recipes/{recipe_id}", response_model=Recipe)
def update_recipe(recipe_id: int, body: RecipeEdit, conn: sqlite3.Connection = Depends(get_conn)) -> Recipe:
    try:
        cleaned = validate(body)
    except ValidationFailed as error:
        raise api_error(422, "The recipe has problems.", error.errors) from error
    if not store.replace_recipe(conn, recipe_id, cleaned, notes=body.notes, custom_tags=body.tags):
        raise api_error(404, "Recipe not found.")
    return store.get_recipe(conn, recipe_id)


@app.delete("/api/recipes/{recipe_id}", status_code=204)
def delete_recipe(recipe_id: int, conn: sqlite3.Connection = Depends(get_conn)) -> Response:
    if not store.delete_recipe(conn, recipe_id):
        raise api_error(404, "Recipe not found.")
    return Response(status_code=204)


@app.post("/api/recipes/{recipe_id}/renormalise", response_model=Recipe)
def renormalise(
    recipe_id: int,
    conn: sqlite3.Connection = Depends(get_conn),
    client: anthropic.Anthropic = Depends(get_client),
) -> Recipe:
    with importer_errors():
        recipe = renormalise_recipe(conn, recipe_id, client)
    if recipe is None:
        raise api_error(404, "Recipe not found.")
    return recipe


@app.post("/api/recipes/{recipe_id}/flags", status_code=201, response_model=FlagCreated)
def flag_recipe(recipe_id: int, body: FlagRequest, conn: sqlite3.Connection = Depends(get_conn)) -> FlagCreated:
    comment = body.comment.strip()
    if not comment:
        raise api_error(422, "Say what's wrong with the recipe so it can be fixed.")
    report_id = reports.flag_recipe(conn, recipe_id, comment)
    if report_id is None:
        raise api_error(404, "Recipe not found.")
    return FlagCreated(id=report_id)


# Mounted last so every /api route above wins.
if config.UI_DIR.is_dir():
    app.mount("/", UiFiles(directory=config.UI_DIR), name="ui")
