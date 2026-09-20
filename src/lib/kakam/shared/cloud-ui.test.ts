import { describe, expect, it, vi } from 'vitest';
import { render } from 'svelte/server';
import { writable } from 'svelte/store';
import AdvancedParams from '$lib/components/chat/Settings/Advanced/AdvancedParams.svelte';
import MemorySidebarItem from '../memory/components/MemorySidebarItem.svelte';
import { user } from '$lib/stores';

vi.mock('$lib/stores', async () => {
	const { writable } = await import('svelte/store');
	return {
		user: writable(null),
		showSettings: writable(false),
		mobile: writable(false),
		showSidebar: writable(true)
	};
});

const context = new Map([['i18n', writable({ t: (text: string) => text })]]);

describe('Cloud advanced parameters', () => {
	it.each([false, true])(
		'hides local controls for admin=%s without changing saved values',
		(admin) => {
			const params = {
				temperature: 0.7,
				top_k: 40,
				num_ctx: 8192,
				think: true,
				keep_alive: '5m',
				custom_params: { provider_option: 'retained' }
			};
			const before = structuredClone(params);
			const { body } = render(AdvancedParams, { props: { params, admin, custom: true }, context });
			for (const label of ['num_ctx', 'num_gpu', 'keep_alive', 'mirostat', 'use_mmap', 'Ollama']) {
				expect(body).not.toContain(label);
			}
			for (const label of ['Temperature', 'top_k', 'top_p', 'max_tokens', 'Reasoning Effort']) {
				expect(body).toContain(label);
			}
			if (admin) expect(body).toContain('provider_option');
			expect(params).toEqual(before);
		}
	);
});

describe('Memory sidebar visibility', () => {
	it.each([
		[null, false],
		[{ role: 'pending' }, false],
		[{ role: 'user', permissions: { features: { memories: false } } }, false],
		[{ role: 'user' }, true],
		[{ role: 'admin' }, true]
	])('respects the existing permission policy for %j', (viewer, visible) => {
		user.set(viewer as never);
		for (const compact of [false, true]) {
			const { body } = render(MemorySidebarItem, { props: { compact } });
			expect(body.includes('aria-label="Memory"')).toBe(visible);
		}
	});
});
