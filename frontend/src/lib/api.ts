import { error } from '@sveltejs/kit';

export const UNITS = [
	'g', 'kg', 'ml', 'l', 'tsp', 'tbsp',
	'pinch', 'dash', 'clove', 'tin', 'bunch', 'handful', 'sprig', 'slice', 'piece'
] as const;
export const COURSES = ['breakfast', 'starter', 'main', 'side', 'dessert', 'baking', 'snack', 'drink', 'sauce'] as const;
export const DIETS = ['vegetarian', 'vegan', 'gluten-free', 'dairy-free', 'nut-free'] as const;

export interface Ingredient {
	id: number;
	position: number;
	group_name: string | null;
	quantity: number | null;
	quantity_max: number | null;
	unit: string | null;
	name: string;
	canonical_name: string;
	preparation: string | null;
	optional: boolean;
}

export interface Step {
	id: number;
	position: number;
	text: string;
	timer_seconds: number | null;
	ingredient_ids: number[];
}

export interface Recipe {
	id: number;
	source_url: string;
	source_domain: string;
	title: string;
	image_url: string | null;
	servings: number | null;
	prep_minutes: number | null;
	cook_minutes: number | null;
	total_minutes: number | null;
	complexity: number;
	cuisine: string | null;
	course: string | null;
	diet: string[];
	equipment: string[];
	techniques: string[];
	tags: string[];
	notes: string;
	model: string;
	parse_version: number;
	created_at: string;
	updated_at: string;
	ingredients: Ingredient[];
	steps: Step[];
}

export interface RecipeSummary {
	id: number;
	title: string;
	image_url: string | null;
	source_domain: string;
	total_minutes: number | null;
	complexity: number;
	cuisine: string | null;
	course: string | null;
	diet: string[];
	created_at: string;
}

export interface FacetValue {
	value: string;
	count: number;
}

export interface Facets {
	total: number;
	ingredients: FacetValue[];
	cuisines: FacetValue[];
	courses: FacetValue[];
	diet: FacetValue[];
	equipment: FacetValue[];
	techniques: FacetValue[];
	tags: FacetValue[];
}

/** An ingredient in an edit. Steps refer to ingredients by key. */
export interface EditIngredient {
	key: string;
	group: string | null;
	quantity: number | null;
	quantity_max: number | null;
	unit: string | null;
	name: string;
	canonical_name: string;
	preparation: string | null;
	optional: boolean;
}

export interface EditStep {
	text: string;
	timer_seconds: number | null;
	ingredient_keys: string[];
}

export interface RecipeEdit {
	title: string;
	servings: number | null;
	prep_minutes: number | null;
	cook_minutes: number | null;
	total_minutes: number | null;
	complexity: number;
	cuisine: string | null;
	course: string | null;
	diet: string[];
	equipment: string[];
	techniques: string[];
	notes: string;
	tags: string[];
	ingredients: EditIngredient[];
	steps: EditStep[];
}

export class ApiError extends Error {
	constructor(
		readonly status: number,
		message: string,
		readonly errors: string[] = []
	) {
		super(message);
	}
}

export function toApiError(e: unknown): ApiError {
	return e instanceof ApiError ? e : new ApiError(0, String(e));
}

/** Await an API call in a load function, turning an ApiError into SvelteKit's error page. */
export async function orErrorPage<T>(promise: Promise<T>): Promise<T> {
	try {
		return await promise;
	} catch (e) {
		if (e instanceof ApiError) error(e.status || 503, e.message);
		throw e;
	}
}

type Fetch = typeof fetch;

async function request<T>(path: string, init: RequestInit = {}, fetcher: Fetch = fetch): Promise<T> {
	let response: Response;
	try {
		response = await fetcher(`/api${path}`, {
			...init,
			headers: { 'Content-Type': 'application/json', ...init.headers }
		});
	} catch {
		throw new ApiError(0, 'Could not reach the server.');
	}
	const body = await response.json().catch(() => null);
	if (!response.ok) {
		// Our errors carry {detail: {message, errors}}; FastAPI's own validation errors carry a list.
		const detail = body?.detail;
		const message = typeof detail?.message === 'string' ? detail.message : `Request failed (HTTP ${response.status}).`;
		throw new ApiError(response.status, message, Array.isArray(detail?.errors) ? detail.errors : []);
	}
	return body as T;
}

export function importRecipe(url: string): Promise<Recipe> {
	return request<Recipe>('/import', { method: 'POST', body: JSON.stringify({ url }) });
}

export function searchRecipes(params: URLSearchParams, fetcher?: Fetch): Promise<RecipeSummary[]> {
	const query = params.toString();
	return request<RecipeSummary[]>(`/recipes${query ? `?${query}` : ''}`, {}, fetcher);
}

export function getFacets(fetcher?: Fetch): Promise<Facets> {
	return request<Facets>('/facets', {}, fetcher);
}

export function getRecipe(id: number | string, fetcher?: Fetch): Promise<Recipe> {
	return request<Recipe>(`/recipes/${id}`, {}, fetcher);
}

export function updateRecipe(id: number, edit: RecipeEdit): Promise<Recipe> {
	return request<Recipe>(`/recipes/${id}`, { method: 'PUT', body: JSON.stringify(edit) });
}

export async function deleteRecipe(id: number): Promise<void> {
	await request<null>(`/recipes/${id}`, { method: 'DELETE' });
}

export function renormaliseRecipe(id: number): Promise<Recipe> {
	return request<Recipe>(`/recipes/${id}/renormalise`, { method: 'POST' });
}

export function flagRecipe(id: number, comment: string): Promise<{ id: number }> {
	return request<{ id: number }>(`/recipes/${id}/flags`, { method: 'POST', body: JSON.stringify({ comment }) });
}
