/// <reference no-default-lib="true"/>
/// <reference lib="esnext" />
/// <reference lib="webworker" />
/// <reference types="@sveltejs/kit" />

/**
 * Keeps the app usable away from the home network, where the Pi can't be reached: out shopping
 * with the list, or cooking at someone else's house.
 *
 * - The app itself (HTML, JS, CSS, icons) is cached at install, so it opens with no network.
 * - A copy of every recipe (GET /api/offline) is saved whenever the Pi answers, and refreshed
 *   after any change made through the app. It carries an ETag, so checking an unchanged
 *   library costs a 304 rather than the whole copy.
 * - Reads go to the Pi first. When it doesn't answer, they are answered from the saved copy, so
 *   browsing, searching, the shopping list and cooking mode all keep working.
 * - Writes (add, create, edit, delete, flag) need the Pi and fail as they would without this.
 *
 * Recipe photos are hotlinked from the sites they came from, which usually still load over mobile
 * data. They aren't saved: a browser counts each cross-site image as megabytes of storage, and
 * running out would throw away the saved recipes with them.
 */

import { build, files, version } from '$service-worker';
import { CHECKED_KEY, OFFLINE_CACHE, OFFLINE_KEY, searchOffline, type OfflineCopy } from '$lib/offline';

const sw = self as unknown as ServiceWorkerGlobalScope;

const SHELL = `shell-${version}`;
const SHELL_FILES = ['/', ...build, ...files];

// Off the home network the Pi's name doesn't resolve, which fails fast. A weak signal can hang
// instead, so give up after this long and use the saved copy.
const NETWORK_TIMEOUT_MS = 4000;
// After a miss, skip the network for a while so every tap doesn't wait for another failure.
const UNREACHABLE_FOR_MS = 30_000;
// Check the saved copy at most this often while browsing at home. Changes refresh it at once.
const REFRESH_EVERY_MS = 5 * 60_000;

let unreachableUntil = 0;
let lastRefresh = 0;
let copy: OfflineCopy | null = null;

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
				if (key.startsWith('shell-') && key !== SHELL) await caches.delete(key);
			}
			await sw.clients.claim();
			await refreshCopy(true);
		})()
	);
});

sw.addEventListener('fetch', (event) => {
	const request = event.request;
	const url = new URL(request.url);
	if (url.origin !== sw.location.origin) return;

	if (url.pathname.startsWith('/api/')) {
		if (request.method !== 'GET') {
			event.respondWith(write(event));
		} else if (!url.pathname.startsWith(OFFLINE_KEY) && url.pathname !== '/api/health') {
			event.respondWith(read(request, url));
		}
		return;
	}
	if (request.method !== 'GET') return;

	if (request.mode === 'navigate') {
		event.respondWith(navigate(event));
	} else {
		event.respondWith(asset(request));
	}
});

/** A change went through: the saved copy is now out of date. */
async function write(event: FetchEvent): Promise<Response> {
	const response = await fetch(event.request);
	if (response.ok) event.waitUntil(refreshCopy(true));
	return response;
}

/** Pages are all the same index.html. Fresh from the Pi when it answers, the cached one when not. */
async function navigate(event: FetchEvent): Promise<Response> {
	const response = await tryNetwork(event.request);
	if (response) {
		event.waitUntil(refreshCopy(false));
		return response;
	}
	return (await caches.match('/', { cacheName: SHELL })) ?? Response.error();
}

/** Built files never change under a version, so the cache wins. */
async function asset(request: Request): Promise<Response> {
	const cached = await caches.match(request, { cacheName: SHELL });
	return cached ?? fetch(request);
}

async function read(request: Request, url: URL): Promise<Response> {
	const response = await tryNetwork(request);
	if (response) return response;

	const saved = await savedCopy();
	if (!saved) {
		return json(503, {
			detail: { message: "Can't reach the recipe server, and no recipes are saved on this device yet. Open the app once on the home wifi." }
		});
	}

	const recipe = url.pathname.match(/^\/api\/recipes\/(\d+)$/);
	if (recipe) {
		const found = saved.recipes.find((r) => r.id === Number(recipe[1]));
		return found ? json(200, found) : json(404, { detail: { message: 'Recipe not found.' } });
	}
	if (url.pathname === '/api/recipes') return json(200, searchOffline(saved.recipes, url.searchParams));
	if (url.pathname === '/api/facets') return json(200, saved.facets);
	return json(503, { detail: { message: "Can't reach the recipe server. This needs the home wifi." } });
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

async function refreshCopy(force: boolean): Promise<void> {
	if (!force && Date.now() - lastRefresh < REFRESH_EVERY_MS) return;
	lastRefresh = Date.now();
	try {
		const cache = await caches.open(OFFLINE_CACHE);
		const etag = (await cache.match(OFFLINE_KEY))?.headers.get('ETag');
		const response = await fetch(OFFLINE_KEY, { cache: 'no-store', headers: etag ? { 'If-None-Match': etag } : {} });
		if (response.status === 200) {
			await cache.put(OFFLINE_KEY, response);
			copy = null;
		} else if (response.status !== 304) {
			return;
		}
		await cache.put(CHECKED_KEY, new Response(JSON.stringify({ checked_at: new Date().toISOString() })));
	} catch {
		// Not home. Keep the copy we have.
	}
}

async function savedCopy(): Promise<OfflineCopy | null> {
	if (copy) return copy;
	const response = await caches.match(OFFLINE_KEY, { cacheName: OFFLINE_CACHE });
	copy = response ? await response.json() : null;
	return copy;
}

function json(status: number, body: unknown): Response {
	return new Response(JSON.stringify(body), {
		status,
		headers: { 'Content-Type': 'application/json', 'X-Recipes-Offline': '1' }
	});
}
