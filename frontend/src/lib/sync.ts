import type { Recipe } from './api';

/** GET /api/sync: what changed in the library since a device's copy was taken. */
export interface SyncResponse {
	epoch: number;
	revision: number;
	/** `changed` is the whole library: drop everything else. */
	full: boolean;
	changed: Recipe[];
	deleted: number[];
}

/** A device's copy of the library, and the point on the server it was taken at. */
export interface LibraryCopy {
	/** null before the first sync, which asks for everything. */
	epoch: number | null;
	revision: number;
	recipes: Map<number, Recipe>;
}

export const EMPTY_COPY: LibraryCopy = { epoch: null, revision: 0, recipes: new Map() };

/** The query string for the next sync from this copy. */
export function syncQuery(copy: LibraryCopy): string {
	const params = new URLSearchParams({ since: String(copy.revision) });
	if (copy.epoch !== null) params.set('epoch', String(copy.epoch));
	return params.toString();
}

/**
 * The copy brought up to date with a sync response. Never changes the copy it's given.
 *
 * Deletions apply before changes: the server reuses a deleted recipe's id for the next new one, and
 * the new recipe must survive.
 */
export function applySync(copy: LibraryCopy, response: SyncResponse): LibraryCopy {
	const recipes = response.full ? new Map<number, Recipe>() : new Map(copy.recipes);
	for (const id of response.deleted) recipes.delete(id);
	for (const recipe of response.changed) recipes.set(recipe.id, recipe);
	return { epoch: response.epoch, revision: response.revision, recipes };
}

/** Whether a sync response changes anything a page shows. */
export function changesAnything(response: SyncResponse): boolean {
	return response.full || response.changed.length > 0 || response.deleted.length > 0;
}
