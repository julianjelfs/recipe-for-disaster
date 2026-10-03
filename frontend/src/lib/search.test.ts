import { describe, expect, it } from 'vitest';
import type { Recipe } from './api';
import { facets, search, summarise } from './search';

// Three recipes with a little overlap: two with leeks, two with bacon, one vegetarian.
let nextId = 1;
type Overrides = Partial<Omit<Recipe, 'ingredients' | 'steps'>> & { ingredients: [string, string][]; steps: string[] };

function recipe(overrides: Overrides): Recipe {
	const id = nextId++;
	return {
		id,
		source_url: null,
		source_domain: null,
		origin: 'created',
		prompt: 'x',
		title: 'Untitled',
		image_url: null,
		servings: 4,
		prep_minutes: null,
		cook_minutes: null,
		total_minutes: null,
		complexity: 2,
		cuisine: null,
		course: null,
		diet: [],
		equipment: [],
		techniques: [],
		tags: [],
		notes: '',
		model: 'm',
		parse_version: 2,
		created_at: '2026-10-01 12:00:00',
		updated_at: '2026-10-01 12:00:00',
		...overrides,
		ingredients: overrides.ingredients.map(([name, canonical], position) => ({
			id: id * 100 + position,
			position,
			group_name: null,
			quantity: 1,
			quantity_max: null,
			unit: null,
			name,
			canonical_name: canonical,
			preparation: null,
			optional: false
		})),
		steps: overrides.steps.map((text, position) => ({ id: id * 100 + position, position, text, timer_seconds: null, ingredient_ids: [] }))
	};
}

const pie = recipe({
	title: 'Leek and bacon pie',
	total_minutes: 90,
	complexity: 3,
	course: 'main',
	cuisine: 'British',
	ingredients: [
		['leeks', 'leek'],
		['smoked streaky bacon', 'bacon']
	],
	steps: ['Fry the bacon, then add the leeks.']
});
const soup = recipe({
	title: 'Leek and potato soup',
	total_minutes: 40,
	complexity: 1,
	course: 'starter',
	cuisine: 'French',
	diet: ['vegetarian'],
	ingredients: [
		['leeks', 'leek'],
		['floury potatoes', 'potato']
	],
	steps: ['Simmer the leeks and potatoes in stock until soft.']
});
const sandwich = recipe({
	title: 'Bacon sandwich',
	complexity: 1,
	course: 'breakfast',
	ingredients: [
		['back bacon', 'bacon'],
		['white bread', 'bread']
	],
	steps: ['Grill the bacon and put it between the bread.']
});
const thighs = recipe({ title: 'Roast thighs', ingredients: [['boneless chicken thighs', 'chicken thigh']], steps: ['Roast.'] });
const library = [pie, soup, sandwich];

function ids(recipes: Recipe[], params: Record<string, string> = {}): number[] {
	return search(recipes, new URLSearchParams(params)).recipes.map((r) => r.id);
}

describe('search', () => {
	it('invariant 7: needs an ingredient matching every one listed', () => {
		expect(ids(library, { has: 'leek,bacon' })).toEqual([pie.id]);
		expect(ids(library, { has: 'leek' }).sort()).toEqual([pie.id, soup.id]);
		expect(ids(library, { has: 'leek,bacon,potato' })).toEqual([]);
	});

	it('invariant 7: matches ingredients singular or plural, and only as whole words', () => {
		const all = [...library, thighs];
		expect(ids(all, { has: 'Leeks' }).sort()).toEqual([pie.id, soup.id]);
		expect(ids(all, { has: 'potatoes' })).toEqual([soup.id]);
		expect(ids(all, { has: 'chicken' })).toEqual([thighs.id]);
		expect(ids(all, { has: 'chicken thighs' })).toEqual([thighs.id]);
		expect(ids(all, { has: 'bac' })).toEqual([]);
	});

	it('searches titles, ingredients and steps, every word as a prefix', () => {
		expect(ids(library, { q: 'pie' })).toEqual([pie.id]);
		expect(ids(library, { q: 'simmer stock' })).toEqual([soup.id]);
		expect(ids(library, { q: 'floury' })).toEqual([soup.id]);
		expect(ids(library, { q: 'lee' }).sort()).toEqual([pie.id, soup.id]);
		expect(ids(library, { q: 'lasagne' })).toEqual([]);
	});

	it('forgives word endings, as a stemmer would', () => {
		const bread = recipe({ title: 'Baked bread', ingredients: [['flour', 'flour']], steps: ['Chop nothing. Roast nothing.'] });
		expect(ids([bread], { q: 'baking' })).toEqual([bread.id]);
		expect(ids([bread], { q: 'chopped' })).toEqual([bread.id]);
		expect(ids([bread], { q: 'roasting' })).toEqual([bread.id]);
		expect(ids([bread], { q: 'boiled' })).toEqual([]);
	});

	it('ranks a title match above a match in the steps', () => {
		// Made first, so a lower id would win a tie: only the ranking puts the toastie ahead.
		const toast = recipe({ title: 'Cheese on toast', ingredients: [['bread', 'bread']], steps: ['Grill until bubbling.'] });
		const toastie = recipe({ title: 'Grilled cheese toastie', ingredients: [['bread', 'bread']], steps: ['Fry.'] });
		expect(ids([toast, toastie], { q: 'grill' })).toEqual([toastie.id, toast.id]);
	});

	it('filters and sorts', () => {
		expect(ids(library, { max_total: '60' })).toEqual([soup.id]);
		expect(ids(library, { max_complexity: '1' }).sort()).toEqual([soup.id, sandwich.id]);
		expect(ids(library, { course: 'breakfast' })).toEqual([sandwich.id]);
		expect(ids(library, { cuisine: 'french' })).toEqual([soup.id]);
		expect(ids(library, { tag: 'Vegetarian' })).toEqual([soup.id]);
		expect(ids(library)).toEqual([sandwich.id, soup.id, pie.id]);
		expect(ids(library, { sort: 'title' })).toEqual([sandwich.id, pie.id, soup.id]);
		expect(ids(library, { sort: 'quickest' })).toEqual([soup.id, pie.id, sandwich.id]);
		expect(ids(library, { sort: 'simplest' })).toEqual([soup.id, sandwich.id, pie.id]);
	});

	// Recipes that tie on time, complexity and title, so only the tiebreak orders them.
	const shelf = Array.from({ length: 11 }, (_, n) =>
		recipe({
			title: n % 2 ? 'Stew' : `Stew ${n % 3}`,
			total_minutes: n % 3 ? 30 : null,
			complexity: 2,
			ingredients: [['onion', 'onion']],
			steps: ['Simmer the stew.']
		})
	);

	it.each(['', 'newest', 'title', 'quickest', 'simplest', 'relevance'])(
		'invariant 25: sort "%s" puts the same library in the same order, however it arrives',
		(sort) => {
			const params: Record<string, string> = sort ? { q: 'stew', sort } : { q: 'stew' };
			const reversed = [...shelf].reverse();
			const shuffled = [...shelf.filter((_, i) => i % 2), ...shelf.filter((_, i) => !(i % 2))];
			expect(ids(reversed, params)).toEqual(ids(shelf, params));
			expect(ids(shuffled, params)).toEqual(ids(shelf, params));
			expect(new Set(ids(shelf, params)).size).toBe(11);
		}
	);

	it('invariant 26: total counts every recipe matching the search and filters', () => {
		const everything = [...library, ...shelf];
		expect(search(everything, new URLSearchParams()).total).toBe(14);
		expect(search(everything, new URLSearchParams({ has: 'leek' })).total).toBe(2);
		const stews = search(everything, new URLSearchParams({ q: 'stew' }));
		expect(stews.total).toBe(11);
		expect(stews.recipes).toHaveLength(11);
	});

	it('returns summaries shaped like the list the home page shows', () => {
		expect(search([soup], new URLSearchParams()).recipes).toEqual([summarise(soup)]);
		expect(Object.keys(summarise(soup)).sort()).toEqual(
			['complexity', 'course', 'created_at', 'cuisine', 'diet', 'id', 'image_url', 'origin', 'source_domain', 'title', 'total_minutes'].sort()
		);
	});
});

describe('facets', () => {
	it('counts recipes, not mentions', () => {
		const twice = recipe({ title: 'Leek gratin', ingredients: [['leeks', 'leek'], ['more leeks', 'leek']], steps: ['Bake.'] });
		const result = facets([...library, twice]);
		expect(result.total).toBe(4);
		expect(result.ingredients).toEqual([
			{ value: 'leek', count: 3 },
			{ value: 'bacon', count: 2 },
			{ value: 'bread', count: 1 },
			{ value: 'potato', count: 1 }
		]);
		expect(result.courses.map((c) => c.value).sort()).toEqual(['breakfast', 'main', 'starter']);
		expect(result.diet).toEqual([{ value: 'vegetarian', count: 1 }]);
	});

	it('counts a cuisine together whatever its case, under the spelling seen first', () => {
		const french = recipe({ title: 'Gratin', cuisine: 'french', ingredients: [['potato', 'potato']], steps: ['Bake.'] });
		expect(facets([soup, french]).cuisines).toEqual([{ value: 'French', count: 2 }]);
	});
});
