/** URL params that narrow the list. Search text and sort order are left out: they sit outside the filters panel. */
const SINGLE = ['max_total', 'max_complexity', 'course', 'cuisine'];
const MULTI = ['has', 'tag'];

/** How many filters are applied, counting each ingredient and tag on its own. */
export function activeFilterCount(params: URLSearchParams): number {
	const singles = SINGLE.filter((name) => params.get(name)).length;
	const multis = MULTI.reduce((sum, name) => sum + (params.get(name) ?? '').split(',').filter(Boolean).length, 0);
	return singles + multis;
}
