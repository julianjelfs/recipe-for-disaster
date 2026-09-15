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
    -- Keep in step with app.schemas.Unit.
    unit TEXT CHECK (unit IN (
        'g', 'kg', 'ml', 'l', 'tsp', 'tbsp',
        'pinch', 'dash', 'clove', 'tin', 'bunch', 'handful', 'sprig', 'slice', 'piece'
    )),
    name TEXT NOT NULL,
    canonical_name TEXT NOT NULL,
    preparation TEXT,
    optional INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX ingredients_recipe ON ingredients(recipe_id);
CREATE INDEX ingredients_canonical ON ingredients(canonical_name);

CREATE TABLE steps (
    id INTEGER PRIMARY KEY,
    recipe_id INTEGER NOT NULL REFERENCES recipes(id) ON DELETE CASCADE,
    position INTEGER NOT NULL,
    text TEXT NOT NULL,
    timer_seconds INTEGER
);
CREATE INDEX steps_recipe ON steps(recipe_id);

CREATE TABLE step_ingredients (
    step_id INTEGER NOT NULL REFERENCES steps(id) ON DELETE CASCADE,
    ingredient_id INTEGER NOT NULL REFERENCES ingredients(id) ON DELETE CASCADE,
    PRIMARY KEY (step_id, ingredient_id)
);

CREATE TRIGGER step_ingredients_same_recipe
BEFORE INSERT ON step_ingredients
WHEN (SELECT recipe_id FROM steps WHERE id = NEW.step_id)
     IS NOT (SELECT recipe_id FROM ingredients WHERE id = NEW.ingredient_id)
BEGIN
    SELECT RAISE(ABORT, 'step and ingredient belong to different recipes');
END;

CREATE TABLE tags (
    recipe_id INTEGER NOT NULL REFERENCES recipes(id) ON DELETE CASCADE,
    kind TEXT NOT NULL CHECK (kind IN ('diet', 'equipment', 'technique', 'custom')),
    value TEXT NOT NULL,
    PRIMARY KEY (recipe_id, kind, value)
);
CREATE INDEX tags_value ON tags(kind, value);
