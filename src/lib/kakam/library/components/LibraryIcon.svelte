<script lang="ts">
	const paths = {
		grid: 'M3 3h7v7H3z M14 3h7v7h-7z M3 14h7v7H3z M14 14h7v7h-7z',
		folder: 'M3 7V5a1 1 0 0 1 1-1h5l2 3h9a1 1 0 0 1 1 1v11a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V7Z',
		file: 'M14 3H6a1 1 0 0 0-1 1v16a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1V8l-5-5Zm0 0v5h5 M8 12h8 M8 16h5',
		arrow: 'M5 12h14 M13 6l6 6-6 6',
		back: 'M19 12H5 M11 6l-6 6 6 6',
		search: 'M21 21l-5-5 M18 10a8 8 0 1 1-16 0 8 8 0 0 1 16 0',
		refresh: 'M20 7v5h-5 M4 17v-5h5 M5.2 7a8 8 0 0 1 13.2-1L20 8 M4 16l1.6 2A8 8 0 0 0 19 17',
		download: 'M12 3v12 M7 10l5 5 5-5 M4 16v4h16v-4',
		code: 'M8 6l-6 6 6 6 M16 6l6 6-6 6 M14 3l-4 18',
		close: 'M6 6l12 12 M6 18L18 6',
		external: 'M14 3h7v7 M21 3L10 14 M10 3H4a1 1 0 0 0-1 1v16a1 1 0 0 0 1 1h16a1 1 0 0 0 1-1v-6',
		note: 'M4 3h16v18H4z M8 7h8 M8 11h8 M8 15h5',
		image: 'M3 3h18v18H3z M3 16l6-6 12 11 M14 8h.01'
	};
	export let name: keyof typeof paths = 'file';
	export let size = 18;
</script>

<svg
	width={size}
	height={size}
	viewBox="0 0 24 24"
	fill="none"
	stroke="currentColor"
	stroke-width="1.6"
	stroke-linecap="round"
	stroke-linejoin="round"
	aria-hidden="true"><path d={paths[name]} /></svg
>
