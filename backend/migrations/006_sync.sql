-- Search moves to the browser, which keeps its own copy of the library and asks GET /api/sync for
-- what changed since the revision it last saw. So the full-text index goes, and every write now
-- leaves a trace the sync can find.
--
-- library_revision holds one counter. Every change to a recipe, its ingredients, steps or tags
-- takes the next value and stamps it on the recipe, and every deletion leaves the deleted id with
-- its revision in deleted_recipes. Triggers do the stamping, so no write path can forget it.
-- A table rebuild in a later migration drops these triggers with it: such a migration must create
-- them again. It also bumps user_version, which tells every device to fetch the library afresh.

DROP TABLE recipe_search;

CREATE TABLE library_revision (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    revision INTEGER NOT NULL
);

ALTER TABLE recipes ADD COLUMN revision INTEGER NOT NULL DEFAULT 0;

-- Existing recipes count as written in id order. No device has a copy yet, so any order would do.
UPDATE recipes SET revision = id;
INSERT INTO library_revision (id, revision) VALUES (1, coalesce((SELECT max(id) FROM recipes), 0));

CREATE TABLE deleted_recipes (
    id INTEGER PRIMARY KEY,
    revision INTEGER NOT NULL
);
CREATE INDEX recipes_revision ON recipes(revision);
CREATE INDEX deleted_recipes_revision ON deleted_recipes(revision);

-- A new recipe takes the next revision. SQLite reuses the highest id once it has been deleted, so
-- a new recipe may have a deleted one's id: it is not deleted any more.
CREATE TRIGGER recipes_revision_insert AFTER INSERT ON recipes
BEGIN
    UPDATE library_revision SET revision = revision + 1;
    UPDATE recipes SET revision = (SELECT revision FROM library_revision) WHERE id = NEW.id;
    DELETE FROM deleted_recipes WHERE id = NEW.id;
END;

-- Any update that doesn't itself set the revision takes the next one. The WHEN stops the trigger's
-- own UPDATE from firing it again.
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

-- A change to a recipe's parts is a change to the recipe: touch it so the update trigger stamps it.
-- After a recipe is deleted its parts go by cascade, and these find no recipe to touch.
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
