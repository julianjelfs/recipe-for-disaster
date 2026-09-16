-- Recipes can now be invented from a prompt as well as imported from a URL, so source_url has to
-- become optional. SQLite can't drop NOT NULL or widen a CHECK in place, so these three tables are
-- rebuilt. app/db.py turns foreign keys off around this file: without that, dropping recipes would
-- cascade to every ingredient, step and tag.

CREATE TABLE recipes_new (
    id INTEGER PRIMARY KEY,
    source_url TEXT UNIQUE,
    source_domain TEXT,
    origin TEXT NOT NULL DEFAULT 'imported' CHECK (origin IN ('imported', 'created')),
    prompt TEXT,
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
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    -- An imported recipe comes from a URL, a created one from a prompt. Never both, never neither.
    CHECK (
        (origin = 'imported' AND source_url IS NOT NULL AND prompt IS NULL)
        OR (origin = 'created' AND source_url IS NULL AND prompt IS NOT NULL)
    )
);

INSERT INTO recipes_new (
    id, source_url, source_domain, origin, prompt, title, image_url, servings,
    prep_minutes, cook_minutes, total_minutes, complexity, cuisine, course, notes,
    raw_extract, raw_text, model, parse_version, created_at, updated_at
)
SELECT
    id, source_url, source_domain, 'imported', NULL, title, image_url, servings,
    prep_minutes, cook_minutes, total_minutes, complexity, cuisine, course, notes,
    raw_extract, raw_text, model, parse_version, created_at, updated_at
FROM recipes;

DROP TABLE recipes;
ALTER TABLE recipes_new RENAME TO recipes;

-- A creation has no URL, and 'create' is a new purpose.
CREATE TABLE claude_usage_new (
    id INTEGER PRIMARY KEY,
    purpose TEXT NOT NULL CHECK (purpose IN ('import', 'renormalise', 'create')),
    source_url TEXT,
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

INSERT INTO claude_usage_new (
    id, purpose, source_url, recipe_id, succeeded, model, calls, input_tokens, output_tokens,
    cache_creation_input_tokens, cache_read_input_tokens, cost_usd, created_at
)
SELECT
    id, purpose, source_url, recipe_id, succeeded, model, calls, input_tokens, output_tokens,
    cache_creation_input_tokens, cache_read_input_tokens, cost_usd, created_at
FROM claude_usage;

DROP TABLE claude_usage;
ALTER TABLE claude_usage_new RENAME TO claude_usage;
CREATE INDEX claude_usage_created ON claude_usage(created_at);

-- Flagging a created recipe stores its (absent) URL, so this can't stay NOT NULL.
CREATE TABLE import_reports_new (
    id INTEGER PRIMARY KEY,
    kind TEXT NOT NULL CHECK (kind IN ('flagged', 'failed')),
    source_url TEXT,
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

INSERT INTO import_reports_new (
    id, kind, source_url, recipe_id, comment, error, recipe_snapshot, raw_extract, raw_text,
    model, parse_version, created_at, resolved_at, resolution
)
SELECT
    id, kind, source_url, recipe_id, comment, error, recipe_snapshot, raw_extract, raw_text,
    model, parse_version, created_at, resolved_at, resolution
FROM import_reports;

DROP TABLE import_reports;
ALTER TABLE import_reports_new RENAME TO import_reports;
CREATE INDEX import_reports_resolved ON import_reports(resolved_at);
