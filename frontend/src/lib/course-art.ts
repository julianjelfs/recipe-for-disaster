import { COURSES } from './api';

/** The drawings in static/course/, written by scripts/icons.mjs. */
export const COURSE_ART = [...COURSES, 'other'] as const;

/**
 * The illustration shown for a recipe with no photo. Every course has one; anything else,
 * including a recipe with no course set, falls back to "other".
 */
export function courseArt(course: string | null): string {
	const name = (COURSE_ART as readonly string[]).includes(course ?? '') ? course : 'other';
	return `/course/${name}.svg`;
}
