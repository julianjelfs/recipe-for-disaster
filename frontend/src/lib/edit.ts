import type { Recipe, RecipeEdit } from './api';

/** The editable form of a stored recipe. Existing ingredients get keys from their ids. */
export function toEdit(recipe: Recipe): RecipeEdit {
	const keyOf = (id: number) => `i${id}`;
	return {
		title: recipe.title,
		servings: recipe.servings,
		prep_minutes: recipe.prep_minutes,
		cook_minutes: recipe.cook_minutes,
		total_minutes: recipe.total_minutes,
		complexity: recipe.complexity,
		cuisine: recipe.cuisine,
		course: recipe.course,
		diet: [...recipe.diet],
		equipment: [...recipe.equipment],
		techniques: [...recipe.techniques],
		notes: recipe.notes,
		tags: [...recipe.tags],
		ingredients: recipe.ingredients.map((ingredient) => ({
			key: keyOf(ingredient.id),
			group: ingredient.group_name,
			quantity: ingredient.quantity,
			quantity_max: ingredient.quantity_max,
			unit: ingredient.unit,
			name: ingredient.name,
			canonical_name: ingredient.canonical_name,
			preparation: ingredient.preparation,
			optional: ingredient.optional
		})),
		steps: recipe.steps.map((step) => ({
			text: step.text,
			timer_seconds: step.timer_seconds,
			ingredient_keys: step.ingredient_ids.map(keyOf)
		}))
	};
}

/** Move list[index] by delta places, in place. Does nothing at either end. */
export function move<T>(list: T[], index: number, delta: number): void {
	const target = index + delta;
	if (target < 0 || target >= list.length) return;
	const [item] = list.splice(index, 1);
	list.splice(target, 0, item);
}

/** "wok, stand mixer," -> ["wok", "stand mixer"] */
export function splitList(text: string): string[] {
	return text
		.split(',')
		.map((item) => item.trim())
		.filter(Boolean);
}
