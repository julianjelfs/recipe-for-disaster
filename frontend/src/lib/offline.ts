// Types only: the service worker imports this file, and must not pull in api.ts and SvelteKit with it.
import type { Facets, Recipe, RecipePage, RecipeSummary } from './api';

// The API's default page size, used when a request doesn't say.
const DEFAULT_LIMIT = 48;

/**
 * The saved copy of the library that lets the app work away from the home network, where the Pi
 * can't be reached. The service worker keeps it fresh and answers the app's API calls from it.
 * Shape matches GET /api/offline.
 */
export interface OfflineCopy {
	recipes: Recipe[];
	facets: Facets;
}

/** Where the service worker keeps the copy. */
export const OFFLINE_CACHE = 'offline-copy';
export const OFFLINE_KEY = '/api/offline';
/**
 * When the Pi last confirmed the copy was current, as {checked_at}. Kept apart from the copy because
 * an unchanged library answers 304, and rewriting the whole copy to restamp it would waste the saving.
 */
export const CHECKED_KEY = '/api/offline/checked';

/** Rough English singular. Same rules as app.search.singular, so ingredient filters match the same way. */
export function singular(word: string): string {
	if (word.length > 3 && word.endsWith('ies')) return word.slice(0, -3) + 'y';
	if (word.length > 3 && word.endsWith('oes')) return word.slice(0, -2);
	if (word.length > 3 && word.endsWith('s') && !word.endsWith('ss')) return word.slice(0, -1);
	return word;
}

function words(text: string): string[] {
	return (
		text
			.normalize('NFKD')
			.replace(/\p{Diacritic}/gu, '')
			.toLowerCase()
			.match(/[\p{L}\p{N}_]+/gu) ?? []
	);
}

// The columns of the server's full-text index, with its bm25 weights.
function columns(recipe: Recipe): [number, string[]][] {
	return [
		[10, words(recipe.title)],
		[5, words(recipe.ingredients.map((i) => `${i.name} ${i.canonical_name}`).join(' '))],
		[1, words(recipe.steps.map((s) => s.text).join(' '))],
		[3, words([...recipe.diet, ...recipe.equipment, ...recipe.techniques, ...recipe.tags].join(' '))],
		[2, words(recipe.notes)],
		[3, words(`${recipe.cuisine ?? ''} ${recipe.course ?? ''}`)]
	];
}

/**
 * A light stand-in for the server's Porter stemmer, enough that "baking", "baked" and "bake" meet,
 * as do "roasting" and "roast", and "chopped" and "chop". Only for text search; ingredient filters use singular().
 */
function stem(word: string): string {
	let stripped = word.replace(/(ing|ed|es|e|s)$/, '');
	// "chopped" -> "chopp" -> "chop", as Porter does, but "rolled" keeps its double l.
	if (/([^aeiouylsz])\1$/.test(stripped)) stripped = stripped.slice(0, -1);
	return stripped.length >= 3 ? stripped : word;
}

// FTS5's bm25 constants.
const K1 = 1.2;
const B = 0.75;

/**
 * Text search scores for the recipes that match, higher first: FTS5's bm25, worked out over the
 * whole saved library as the server works it out over its index. Every word must match the start
 * of a word somewhere, as on the server, with common endings forgiven as its stemmer forgives them.
 */
function textScores(recipes: Recipe[], query: string[]): Map<number, number> {
	const docs = recipes.map((recipe) => {
		const cols = columns(recipe);
		return { id: recipe.id, cols, size: cols.reduce((sum, [, text]) => sum + text.length, 0) };
	});
	const averageSize = docs.reduce((sum, doc) => sum + doc.size, 0) / (docs.length || 1);

	// For each typed word, each recipe's hits, weighted by the column they fall in.
	const hits = query.map((q) => {
		const root = stem(q);
		const matches = (w: string) => w.startsWith(q) || stem(w).startsWith(root);
		return docs.map((doc) => doc.cols.reduce((sum, [weight, text]) => sum + weight * text.filter(matches).length, 0));
	});
	const idf = hits.map((perDoc) => {
		const n = perDoc.filter((f) => f > 0).length;
		return Math.max(Math.log((docs.length - n + 0.5) / (n + 0.5)), 1e-6);
	});

	const scores = new Map<number, number>();
	docs.forEach((doc, i) => {
		if (hits.some((perDoc) => perDoc[i] === 0)) return;
		const norm = K1 * (1 - B + (B * doc.size) / averageSize);
		const score = hits.reduce((sum, perDoc, t) => sum + (idf[t] * perDoc[i] * (K1 + 1)) / (perDoc[i] + norm), 0);
		scores.set(doc.id, score);
	});
	return scores;
}

function hasIngredient(recipe: Recipe, name: string): boolean {
	const phrase = name.toLowerCase().split(/\s+/).filter(Boolean).join(' ');
	if (!phrase) return true;
	const single = phrase.split(' ').map(singular).join(' ');
	return recipe.ingredients.some((i) => {
		const padded = ` ${i.canonical_name} `;
		return padded.includes(` ${phrase} `) || padded.includes(` ${single} `);
	});
}

function list(value: string | null): string[] {
	return (value ?? '')
		.split(',')
		.map((v) => v.trim())
		.filter(Boolean);
}

function number(value: string | null): number | null {
	if (value === null || value.trim() === '') return null;
	const n = Number(value);
	return Number.isFinite(n) ? n : null;
}

const byTitle = (a: Recipe, b: Recipe) => a.title.toLowerCase().localeCompare(b.title.toLowerCase()) || a.id - b.id;
const nullsLast = (a: number | null, b: number | null) => (a === null ? 1 : 0) - (b === null ? 1 : 0) || (a ?? 0) - (b ?? 0);

const ORDER: Record<string, (a: Recipe, b: Recipe) => number> = {
	newest: (a, b) => b.created_at.localeCompare(a.created_at) || b.id - a.id,
	title: byTitle,
	quickest: (a, b) => nullsLast(a.total_minutes, b.total_minutes) || byTitle(a, b),
	simplest: (a, b) => a.complexity - b.complexity || nullsLast(a.total_minutes, b.total_minutes) || byTitle(a, b)
};

export function summarise(recipe: Recipe): RecipeSummary {
	const { id, title, image_url, source_domain, origin, total_minutes, complexity, cuisine, course, diet, created_at } =
		recipe;
	return { id, title, image_url, source_domain, origin, total_minutes, complexity, cuisine, course, diet, created_at };
}

/** GET /api/recipes, answered from the saved copy. Takes the same query parameters. */
export function searchOffline(recipes: Recipe[], params: URLSearchParams): RecipePage {
	const query = words(params.get('q') ?? '');
	const has = list(params.get('has'));
	const tags = list(params.get('tag')).map((t) => t.toLowerCase());
	const maxTotal = number(params.get('max_total'));
	const maxComplexity = number(params.get('max_complexity'));
	const cuisine = params.get('cuisine')?.toLowerCase();
	const course = params.get('course');

	const scores = query.length ? textScores(recipes, query) : new Map<number, number>();
	const matches = recipes.filter((recipe) => {
		if (query.length && !scores.has(recipe.id)) return false;
		if (!has.every((name) => hasIngredient(recipe, name))) return false;
		// As in SQL, a recipe with no total time never passes a time limit.
		if (maxTotal !== null && (recipe.total_minutes === null || recipe.total_minutes > maxTotal)) return false;
		if (maxComplexity !== null && recipe.complexity > maxComplexity) return false;
		if (cuisine && recipe.cuisine?.toLowerCase() !== cuisine) return false;
		if (course && recipe.course !== course) return false;
		const recipeTags = [...recipe.diet, ...recipe.equipment, ...recipe.techniques, ...recipe.tags];
		return tags.every((tag) => recipeTags.includes(tag));
	});

	const sort = params.get('sort') ?? (query.length ? 'relevance' : 'newest');
	const order =
		sort === 'relevance' && query.length
			? (a: Recipe, b: Recipe) => (scores.get(b.id) ?? 0) - (scores.get(a.id) ?? 0) || a.id - b.id
			: (ORDER[sort] ?? ORDER.newest);
	matches.sort(order);

	const offset = number(params.get('offset')) ?? 0;
	const limit = number(params.get('limit')) ?? DEFAULT_LIMIT;
	return { recipes: matches.slice(offset, offset + limit).map(summarise), total: matches.length };
}

/** "5 minutes ago", "yesterday", "3 days ago": when the saved copy was last known to be current. */
export function savedAgo(savedAt: string, now: Date = new Date()): string {
	const minutes = Math.max(0, Math.round((now.getTime() - new Date(savedAt).getTime()) / 60_000));
	if (minutes < 1) return 'just now';
	if (minutes < 60) return minutes === 1 ? '1 minute ago' : `${minutes} minutes ago`;
	const hours = Math.round(minutes / 60);
	if (hours < 24) return hours === 1 ? '1 hour ago' : `${hours} hours ago`;
	const days = Math.round(hours / 24);
	return days === 1 ? 'yesterday' : `${days} days ago`;
}
