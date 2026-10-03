import type { FacetValue, Facets, Recipe, RecipeSummary } from './api';

/**
 * Search, filters and facets over the library copy each device keeps (see library.svelte.ts).
 * There is no server-side search: this is the only implementation, online or off.
 */

export interface SearchResult {
	/** Every match, in order. The home page shows them a screenful at a time. */
	recipes: RecipeSummary[];
	total: number;
}

/** Rough English singular, enough to match "leeks" to "leek" and "tomatoes" to "tomato". */
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

// What text search looks at, and how much a hit in each counts (bm25 column weights). Worked out
// once per recipe object: a sync replaces the object when the recipe changes.
const columnCache = new WeakMap<Recipe, [number, string[]][]>();

function columns(recipe: Recipe): [number, string[]][] {
	let cached = columnCache.get(recipe);
	if (!cached) {
		cached = readColumns(recipe);
		columnCache.set(recipe, cached);
	}
	return cached;
}

function readColumns(recipe: Recipe): [number, string[]][] {
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
 * A light stemmer, a stand-in for SQLite's Porter one, enough that "baking", "baked" and "bake" meet,
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
 * Text search scores for the recipes that match, higher first: bm25 as SQLite's FTS5 computes it,
 * over the whole library. Every word must match the start of a word somewhere, with common endings
 * forgiven by stem().
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

/**
 * The recipes matching the home page's URL parameters: q (text), has (ingredients, comma-separated),
 * tag, max_total, max_complexity, cuisine, course and sort.
 */
export function search(recipes: Recipe[], params: URLSearchParams): SearchResult {
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
		// A recipe with no total time never passes a time limit: nobody knows it's quick.
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
	return { recipes: matches.map(summarise), total: matches.length };
}


function counted(counts: Map<string, number>): FacetValue[] {
	return [...counts]
		.map(([value, count]) => ({ value, count }))
		.sort((a, b) => b.count - a.count || (a.value < b.value ? -1 : a.value > b.value ? 1 : 0));
}

function bump(counts: Map<string, number>, value: string) {
	counts.set(value, (counts.get(value) ?? 0) + 1);
}

/** What the library holds, for the filter panel: each value with the number of recipes that have it. */
export function facets(recipes: Recipe[]): Facets {
	const ingredients = new Map<string, number>();
	const courses = new Map<string, number>();
	const diet = new Map<string, number>();
	const equipment = new Map<string, number>();
	const techniques = new Map<string, number>();
	const tags = new Map<string, number>();
	// Cuisines count together whatever their case, under the spelling seen first.
	const cuisines = new Map<string, number>();
	const cuisineSpelling = new Map<string, string>();

	for (const recipe of [...recipes].sort((a, b) => a.id - b.id)) {
		for (const name of new Set(recipe.ingredients.map((i) => i.canonical_name))) bump(ingredients, name);
		if (recipe.course) bump(courses, recipe.course);
		if (recipe.cuisine) {
			const key = recipe.cuisine.toLowerCase();
			if (!cuisineSpelling.has(key)) cuisineSpelling.set(key, recipe.cuisine);
			bump(cuisines, cuisineSpelling.get(key)!);
		}
		for (const value of new Set(recipe.diet)) bump(diet, value);
		for (const value of new Set(recipe.equipment)) bump(equipment, value);
		for (const value of new Set(recipe.techniques)) bump(techniques, value);
		for (const value of new Set(recipe.tags)) bump(tags, value);
	}

	return {
		total: recipes.length,
		ingredients: counted(ingredients),
		cuisines: counted(cuisines),
		courses: counted(courses),
		diet: counted(diet),
		equipment: counted(equipment),
		techniques: counted(techniques),
		tags: counted(tags)
	};
}
