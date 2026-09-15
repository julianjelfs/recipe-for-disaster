import type { Ingredient } from './api';

const WEIGHT_AND_VOLUME = new Set(['g', 'kg', 'ml', 'l']);
const PLURAL_UNITS: Record<string, string> = {
	clove: 'cloves',
	tin: 'tins',
	bunch: 'bunches',
	handful: 'handfuls',
	sprig: 'sprigs',
	slice: 'slices',
	piece: 'pieces',
	pinch: 'pinches',
	dash: 'dashes'
};
const FRACTIONS: [number, string][] = [
	[1 / 8, '⅛'],
	[1 / 4, '¼'],
	[1 / 3, '⅓'],
	[1 / 2, '½'],
	[2 / 3, '⅔'],
	[3 / 4, '¾']
];

/** Spoons and counts: 1.5 -> "1½", 0.33 -> "⅓", 2.2 -> "2.2". */
export function formatCount(value: number): string {
	const whole = Math.floor(value);
	const rest = value - whole;
	if (rest < 0.04) return String(whole);
	if (rest > 0.96) return String(whole + 1);
	const fraction = FRACTIONS.find(([amount]) => Math.abs(rest - amount) < 0.04);
	if (fraction) return whole ? `${whole}${fraction[1]}` : fraction[1];
	return String(Math.round(value * 10) / 10);
}

/** Weights and volumes: nearest 5 from 100 up, whole numbers from 10, one decimal below. */
export function formatMetric(value: number, unit: string): string {
	if (unit === 'kg' || unit === 'l') return String(Math.round(value * 100) / 100);
	if (value >= 100) return String(Math.round(value / 5) * 5);
	if (value >= 10) return String(Math.round(value));
	return String(Math.round(value * 10) / 10);
}

/**
 * The amount shown before an ingredient's name: "200g", "½ tsp", "2 cloves", "5-6",
 * "1 ×" before a name that starts with a size, or "" when the amount is unspecified.
 */
export function formatAmount(ingredient: Pick<Ingredient, 'quantity' | 'quantity_max' | 'unit' | 'name'>): string {
	const { quantity, quantity_max, name } = ingredient;
	if (quantity === null) return '';
	let unit = ingredient.unit;

	if (unit && WEIGHT_AND_VOLUME.has(unit)) {
		const amount = formatMetric(quantity, unit) + (quantity_max === null ? '' : `-${formatMetric(quantity_max, unit)}`);
		return `${amount}${unit}`;
	}

	// "1 piece 5cm piece fresh ginger" repeats itself; the name already says it's a piece.
	if (unit && new RegExp(`\\b${unit}(e?s)?\\b`, 'i').test(name)) unit = null;

	const amount = formatCount(quantity) + (quantity_max === null ? '' : `-${formatCount(quantity_max)}`);
	if (!unit) return /^\d/.test(name) ? `${amount} ×` : amount;
	const plural = (quantity_max ?? quantity) > 1 && PLURAL_UNITS[unit];
	return `${amount} ${plural || unit}`;
}

/** "45 min", "1 hr 30 min", or null when unknown. */
export function formatMinutes(minutes: number | null): string | null {
	if (minutes === null) return null;
	if (minutes < 60) return `${minutes} min`;
	const rest = minutes % 60;
	return rest ? `${Math.floor(minutes / 60)} hr ${rest} min` : `${minutes / 60} hr`;
}

/** A timer's length: "20 min", "1 hr 15 min", "90 sec". */
export function formatTimer(seconds: number): string {
	return seconds % 60 === 0 ? (formatMinutes(seconds / 60) ?? '') : `${seconds} sec`;
}
