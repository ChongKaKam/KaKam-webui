<script lang="ts">
	import { WEBUI_NAME } from '$lib/stores';
	import { WEBUI_VERSION } from '$lib/constants';
</script>

<!-- Preserve the existing Open WebUI footer identifier. -->
<div class="mt-3 text-center text-xs text-gray-500 dark:text-gray-400">
	{$WEBUI_NAME} ‧ v{WEBUI_VERSION}
</div>
