<script lang="ts">
	import { goto } from '$app/navigation';
	import { page } from '$app/state';
	import IngredientFilter from '$lib/IngredientFilter.svelte';
	import RecipeImage from '$lib/RecipeImage.svelte';
	import { formatMinutes } from '$lib/format';

	let { data } = $props();

	const params = $derived(page.url.searchParams);
	const has = $derived(splitParam('has'));
	const tags = $derived(splitParam('tag'));
	const filtering = $derived([...params.keys()].length > 0);

	let text = $state(page.url.searchParams.get('q') ?? '');
	let debounce: ReturnType<typeof setTimeout> | undefined;

	function splitParam(name: string): string[] {
		return (params.get(name) ?? '').split(',').filter(Boolean);
	}

	/** Filters live in the URL so the back button and bookmarks keep them. */
	function update(changes: Record<string, string | null>) {
		const next = new URLSearchParams(page.url.searchParams);
		for (const [key, value] of Object.entries(changes)) {
			if (value) next.set(key, value);
			else next.delete(key);
		}
		const query = next.toString();
		goto(query ? `?${query}` : '/', { replaceState: true, keepFocus: true, noScroll: true });
	}

	function onTextInput() {
		clearTimeout(debounce);
		debounce = setTimeout(() => update({ q: text.trim() || null }), 250);
	}

	function setIngredients(next: string[]) {
		update({ has: next.join(',') || null });
	}

	function toggleTag(value: string) {
		const next = tags.includes(value) ? tags.filter((tag) => tag !== value) : [...tags, value];
		update({ tag: next.join(',') || null });
	}

	function clearAll() {
		text = '';
		goto('/', { replaceState: true, noScroll: true });
	}
</script>

<svelte:head>
	<title>Recipes</title>
</svelte:head>

<input
	class="search"
	type="search"
	placeholder="Search recipes"
	aria-label="Search recipes"
	bind:value={text}
	oninput={onTextInput}
/>

<div class="filters">
	<IngredientFilter ingredients={data.facets.ingredients} chosen={has} onchange={setIngredients} />

	<select aria-label="Maximum total time" value={params.get('max_total') ?? ''} onchange={(e) => update({ max_total: e.currentTarget.value })}>
		<option value="">Any time</option>
		{#each [15, 30, 45, 60, 90, 120] as minutes (minutes)}
			<option value={String(minutes)}>Up to {formatMinutes(minutes)}</option>
		{/each}
	</select>

	<select aria-label="Maximum complexity" value={params.get('max_complexity') ?? ''} onchange={(e) => update({ max_complexity: e.currentTarget.value })}>
		<option value="">Any complexity</option>
		{#each [1, 2, 3, 4] as level (level)}
			<option value={String(level)}>Complexity {level} or less</option>
		{/each}
	</select>

	{#if data.facets.courses.length}
		<select aria-label="Course" value={params.get('course') ?? ''} onchange={(e) => update({ course: e.currentTarget.value })}>
			<option value="">Any course</option>
			{#each data.facets.courses as course (course.value)}
				<option value={course.value}>{course.value} ({course.count})</option>
			{/each}
		</select>
	{/if}

	{#if data.facets.cuisines.length}
		<select aria-label="Cuisine" value={params.get('cuisine') ?? ''} onchange={(e) => update({ cuisine: e.currentTarget.value })}>
			<option value="">Any cuisine</option>
			{#each data.facets.cuisines as cuisine (cuisine.value)}
				<option value={cuisine.value}>{cuisine.value} ({cuisine.count})</option>
			{/each}
		</select>
	{/if}

	<select aria-label="Sort" value={params.get('sort') ?? ''} onchange={(e) => update({ sort: e.currentTarget.value })}>
		<option value="">{params.get('q') ? 'Best match' : 'Newest'}</option>
		<option value="newest">Newest</option>
		<option value="title">A to Z</option>
		<option value="quickest">Quickest</option>
		<option value="simplest">Simplest</option>
	</select>
</div>

{#if data.facets.diet.length || data.facets.tags.length}
	<div class="chips">
		{#each [...data.facets.diet, ...data.facets.tags] as tag (tag.value)}
			<button class="chip" class:on={tags.includes(tag.value)} aria-pressed={tags.includes(tag.value)} onclick={() => toggleTag(tag.value)}>
				{tag.value}
			</button>
		{/each}
	</div>
{/if}

{#if data.facets.total === 0}
	<p class="empty">No recipes yet. <a href="/add">Add your first one.</a></p>
{:else if data.recipes.length === 0}
	<p class="empty">
		Nothing matches.
		{#if filtering}<button class="link" onclick={clearAll}>Clear the search and filters</button>{/if}
	</p>
{:else}
	<p class="count">
		{data.recipes.length === data.facets.total ? `${data.facets.total} recipes` : `${data.recipes.length} of ${data.facets.total} recipes`}
	</p>
	<ul class="grid">
		{#each data.recipes as recipe (recipe.id)}
			<li>
				<a class="card" href="/r/{recipe.id}">
					<div class="picture">
						<RecipeImage src={recipe.image_url} course={recipe.course} title={recipe.title} />
					</div>
					<span class="title">{recipe.title}</span>
					<span class="meta">
						{[
							formatMinutes(recipe.total_minutes),
							`Complexity ${recipe.complexity}/5`,
							recipe.source_domain ?? (recipe.origin === 'created' ? 'Created' : null)
						]
							.filter(Boolean)
							.join(' · ')}
					</span>
				</a>
			</li>
		{/each}
	</ul>
{/if}

<style>
	.search {
		width: 100%;
		font-size: 1.15rem;
	}

	.filters {
		display: flex;
		flex-wrap: wrap;
		gap: 0.5rem;
		margin-top: 0.75rem;
	}

	.chips {
		display: flex;
		flex-wrap: wrap;
		gap: 0.4rem;
		margin-top: 0.75rem;
	}

	.chip {
		padding: 0.2rem 0.7rem;
		border: 1px solid var(--line);
		border-radius: 999px;
		background: var(--card);
		color: var(--fg);
		font-weight: normal;
	}

	.chip.on {
		border-color: var(--accent);
		background: var(--accent);
		color: var(--accent-fg);
	}

	.count,
	.empty {
		color: var(--muted);
	}

	.grid {
		display: grid;
		grid-template-columns: repeat(auto-fill, minmax(14rem, 1fr));
		gap: 1rem;
		padding: 0;
		list-style: none;
	}

	.card {
		display: flex;
		flex-direction: column;
		height: 100%;
		overflow: hidden;
		border: 1px solid var(--line);
		border-radius: 0.75rem;
		background: var(--card);
		color: var(--fg);
		text-decoration: none;
	}

	.picture {
		display: grid;
		width: 100%;
		aspect-ratio: 4 / 3;
		overflow: hidden;
		background: var(--line);
	}

	.picture :global(img) {
		width: 100%;
		height: 100%;
		object-fit: cover;
	}

	/* The course illustration sits in the middle instead of filling the tile. */
	.picture :global(.art) {
		width: 100%;
		height: 100%;
	}

	.title {
		padding: 0.6rem 0.75rem 0;
		font-weight: 600;
	}

	.meta {
		padding: 0.25rem 0.75rem 0.75rem;
		color: var(--muted);
		font-size: 0.85rem;
	}
</style>
