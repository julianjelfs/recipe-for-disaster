-- Bad imports to follow up on: recipes someone flagged, and imports that failed.
-- Each row keeps its own copy of the data involved, so it stays useful after the recipe changes.
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
CREATE INDEX import_reports_resolved ON import_reports(resolved_at);
