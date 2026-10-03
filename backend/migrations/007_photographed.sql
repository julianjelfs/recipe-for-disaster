-- Recipes can now be read from photos of a recipe book, as well as imported from a URL or created
-- from a brief. A photographed recipe has neither a URL nor a brief: its source is the photos,
-- kept in recipe_photos so "try again" can read them afresh. SQLite can't widen a CHECK in place,
-- so recipes and claude_usage are rebuilt, as in 005.
--
-- Rebuilding recipes drops the sync triggers that 006 put on it, and the triggers on its child
-- tables refer to it by name, which a rename refuses while the table is missing. So every sync
-- trigger is dropped first and created again at the end, exactly as 006 defines them.

DROP TRIGGER recipes_revision_insert;
DROP TRIGGER recipes_revision_update;
DROP TRIGGER recipes_revision_delete;
DROP TRIGGER ingredients_revision_insert;
DROP TRIGGER ingredients_revision_update;
DROP TRIGGER ingredients_revision_delete;
DROP TRIGGER steps_revision_insert;
DROP TRIGGER steps_revision_update;
DROP TRIGGER steps_revision_delete;
DROP TRIGGER tags_revision_insert;
DROP TRIGGER tags_revision_update;
DROP TRIGGER tags_revision_delete;
DROP TRIGGER step_ingredients_revision_insert;
DROP TRIGGER step_ingredients_revision_delete;

CREATE TABLE recipes_new (
    id INTEGER PRIMARY KEY,
    source_url TEXT UNIQUE,
    source_domain TEXT,
    origin TEXT NOT NULL DEFAULT 'imported' CHECK (origin IN ('imported', 'created', 'photographed')),
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
    revision INTEGER NOT NULL DEFAULT 0,
    -- Imported from a URL, created from a brief, or photographed (its photos are in recipe_photos).
    CHECK (
        (origin = 'imported' AND source_url IS NOT NULL AND prompt IS NULL)
        OR (origin = 'created' AND source_url IS NULL AND prompt IS NOT NULL)
        OR (origin = 'photographed' AND source_url IS NULL AND prompt IS NULL)
    )
);

INSERT INTO recipes_new (
    id, source_url, source_domain, origin, prompt, title, image_url, servings,
    prep_minutes, cook_minutes, total_minutes, complexity, cuisine, course, notes,
    raw_extract, raw_text, model, parse_version, created_at, updated_at, revision
)
SELECT
    id, source_url, source_domain, origin, prompt, title, image_url, servings,
    prep_minutes, cook_minutes, total_minutes, complexity, cuisine, course, notes,
    raw_extract, raw_text, model, parse_version, created_at, updated_at, revision
FROM recipes;

DROP TABLE recipes;
ALTER TABLE recipes_new RENAME TO recipes;
CREATE INDEX recipes_revision ON recipes(revision);

-- AUTOINCREMENT so an id is never reused: GET /api/photos/{id} is cached forever on the phone.
CREATE TABLE recipe_photos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    recipe_id INTEGER NOT NULL REFERENCES recipes(id) ON DELETE CASCADE,
    position INTEGER NOT NULL,
    media_type TEXT NOT NULL CHECK (media_type IN ('image/jpeg', 'image/png', 'image/webp')),
    data BLOB NOT NULL
);
CREATE INDEX recipe_photos_recipe ON recipe_photos(recipe_id);

CREATE TABLE claude_usage_new (
    id INTEGER PRIMARY KEY,
    purpose TEXT NOT NULL CHECK (purpose IN ('import', 'renormalise', 'create', 'photo')),
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

-- The sync triggers, as 006 defines them.
CREATE TRIGGER recipes_revision_insert AFTER INSERT ON recipes
BEGIN
    UPDATE library_revision SET revision = revision + 1;
    UPDATE recipes SET revision = (SELECT revision FROM library_revision) WHERE id = NEW.id;
    DELETE FROM deleted_recipes WHERE id = NEW.id;
END;

CREATE TRIGGER recipes_revision_update AFTER UPDATE ON recipes
WHEN NEW.revision = OLD.revision
BEGIN
    UPDATE library_revision SET revision = revision + 1;
    UPDATE recipes SET revision = (SELECT revision FROM library_revision) WHERE id = NEW.id;
END;

CREATE TRIGGER recipes_revision_delete AFTER DELETE ON recipes
BEGIN
    UPDATE library_revision SET revision = revision + 1;
    INSERT OR REPLACE INTO deleted_recipes (id, revision) VALUES (OLD.id, (SELECT revision FROM library_revision));
END;

CREATE TRIGGER ingredients_revision_insert AFTER INSERT ON ingredients
BEGIN UPDATE recipes SET revision = revision WHERE id = NEW.recipe_id; END;
CREATE TRIGGER ingredients_revision_update AFTER UPDATE ON ingredients
BEGIN UPDATE recipes SET revision = revision WHERE id IN (OLD.recipe_id, NEW.recipe_id); END;
CREATE TRIGGER ingredients_revision_delete AFTER DELETE ON ingredients
BEGIN UPDATE recipes SET revision = revision WHERE id = OLD.recipe_id; END;

CREATE TRIGGER steps_revision_insert AFTER INSERT ON steps
BEGIN UPDATE recipes SET revision = revision WHERE id = NEW.recipe_id; END;
CREATE TRIGGER steps_revision_update AFTER UPDATE ON steps
BEGIN UPDATE recipes SET revision = revision WHERE id IN (OLD.recipe_id, NEW.recipe_id); END;
CREATE TRIGGER steps_revision_delete AFTER DELETE ON steps
BEGIN UPDATE recipes SET revision = revision WHERE id = OLD.recipe_id; END;

CREATE TRIGGER tags_revision_insert AFTER INSERT ON tags
BEGIN UPDATE recipes SET revision = revision WHERE id = NEW.recipe_id; END;
CREATE TRIGGER tags_revision_update AFTER UPDATE ON tags
BEGIN UPDATE recipes SET revision = revision WHERE id IN (OLD.recipe_id, NEW.recipe_id); END;
CREATE TRIGGER tags_revision_delete AFTER DELETE ON tags
BEGIN UPDATE recipes SET revision = revision WHERE id = OLD.recipe_id; END;

CREATE TRIGGER step_ingredients_revision_insert AFTER INSERT ON step_ingredients
BEGIN UPDATE recipes SET revision = revision WHERE id = (SELECT recipe_id FROM steps WHERE id = NEW.step_id); END;
CREATE TRIGGER step_ingredients_revision_delete AFTER DELETE ON step_ingredients
BEGIN UPDATE recipes SET revision = revision WHERE id = (SELECT recipe_id FROM steps WHERE id = OLD.step_id); END;
