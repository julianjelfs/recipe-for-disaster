import { describe, expect, it } from 'vitest';
import type { Recipe } from './api';
import { applySync, changesAnything, EMPTY_COPY, syncQuery, type LibraryCopy, type SyncResponse } from './sync';

function recipe(id: number, title: string): Recipe {
	return { id, title } as Recipe;
}

function copyOf(...recipes: Recipe[]): LibraryCopy {
	return { epoch: 6, revision: 10, recipes: new Map(recipes.map((r) => [r.id, r])) };
}

function response(overrides: Partial<SyncResponse>): SyncResponse {
	return { epoch: 6, revision: 11, full: false, changed: [], deleted: [], ...overrides };
}

const titles = (copy: LibraryCopy) => [...copy.recipes.values()].map((r) => `${r.id} ${r.title}`).sort();

describe('applySync', () => {
	it('invariant 31: adds and replaces changed recipes, and drops deleted ones', () => {
		const before = copyOf(recipe(1, 'Pie'), recipe(2, 'Soup'), recipe(3, 'Stew'));
		const after = applySync(before, response({ changed: [recipe(2, 'Leek soup'), recipe(4, 'Curry')], deleted: [3] }));
		expect(titles(after)).toEqual(['1 Pie', '2 Leek soup', '4 Curry']);
		expect(after.revision).toBe(11);
	});

	it('invariant 31: a reused id listed as deleted and changed keeps the new recipe', () => {
		const before = copyOf(recipe(1, 'Pie'), recipe(2, 'Soup'));
		const after = applySync(before, response({ changed: [recipe(2, 'Squash stew')], deleted: [2] }));
		expect(titles(after)).toEqual(['1 Pie', '2 Squash stew']);
	});

	it('invariant 31: a full response replaces everything the device held', () => {
		const before = copyOf(recipe(1, 'Pie'), recipe(2, 'Soup'));
		const after = applySync(before, response({ full: true, epoch: 7, revision: 3, changed: [recipe(5, 'Tart')] }));
		expect(titles(after)).toEqual(['5 Tart']);
		expect([after.epoch, after.revision]).toEqual([7, 3]);
	});

	it('never changes the copy it is given', () => {
		const before = copyOf(recipe(1, 'Pie'));
		applySync(before, response({ deleted: [1] }));
		expect(titles(before)).toEqual(['1 Pie']);
	});
});

describe('syncQuery', () => {
	it('asks for everything before the first sync', () => {
		expect(syncQuery(EMPTY_COPY)).toBe('since=0');
	});

	it('asks for what changed since the copy was taken', () => {
		expect(syncQuery(copyOf())).toBe('since=10&epoch=6');
	});
});

describe('changesAnything', () => {
	it('is false only for a sync that found nothing', () => {
		expect(changesAnything(response({}))).toBe(false);
		expect(changesAnything(response({ deleted: [1] }))).toBe(true);
		expect(changesAnything(response({ changed: [recipe(1, 'Pie')] }))).toBe(true);
		expect(changesAnything(response({ full: true }))).toBe(true);
	});
});
