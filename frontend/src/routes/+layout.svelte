<script lang="ts">
	import '$lib/app.css';
	import favicon from '$lib/assets/favicon.svg';
	import { page } from '$app/state';

	let { children } = $props();

	// Cooking mode covers the whole screen, so the site header would only be a hidden tab stop.
	const cooking = $derived(page.route.id === '/r/[id]/cook');
</script>

<svelte:head>
	<link rel="icon" href={favicon} />
</svelte:head>

{#if !cooking}
	<header class="site">
		<a class="brand" href="/">Recipe for Disaster</a>
		<nav>
			<a href="/add">Add recipe</a>
		</nav>
	</header>
{/if}

<main>
	{@render children()}
</main>

<style>
	.site {
		display: flex;
		align-items: baseline;
		justify-content: space-between;
		gap: 1rem;
		max-width: var(--page-width);
		margin: 0 auto;
		padding: 1rem;
		border-bottom: 1px solid var(--line);
	}

	.brand {
		color: var(--fg);
		font-weight: 700;
		text-decoration: none;
	}
</style>
