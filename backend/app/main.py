"""FastAPI app. JSON API under /api, and the built frontend everywhere else."""

import os
import sqlite3
from collections.abc import Callable, Iterator
from contextlib import asynccontextmanager, contextmanager
from functools import lru_cache

import anthropic
from fastapi import Depends, FastAPI, HTTPException, Response

from app import config, db, reports, search, store
from app.importer.extract import ExtractError
from app.importer.fetch import FetchError, InvalidUrl, fetch_html
from app.importer.normalise import NormaliseError
from app.importer.pipeline import import_url, renormalise_recipe
from app.importer.validate import ValidationFailed, validate
from app.schemas import (
    Facets,
    FlagCreated,
    FlagRequest,
    ImportRequest,
    Recipe,
    RecipeEdit,
    RecipeSummary,
    SearchSort,
)
from app.ui import UiFiles


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


def _split(values: str) -> list[str]:
    return [value.strip() for value in values.split(",") if value.strip()]


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


@app.get("/api/recipes", response_model=list[RecipeSummary])
def list_recipes(
    q: str | None = None,
    has: str = "",
    max_total: int | None = None,
    max_complexity: int | None = None,
    cuisine: str | None = None,
    course: str | None = None,
    tag: str = "",
    sort: SearchSort | None = None,
    conn: sqlite3.Connection = Depends(get_conn),
) -> list[RecipeSummary]:
    """`has` and `tag` take comma-separated lists; a recipe must match every entry."""
    return search.search_recipes(
        conn,
        q=q,
        has=_split(has),
        max_total=max_total,
        max_complexity=max_complexity,
        cuisine=cuisine,
        course=course,
        tags=_split(tag),
        sort=sort,
    )


@app.get("/api/facets", response_model=Facets)
def read_facets(conn: sqlite3.Connection = Depends(get_conn)) -> Facets:
    return search.facets(conn)


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
