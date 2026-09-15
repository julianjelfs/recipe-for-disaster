export interface Amount {
	quantity: number | null;
	quantity_max: number | null;
}

/** Multiply an ingredient's amounts by factor. Unspecified amounts stay unspecified. */
export function scaleAmount<T extends Amount>(item: T, factor: number): T {
	return {
		...item,
		quantity: item.quantity === null ? null : item.quantity * factor,
		quantity_max: item.quantity_max === null ? null : item.quantity_max * factor
	};
}

/** The ?scale= URL parameter, or 1 when it is missing or makes no sense. */
export function parseScale(value: string | null): number {
	const scale = Number(value);
	return Number.isFinite(scale) && scale > 0 && scale <= 20 ? scale : 1;
}

export function servingsFor(original: number | null, scale: number): number | null {
	return original === null ? null : Math.round(original * scale * 100) / 100;
}

/**
 * The scale after pressing + (1) or − (-1). With known servings each press is one serving;
 * without them each press is half the recipe.
 */
export function stepScale(original: number | null, scale: number, direction: 1 | -1): number {
	if (original) {
		const servings = Math.max(1, Math.round(original * scale) + direction);
		return servings / original;
	}
	return Math.max(0.5, scale + direction * 0.5);
}
