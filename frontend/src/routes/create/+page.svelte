<script lang="ts">
	import { goto } from '$app/navigation';
	import { ApiError, createRecipe, toApiError } from '$lib/api';
	import { FLAVOURS, briefRoom, composeBrief, type Flavour } from '$lib/flavours';

	const EXAMPLES = [
		'something warming with butternut squash and chorizo, for 4, under an hour',
		'a midweek pasta using what a corner shop sells',
		'a lemon drizzle traybake for a school bake sale',
		'a vegan curry with whatever keeps in the cupboard'
	];

	// Remembered on this device, so a vegetarian household ticks it once.
	const VEGETARIAN_KEY = 'create:vegetarian';

	let brief = $state('');
	let flavour = $state<Flavour | undefined>(undefined);
	let vegetarian = $state(loadVegetarian());
	let busy = $state(false);
	let error = $state<ApiError | null>(null);

	const room = $derived(briefRoom(flavour, vegetarian));
	const composed = $derived(composeBrief(brief, flavour, vegetarian));

	function loadVegetarian(): boolean {
		try {
			return localStorage.getItem(VEGETARIAN_KEY) !== 'false';
		} catch {
			return true;
		}
	}

	function saveVegetarian() {
		try {
			localStorage.setItem(VEGETARIAN_KEY, String(vegetarian));
		} catch {
			// Storage blocked (e.g. private browsing): the box still works until the page reloads.
		}
	}

	function pick(choice: Flavour) {
		flavour = flavour?.key === choice.key ? undefined : choice;
	}

	async function submit(event: SubmitEvent) {
		event.preventDefault();
		busy = true;
		error = null;
		try {
			const recipe = await createRecipe(composed);
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
	<fieldset class="flavours" disabled={busy}>
		<legend>Build it on a flavour base</legend>
		<div class="chips">
			{#each FLAVOURS as choice (choice.key)}
				<button
					type="button"
					class="chip"
					class:on={flavour?.key === choice.key}
					aria-pressed={flavour?.key === choice.key}
					onclick={() => pick(choice)}>{choice.name}</button
				>
			{/each}
		</div>
		{#if flavour}
			<p class="pantry">{flavour.from}: {flavour.pantry}</p>
		{/if}
	</fieldset>

	<label for="brief">What are you after?{#if flavour}<span class="optional"> Optional with a base.</span>{/if}</label>
	<textarea
		id="brief"
		rows="3"
		required={!flavour}
		maxlength={room}
		placeholder="something warming with butternut squash and chorizo, for 4, under an hour"
		bind:value={brief}
		disabled={busy}
	></textarea>
	<div class="actions">
		<button disabled={busy || !composed || brief.length > room}>{busy ? 'Inventing…' : 'Create recipe'}</button>
		<label class="vegetarian">
			<input type="checkbox" bind:checked={vegetarian} onchange={saveVegetarian} disabled={busy} /> Vegetarian
		</label>
		<span class="count" class:over={brief.length > room}>{brief.length}/{room}</span>
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

	.count.over {
		color: var(--accent);
	}

	.flavours {
		margin: 0 0 1rem;
		padding: 0;
		border: none;
	}

	.flavours legend {
		margin-bottom: 0.4rem;
		padding: 0;
		color: var(--muted);
	}

	.chips {
		display: flex;
		flex-wrap: wrap;
		gap: 0.4rem;
	}

	.chip {
		padding: 0.2rem 0.7rem;
		border: 1px solid var(--line);
		border-radius: 999px;
		background: var(--bg);
		color: var(--fg);
		font-weight: normal;
	}

	.chip.on {
		border-color: var(--accent);
		background: var(--accent);
		color: var(--accent-fg);
	}

	.pantry {
		margin: 0.5rem 0 0;
		color: var(--muted);
		font-size: 0.9rem;
	}

	.optional {
		font-size: 0.85rem;
	}

	.vegetarian {
		display: flex;
		align-items: center;
		gap: 0.3rem;
		margin: 0;
		color: var(--fg);
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
