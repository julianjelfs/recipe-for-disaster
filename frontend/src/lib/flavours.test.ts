import { describe, expect, it } from 'vitest';
import { FLAVOURS, MAX_BRIEF, briefRoom, composeBrief } from './flavours';

const berbere = FLAVOURS.find((flavour) => flavour.key === 'berbere')!;

describe('composeBrief', () => {
	it('is empty with nothing typed and no base, even when vegetarian', () => {
		expect(composeBrief('  ', undefined, true)).toBe('');
	});

	it('makes a brief from a base alone, naming its pantry', () => {
		const brief = composeBrief('', berbere, false);
		expect(brief).toContain('Ethiopian');
		expect(brief).toContain(berbere.pantry);
	});

	it('keeps what was typed first and adds vegetarian and the base after it', () => {
		expect(composeBrief(' a quick lunch ', berbere, true).split('\n')).toEqual([
			'a quick lunch',
			'Vegetarian.',
			`Flavour base: Ethiopian, berbere. Build it around ${berbere.pantry}.`
		]);
	});

	it('leaves the typed brief alone when no base is picked and vegetarian is off', () => {
		expect(composeBrief('soup', undefined, false)).toBe('soup');
	});
});

describe('briefRoom', () => {
	it('never lets a full textarea push the brief over the API limit', () => {
		for (const flavour of [undefined, ...FLAVOURS]) {
			for (const vegetarian of [false, true]) {
				const typed = 'x'.repeat(briefRoom(flavour, vegetarian));
				expect(composeBrief(typed, flavour, vegetarian).length).toBeLessThanOrEqual(MAX_BRIEF);
			}
		}
	});

	it('is the whole limit when nothing is added', () => {
		expect(briefRoom(undefined, false)).toBe(MAX_BRIEF);
	});
});

describe('FLAVOURS', () => {
	it('keeps every pantry vegetarian', () => {
		const meaty = /fish sauce|(?<!mushroom )oyster sauce|bonito|anchov|shrimp|prawn|chicken|beef|pork|lard/i;
		for (const flavour of FLAVOURS) {
			expect(flavour.pantry, flavour.name).not.toMatch(meaty);
		}
	});

	it('has unique keys', () => {
		expect(new Set(FLAVOURS.map((flavour) => flavour.key)).size).toBe(FLAVOURS.length);
	});
});
