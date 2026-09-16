import { describe, expect, it } from 'vitest';
import type { FacetValue } from './api';
import { suggestIngredients } from './suggest';

// As the API returns them: most-used first.
const ingredients: FacetValue[] = [
	{ value: 'onion', count: 9 },
	{ value: 'garlic', count: 8 },
	{ value: 'tomato', count: 5 },
	{ value: 'plum tomato', count: 3 },
	{ value: 'tomato purée', count: 3 },
	{ value: 'potato', count: 2 },
	{ value: 'leek', count: 2 },
	{ value: 'butter', count: 2 },
	{ value: 'egg', count: 1 },
	{ value: 'chicken thigh', count: 1 }
];

describe('suggestIngredients', () => {
	it('offers names, never counts', () => {
		for (const suggestion of suggestIngredients(ingredients, 'to', [])) {
			expect(suggestion).not.toMatch(/\d/);
		}
	});

	it('puts names starting with what you typed first', () => {
		expect(suggestIngredients(ingredients, 'to', [])).toEqual(['tomato', 'tomato purée', 'plum tomato', 'potato']);
	});

	it('leaves out ingredients already chosen', () => {
		expect(suggestIngredients(ingredients, 'to', ['tomato'])).toEqual(['tomato purée', 'plum tomato', 'potato']);
		expect(suggestIngredients(ingredients, 'leek', ['Leek'])).toEqual([]);
	});

	it('ignores case and surrounding space', () => {
		expect(suggestIngredients(ingredients, '  GARLIC ', [])).toEqual(['garlic']);
	});

	it('offers the most-used ingredients before anything is typed', () => {
		expect(suggestIngredients(ingredients, '', [], 3)).toEqual(['onion', 'garlic', 'tomato']);
	});

	it('returns nothing when there is no match', () => {
		expect(suggestIngredients(ingredients, 'saffron', [])).toEqual([]);
	});

	it('never returns more than the limit', () => {
		expect(suggestIngredients(ingredients, '', [], 4)).toHaveLength(4);
		expect(suggestIngredients(ingredients, 'o', [], 2)).toHaveLength(2);
	});
});
