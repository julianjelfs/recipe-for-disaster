import { existsSync } from 'node:fs';
import { describe, expect, it } from 'vitest';
import { COURSES } from './api';
import { COURSE_ART, courseArt } from './course-art';

const staticDir = new URL('../../static/', import.meta.url);

describe('course illustrations', () => {
	it('invariant 24: every course has a drawing that exists', () => {
		for (const course of COURSES) {
			const path = courseArt(course);
			expect(path, course).toBe(`/course/${course}.svg`);
			expect(existsSync(new URL(`.${path}`, staticDir)), path).toBe(true);
		}
		expect(COURSE_ART.length).toBe(COURSES.length + 1);
	});

	it('invariant 24: a recipe with no course, or an unknown one, still gets a drawing', () => {
		for (const course of [null, '', 'elevenses', 'supper']) {
			expect(courseArt(course)).toBe('/course/other.svg');
		}
		expect(existsSync(new URL('./course/other.svg', staticDir))).toBe(true);
	});
});
