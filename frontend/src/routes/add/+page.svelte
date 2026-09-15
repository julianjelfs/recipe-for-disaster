<script lang="ts">
	import { goto } from '$app/navigation';
	import { page } from '$app/state';
	import { onMount } from 'svelte';
	import { ApiError, importRecipe } from '$lib/api';

	// Share targets and shortcuts pass the link as ?url=, or sometimes inside ?text=.
	const shared = page.url.searchParams.get('url') ?? page.url.searchParams.get('text')?.match(/https?:\/\/\S+/)?.[0] ?? '';

	let url = $state(shared);
	let busy = $state(false);
	let error = $state<ApiError | null>(null);

	async function runImport() {
		busy = true;
		error = null;
		try {
			const recipe = await importRecipe(url.trim());
			await goto(`/r/${recipe.id}`, { replaceState: true });
		} catch (e) {
			error = e instanceof ApiError ? e : new ApiError(0, String(e));
		} finally {
			busy = false;
		}
	}

	function submit(event: SubmitEvent) {
		event.preventDefault();
		runImport();
	}

	onMount(() => {
		if (shared) runImport();
	});
</script>

<svelte:head>
	<title>Add a recipe</title>
</svelte:head>

<h1>Add a recipe</h1>

<form onsubmit={submit}>
	<label for="url">Recipe URL</label>
	<div class="row">
		<input id="url" type="url" required placeholder="https://" bind:value={url} disabled={busy} />
		<button disabled={busy || !url.trim()}>{busy ? 'Importing…' : 'Import'}</button>
	</div>
</form>

{#if busy}
	<p class="hint">Fetching the page and tidying the recipe. This takes a few seconds.</p>
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
	label {
		display: block;
		margin-bottom: 0.25rem;
		color: var(--muted);
	}

	.row {
		display: flex;
		gap: 0.5rem;
	}

	input {
		flex: 1;
		min-width: 0;
	}

	.hint {
		color: var(--muted);
	}

	.error {
		margin-top: 1rem;
		padding: 0.75rem 1rem;
		border-radius: 0.5rem;
		background: var(--danger-bg);
	}

	.error p {
		margin: 0;
	}
</style>
