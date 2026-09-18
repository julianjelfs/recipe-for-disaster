import { getFacets, orErrorPage, searchRecipes } from '$lib/api';
import type { PageLoad } from './$types';

export const load: PageLoad = async ({ url, fetch }) => {
	const [recipes, facets] = await orErrorPage(Promise.all([searchRecipes(url.searchParams, {}, fetch), getFacets(fetch)]));
	return { page: recipes, facets };
};
