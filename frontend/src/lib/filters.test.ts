import { describe, expect, it } from 'vitest';
import { activeFilterCount } from './filters';

describe('activeFilterCount', () => {
	it.each([
		['', 0],
		['q=soup', 0],
		['sort=title', 0],
		['q=soup&sort=quickest', 0],
		['max_total=30', 1],
		['has=chicken', 1],
		['has=chicken,lemon', 2],
		['tag=vegan,quick&course=Main', 3],
		['has=&tag=', 0],
		['max_total=30&max_complexity=2&course=Main&cuisine=Thai&has=rice&tag=vegan&q=x&sort=title', 6]
	])('%s → %i', (query, expected) => {
		expect(activeFilterCount(new URLSearchParams(query))).toBe(expected);
	});
});
