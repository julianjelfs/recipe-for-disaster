"""Records of bad imports: recipes someone flagged, and imports or creations that failed."""

import json
import sqlite3

from app import config, store
from app.importer.extract import Extract


def record_failure(
    conn: sqlite3.Connection,
    *,
    source_url: str | None,
    error: Exception,
    extract: Extract | None,
    model: str,
    comment: str = "",
) -> int:
    """Store a failure worth reviewing. A creation has no URL and no page data, so it carries its brief."""
    raw_extract = json.dumps(extract.structured, ensure_ascii=False) if extract and extract.structured is not None else None
    with conn:
        return conn.execute(
            """
            INSERT INTO import_reports (kind, source_url, comment, error, raw_extract, raw_text, model, parse_version)
            VALUES ('failed', ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                source_url,
                comment,
                f"{type(error).__name__}: {error}",
                raw_extract,
                extract.text if extract else None,
                model,
                config.PARSE_VERSION,
            ),
        ).lastrowid


def flag_recipe(conn: sqlite3.Connection, recipe_id: int, comment: str) -> int | None:
    """Store a report with a snapshot of the recipe as it is now. Returns None if there is no such recipe."""
    recipe = store.get_recipe(conn, recipe_id)
    if recipe is None:
        return None
    raw = conn.execute("SELECT raw_extract, raw_text FROM recipes WHERE id = ?", (recipe_id,)).fetchone()
    with conn:
        return conn.execute(
            """
            INSERT INTO import_reports (
                kind, source_url, recipe_id, comment, recipe_snapshot, raw_extract, raw_text, model, parse_version
            ) VALUES ('flagged', ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                recipe.source_url,
                recipe_id,
                comment,
                recipe.model_dump_json(),
                raw["raw_extract"],
                raw["raw_text"],
                recipe.model,
                recipe.parse_version,
            ),
        ).lastrowid


def list_reports(conn: sqlite3.Connection, include_resolved: bool = False) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM import_reports WHERE ? OR resolved_at IS NULL ORDER BY id DESC",
        (include_resolved,),
    ).fetchall()


def get_report(conn: sqlite3.Connection, report_id: int) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM import_reports WHERE id = ?", (report_id,)).fetchone()


def resolve_report(conn: sqlite3.Connection, report_id: int, resolution: str) -> bool:
    with conn:
        cursor = conn.execute(
            "UPDATE import_reports SET resolved_at = datetime('now'), resolution = ? WHERE id = ? AND resolved_at IS NULL",
            (resolution, report_id),
        )
    return cursor.rowcount == 1
