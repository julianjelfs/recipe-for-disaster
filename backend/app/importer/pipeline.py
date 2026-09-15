"""Import a recipe from a URL (fetch, extract, normalise, store), or re-read one from its saved page data."""

import sqlite3
from collections.abc import Callable

import anthropic

from app import config, reports, store
from app.importer.extract import Extract, ExtractError, extract, restore
from app.importer.fetch import FetchError, canonicalise_url, fetch_html
from app.importer.normalise import NormaliseError, normalise
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

    page: Extract | None = None
    try:
        page = extract(fetch(source_url), source_url)
        result = normalise(page, client, config.MODEL)
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


def renormalise_recipe(conn: sqlite3.Connection, recipe_id: int, client: anthropic.Anthropic) -> Recipe | None:
    """Re-run Claude over the page data saved at import, keeping notes and custom tags.

    Never fetches the page again. Returns None if there is no such recipe; on failure the
    recipe is left as it was and the failure is recorded.
    """
    raw = store.get_raw(conn, recipe_id)
    if raw is None:
        return None
    page = restore(raw["raw_extract"], raw["raw_text"])
    try:
        result = normalise(page, client, config.MODEL)
    except (ValidationFailed, NormaliseError) as error:
        reports.record_failure(conn, source_url=raw["source_url"], error=error, extract=page, model=config.MODEL)
        raise
    store.replace_recipe(conn, recipe_id, result.recipe, model=config.MODEL, parse_version=config.PARSE_VERSION)
    return store.get_recipe(conn, recipe_id)
