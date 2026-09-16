<script lang="ts">
	import type { FacetValue } from './api';
	import { suggestIngredients } from './suggest';

	let {
		ingredients,
		chosen,
		onchange
	}: { ingredients: FacetValue[]; chosen: string[]; onchange: (next: string[]) => void } = $props();

	let query = $state('');
	let open = $state(false);
	let active = $state(0);
	let input: HTMLInputElement;

	const suggestions = $derived(suggestIngredients(ingredients, query, chosen));

	function choose(name: string) {
		if (!chosen.includes(name)) onchange([...chosen, name]);
		query = '';
		open = false;
		active = 0;
		input.focus();
	}

	function remove(name: string) {
		onchange(chosen.filter((item) => item !== name));
	}

	function onInput() {
		open = true;
		active = 0;
	}

	function onKeydown(event: KeyboardEvent) {
		if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
			event.preventDefault();
			open = true;
			const step = event.key === 'ArrowDown' ? 1 : -1;
			active = (active + step + suggestions.length) % Math.max(suggestions.length, 1);
		} else if (event.key === 'Enter') {
			event.preventDefault();
			const picked = open && suggestions[active] ? suggestions[active] : query.trim().toLowerCase();
			if (picked) choose(picked);
		} else if (event.key === 'Escape') {
			open = false;
		} else if (event.key === 'Backspace' && !query && chosen.length) {
			// Backspace on an empty box takes the last chip off, the way tag inputs usually behave.
			remove(chosen[chosen.length - 1]);
		}
	}
</script>

<div class="ingredient-filter">
	{#each chosen as name (name)}
		<span class="chip">
			{name}
			<button type="button" onclick={() => remove(name)} aria-label="Stop filtering by {name}">✕</button>
		</span>
	{/each}

	<div class="field">
		<input
			bind:this={input}
			bind:value={query}
			role="combobox"
			aria-expanded={open && suggestions.length > 0}
			aria-controls="ingredient-suggestions"
			aria-autocomplete="list"
			aria-label="Filter by ingredient"
			placeholder={chosen.length ? 'And…' : 'Has ingredient'}
			oninput={onInput}
			onkeydown={onKeydown}
			onfocus={() => (open = true)}
			onblur={() => setTimeout(() => (open = false), 120)}
		/>

		{#if open && suggestions.length}
			<ul id="ingredient-suggestions" role="listbox">
				{#each suggestions as name, index (name)}
					<li
						role="option"
						aria-selected={index === active}
						class:active={index === active}
						onmousedown={() => choose(name)}
						onmouseenter={() => (active = index)}
					>
						{name}
					</li>
				{/each}
			</ul>
		{/if}
	</div>
</div>

<style>
	.ingredient-filter {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 0.4rem;
	}

	.chip {
		display: inline-flex;
		align-items: center;
		gap: 0.35rem;
		padding: 0.2rem 0.4rem 0.2rem 0.7rem;
		border-radius: 999px;
		background: var(--accent);
		color: var(--accent-fg);
		font-size: 0.9rem;
	}

	.chip button {
		padding: 0 0.25rem;
		background: none;
		color: inherit;
		font-size: 0.9rem;
		line-height: 1;
		cursor: pointer;
	}

	.field {
		position: relative;
	}

	.field input {
		width: 11rem;
	}

	ul {
		position: absolute;
		z-index: 5;
		top: calc(100% + 0.25rem);
		left: 0;
		min-width: 12rem;
		max-height: 14rem;
		overflow-y: auto;
		margin: 0;
		padding: 0.25rem;
		border: 1px solid var(--line);
		border-radius: 0.5rem;
		background: var(--card);
		box-shadow: 0 8px 24px rgb(0 0 0 / 0.25);
		list-style: none;
	}

	li {
		padding: 0.4rem 0.6rem;
		border-radius: 0.35rem;
		cursor: pointer;
	}

	li.active {
		background: var(--accent);
		color: var(--accent-fg);
	}
</style>
