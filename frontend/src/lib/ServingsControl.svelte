<script lang="ts">
	import { formatCount } from './format';
	import { servingsFor, stepScale } from './scale';

	let {
		servings,
		scale,
		onchange
	}: { servings: number | null; scale: number; onchange: (scale: number) => void } = $props();

	const shown = $derived(servingsFor(servings, scale));
	const atMinimum = $derived(servings ? (shown ?? 1) <= 1 : scale <= 0.5);
</script>

<div class="servings" role="group" aria-label="Servings">
	<button type="button" class="secondary" aria-label="Fewer servings" disabled={atMinimum} onclick={() => onchange(stepScale(servings, scale, -1))}>−</button>
	<span class="value">{servings ? `Serves ${shown}` : `× ${formatCount(scale)}`}</span>
	<button type="button" class="secondary" aria-label="More servings" onclick={() => onchange(stepScale(servings, scale, 1))}>+</button>
	{#if scale !== 1}
		<button type="button" class="link" onclick={() => onchange(1)}>Reset</button>
	{/if}
</div>

<style>
	.servings {
		display: flex;
		align-items: center;
		gap: 0.5rem;
	}

	.servings button.secondary {
		width: 2.4rem;
		padding: 0.35rem 0;
		font-size: 1.1rem;
	}

	.value {
		min-width: 5.5rem;
		text-align: center;
		font-weight: 600;
	}
</style>
