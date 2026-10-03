<script lang="ts">
	import { goto } from '$app/navigation';
	import { page } from '$app/state';
	import { onDestroy, onMount } from 'svelte';
	import { ApiError, importRecipe, photographRecipe } from '$lib/api';
	import { prepare } from '$lib/photos';
	import { sharedUrl } from '$lib/share';

	// Matches the API's limit. A recipe rarely runs past two pages.
	const MAX_PHOTOS = 4;

	const shared = sharedUrl(page.url.searchParams);

	let url = $state(shared);
	let photos = $state<{ file: File; preview: string }[]>([]);
	let busy = $state<'url' | 'photos' | null>(null);
	let error = $state<ApiError | null>(null);

	async function runImport() {
		busy = 'url';
		error = null;
		try {
			const recipe = await importRecipe(url.trim());
			await goto(`/r/${recipe.id}`, { replaceState: true });
		} catch (e) {
			error = e instanceof ApiError ? e : new ApiError(0, String(e));
		} finally {
			busy = null;
		}
	}

	function addPhotos(event: Event) {
		const input = event.currentTarget as HTMLInputElement;
		const room = MAX_PHOTOS - photos.length;
		const chosen = [...(input.files ?? [])].slice(0, room);
		photos = [...photos, ...chosen.map((file) => ({ file, preview: URL.createObjectURL(file) }))];
		// Lets the same photo be chosen again after removing it.
		input.value = '';
	}

	function removePhoto(index: number) {
		URL.revokeObjectURL(photos[index].preview);
		photos = photos.filter((_, i) => i !== index);
	}

	async function readPhotos() {
		busy = 'photos';
		error = null;
		try {
			let uploads;
			try {
				uploads = await Promise.all(photos.map((photo) => prepare(photo.file)));
			} catch {
				throw new ApiError(0, "Couldn't open one of those photos. Try taking it again, or choose a JPEG.");
			}
			const recipe = await photographRecipe(uploads);
			await goto(`/r/${recipe.id}`, { replaceState: true });
		} catch (e) {
			error = e instanceof ApiError ? e : new ApiError(0, String(e));
		} finally {
			busy = null;
		}
	}

	onDestroy(() => photos.forEach((photo) => URL.revokeObjectURL(photo.preview)));

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
		<input id="url" type="url" required placeholder="https://" bind:value={url} disabled={busy !== null} />
		<button disabled={busy !== null || !url.trim()}>{busy === 'url' ? 'Importing…' : 'Import'}</button>
	</div>
</form>

{#if busy === 'url'}
	<p class="hint">Fetching the page and tidying the recipe. This takes a few seconds.</p>
{/if}

<section class="photos">
	<h2>Or photograph a recipe book</h2>
	<p class="hint">One photo per page, up to {MAX_PHOTOS}, in page order. Flat and well lit reads best.</p>

	{#if photos.length}
		<ol class="thumbs">
			{#each photos as photo, index (photo.preview)}
				<li>
					<img src={photo.preview} alt="Page {index + 1}" />
					<button class="remove" aria-label="Remove page {index + 1}" onclick={() => removePhoto(index)} disabled={busy !== null}>✕</button>
				</li>
			{/each}
		</ol>
	{/if}

	<div class="row">
		{#if photos.length < MAX_PHOTOS}
			<!-- Two inputs: on Android, `multiple` hides the camera, and `capture` hides the library. -->
			<label class="pick" class:primary={!photos.length} class:disabled={busy !== null}>
				{photos.length ? 'Photograph next page' : 'Take a photo'}
				<input type="file" accept="image/*" capture="environment" onchange={addPhotos} disabled={busy !== null} />
			</label>
			<label class="pick" class:disabled={busy !== null}>
				Choose from library
				<input type="file" accept="image/*" multiple onchange={addPhotos} disabled={busy !== null} />
			</label>
		{/if}
		{#if photos.length}
			<button onclick={readPhotos} disabled={busy !== null}>{busy === 'photos' ? 'Reading…' : 'Read recipe'}</button>
		{/if}
	</div>

	{#if busy === 'photos'}
		<p class="hint">Claude is reading the page. This takes 10 to 20 seconds.</p>
	{/if}
</section>

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

	.photos {
		margin-top: 2.5rem;
	}

	.photos h2 {
		font-size: 1.15rem;
	}

	.thumbs {
		display: flex;
		flex-wrap: wrap;
		gap: 0.5rem;
		margin: 0 0 0.75rem;
		padding: 0;
		list-style: none;
	}

	.thumbs li {
		position: relative;
	}

	.thumbs img {
		display: block;
		width: 6rem;
		height: 8rem;
		border: 1px solid var(--line);
		border-radius: 0.5rem;
		object-fit: cover;
	}

	.remove {
		position: absolute;
		top: 0.25rem;
		right: 0.25rem;
		padding: 0.1rem 0.4rem;
		border-radius: 999px;
		font-size: 0.8rem;
	}

	/* The file input is inside its label, so tapping the button opens the camera or library. */
	.pick {
		position: relative;
		display: inline-block;
		margin: 0;
		padding: 0.6rem 1rem;
		border: 1px solid var(--line);
		border-radius: 0.5rem;
		background: var(--card);
		color: var(--fg);
		font-weight: 600;
		cursor: pointer;
	}

	.pick input {
		position: absolute;
		width: 1px;
		height: 1px;
		opacity: 0;
	}

	.pick.primary {
		border-color: var(--accent);
		background: var(--accent);
		color: var(--accent-fg);
	}

	.photos .row {
		flex-wrap: wrap;
	}

	.pick.disabled {
		opacity: 0.5;
		pointer-events: none;
	}
</style>
