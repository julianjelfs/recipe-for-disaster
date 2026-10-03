import { invalidateAll } from '$app/navigation';
import type { Recipe } from './api';
import { applySync, changesAnything, EMPTY_COPY, syncQuery, type LibraryCopy, type SyncResponse } from './sync';

/**
 * This device's copy of the whole library. Every page reads recipes from here, and search runs over
 * it, so the app works the same with or without the Pi. The copy lives in IndexedDB between visits
 * and is brought up to date from GET /api/sync: when the app opens, when it comes back into view,
 * every few minutes while it's open, and after every change made through it.
 */

// Off the home network the Pi's name doesn't resolve, which fails fast. A weak signal can hang.
const SYNC_TIMEOUT_MS = 4000;
const SYNC_EVERY_MS = 5 * 60_000;

/** Whether the Pi answered the last sync, and when the copy was last confirmed current. */
export const connection = $state<{ away: boolean; syncedAt: string | null }>({ away: false, syncedAt: null });

let copy: LibraryCopy = EMPTY_COPY;
let list: Recipe[] = [];
let opened: Promise<void> | null = null;
// Syncs run one after another, so two can't both apply their changes to the same starting copy.
let queue: Promise<unknown> = Promise.resolve();

/** Resolves once the saved copy is loaded. On a device with no copy yet, waits for the first sync. */
export function ready(): Promise<void> {
	opened ??= open();
	return opened;
}

/** Every recipe in the copy. */
export function recipes(): Recipe[] {
	return list;
}

/**
 * One recipe, or undefined if the library doesn't have it. A recipe this device hasn't heard of
 * yet (someone just added it on another phone) gets one sync before giving up.
 */
export async function find(id: number): Promise<Recipe | undefined> {
	await ready();
	if (!copy.recipes.has(id)) await sync();
	return copy.recipes.get(id);
}

/** Bring the copy up to date. Resolves true if anything changed. */
export function sync(): Promise<boolean> {
	const run = queue.then(syncOnce, syncOnce);
	queue = run;
	return run;
}

/** Sync, and redraw the page if that changed anything. For syncs nobody is waiting on. */
function refresh() {
	sync().then((changed) => {
		if (changed) invalidateAll();
	});
}

/** A hidden tab has nobody looking at it: it catches up when it comes back into view. */
function refreshIfVisible() {
	if (document.visibilityState === 'visible') refresh();
}

async function open(): Promise<void> {
	const saved = await storage.load();
	if (saved) {
		setCopy(saved.copy);
		connection.syncedAt = saved.syncedAt;
	}
	if (copy.epoch === null) await sync();
	else refresh();

	document.addEventListener('visibilitychange', refreshIfVisible);
	window.addEventListener('online', refreshIfVisible);
	setInterval(refreshIfVisible, SYNC_EVERY_MS);
}

async function syncOnce(): Promise<boolean> {
	let response: SyncResponse;
	try {
		const reply = await fetch(`/api/sync?${syncQuery(copy)}`, {
			cache: 'no-store',
			signal: AbortSignal.timeout(SYNC_TIMEOUT_MS)
		});
		// A gateway error is Caddy answering for an app that is down or restarting.
		if (!reply.ok) throw new Error(`HTTP ${reply.status}`);
		response = await reply.json();
	} catch {
		connection.away = true;
		return false;
	}
	setCopy(applySync(copy, response));
	connection.away = false;
	connection.syncedAt = new Date().toISOString();
	await storage.save(response, copy, connection.syncedAt);
	return changesAnything(response);
}

function setCopy(next: LibraryCopy) {
	copy = next;
	list = [...next.recipes.values()];
}

/**
 * The copy in IndexedDB: one row per recipe, and one for where the copy stands. A sync's changes and
 * the new revision go in one transaction, so a copy is never saved half updated. If IndexedDB isn't
 * there (some private windows), the app still works and syncs from scratch on each visit.
 */
const storage = {
	async load(): Promise<{ copy: LibraryCopy; syncedAt: string | null } | null> {
		try {
			const db = await database();
			const tx = db.transaction(['recipes', 'meta'], 'readonly');
			const [rows, meta] = await Promise.all([
				request<Recipe[]>(tx.objectStore('recipes').getAll()),
				request<Meta | undefined>(tx.objectStore('meta').get(META_KEY))
			]);
			if (!meta) return null;
			return {
				copy: { epoch: meta.epoch, revision: meta.revision, recipes: new Map(rows.map((r) => [r.id, r])) },
				syncedAt: meta.syncedAt
			};
		} catch {
			return null;
		}
	},

	async save(response: SyncResponse, copy: LibraryCopy, syncedAt: string): Promise<void> {
		try {
			const db = await database();
			const tx = db.transaction(['recipes', 'meta'], 'readwrite');
			const recipes = tx.objectStore('recipes');
			if (response.full) recipes.clear();
			for (const id of response.deleted) recipes.delete(id);
			for (const recipe of response.changed) recipes.put(recipe);
			const meta: Meta = { epoch: copy.epoch!, revision: copy.revision, syncedAt };
			tx.objectStore('meta').put(meta, META_KEY);
			await finished(tx);
		} catch {
			// Not saved: the next visit syncs from where the last saved copy stood.
		}
	}
};

interface Meta {
	epoch: number;
	revision: number;
	syncedAt: string;
}

const META_KEY = 'copy';
let db: Promise<IDBDatabase> | null = null;

function database(): Promise<IDBDatabase> {
	db ??= new Promise((resolve, reject) => {
		const open = indexedDB.open('recipe-library', 1);
		open.onupgradeneeded = () => {
			open.result.createObjectStore('recipes', { keyPath: 'id' });
			open.result.createObjectStore('meta');
		};
		open.onsuccess = () => resolve(open.result);
		open.onerror = () => reject(open.error);
	});
	return db;
}

function request<T>(req: IDBRequest): Promise<T> {
	return new Promise((resolve, reject) => {
		req.onsuccess = () => resolve(req.result as T);
		req.onerror = () => reject(req.error);
	});
}

function finished(tx: IDBTransaction): Promise<void> {
	return new Promise((resolve, reject) => {
		tx.oncomplete = () => resolve();
		tx.onerror = tx.onabort = () => reject(tx.error);
	});
}
