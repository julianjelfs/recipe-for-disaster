<script lang="ts">
	import { page } from '$app/state';
</script>

<h1>{page.status === 404 ? 'Not found' : 'Something went wrong'}</h1>
<p>{page.error?.message}</p>
<p><a href="/">Back to recipes</a></p>
