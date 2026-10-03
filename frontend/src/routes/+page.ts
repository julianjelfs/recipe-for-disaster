import { ready, recipes } from '$lib/library.svelte';
import { facets, search } from '$lib/search';
import type { PageLoad } from './$types';

export const load: PageLoad = async ({ url }) => {
	await ready();
	const library = recipes();
	return { results: search(library, url.searchParams), facets: facets(library) };
};
