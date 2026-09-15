import type { Ingredient } from './api';
import { scaleAmount } from './scale';

export interface ShoppingItem {
	/** Stable across scaling, so ticks can be remembered. */
	key: string;
	quantity: number | null;
	quantity_max: number | null;
	unit: string | null;
	name: string;
	optional: boolean;
	ingredientIds: number[];
}

/**
 * The recipe's ingredients at the chosen scale, with repeats of the same ingredient added together:
 * 2 tbsp cocoa powder in the sponge and 5 tbsp in the buttercream become 7 tbsp.
 *
 * Lines only merge when they share a unit and both have an exact amount, or both have no amount
 * ("salt" twice). Ranges and mixed lines stay separate rather than being added up wrongly.
 */
export function shoppingList(ingredients: Ingredient[], scale: number): ShoppingItem[] {
	const items: ShoppingItem[] = [];
	const firstByKey = new Map<string, { item: ShoppingItem; names: Set<string>; canonical: string }>();

	for (const ingredient of ingredients.map((item) => scaleAmount(item, scale))) {
		const mergeKey = `${ingredient.canonical_name}|${ingredient.unit ?? ''}`;
		const first = firstByKey.get(mergeKey);
		const bothExact =
			first &&
			first.item.quantity !== null &&
			first.item.quantity_max === null &&
			ingredient.quantity !== null &&
			ingredient.quantity_max === null;
		const bothUnspecified = first && first.item.quantity === null && ingredient.quantity === null;

		if (first && (bothExact || bothUnspecified)) {
			if (bothExact) first.item.quantity = (first.item.quantity ?? 0) + (ingredient.quantity ?? 0);
			first.item.optional &&= ingredient.optional;
			first.item.ingredientIds.push(ingredient.id);
			first.names.add(ingredient.name);
			// "unsalted butter" and "butter" together read as plain "butter".
			if (first.names.size > 1) first.item.name = first.canonical;
			continue;
		}

		const item: ShoppingItem = {
			key: `i${ingredient.id}`,
			quantity: ingredient.quantity,
			quantity_max: ingredient.quantity_max,
			unit: ingredient.unit,
			name: ingredient.name,
			optional: ingredient.optional,
			ingredientIds: [ingredient.id]
		};
		items.push(item);
		if (!first) firstByKey.set(mergeKey, { item, names: new Set([ingredient.name]), canonical: ingredient.canonical_name });
	}
	return items;
}
