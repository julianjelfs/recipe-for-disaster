<script lang="ts">
	import { goto } from '$app/navigation';
	import { ApiError, createRecipe, toApiError } from '$lib/api';

	const EXAMPLES = [
		'something warming with butternut squash and chorizo, for 4, under an hour',
		'a midweek pasta using what a corner shop sells',
		'a lemon drizzle traybake for a school bake sale',
		'a vegan curry with whatever keeps in the cupboard'
	];

	let brief = $state('');
	let busy = $state(false);
	let error = $state<ApiError | null>(null);

	async function submit(event: SubmitEvent) {
		event.preventDefault();
		busy = true;
		error = null;
		try {
			const recipe = await createRecipe(brief.trim());
			await goto(`/r/${recipe.id}`, { replaceState: true });
		} catch (e) {
			error = toApiError(e);
		} finally {
			busy = false;
		}
	}
</script>

<svelte:head>
	<title>Create a recipe</title>
</svelte:head>

<h1>Create a recipe</h1>
<p class="lead">Say what you fancy and Claude will invent a recipe for it. Delete it if it's no good.</p>

<form onsubmit={submit}>
	<label for="brief">What are you after?</label>
	<textarea
		id="brief"
		rows="3"
		required
		maxlength="500"
		placeholder="something warming with butternut squash and chorizo, for 4, under an hour"
		bind:value={brief}
		disabled={busy}
	></textarea>
	<div class="actions">
		<button disabled={busy || !brief.trim()}>{busy ? 'Inventing…' : 'Create recipe'}</button>
		<span class="count">{brief.length}/500</span>
	</div>
</form>

<p class="hint">Mention servings, a time limit, ingredients to use up, or anything you can't eat.</p>

<ul class="examples">
	{#each EXAMPLES as example (example)}
		<li><button type="button" class="link" onclick={() => (brief = example)} disabled={busy}>{example}</button></li>
	{/each}
</ul>

{#if busy}
	<p class="hint">Writing the recipe. This takes a few seconds.</p>
{/if}

{#if error}
	<div class="error" role="alert">
		<p>{error.message}</p>
		{#if error.errors.length}
			<ul>
				{#each error.errors as message, index (index)}
					<li>{message}</li>
				{/each}
			</ul>
		{/if}
	</div>
{/if}

<style>
	.lead {
		color: var(--muted);
	}

	label {
		display: block;
		margin-bottom: 0.25rem;
		color: var(--muted);
	}

	textarea {
		width: 100%;
		font-size: 1.05rem;
	}

	.actions {
		display: flex;
		align-items: center;
		gap: 0.75rem;
		margin-top: 0.5rem;
	}

	.count {
		color: var(--muted);
		font-size: 0.85rem;
	}

	.hint {
		color: var(--muted);
	}

	.examples {
		padding: 0;
		list-style: none;
	}

	.examples li {
		margin-bottom: 0.35rem;
	}

	.examples button {
		text-align: left;
	}
</style>
