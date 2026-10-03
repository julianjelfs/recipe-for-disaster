import { describe, expect, it } from 'vitest';
import type { Recipe } from './api';
import { savedAgo, searchOffline, summarise } from './offline';

// The same three recipes as library() in backend/tests/test_library.py, so the offline search can be
// held to the same expectations as the server's.
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
	return searchOffline(recipes, new URLSearchParams(params)).recipes.map((r) => r.id);
}

describe('searchOffline', () => {
	it('needs every listed ingredient', () => {
		expect(ids(library, { has: 'leek,bacon' })).toEqual([pie.id]);
		expect(ids(library, { has: 'leek' }).sort()).toEqual([pie.id, soup.id]);
		expect(ids(library, { has: 'leek,bacon,potato' })).toEqual([]);
	});

	it('matches ingredients singular or plural, and only as whole words', () => {
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

	it('forgives word endings as the server stemmer does', () => {
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

	it('filters and sorts as the server does', () => {
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

	it('pages through every match once, with total counting them all', () => {
		const whole = ids(library);
		const paged = [0, 1, 2, 3].flatMap((offset) => ids(library, { offset: String(offset), limit: '1' }));
		expect(paged).toEqual(whole);
		expect(searchOffline(library, new URLSearchParams({ limit: '1', offset: '1' })).total).toBe(3);
	});

	it('returns summaries shaped like the server list', () => {
		expect(searchOffline([soup], new URLSearchParams()).recipes).toEqual([summarise(soup)]);
		expect(Object.keys(summarise(soup)).sort()).toEqual(
			['complexity', 'course', 'created_at', 'cuisine', 'diet', 'id', 'image_url', 'origin', 'source_domain', 'title', 'total_minutes'].sort()
		);
	});
});

describe('savedAgo', () => {
	const now = new Date('2026-10-03T12:00:00Z');
	it.each([
		['2026-10-03T11:59:45Z', 'just now'],
		['2026-10-03T11:59:00Z', '1 minute ago'],
		['2026-10-03T11:20:00Z', '40 minutes ago'],
		['2026-10-03T09:00:00Z', '3 hours ago'],
		['2026-10-02T10:00:00Z', 'yesterday'],
		['2026-09-28T12:00:00Z', '5 days ago']
	])('%s is %s', (savedAt, expected) => {
		expect(savedAgo(savedAt, now)).toBe(expected);
	});
});
