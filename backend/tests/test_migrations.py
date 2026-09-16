"""Migrations run against databases that already hold recipes, so they must not lose any."""

import sqlite3

import pytest

from app import db

# The schema as it stood at migration 004, before created recipes existed. Enough of it to hold a
# recipe with children, so a migration that drops the recipes table takes them with it.
SCHEMA_AT_4 = """
CREATE TABLE recipes (
    id INTEGER PRIMARY KEY,
    source_url TEXT NOT NULL UNIQUE,
    source_domain TEXT NOT NULL,
    title TEXT NOT NULL,
    image_url TEXT,
    servings INTEGER,
    prep_minutes INTEGER,
    cook_minutes INTEGER,
    total_minutes INTEGER,
    complexity INTEGER NOT NULL CHECK (complexity BETWEEN 1 AND 5),
    cuisine TEXT,
    course TEXT,
    notes TEXT NOT NULL DEFAULT '',
    raw_extract TEXT,
    raw_text TEXT,
    model TEXT NOT NULL,
    parse_version INTEGER NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE ingredients (
    id INTEGER PRIMARY KEY,
    recipe_id INTEGER NOT NULL REFERENCES recipes(id) ON DELETE CASCADE,
    position INTEGER NOT NULL,
    group_name TEXT,
    quantity REAL,
    quantity_max REAL,
    unit TEXT,
    name TEXT NOT NULL,
    canonical_name TEXT NOT NULL,
    preparation TEXT,
    optional INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE steps (
    id INTEGER PRIMARY KEY,
    recipe_id INTEGER NOT NULL REFERENCES recipes(id) ON DELETE CASCADE,
    position INTEGER NOT NULL,
    text TEXT NOT NULL,
    timer_seconds INTEGER
);
CREATE TABLE step_ingredients (
    step_id INTEGER NOT NULL REFERENCES steps(id) ON DELETE CASCADE,
    ingredient_id INTEGER NOT NULL REFERENCES ingredients(id) ON DELETE CASCADE,
    PRIMARY KEY (step_id, ingredient_id)
);
CREATE TABLE tags (
    recipe_id INTEGER NOT NULL REFERENCES recipes(id) ON DELETE CASCADE,
    kind TEXT NOT NULL CHECK (kind IN ('diet', 'equipment', 'technique', 'custom')),
    value TEXT NOT NULL,
    PRIMARY KEY (recipe_id, kind, value)
);
CREATE VIRTUAL TABLE recipe_search USING fts5(
    recipe_id UNINDEXED, title, ingredients, steps, tags, notes, meta,
    tokenize = 'porter unicode61 remove_diacritics 2'
);
CREATE TABLE import_reports (
    id INTEGER PRIMARY KEY,
    kind TEXT NOT NULL CHECK (kind IN ('flagged', 'failed')),
    source_url TEXT NOT NULL,
    recipe_id INTEGER REFERENCES recipes(id) ON DELETE SET NULL,
    comment TEXT NOT NULL DEFAULT '',
    error TEXT,
    recipe_snapshot TEXT,
    raw_extract TEXT,
    raw_text TEXT,
    model TEXT,
    parse_version INTEGER,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    resolved_at TEXT,
    resolution TEXT
);
CREATE TABLE claude_usage (
    id INTEGER PRIMARY KEY,
    purpose TEXT NOT NULL CHECK (purpose IN ('import', 'renormalise')),
    source_url TEXT NOT NULL,
    recipe_id INTEGER REFERENCES recipes(id) ON DELETE SET NULL,
    succeeded INTEGER NOT NULL,
    model TEXT NOT NULL,
    calls INTEGER NOT NULL,
    input_tokens INTEGER NOT NULL,
    output_tokens INTEGER NOT NULL,
    cache_creation_input_tokens INTEGER NOT NULL,
    cache_read_input_tokens INTEGER NOT NULL,
    cost_usd REAL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
"""


@pytest.fixture
def database_at_4(tmp_path):
    """A database as an installed copy looked like before this feature: real content, user_version 4."""
    path = tmp_path / "old.db"
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA_AT_4)
    conn.execute(
        "INSERT INTO recipes (id, source_url, source_domain, title, complexity, model, parse_version)"
        " VALUES (1, 'https://www.bbcgoodfood.com/recipes/cake', 'bbcgoodfood.com', 'Easy chocolate cake', 2, 'claude-haiku-4-5', 1)"
    )
    conn.execute("INSERT INTO ingredients (id, recipe_id, position, name, canonical_name) VALUES (1, 1, 0, 'butter', 'butter')")
    conn.execute("INSERT INTO ingredients (id, recipe_id, position, name, canonical_name) VALUES (2, 1, 1, 'eggs', 'egg')")
    conn.execute("INSERT INTO steps (id, recipe_id, position, text) VALUES (1, 1, 0, 'Beat the butter and eggs.')")
    conn.execute("INSERT INTO step_ingredients (step_id, ingredient_id) VALUES (1, 1), (1, 2)")
    conn.execute("INSERT INTO tags (recipe_id, kind, value) VALUES (1, 'diet', 'vegetarian')")
    conn.execute("INSERT INTO recipe_search (recipe_id, title, ingredients, steps, tags, notes, meta)"
                 " VALUES (1, 'Easy chocolate cake', 'butter eggs', 'Beat the butter and eggs.', 'vegetarian', '', 'British baking')")
    conn.execute(
        "INSERT INTO claude_usage (purpose, source_url, recipe_id, succeeded, model, calls, input_tokens,"
        " output_tokens, cache_creation_input_tokens, cache_read_input_tokens, cost_usd)"
        " VALUES ('import', 'https://www.bbcgoodfood.com/recipes/cake', 1, 1, 'claude-haiku-4-5', 1, 1000, 500, 0, 0, 0.0035)"
    )
    conn.execute("PRAGMA user_version = 4")
    conn.commit()
    conn.close()
    return path


def counts(conn: sqlite3.Connection) -> dict[str, int]:
    return {
        table: conn.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
        for table in ("recipes", "ingredients", "steps", "step_ingredients", "tags", "recipe_search", "claude_usage")
    }


def test_inv23_migrating_keeps_existing_recipe_content(database_at_4):
    """Invariant 23: migrating a database that already holds recipes preserves their content.

    Rebuilding the recipes table drops the old one, which cascades to ingredients, steps and tags
    unless foreign keys are off. Without that, this migration would leave an empty recipe behind
    and report success.
    """
    conn = db.connect(database_at_4)
    before = counts(conn)
    assert before["ingredients"] == 2

    db.migrate(conn)

    assert counts(conn) == before
    assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
    assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1

    recipe = conn.execute("SELECT * FROM recipes WHERE id = 1").fetchone()
    assert (recipe["title"], recipe["origin"], recipe["prompt"]) == ("Easy chocolate cake", "imported", None)
    assert recipe["source_url"] == "https://www.bbcgoodfood.com/recipes/cake"
    assert [r["name"] for r in conn.execute("SELECT name FROM ingredients WHERE recipe_id = 1 ORDER BY position")] == ["butter", "eggs"]
    assert conn.execute("SELECT count(*) FROM claude_usage WHERE recipe_id = 1").fetchone()[0] == 1
    conn.close()


def test_the_migrated_database_accepts_created_recipes(database_at_4):
    conn = db.connect(database_at_4)
    db.migrate(conn)
    with conn:
        conn.execute(
            "INSERT INTO recipes (origin, prompt, title, complexity, model, parse_version)"
            " VALUES ('created', 'something with squash', 'Squash stew', 2, 'claude-haiku-4-5', 2)"
        )
        conn.execute(
            "INSERT INTO claude_usage (purpose, succeeded, model, calls, input_tokens, output_tokens,"
            " cache_creation_input_tokens, cache_read_input_tokens) VALUES ('create', 1, 'm', 1, 1, 1, 0, 0)"
        )
        conn.execute("INSERT INTO import_reports (kind, comment) VALUES ('flagged', 'no url on this one')")
    assert conn.execute("SELECT count(*) FROM recipes WHERE origin = 'created'").fetchone()[0] == 1
    conn.close()


def test_migrating_twice_changes_nothing(database_at_4):
    conn = db.connect(database_at_4)
    db.migrate(conn)
    after_first = counts(conn)
    db.migrate(conn)
    assert counts(conn) == after_first
    conn.close()
