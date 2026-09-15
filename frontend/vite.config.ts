import adapter from '@sveltejs/adapter-static';
import { sveltekit } from '@sveltejs/kit/vite';
import { defineConfig } from 'vite';

export default defineConfig({
	plugins: [
		sveltekit({
			compilerOptions: {
				// Force runes mode for the project, except for libraries. Can be removed in svelte 6.
				runes: ({ filename }) =>
					filename.split(/[/\\]/).includes('node_modules') ? undefined : true
			},

			// Built as a single-page app. FastAPI serves index.html for every non-API path.
			adapter: adapter({ fallback: 'index.html' })
		})
	],
	server: {
		proxy: {
			// The dev API runs on 8011: the installed service has 8010 and Triad Trainer has 8000.
			'/api': process.env.API_URL ?? 'http://127.0.0.1:8011'
		}
	}
});
