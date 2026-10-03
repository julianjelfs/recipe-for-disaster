/// <reference no-default-lib="true"/>
/// <reference lib="esnext" />
/// <reference lib="webworker" />
/// <reference types="@sveltejs/kit" />

/**
 * Lets the app open away from the home network, where the Pi can't be reached: out shopping with
 * the list, or cooking at someone else's house.
 *
 * This only caches the app itself (HTML, JS, CSS, icons). The recipes are the app's own business:
 * it keeps a copy of the library in IndexedDB and syncs it (see lib/library.svelte.ts), so API
 * requests pass straight through.
 *
 * Recipe photos are hotlinked from the sites they came from, which usually still load over mobile
 * data. They aren't saved: a browser counts each cross-site image as megabytes of storage, and
 * running out would throw away the saved recipes with them.
 */

import { build, files, version } from '$service-worker';

const sw = self as unknown as ServiceWorkerGlobalScope;

const SHELL = `shell-${version}`;
const SHELL_FILES = ['/', ...build, ...files];

// Off the home network the Pi's name doesn't resolve, which fails fast. A weak signal can hang
// instead, so give up after this long and use the cached page.
const NETWORK_TIMEOUT_MS = 4000;
// After a miss, skip the network for a while so every navigation doesn't wait for another failure.
const UNREACHABLE_FOR_MS = 30_000;

let unreachableUntil = 0;

sw.addEventListener('install', (event) => {
	event.waitUntil(
		caches
			.open(SHELL)
			.then((cache) => cache.addAll(SHELL_FILES))
			.then(() => sw.skipWaiting())
	);
});

sw.addEventListener('activate', (event) => {
	event.waitUntil(
		(async () => {
			for (const key of await caches.keys()) {
				if (key !== SHELL) await caches.delete(key);
			}
			await sw.clients.claim();
		})()
	);
});

sw.addEventListener('fetch', (event) => {
	const request = event.request;
	const url = new URL(request.url);
	if (request.method !== 'GET' || url.origin !== sw.location.origin || url.pathname.startsWith('/api/')) return;

	if (request.mode === 'navigate') {
		event.respondWith(navigate(request));
	} else {
		event.respondWith(asset(request));
	}
});

/** Pages are all the same index.html. Fresh from the Pi when it answers, the cached one when not. */
async function navigate(request: Request): Promise<Response> {
	const response = await tryNetwork(request);
	return response ?? (await caches.match('/', { cacheName: SHELL })) ?? Response.error();
}

/** Built files never change under a version, so the cache wins. */
async function asset(request: Request): Promise<Response> {
	const cached = await caches.match(request, { cacheName: SHELL });
	return cached ?? fetch(request);
}

/**
 * The Pi's response, or null if it can't be reached. A gateway error counts as unreachable: that
 * is Caddy answering for an app that is down or restarting.
 */
async function tryNetwork(request: Request): Promise<Response | null> {
	if (Date.now() < unreachableUntil) return null;
	try {
		// A race rather than an AbortSignal: fetch() refuses any options alongside a navigation request.
		const timeout = new Promise<never>((_, reject) => setTimeout(() => reject(new Error('timeout')), NETWORK_TIMEOUT_MS));
		const response = await Promise.race([fetch(request), timeout]);
		if (response.status < 502 || response.status > 504) return response;
	} catch {
		// Offline, the name didn't resolve, or the timeout fired.
	}
	unreachableUntil = Date.now() + UNREACHABLE_FOR_MS;
	return null;
}
