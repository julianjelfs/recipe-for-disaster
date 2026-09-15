import { describe, expect, it } from 'vitest';
import type { Ingredient } from './api';
import { shoppingList } from './shopping';

let nextId = 1;
function ingredient(fields: Partial<Ingredient> & Pick<Ingredient, 'name' | 'canonical_name'>): Ingredient {
	return {
		id: nextId++,
		position: 0,
		group_name: null,
		quantity: null,
		quantity_max: null,
		unit: null,
		preparation: null,
		optional: false,
		...fields
	};
}

// The BBC Good Food chocolate cake, which uses butter, cocoa, milk and salt twice.
const cake = [
	ingredient({ name: 'unsalted butter', canonical_name: 'butter', quantity: 200, unit: 'g', group_name: 'For the cake' }),
	ingredient({ name: 'cocoa powder', canonical_name: 'cocoa powder', quantity: 2, unit: 'tbsp', group_name: 'For the cake' }),
	ingredient({ name: 'milk', canonical_name: 'milk', quantity: 2, unit: 'tbsp', group_name: 'For the cake' }),
	ingredient({ name: 'salt', canonical_name: 'salt', group_name: 'For the cake' }),
	ingredient({ name: 'large eggs', canonical_name: 'egg', quantity: 4 }),
	ingredient({ name: 'butter', canonical_name: 'butter', quantity: 200, unit: 'g', group_name: 'For the buttercream' }),
	ingredient({ name: 'cocoa powder', canonical_name: 'cocoa powder', quantity: 5, unit: 'tbsp', group_name: 'For the buttercream' }),
	ingredient({ name: 'milk', canonical_name: 'milk', quantity: 50, unit: 'ml', group_name: 'For the buttercream' }),
	ingredient({ name: 'salt', canonical_name: 'salt', group_name: 'For the buttercream' }),
	ingredient({ name: 'fresh red chillies', canonical_name: 'chilli', quantity: 1, quantity_max: 2 }),
	ingredient({ name: 'fresh red chillies', canonical_name: 'chilli', quantity: 1 })
];

describe('shoppingList', () => {
	it('invariant 19: includes every ingredient exactly once', () => {
		const ids = shoppingList(cake, 1).flatMap((item) => item.ingredientIds);
		expect(ids.toSorted((a, b) => a - b)).toEqual(cake.map((item) => item.id));
	});

	it('invariant 19: a merged line is the sum of the lines it replaces, at any scale', () => {
		for (const scale of [0.5, 1, 1.5, 3]) {
			const byName = new Map(shoppingList(cake, scale).map((item) => [`${item.name}|${item.unit}`, item]));
			expect(byName.get('butter|g')?.quantity).toBeCloseTo(400 * scale);
			expect(byName.get('cocoa powder|tbsp')?.quantity).toBeCloseTo(7 * scale);
		}
	});

	it('keeps lines apart when adding them up would be wrong', () => {
		const names = shoppingList(cake, 1).map((item) => [item.quantity ?? '-', item.unit, item.name].filter(Boolean).join(' '));
		expect(names).toEqual([
			'400 g butter',
			'7 tbsp cocoa powder',
			'2 tbsp milk',
			'- salt',
			'4 large eggs',
			'50 ml milk',
			'1 fresh red chillies',
			'1 fresh red chillies'
		]);
	});

	it('keys each line by its first ingredient so ticks survive changing the servings', () => {
		expect(shoppingList(cake, 1).map((item) => item.key)).toEqual(shoppingList(cake, 2).map((item) => item.key));
	});

	it('is only optional when every merged ingredient is', () => {
		const lemons = [
			ingredient({ name: 'lemon', canonical_name: 'lemon', quantity: 1, optional: true }),
			ingredient({ name: 'lemon', canonical_name: 'lemon', quantity: 1 })
		];
		expect(shoppingList(lemons, 1)).toMatchObject([{ quantity: 2, optional: false }]);
	});
});
