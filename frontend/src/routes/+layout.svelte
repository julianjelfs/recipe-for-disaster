<script lang="ts">
	import '$lib/app.css';
	import { page } from '$app/state';
	import { onMount } from 'svelte';
	import { CHECKED_KEY, OFFLINE_CACHE, savedAgo } from '$lib/offline';

	let { children } = $props();

	// Cooking mode covers the whole screen, so the site header would only be a hidden tab stop.
	const cooking = $derived(page.route.id === '/r/[id]/cook');

	// Away from the home network the service worker answers from a saved copy. Say so, and how old it is.
	let away = $state(false);
	let checkedAt = $state<string | null>(null);

	async function checkReach() {
		try {
			const response = await fetch('/api/health', { cache: 'no-store', signal: AbortSignal.timeout(4000) });
			away = !response.ok;
		} catch {
			away = true;
		}
		if (away) checkedAt = await readCheckedAt();
	}

	async function readCheckedAt(): Promise<string | null> {
		try {
			const response = await caches.match(CHECKED_KEY, { cacheName: OFFLINE_CACHE });
			return response ? (await response.json()).checked_at : null;
		} catch {
			// No Cache Storage: a plain-http dev URL, or storage blocked.
			return null;
		}
	}

	onMount(() => {
		checkReach();
		const onVisible = () => document.visibilityState === 'visible' && checkReach();
		document.addEventListener('visibilitychange', onVisible);
		window.addEventListener('online', checkReach);
		window.addEventListener('offline', checkReach);
		return () => {
			document.removeEventListener('visibilitychange', onVisible);
			window.removeEventListener('online', checkReach);
			window.removeEventListener('offline', checkReach);
		};
	});
</script>

{#if !cooking}
	<header class="site">
		<a class="brand" href="/">
			<img src="/favicon.svg" alt="" width="28" height="28" />
			Recipe for Disaster
		</a>
		<nav>
			<a class="button" href="/add">Add recipe</a>
			<a class="button" href="/create">Create recipe</a>
		</nav>
	</header>
	{#if away}
		<p class="away" role="status">
			{#if checkedAt}
				Away from home. These are the recipes saved on this device, last brought up to date {savedAgo(checkedAt)}.
				Adding, creating and editing need the home wifi.
			{:else}
				Can't reach the recipe server, and no recipes are saved on this device yet. Open the app once on the home wifi.
			{/if}
		</p>
	{/if}
{/if}

<main>
	{@render children()}
</main>

<style>
	.site {
		display: flex;
		align-items: center;
		flex-wrap: wrap;
		justify-content: space-between;
		gap: 0.75rem 1rem;
		max-width: var(--page-width);
		margin: 0 auto;
		padding: 1rem;
		border-bottom: 1px solid var(--line);
	}

	nav {
		display: flex;
		gap: 0.5rem;
	}

	/* Outlined, so the header doesn't shout over the page's own buttons. */
	nav .button {
		padding: 0.45rem 0.85rem;
		border: 1px solid var(--accent);
		background: transparent;
		color: var(--accent);
	}

	.away {
		max-width: var(--page-width);
		margin: 0 auto;
		padding: 0.5rem 1rem;
		border-bottom: 1px solid var(--line);
		color: var(--muted);
		font-size: 0.9rem;
	}

	.brand {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		color: var(--fg);
		font-weight: 700;
		text-decoration: none;
	}

	.brand img {
		border-radius: 0.4rem;
	}
</style>
