<script lang="ts">
	import { goto, invalidateAll, replaceState } from '$app/navigation';
	import { page } from '$app/state';
	import { untrack } from 'svelte';
	import ServingsControl from '$lib/ServingsControl.svelte';
	import { deleteRecipe, flagRecipe, renormaliseRecipe, toApiError, type ApiError, type Ingredient } from '$lib/api';
	import { formatAmount, formatMinutes } from '$lib/format';
	import { parseScale, scaleAmount } from '$lib/scale';

	let { data } = $props();
	const recipe = $derived(data.recipe);

	let scale = $state(untrack(() => parseScale(page.url.searchParams.get('scale'))));
	const cookHref = $derived(`/r/${recipe.id}/cook${scale === 1 ? '' : `?scale=${scale}`}`);

	/** Keep the scale in the URL so it carries into cooking mode and survives a reload. */
	function setScale(next: number) {
		scale = next;
		const url = new URL(page.url);
		if (next === 1) url.searchParams.delete('scale');
		else url.searchParams.set('scale', String(next));
		replaceState(url, {});
	}

	/** Consecutive ingredients sharing a group heading, in recipe order. */
	function groupIngredients(ingredients: Ingredient[]) {
		const groups: { name: string | null; items: Ingredient[] }[] = [];
		for (const ingredient of ingredients) {
			const last = groups.at(-1);
			if (last && last.name === ingredient.group_name) last.items.push(ingredient);
			else groups.push({ name: ingredient.group_name, items: [ingredient] });
		}
		return groups;
	}

	const groups = $derived(groupIngredients(recipe.ingredients.map((ingredient) => scaleAmount(ingredient, scale))));
	const facts = $derived(
		[
			recipe.prep_minutes !== null && `Prep ${formatMinutes(recipe.prep_minutes)}`,
			recipe.cook_minutes !== null && `Cook ${formatMinutes(recipe.cook_minutes)}`,
			recipe.total_minutes !== null && `Total ${formatMinutes(recipe.total_minutes)}`,
			`Complexity ${recipe.complexity}/5`,
			recipe.cuisine,
			recipe.course,
			...recipe.diet
		].filter(Boolean)
	);
	const labels = $derived([...recipe.tags, ...recipe.equipment, ...recipe.techniques]);

	let busy = $state<'renormalise' | 'delete' | null>(null);
	let confirmingDelete = $state(false);
	let actionError = $state<ApiError | null>(null);

	async function renormalise() {
		busy = 'renormalise';
		actionError = null;
		try {
			await renormaliseRecipe(recipe.id);
			await invalidateAll();
		} catch (e) {
			actionError = toApiError(e);
		} finally {
			busy = null;
		}
	}

	async function remove() {
		busy = 'delete';
		actionError = null;
		try {
			await deleteRecipe(recipe.id);
			await goto('/', { replaceState: true });
		} catch (e) {
			actionError = toApiError(e);
			busy = null;
		}
	}

	type FlagState =
		| { kind: 'closed' }
		| { kind: 'open'; error?: string }
		| { kind: 'sending' }
		| { kind: 'sent'; reportId: number };

	let flag = $state<FlagState>({ kind: 'closed' });
	let flagComment = $state('');

	async function sendFlag(event: SubmitEvent) {
		event.preventDefault();
		flag = { kind: 'sending' };
		try {
			const report = await flagRecipe(recipe.id, flagComment.trim());
			flag = { kind: 'sent', reportId: report.id };
			flagComment = '';
		} catch (e) {
			flag = { kind: 'open', error: toApiError(e).message };
		}
	}
</script>

<svelte:head>
	<title>{recipe.title}</title>
</svelte:head>

<article>
	<header>
		{#if recipe.image_url}
			<img src={recipe.image_url} alt="" referrerpolicy="no-referrer" />
		{/if}
		<h1>{recipe.title}</h1>
		<ul class="facts">
			{#each facts as fact, index (index)}
				<li>{fact}</li>
			{/each}
		</ul>

		<div class="actions">
			<a class="button" href={cookHref}>Start cooking</a>
			<a class="button secondary" href="/r/{recipe.id}/edit">Edit</a>
			<button
				class="secondary"
				onclick={renormalise}
				disabled={busy !== null}
				title="Replaces the ingredients and steps with a fresh read of the saved page. Notes and tags stay."
			>
				{busy === 'renormalise' ? 'Re-reading…' : 'Re-read with Claude'}
			</button>
			{#if confirmingDelete}
				<button class="danger" onclick={remove} disabled={busy !== null}>
					{busy === 'delete' ? 'Deleting…' : 'Delete for good'}
				</button>
				<button class="link" onclick={() => (confirmingDelete = false)}>Keep it</button>
			{:else}
				<button class="secondary" onclick={() => (confirmingDelete = true)} disabled={busy !== null}>Delete</button>
			{/if}
		</div>

		{#if busy === 'renormalise'}
			<p class="hint">Claude is reading the saved page again. This can take up to a minute.</p>
		{/if}

		{#if actionError}
			<div class="error" role="alert">
				<p>{actionError.message}</p>
				{#if actionError.errors.length}
					<ul>
						{#each actionError.errors as message, index (index)}
							<li>{message}</li>
						{/each}
					</ul>
				{/if}
			</div>
		{/if}
	</header>

	{#if recipe.notes}
		<section class="notes">
			<h2>Notes</h2>
			<p>{recipe.notes}</p>
		</section>
	{/if}

	<div class="columns">
		<section>
			<div class="ingredients-heading">
				<h2>Ingredients</h2>
				<ServingsControl servings={recipe.servings} {scale} onchange={setScale} />
			</div>
			{#each groups as group, index (index)}
				{#if group.name}
					<h3>{group.name}</h3>
				{/if}
				<ul class="ingredients">
					{#each group.items as ingredient (ingredient.id)}
						<li>
							<span class="amount">{formatAmount(ingredient)}</span>
							{ingredient.name}{#if ingredient.preparation}, {ingredient.preparation}{/if}
							{#if ingredient.optional}<em>(optional)</em>{/if}
						</li>
					{/each}
				</ul>
			{/each}
		</section>

		<section>
			<h2>Method</h2>
			<ol class="steps">
				{#each recipe.steps as step (step.id)}
					<li>{step.text}</li>
				{/each}
			</ol>
		</section>
	</div>

	{#if labels.length}
		<ul class="labels">
			{#each labels as label, index (index)}
				<li>{label}</li>
			{/each}
		</ul>
	{/if}

	<footer>
		<p>From <a href={recipe.source_url} target="_blank" rel="noreferrer">{recipe.source_domain}</a></p>

		{#if flag.kind === 'closed'}
			<button class="link" onclick={() => (flag = { kind: 'open' })}>Flag a problem with this import</button>
		{:else if flag.kind === 'sent'}
			<p>Thanks. Saved as report #{flag.reportId}.</p>
		{:else}
			<form class="flag" onsubmit={sendFlag}>
				<label for="flag-comment">What's wrong with it?</label>
				<textarea
					id="flag-comment"
					rows="3"
					bind:value={flagComment}
					placeholder="For example: flour should be 250g, or step 4 is missing"
				></textarea>
				<div class="flag-actions">
					<button disabled={flag.kind === 'sending' || !flagComment.trim()}>
						{flag.kind === 'sending' ? 'Sending…' : 'Send'}
					</button>
					<button type="button" class="link" onclick={() => (flag = { kind: 'closed' })}>Cancel</button>
				</div>
				{#if flag.kind === 'open' && flag.error}
					<p role="alert">{flag.error}</p>
				{/if}
			</form>
		{/if}
	</footer>
</article>

<style>
	header img {
		width: 100%;
		max-height: 20rem;
		object-fit: cover;
		border-radius: 0.75rem;
	}

	.facts,
	.labels {
		display: flex;
		flex-wrap: wrap;
		gap: 0.5rem;
		padding: 0;
		list-style: none;
	}

	.facts li,
	.labels li {
		padding: 0.15rem 0.6rem;
		border: 1px solid var(--line);
		border-radius: 999px;
		color: var(--muted);
		font-size: 0.9rem;
	}

	.actions {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 0.5rem;
	}

	.hint {
		color: var(--muted);
	}

	.notes p {
		white-space: pre-line;
	}

	.columns {
		display: grid;
		grid-template-columns: minmax(0, 1fr) minmax(0, 2fr);
		gap: 2rem;
	}

	@media (max-width: 40rem) {
		.columns {
			grid-template-columns: minmax(0, 1fr);
		}
	}

	.ingredients-heading {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		justify-content: space-between;
		gap: 0.5rem;
	}

	h3 {
		margin-bottom: 0.25rem;
		font-size: 1rem;
		color: var(--muted);
	}

	.ingredients {
		padding: 0;
		list-style: none;
	}

	.ingredients li {
		padding: 0.3rem 0;
		border-bottom: 1px solid var(--line);
	}

	.amount {
		font-weight: 600;
	}

	.steps li {
		margin-bottom: 0.75rem;
		padding-left: 0.25rem;
	}

	footer {
		margin-top: 2rem;
		padding-top: 1rem;
		border-top: 1px solid var(--line);
		color: var(--muted);
	}

	.flag {
		display: grid;
		gap: 0.5rem;
		max-width: 32rem;
	}

	.flag-actions {
		display: flex;
		align-items: center;
		gap: 1rem;
	}
</style>
