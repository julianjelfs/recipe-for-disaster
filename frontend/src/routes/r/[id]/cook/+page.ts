import { error } from '@sveltejs/kit';
import { find } from '$lib/library.svelte';
import type { PageLoad } from './$types';

export const load: PageLoad = async ({ params }) => {
	const recipe = await find(Number(params.id));
	if (!recipe) error(404, 'Recipe not found.');
	return { recipe };
};
