<script lang="ts">
	export let editing = false;
	export let onFinish: () => void = () => {};
</script>

<button
	type="button"
	aria-pressed={editing}
	on:click={() => {
		if (editing) onFinish();
		editing = !editing;
	}}
>
	{editing ? '完成' : '编辑'}
</button>
