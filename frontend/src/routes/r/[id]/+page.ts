import { getRecipe, orErrorPage } from '$lib/api';
import type { PageLoad } from './$types';

export const load: PageLoad = async ({ params, fetch }) => {
	return { recipe: await orErrorPage(getRecipe(params.id, fetch)) };
};
