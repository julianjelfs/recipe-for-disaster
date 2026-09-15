import { describe, expect, it } from 'vitest';
import { formatAmount, formatCount, formatTimer } from './format';

function ingredient(quantity: number | null, unit: string | null, name: string, quantity_max: number | null = null) {
	return { quantity, quantity_max, unit, name };
}

describe('formatAmount', () => {
	it.each([
		[ingredient(200, 'g', 'caster sugar'), '200g'],
		[ingredient(56.5, 'g', 'unsalted butter'), '57g'],
		[ingredient(337.5, 'g', 'plain flour'), '340g'],
		[ingredient(1.25, 'kg', 'beef mince'), '1.25kg'],
		[ingredient(1, 'g', 'ginger'), '1g'],
		[ingredient(0.5, 'tsp', 'salt'), '½ tsp'],
		[ingredient(1.5, 'tbsp', 'olive oil'), '1½ tbsp'],
		[ingredient(1, 'clove', 'garlic'), '1 clove'],
		[ingredient(2, 'clove', 'garlic'), '2 cloves'],
		[ingredient(0.5, 'bunch', 'fresh coriander'), '½ bunch'],
		[ingredient(2, 'bunch', 'spring onions'), '2 bunches'],
		[ingredient(4, null, 'large eggs'), '4'],
		[ingredient(5, null, 'stems choy sum', 6), '5-6'],
		// Report #2: stored as 1 piece of "5cm piece fresh ginger".
		[ingredient(1, 'piece', '5cm piece fresh ginger'), '1 ×'],
		[ingredient(1, null, '5cm piece fresh ginger'), '1 ×'],
		[ingredient(null, null, 'sea salt'), '']
	])('%o -> %s', (item, expected) => {
		expect(formatAmount(item)).toBe(expected);
	});
});

describe('formatCount', () => {
	it('uses fractions cooks read easily', () => {
		expect(formatCount(0.25)).toBe('¼');
		expect(formatCount(0.333)).toBe('⅓');
		expect(formatCount(2.75)).toBe('2¾');
		expect(formatCount(1.98)).toBe('2');
		expect(formatCount(2.2)).toBe('2.2');
	});
});

describe('formatTimer', () => {
	it('shows minutes when it can', () => {
		expect(formatTimer(1200)).toBe('20 min');
		expect(formatTimer(4500)).toBe('1 hr 15 min');
		expect(formatTimer(90)).toBe('90 sec');
	});
});
