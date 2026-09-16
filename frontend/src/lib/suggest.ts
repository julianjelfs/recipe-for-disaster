import type { FacetValue } from './api';

/**
 * Ingredient suggestions for what has been typed so far. Names only: the counts belong to the
 * facet list, not to a cook picking "leek" from a menu.
 *
 * Ingredients already chosen drop out. Names starting with the query come before names that
 * merely contain it, so typing "to" offers "tomato" before "plum tomato". With nothing typed,
 * the list is whatever the API gave us, which is ordered by how many recipes use it.
 */
export function suggestIngredients(
	ingredients: FacetValue[],
	query: string,
	chosen: string[],
	limit = 8
): string[] {
	const wanted = query.trim().toLowerCase();
	const taken = new Set(chosen.map((name) => name.toLowerCase()));
	const available = ingredients.map((item) => item.value).filter((name) => !taken.has(name.toLowerCase()));
	if (!wanted) return available.slice(0, limit);

	const starts = available.filter((name) => name.toLowerCase().startsWith(wanted));
	const contains = available.filter(
		(name) => !name.toLowerCase().startsWith(wanted) && name.toLowerCase().includes(wanted)
	);
	return [...starts, ...contains].slice(0, limit);
}
