-- Full-text index with one row per recipe. app.store rewrites a recipe's row whenever the recipe changes.
CREATE VIRTUAL TABLE recipe_search USING fts5(
    recipe_id UNINDEXED,
    title,
    ingredients,
    steps,
    tags,
    notes,
    meta,
    tokenize = 'porter unicode61 remove_diacritics 2'
);

-- Index recipes imported before this migration. Same columns as app.store._INDEX_ROW.
INSERT INTO recipe_search (recipe_id, title, ingredients, steps, tags, notes, meta)
SELECT
    r.id,
    r.title,
    coalesce((SELECT group_concat(i.name || ' ' || i.canonical_name, ' ') FROM ingredients i WHERE i.recipe_id = r.id), ''),
    coalesce((SELECT group_concat(s.text, ' ') FROM steps s WHERE s.recipe_id = r.id), ''),
    coalesce((SELECT group_concat(t.value, ' ') FROM tags t WHERE t.recipe_id = r.id), ''),
    r.notes,
    coalesce(r.cuisine, '') || ' ' || coalesce(r.course, '')
FROM recipes r;
