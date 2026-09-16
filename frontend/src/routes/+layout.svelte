<script lang="ts">
	import '$lib/app.css';
	import { page } from '$app/state';

	let { children } = $props();

	// Cooking mode covers the whole screen, so the site header would only be a hidden tab stop.
	const cooking = $derived(page.route.id === '/r/[id]/cook');
</script>

{#if !cooking}
	<header class="site">
		<a class="brand" href="/">
			<img src="/favicon.svg" alt="" width="28" height="28" />
			Recipe for Disaster
		</a>
		<nav>
			<a href="/add">Add recipe</a>
			<a href="/create">Create recipe</a>
		</nav>
	</header>
{/if}

<main>
	{@render children()}
</main>

<style>
	.site {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 1rem;
		max-width: var(--page-width);
		margin: 0 auto;
		padding: 1rem;
		border-bottom: 1px solid var(--line);
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
