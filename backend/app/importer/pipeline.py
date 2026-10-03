"""Get a recipe into the library: import one from a URL, invent one from a brief, read one from
photos of a recipe book, or re-read one."""

import base64
import sqlite3
from collections.abc import Callable

import anthropic

from app import config, costs, reports, store
from app.importer.create import invent_recipe
from app.importer.extract import Extract, ExtractError, extract, restore
from app.importer.fetch import FetchError, canonicalise_url, fetch_html
from app.importer.normalise import NormaliseError, Usage, normalise
from app.importer.photo import read_photos
from app.importer.validate import ValidationFailed
from app.schemas import Recipe

# Failures worth reviewing later. Bad URLs and transient Claude API errors are not.
RECORDED_FAILURES = (FetchError, ExtractError, ValidationFailed, NormaliseError)


def import_url(
    conn: sqlite3.Connection,
    url: str,
    client: anthropic.Anthropic,
    fetch: Callable[[str], str] = fetch_html,
) -> tuple[Recipe, bool]:
    """Return the stored recipe and whether this call created it."""
    source_url = canonicalise_url(url)
    existing_id = store.find_recipe_id(conn, source_url)
    if existing_id is not None:
        return store.get_recipe(conn, existing_id), False

    usage = Usage()
    recipe_id: int | None = None
    try:
        page: Extract | None = None
        try:
            page = extract(fetch(source_url), source_url)
            result = normalise(page, client, config.MODEL, usage)
        except RECORDED_FAILURES as error:
            reports.record_failure(conn, source_url=source_url, error=error, extract=page, model=config.MODEL)
            raise

        try:
            recipe_id = store.insert_recipe(
                conn,
                source_url=source_url,
                recipe=result.recipe,
                extract=page,
                model=config.MODEL,
                parse_version=config.PARSE_VERSION,
            )
        except sqlite3.IntegrityError:
            # Another request stored the same URL while this one was waiting on Claude.
            existing_id = store.find_recipe_id(conn, source_url)
            if existing_id is None:
                raise
            return store.get_recipe(conn, existing_id), False
        return store.get_recipe(conn, recipe_id), True
    finally:
        # Every call is paid for, so record it whether or not the import worked.
        costs.record(
            conn,
            purpose="import",
            source_url=source_url,
            recipe_id=recipe_id,
            succeeded=recipe_id is not None,
            model=config.MODEL,
            usage=usage,
        )


def create_recipe(conn: sqlite3.Connection, brief: str, client: anthropic.Anthropic) -> Recipe:
    """Invent a recipe from a brief and store it. No URL, no page, no dedupe."""
    usage = Usage()
    recipe_id: int | None = None
    try:
        try:
            result = invent_recipe(brief, client, config.MODEL, usage)
        except (ValidationFailed, NormaliseError) as error:
            # A created recipe that fails validation means the shared rules have a problem.
            reports.record_failure(conn, source_url=None, error=error, extract=None, model=config.MODEL, comment=brief)
            raise
        recipe_id = store.insert_recipe(
            conn,
            source_url=None,
            recipe=result.recipe,
            extract=None,
            model=config.MODEL,
            parse_version=config.PARSE_VERSION,
            origin="created",
            prompt=brief,
        )
        return store.get_recipe(conn, recipe_id)
    finally:
        costs.record(
            conn,
            purpose="create",
            source_url=None,
            recipe_id=recipe_id,
            succeeded=recipe_id is not None,
            model=config.MODEL,
            usage=usage,
        )


def _encoded(photos: list[tuple[str, bytes]]) -> list[tuple[str, str]]:
    return [(media_type, base64.standard_b64encode(data).decode()) for media_type, data in photos]


def import_photos(conn: sqlite3.Connection, photos: list[tuple[str, bytes]], client: anthropic.Anthropic) -> Recipe:
    """Read a recipe from photos of a printed page, (media type, bytes) in page order, and store it
    with its photos so it can be read again later without a new picture."""
    usage = Usage()
    recipe_id: int | None = None
    try:
        try:
            result = read_photos(_encoded(photos), client, config.PHOTO_MODEL, usage)
        except (ValidationFailed, NormaliseError) as error:
            reports.record_failure(
                conn, source_url=None, error=error, extract=None, model=config.PHOTO_MODEL,
                comment=f"Read from {len(photos)} photo(s) of a recipe book",
            )
            raise
        recipe_id = store.insert_recipe(
            conn,
            source_url=None,
            recipe=result.recipe,
            extract=None,
            model=config.PHOTO_MODEL,
            parse_version=config.PARSE_VERSION,
            origin="photographed",
            photos=photos,
        )
        return store.get_recipe(conn, recipe_id)
    finally:
        costs.record(
            conn,
            purpose="photo",
            source_url=None,
            recipe_id=recipe_id,
            succeeded=recipe_id is not None,
            model=config.PHOTO_MODEL,
            usage=usage,
        )


def renormalise_recipe(conn: sqlite3.Connection, recipe_id: int, client: anthropic.Anthropic) -> Recipe | None:
    """Ask Claude for this recipe again: the saved page for an import, the saved brief for a creation,
    the saved photos for a photographed recipe.

    Never fetches anything. Returns None if there is no such recipe; on failure the recipe is left
    as it was and the failure is recorded. Notes and custom tags survive either way.
    """
    raw = store.get_raw(conn, recipe_id)
    if raw is None:
        return None
    origin = raw["origin"]
    page = restore(raw["raw_extract"], raw["raw_text"]) if origin == "imported" else None
    model = config.PHOTO_MODEL if origin == "photographed" else config.MODEL

    usage = Usage()
    succeeded = False
    try:
        try:
            if origin == "created":
                result = invent_recipe(raw["prompt"], client, model, usage)
            elif origin == "photographed":
                result = read_photos(_encoded(store.get_photos(conn, recipe_id)), client, model, usage)
            else:
                result = normalise(page, client, model, usage)
        except (ValidationFailed, NormaliseError) as error:
            reports.record_failure(
                conn,
                source_url=raw["source_url"],
                error=error,
                extract=page,
                model=model,
                comment=raw["prompt"] or "",
            )
            raise
        store.replace_recipe(conn, recipe_id, result.recipe, model=model, parse_version=config.PARSE_VERSION)
        succeeded = True
    finally:
        costs.record(
            conn,
            purpose="renormalise",
            source_url=raw["source_url"],
            recipe_id=recipe_id,
            succeeded=succeeded,
            model=model,
            usage=usage,
        )
    return store.get_recipe(conn, recipe_id)
