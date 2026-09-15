import { describe, expect, it } from 'vitest';
import { formatClock, nextStep, previousStep, remainingMs, stepFromParam } from './cook';

describe('step navigation', () => {
	it('invariant 9: next on the last step stays on the last step', () => {
		expect(nextStep(3, 5)).toBe(4);
		expect(nextStep(4, 5)).toBe(4);
		expect(nextStep(0, 1)).toBe(0);
	});

	it('invariant 9: back on the first step stays on the first step', () => {
		expect(previousStep(2)).toBe(1);
		expect(previousStep(0)).toBe(0);
	});

	it('invariant 9: pressing either way many times never leaves the steps', () => {
		let index = 0;
		for (let press = 0; press < 20; press++) {
			index = nextStep(index, 7);
			expect(index).toBeGreaterThanOrEqual(0);
			expect(index).toBeLessThan(7);
		}
		expect(index).toBe(6);
		for (let press = 0; press < 20; press++) {
			index = previousStep(index);
			expect(index).toBeGreaterThanOrEqual(0);
		}
		expect(index).toBe(0);
	});

	it('reads the step from the URL, 1-based and clamped', () => {
		expect(stepFromParam('3', 5)).toBe(2);
		expect(stepFromParam('99', 5)).toBe(4);
		expect(stepFromParam('0', 5)).toBe(0);
		expect(stepFromParam('2.5', 5)).toBe(0);
		expect(stepFromParam(null, 5)).toBe(0);
	});
});

describe('timers', () => {
	const timer = { id: 1, label: 'Step 3', stepNumber: 3, endsAt: 1_000_000 };

	it('counts down to zero and stops there', () => {
		expect(remainingMs(timer, 940_000)).toBe(60_000);
		expect(remainingMs(timer, 1_000_000)).toBe(0);
		expect(remainingMs(timer, 2_000_000)).toBe(0);
	});

	it('formats the clock, rounding up to the next second', () => {
		expect(formatClock(1_200_000)).toBe('20:00');
		expect(formatClock(4_500_000)).toBe('1:15:00');
		expect(formatClock(59_001)).toBe('1:00');
		expect(formatClock(0)).toBe('0:00');
	});
});
