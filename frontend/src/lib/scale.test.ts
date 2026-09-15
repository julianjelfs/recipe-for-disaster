import { describe, expect, it } from 'vitest';
import { parseScale, scaleAmount, servingsFor, stepScale } from './scale';

describe('scaleAmount', () => {
	it('invariant 8: multiplies every non-null quantity by k and leaves null quantities null', () => {
		const items = [
			{ quantity: 200, quantity_max: null },
			{ quantity: 5, quantity_max: 6 },
			{ quantity: null, quantity_max: null },
			{ quantity: 0.5, quantity_max: null }
		];
		for (const k of [0.25, 0.5, 1, 1.5, 2, 3.25]) {
			for (const item of items) {
				const scaled = scaleAmount(item, k);
				expect(scaled.quantity).toBe(item.quantity === null ? null : item.quantity * k);
				expect(scaled.quantity_max).toBe(item.quantity_max === null ? null : item.quantity_max * k);
			}
		}
	});

	it('keeps the other fields and leaves the original alone', () => {
		const flour = { quantity: 250, quantity_max: null, unit: 'g', name: 'plain flour' };
		expect(scaleAmount(flour, 2)).toEqual({ quantity: 500, quantity_max: null, unit: 'g', name: 'plain flour' });
		expect(flour.quantity).toBe(250);
	});
});

describe('stepScale', () => {
	it('moves one serving at a time when servings are known', () => {
		expect(stepScale(4, 1, 1)).toBe(1.25);
		expect(stepScale(4, 1.25, -1)).toBe(1);
		expect(stepScale(4, 0.25, -1)).toBe(0.25);
		expect(servingsFor(4, stepScale(4, 1, 1))).toBe(5);
	});

	it('moves by half the recipe when servings are unknown', () => {
		expect(stepScale(null, 1, 1)).toBe(1.5);
		expect(stepScale(null, 0.5, -1)).toBe(0.5);
	});
});

describe('parseScale', () => {
	it('falls back to 1 for missing or nonsense values', () => {
		expect(parseScale(null)).toBe(1);
		expect(parseScale('abc')).toBe(1);
		expect(parseScale('-2')).toBe(1);
		expect(parseScale('1000')).toBe(1);
		expect(parseScale('1.5')).toBe(1.5);
	});
});
