<script lang="ts">
	import { courseArt } from './course-art';

	let {
		src,
		course,
		title,
		eager = false
	}: { src: string | null; course: string | null; title: string; eager?: boolean } = $props();

	// Photos are hotlinked, so they go missing when a site moves them or there's no signal.
	let failed = $state(false);
</script>

{#if src && !failed}
	<img {src} alt="" loading={eager ? 'eager' : 'lazy'} referrerpolicy="no-referrer" onerror={() => (failed = true)} />
{:else}
	<!-- No photo: invented recipes never have one, plenty of imported pages don't either, and a hotlinked one can fail. -->
	<div class="art">
		<img src={courseArt(course)} alt="" aria-hidden="true" />
		<span class="visually-hidden">No photo of {title}</span>
	</div>
{/if}

<style>
	.art {
		display: grid;
		place-items: center;
		background: var(--line);
	}

	.art img {
		width: 44%;
		height: auto;
		opacity: 0.85;
	}

	.visually-hidden {
		position: absolute;
		width: 1px;
		height: 1px;
		overflow: hidden;
		clip-path: inset(50%);
		white-space: nowrap;
	}
</style>
