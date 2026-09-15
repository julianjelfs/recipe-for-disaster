-- One row per import or re-read that called Claude, whether it worked or not, so spending can be tracked.
-- Cost is worked out when the row is written, at the prices in app/costs.py at that time.
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
CREATE INDEX claude_usage_created ON claude_usage(created_at);
