<script lang="ts">
	import { goto } from '$app/navigation';
	import { untrack } from 'svelte';
	import { COURSES, DIETS, UNITS, toApiError, updateRecipe, type ApiError } from '$lib/api';
	import { move, splitList, toEdit } from '$lib/edit';

	let { data } = $props();

	// The form edits a copy taken when the page opens.
	const recipeId = untrack(() => data.recipe.id);
	let edit = $state(untrack(() => toEdit(data.recipe)));
	let equipment = $state(untrack(() => data.recipe.equipment.join(', ')));
	let techniques = $state(untrack(() => data.recipe.techniques.join(', ')));
	let tags = $state(untrack(() => data.recipe.tags.join(', ')));

	let saving = $state(false);
	let error = $state<ApiError | null>(null);
	let nextKey = 0;

	function addIngredient() {
		edit.ingredients.push({
			key: `new-${nextKey++}`,
			group: edit.ingredients.at(-1)?.group ?? null,
			quantity: null,
			quantity_max: null,
			unit: null,
			name: '',
			canonical_name: '',
			preparation: null,
			optional: false
		});
	}

	function removeIngredient(index: number) {
		const [removed] = edit.ingredients.splice(index, 1);
		for (const step of edit.steps) {
			step.ingredient_keys = step.ingredient_keys.filter((key) => key !== removed.key);
		}
	}

	function addStep() {
		edit.steps.push({ text: '', timer_seconds: null, ingredient_keys: [] });
	}

	function toggleStepIngredient(stepIndex: number, key: string) {
		const step = edit.steps[stepIndex];
		step.ingredient_keys = step.ingredient_keys.includes(key)
			? step.ingredient_keys.filter((item) => item !== key)
			: [...step.ingredient_keys, key];
	}

	function setTimerMinutes(stepIndex: number, minutes: string) {
		edit.steps[stepIndex].timer_seconds = minutes === '' ? null : Math.round(Number(minutes) * 60);
	}

	function blankToNull(value: string | null): string | null {
		return value && value.trim() ? value.trim() : null;
	}

	async function save(event: SubmitEvent) {
		event.preventDefault();
		saving = true;
		error = null;
		const draft = $state.snapshot(edit);
		try {
			await updateRecipe(recipeId, {
				...draft,
				cuisine: blankToNull(draft.cuisine),
				ingredients: draft.ingredients.map((ingredient) => ({
					...ingredient,
					group: blankToNull(ingredient.group),
					preparation: blankToNull(ingredient.preparation),
					canonical_name: ingredient.canonical_name.trim() || ingredient.name.trim().toLowerCase()
				})),
				equipment: splitList(equipment),
				techniques: splitList(techniques),
				tags: splitList(tags)
			});
			await goto(`/r/${recipeId}`);
		} catch (e) {
			error = toApiError(e);
		} finally {
			saving = false;
		}
	}
</script>

<svelte:head>
	<title>Edit {edit.title}</title>
</svelte:head>

<h1>Edit recipe</h1>

<form onsubmit={save}>
	<fieldset>
		<legend>About</legend>
		<label class="wide">Title <input required bind:value={edit.title} /></label>
		<div class="grid">
			<label>Serves <input type="number" min="1" bind:value={edit.servings} /></label>
			<label>Prep (min) <input type="number" min="0" bind:value={edit.prep_minutes} /></label>
			<label>Cook (min) <input type="number" min="0" bind:value={edit.cook_minutes} /></label>
			<label>Total (min) <input type="number" min="0" bind:value={edit.total_minutes} /></label>
			<label>
				Complexity
				<select bind:value={edit.complexity}>
					{#each [1, 2, 3, 4, 5] as level (level)}
						<option value={level}>{level}</option>
					{/each}
				</select>
			</label>
			<label>
				Course
				<select bind:value={edit.course}>
					<option value={null}>none</option>
					{#each COURSES as course (course)}
						<option value={course}>{course}</option>
					{/each}
				</select>
			</label>
			<label>Cuisine <input bind:value={edit.cuisine} /></label>
		</div>
		<div class="checks">
			{#each DIETS as diet (diet)}
				<label class="check"><input type="checkbox" value={diet} bind:group={edit.diet} /> {diet}</label>
			{/each}
		</div>
		<label class="wide">Equipment <input bind:value={equipment} placeholder="Comma separated" /></label>
		<label class="wide">Techniques <input bind:value={techniques} placeholder="Comma separated" /></label>
		<label class="wide">Tags <input bind:value={tags} placeholder="Comma separated, e.g. family favourite" /></label>
		<label class="wide">Notes <textarea rows="3" bind:value={edit.notes}></textarea></label>
	</fieldset>

	<fieldset>
		<legend>Ingredients</legend>
		{#each edit.ingredients as ingredient, index (ingredient.key)}
			<div class="item">
				<div class="row">
					<input class="number" type="number" step="any" min="0" placeholder="Qty" aria-label="Quantity" bind:value={ingredient.quantity} />
					<input class="number" type="number" step="any" min="0" placeholder="to" aria-label="Up to quantity" bind:value={ingredient.quantity_max} />
					<select aria-label="Unit" bind:value={ingredient.unit}>
						<option value={null}>no unit</option>
						{#each UNITS as unit (unit)}
							<option value={unit}>{unit}</option>
						{/each}
					</select>
					<input class="grow" placeholder="Name" aria-label="Name" required bind:value={ingredient.name} />
				</div>
				<div class="row">
					<input class="grow" placeholder="Preparation" aria-label="Preparation" bind:value={ingredient.preparation} />
					<input class="grow" placeholder="Search as" aria-label="Search as" bind:value={ingredient.canonical_name} />
					<input class="grow" placeholder="Group" aria-label="Group" bind:value={ingredient.group} />
					<label class="check"><input type="checkbox" bind:checked={ingredient.optional} /> optional</label>
					<span class="row-actions">
						<button type="button" class="icon" aria-label="Move up" disabled={index === 0} onclick={() => move(edit.ingredients, index, -1)}>↑</button>
						<button type="button" class="icon" aria-label="Move down" disabled={index === edit.ingredients.length - 1} onclick={() => move(edit.ingredients, index, 1)}>↓</button>
						<button type="button" class="icon" aria-label="Remove ingredient" onclick={() => removeIngredient(index)}>✕</button>
					</span>
				</div>
			</div>
		{/each}
		<button type="button" class="secondary" onclick={addIngredient}>Add ingredient</button>
	</fieldset>

	<fieldset>
		<legend>Method</legend>
		{#each edit.steps as step, index (step)}
			<div class="item">
				<div class="row">
					<span class="step-number">{index + 1}</span>
					<textarea class="grow" rows="3" aria-label="Step {index + 1}" required bind:value={step.text}></textarea>
				</div>
				<div class="row">
					<label>
						Timer (min)
						<input
							class="number"
							type="number"
							step="any"
							min="0"
							value={step.timer_seconds === null ? '' : step.timer_seconds / 60}
							oninput={(e) => setTimerMinutes(index, e.currentTarget.value)}
						/>
					</label>
					<details class="grow">
						<summary>Uses {step.ingredient_keys.length} ingredient{step.ingredient_keys.length === 1 ? '' : 's'}</summary>
						<div class="checks">
							{#each edit.ingredients as ingredient (ingredient.key)}
								<label class="check">
									<input
										type="checkbox"
										checked={step.ingredient_keys.includes(ingredient.key)}
										onchange={() => toggleStepIngredient(index, ingredient.key)}
									/>
									{ingredient.name || 'unnamed'}
								</label>
							{/each}
						</div>
					</details>
					<span class="row-actions">
						<button type="button" class="icon" aria-label="Move step up" disabled={index === 0} onclick={() => move(edit.steps, index, -1)}>↑</button>
						<button type="button" class="icon" aria-label="Move step down" disabled={index === edit.steps.length - 1} onclick={() => move(edit.steps, index, 1)}>↓</button>
						<button type="button" class="icon" aria-label="Remove step" onclick={() => edit.steps.splice(index, 1)}>✕</button>
					</span>
				</div>
			</div>
		{/each}
		<button type="button" class="secondary" onclick={addStep}>Add step</button>
	</fieldset>

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

	<div class="save">
		<button disabled={saving}>{saving ? 'Saving…' : 'Save'}</button>
		<a href="/r/{recipeId}">Cancel</a>
	</div>
</form>

<style>
	fieldset {
		display: grid;
		gap: 0.75rem;
		margin: 0 0 1.5rem;
		padding: 1rem;
		border: 1px solid var(--line);
		border-radius: 0.75rem;
	}

	legend {
		padding: 0 0.25rem;
		font-weight: 700;
	}

	label {
		display: grid;
		gap: 0.2rem;
		color: var(--muted);
		font-size: 0.9rem;
	}

	label input,
	label select,
	label textarea {
		color: var(--fg);
		font-size: 1rem;
	}

	.grid {
		display: grid;
		grid-template-columns: repeat(auto-fill, minmax(8rem, 1fr));
		gap: 0.75rem;
	}

	.checks {
		display: flex;
		flex-wrap: wrap;
		gap: 0.25rem 1rem;
		padding-top: 0.5rem;
	}

	.check {
		display: flex;
		align-items: center;
		gap: 0.35rem;
		color: var(--fg);
	}

	.item {
		display: grid;
		gap: 0.4rem;
		padding-bottom: 0.75rem;
		border-bottom: 1px solid var(--line);
	}

	.row {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 0.4rem;
	}

	.grow {
		flex: 1 1 10rem;
		min-width: 0;
	}

	.number {
		width: 5rem;
	}

	.step-number {
		align-self: start;
		min-width: 1.5rem;
		padding-top: 0.6rem;
		font-weight: 700;
	}

	.row-actions {
		display: flex;
		gap: 0.25rem;
		margin-left: auto;
	}

	.icon {
		padding: 0.35rem 0.6rem;
		background: var(--card);
		border: 1px solid var(--line);
		color: var(--fg);
	}

	summary {
		cursor: pointer;
		color: var(--muted);
	}

	.save {
		display: flex;
		align-items: center;
		gap: 1rem;
	}
</style>
