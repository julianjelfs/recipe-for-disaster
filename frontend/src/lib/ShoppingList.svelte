<script lang="ts">
	import type { Ingredient } from './api';
	import { formatAmount, formatCount } from './format';
	import { shoppingList } from './shopping';

	let {
		recipeId,
		title,
		ingredients,
		scale
	}: { recipeId: number; title: string; ingredients: Ingredient[]; scale: number } = $props();

	let dialog: HTMLDialogElement;
	let ticked = $state<string[]>([]);

	const items = $derived(shoppingList(ingredients, scale));
	const toGet = $derived(items.filter((item) => !ticked.includes(item.key)).length);
	const storageKey = $derived(`shopping-list:${recipeId}`);

	// Ticks live on this device, so they survive the phone locking or the page reloading in a shop.
	function loadTicks(): string[] {
		try {
			const saved = JSON.parse(localStorage.getItem(storageKey) ?? '[]');
			return Array.isArray(saved) ? saved : [];
		} catch {
			return [];
		}
	}

	function saveTicks() {
		try {
			localStorage.setItem(storageKey, JSON.stringify(ticked));
		} catch {
			// Storage blocked (e.g. private browsing): ticks still work until the page reloads.
		}
	}

	function open() {
		ticked = loadTicks();
		dialog.showModal();
	}

	function toggle(key: string) {
		ticked = ticked.includes(key) ? ticked.filter((item) => item !== key) : [...ticked, key];
		saveTicks();
	}

	function untickAll() {
		ticked = [];
		saveTicks();
	}
</script>

<button type="button" class="secondary" onclick={open}>Shopping list</button>

<dialog bind:this={dialog} aria-labelledby="shopping-title">
	<header>
		<h2 id="shopping-title">Shopping list</h2>
		<button type="button" class="link" onclick={() => dialog.close()}>Close</button>
	</header>
	<p class="summary">
		{title}{scale === 1 ? '' : ` (× ${formatCount(scale)})`} · {toGet === 0 ? 'got everything' : `${toGet} of ${items.length} to get`}
	</p>
	<ul>
		{#each items as item (item.key)}
			<li class:ticked={ticked.includes(item.key)}>
				<label>
					<input type="checkbox" checked={ticked.includes(item.key)} onchange={() => toggle(item.key)} />
					<span>
						<strong>{formatAmount(item)}</strong>
						{item.name}{#if item.optional}&nbsp;<em>(optional)</em>{/if}
					</span>
				</label>
			</li>
		{/each}
	</ul>
	{#if ticked.length}
		<button type="button" class="link" onclick={untickAll}>Untick everything</button>
	{/if}
</dialog>

<style>
	dialog {
		width: min(32rem, calc(100vw - 2rem));
		max-height: 85vh;
		padding: 1rem 1.25rem 1.25rem;
		border: 0;
		border-radius: 0.75rem;
		background: var(--card);
		color: var(--fg);
	}

	dialog::backdrop {
		background: rgb(0 0 0 / 0.5);
	}

	/* A sheet up from the bottom on phones, where it's easiest to reach. */
	@media (max-width: 40rem) {
		dialog {
			width: 100vw;
			max-width: 100vw;
			margin: auto 0 0;
			padding-bottom: max(1.25rem, env(safe-area-inset-bottom));
			border-radius: 0.75rem 0.75rem 0 0;
		}
	}

	header {
		display: flex;
		align-items: baseline;
		justify-content: space-between;
	}

	h2 {
		margin: 0;
	}

	.summary {
		margin: 0.25rem 0 0.75rem;
		color: var(--muted);
	}

	ul {
		margin: 0 0 0.75rem;
		padding: 0;
		list-style: none;
	}

	li {
		border-bottom: 1px solid var(--line);
	}

	label {
		display: flex;
		align-items: center;
		gap: 0.75rem;
		padding: 0.65rem 0;
		cursor: pointer;
	}

	input {
		flex: none;
		width: 1.3rem;
		height: 1.3rem;
		accent-color: var(--accent);
	}

	li.ticked span {
		color: var(--muted);
		text-decoration: line-through;
	}
</style>
