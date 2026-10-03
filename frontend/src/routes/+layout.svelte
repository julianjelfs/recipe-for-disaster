<script lang="ts">
	import '$lib/app.css';
	import { page } from '$app/state';
	import { formatAgo } from '$lib/format';
	import { connection, ready } from '$lib/library.svelte';

	let { children } = $props();

	// Cooking mode covers the whole screen, so the site header would only be a hidden tab stop.
	const cooking = $derived(page.route.id === '/r/[id]/cook');

	// Every page waits for the library anyway. This starts it for pages that don't, like /add.
	ready();
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
	{#if connection.away}
		<p class="away" role="status">
			{#if connection.syncedAt}
				Away from home. These are the recipes saved on this device, last brought up to date {formatAgo(connection.syncedAt)}.
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
		padding: 0.9rem 1.25rem;
		border-bottom: 1px solid var(--line);
	}

	nav {
		display: flex;
		gap: 0.5rem;
	}

	/* Outlined, so the header doesn't shout over the page's own buttons. */
	nav .button {
		padding: 0.45rem 0.85rem;
		border: 1px solid var(--edge);
		background: var(--card);
		color: var(--fg);
	}

	nav .button:hover {
		border-color: var(--muted);
	}

	.away {
		max-width: var(--page-width);
		margin: 0 auto;
		padding: 0.5rem 1.25rem;
		border-bottom: 1px solid var(--line);
		color: var(--muted);
		font-size: 0.9rem;
	}

	.brand {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		color: var(--fg);
		font-family: var(--serif);
		font-size: 1.3rem;
		font-weight: 700;
		text-decoration: none;
	}

	.brand img {
		border-radius: 7px;
	}
</style>
