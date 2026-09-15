<script lang="ts">
	import { goto, replaceState } from '$app/navigation';
	import { page } from '$app/state';
	import { onMount, untrack } from 'svelte';
	import { alarm, unlockSound } from '$lib/alarm';
	import type { Ingredient } from '$lib/api';
	import { formatClock, nextStep, previousStep, remainingMs, stepFromParam, type Timer } from '$lib/cook';
	import { formatAmount, formatCount, formatTimer } from '$lib/format';
	import { parseScale, scaleAmount } from '$lib/scale';
	import { keepScreenOn } from '$lib/wakelock';

	// A finished timer rings this many times, this far apart, unless dismissed.
	const RINGS = 5;
	const RING_EVERY_MS = 4000;
	const SWIPE_PX = 60;

	let { data } = $props();
	const recipe = $derived(data.recipe);
	const scale = $derived(parseScale(page.url.searchParams.get('scale')));
	const recipeHref = $derived(`/r/${recipe.id}${scale === 1 ? '' : `?scale=${scale}`}`);

	let index = $state(untrack(() => stepFromParam(page.url.searchParams.get('step'), data.recipe.steps.length)));
	const step = $derived(recipe.steps[index]);
	const isLast = $derived(index === recipe.steps.length - 1);
	const scaled = $derived(new Map(recipe.ingredients.map((ingredient) => [ingredient.id, scaleAmount(ingredient, scale)])));
	const stepIngredients = $derived(
		step.ingredient_ids.map((id) => scaled.get(id)).filter((ingredient): ingredient is Ingredient => !!ingredient)
	);

	let overview = $state(false);
	let screenOn = $state(false);
	let fullscreen = $state(false);
	const canFullscreen = document.fullscreenEnabled;

	let timers = $state<Timer[]>([]);
	let now = $state(Date.now());
	let nextTimerId = 1;
	const stepTimer = $derived(timers.find((timer) => timer.stepNumber === index + 1));
	// Timer id -> how many times it has rung and when it last did. Not shown, so not reactive.
	const rings = new Map<number, { count: number; at: number }>();

	let container: HTMLDivElement;

	/** Keep the step in the URL so a reload returns to the same place. */
	function goTo(target: number) {
		index = target;
		const url = new URL(page.url);
		url.searchParams.set('step', String(target + 1));
		replaceState(url, {});
	}

	function next() {
		if (isLast) goto(recipeHref);
		else goTo(nextStep(index, recipe.steps.length));
	}

	function back() {
		goTo(previousStep(index));
	}

	function startTimer() {
		if (!step.timer_seconds || stepTimer) return;
		unlockSound();
		timers.push({
			id: nextTimerId++,
			label: `Step ${index + 1}`,
			stepNumber: index + 1,
			endsAt: Date.now() + step.timer_seconds * 1000
		});
	}

	function removeTimer(id: number) {
		timers = timers.filter((timer) => timer.id !== id);
		rings.delete(id);
	}

	async function toggleFullscreen() {
		try {
			if (document.fullscreenElement) await document.exitFullscreen();
			else await document.documentElement.requestFullscreen();
		} catch {
			// The browser refused; the page still works without it.
		}
	}

	function onKeydown(event: KeyboardEvent) {
		if (overview) return;
		if (['ArrowRight', 'PageDown', ' '].includes(event.key)) {
			event.preventDefault();
			next();
		} else if (['ArrowLeft', 'PageUp'].includes(event.key)) {
			event.preventDefault();
			back();
		}
	}

	onMount(() => {
		const stopWakeLock = keepScreenOn((active) => (screenOn = active));

		let swipeStart: { x: number; y: number } | null = null;
		const onPointerDown = (event: PointerEvent) => (swipeStart = { x: event.clientX, y: event.clientY });
		const onPointerUp = (event: PointerEvent) => {
			if (!swipeStart || overview) return;
			const dx = event.clientX - swipeStart.x;
			const dy = event.clientY - swipeStart.y;
			swipeStart = null;
			if (Math.abs(dx) > SWIPE_PX && Math.abs(dx) > Math.abs(dy) * 1.5) {
				if (dx < 0) next();
				else back();
			}
		};
		container.addEventListener('pointerdown', onPointerDown);
		container.addEventListener('pointerup', onPointerUp);

		const tick = setInterval(() => {
			now = Date.now();
			for (const timer of timers) {
				if (remainingMs(timer, now) > 0) continue;
				const rung = rings.get(timer.id);
				if (!rung || (rung.count < RINGS && now - rung.at >= RING_EVERY_MS)) {
					alarm();
					rings.set(timer.id, { count: (rung?.count ?? 0) + 1, at: now });
				}
			}
		}, 250);

		return () => {
			stopWakeLock();
			container.removeEventListener('pointerdown', onPointerDown);
			container.removeEventListener('pointerup', onPointerUp);
			clearInterval(tick);
		};
	});
</script>

<svelte:window onkeydown={onKeydown} />
<svelte:document onfullscreenchange={() => (fullscreen = !!document.fullscreenElement)} />

<svelte:head>
	<title>Cooking {recipe.title}</title>
</svelte:head>

<div class="cook" bind:this={container}>
	<header>
		<a class="exit" href={recipeHref} aria-label="Leave cooking mode">✕</a>
		<div class="where">
			<span class="title">{recipe.title}</span>
			<span class="position">
				Step {index + 1} of {recipe.steps.length}{screenOn ? '' : ' · the screen may sleep'}
			</span>
		</div>
		<button class="secondary" aria-expanded={overview} onclick={() => (overview = !overview)}>
			{overview ? 'Back to step' : 'All steps'}
		</button>
		{#if canFullscreen}
			<button class="secondary" onclick={toggleFullscreen}>{fullscreen ? 'Exit full screen' : 'Full screen'}</button>
		{/if}
	</header>

	<div class="progress" style:--done={(index + 1) / recipe.steps.length}></div>

	{#if overview}
		<section class="overview">
			<h2>Ingredients{scale === 1 ? '' : ` (× ${formatCount(scale)})`}</h2>
			<ul class="ingredient-list">
				{#each recipe.ingredients as ingredient (ingredient.id)}
					{@const amount = scaled.get(ingredient.id)}
					<li>
						<strong>{amount ? formatAmount(amount) : ''}</strong>
						{ingredient.name}{#if ingredient.preparation}, {ingredient.preparation}{/if}
					</li>
				{/each}
			</ul>
			<h2>Steps</h2>
			<ol class="step-list">
				{#each recipe.steps as item, itemIndex (item.id)}
					<li>
						<button
							class="step-link"
							class:current={itemIndex === index}
							onclick={() => {
								goTo(itemIndex);
								overview = false;
							}}
						>
							{item.text}
						</button>
					</li>
				{/each}
			</ol>
		</section>
	{:else}
		<section class="step" aria-live="polite">
			<p class="text">{step.text}</p>

			{#if stepIngredients.length}
				<ul class="uses">
					{#each stepIngredients as ingredient (ingredient.id)}
						<li><strong>{formatAmount(ingredient)}</strong> {ingredient.name}</li>
					{/each}
				</ul>
			{/if}

			{#if scale !== 1 && stepIngredients.length}
				<p class="scale-note">Amounts above are for × {formatCount(scale)}. Amounts written in the step aren't.</p>
			{/if}

			{#if step.timer_seconds}
				<button class="timer-start" onclick={startTimer} disabled={!!stepTimer}>
					{stepTimer ? 'Timer running' : `Start ${formatTimer(step.timer_seconds)} timer`}
				</button>
			{/if}
		</section>
	{/if}

	{#if timers.length}
		<ul class="timers">
			{#each timers as timer (timer.id)}
				{@const left = remainingMs(timer, now)}
				<li class:done={left === 0}>
					<span>{timer.label}</span>
					<span class="clock">{left === 0 ? 'Done' : formatClock(left)}</span>
					<button class="link" onclick={() => removeTimer(timer.id)}>{left === 0 ? 'Dismiss' : 'Cancel'}</button>
				</li>
			{/each}
		</ul>
	{/if}

	<nav class="controls">
		<button class="secondary" onclick={back} disabled={index === 0}>Back</button>
		<button onclick={next}>{isLast ? 'Finish' : 'Next'}</button>
	</nav>
</div>

<style>
	.cook {
		position: fixed;
		inset: 0;
		z-index: 10;
		display: flex;
		flex-direction: column;
		padding: max(0.75rem, env(safe-area-inset-top)) max(1rem, env(safe-area-inset-right))
			max(0.75rem, env(safe-area-inset-bottom)) max(1rem, env(safe-area-inset-left));
		background: var(--bg);
		touch-action: pan-y;
	}

	header {
		display: flex;
		align-items: center;
		gap: 0.75rem;
	}

	.exit {
		padding: 0.25rem 0.5rem;
		color: var(--fg);
		font-size: 1.5rem;
		text-decoration: none;
	}

	.where {
		display: flex;
		flex: 1;
		flex-direction: column;
		min-width: 0;
	}

	.title {
		overflow: hidden;
		font-weight: 600;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.position {
		color: var(--muted);
		font-size: 0.9rem;
	}

	.progress {
		height: 0.3rem;
		margin: 0.75rem 0;
		border-radius: 1rem;
		background: linear-gradient(to right, var(--accent) calc(var(--done) * 100%), var(--line) 0);
	}

	.step,
	.overview {
		flex: 1;
		overflow-y: auto;
	}

	.step {
		display: flex;
		flex-direction: column;
		justify-content: center;
		max-width: 50rem;
		width: 100%;
		margin: 0 auto;
	}

	.text {
		margin: 0 0 1.5rem;
		font-size: clamp(1.6rem, 4.5vw, 3rem);
		line-height: 1.35;
	}

	.uses {
		display: flex;
		flex-wrap: wrap;
		gap: 0.5rem;
		margin: 0 0 1rem;
		padding: 0;
		list-style: none;
		font-size: clamp(1rem, 2.5vw, 1.4rem);
	}

	.uses li {
		padding: 0.35rem 0.8rem;
		border: 1px solid var(--line);
		border-radius: 999px;
		background: var(--card);
	}

	.scale-note {
		color: var(--muted);
	}

	.timer-start {
		align-self: flex-start;
		padding: 0.8rem 1.4rem;
		font-size: 1.2rem;
	}

	.overview {
		max-width: 50rem;
		width: 100%;
		margin: 0 auto;
	}

	.ingredient-list {
		padding: 0;
		list-style: none;
	}

	.ingredient-list li {
		padding: 0.3rem 0;
		border-bottom: 1px solid var(--line);
	}

	.step-list {
		padding-left: 1.5rem;
	}

	.step-link {
		width: 100%;
		margin: 0.25rem 0;
		padding: 0.5rem 0.75rem;
		border: 1px solid transparent;
		background: none;
		color: var(--fg);
		font-weight: normal;
		text-align: left;
	}

	.step-link.current {
		border-color: var(--accent);
	}

	.timers {
		display: flex;
		flex-wrap: wrap;
		gap: 0.5rem;
		margin: 0.75rem 0 0;
		padding: 0;
		list-style: none;
	}

	.timers li {
		display: flex;
		align-items: center;
		gap: 0.75rem;
		padding: 0.4rem 0.9rem;
		border: 1px solid var(--line);
		border-radius: 999px;
		background: var(--card);
	}

	.clock {
		font-size: 1.3rem;
		font-variant-numeric: tabular-nums;
		font-weight: 700;
	}

	.timers li.done {
		border-color: var(--accent);
		animation: flash 1s steps(2) infinite;
	}

	@keyframes flash {
		50% {
			background: var(--accent);
			color: var(--accent-fg);
		}
	}

	.controls {
		display: grid;
		grid-template-columns: 1fr 2fr;
		gap: 0.75rem;
		margin-top: 0.75rem;
	}

	.controls button {
		padding: 1.1rem;
		font-size: 1.3rem;
	}
</style>
