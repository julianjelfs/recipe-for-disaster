import { existsSync, readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';
import { sharedUrl } from './share';

const staticDir = new URL('../../static/', import.meta.url);
const manifest = JSON.parse(readFileSync(new URL('manifest.webmanifest', staticDir), 'utf8'));
const link = 'https://www.bbcgoodfood.com/recipes/easy-chocolate-cake';

describe('sharing a link to the app', () => {
	it('invariant 17: the manifest sends shared links to /add in the url and text parameters', () => {
		expect(manifest.share_target).toEqual({
			action: '/add',
			method: 'GET',
			params: { title: 'title', text: 'text', url: 'url' }
		});
	});

	it('invariant 17: the add page finds the link in either parameter', () => {
		expect(sharedUrl(new URLSearchParams({ url: link }))).toBe(link);
		expect(sharedUrl(new URLSearchParams({ title: 'Easy chocolate cake', text: `Look at this ${link}` }))).toBe(link);
		expect(sharedUrl(new URLSearchParams({ url: '', text: link }))).toBe(link);
		expect(sharedUrl(new URLSearchParams({ text: 'no link here' }))).toBe('');
		expect(sharedUrl(new URLSearchParams())).toBe('');
	});
});

describe('manifest', () => {
	it('installs standalone with icons that exist, including a maskable one', () => {
		expect(manifest.display).toBe('standalone');
		for (const icon of manifest.icons as { src: string }[]) {
			expect(existsSync(new URL(`.${icon.src}`, staticDir)), icon.src).toBe(true);
		}
		expect((manifest.icons as { purpose: string }[]).some((icon) => icon.purpose === 'maskable')).toBe(true);
	});
});
