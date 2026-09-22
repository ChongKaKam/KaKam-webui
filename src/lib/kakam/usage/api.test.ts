import { afterEach, expect, it, vi } from 'vitest';
import { getSiteUsage } from './api';

afterEach(() => {
	vi.unstubAllGlobals();
});
const fixture = {
	input_tokens: 100,
	output_tokens: 20,
	total_tokens: 120,
	recorded_messages: 3,
	recorded_users: 2
};
it('uses the authenticated caller and supports cancellation without a shared cache', async () => {
	const fetch = vi.fn().mockResolvedValue(new Response(JSON.stringify(fixture)));
	vi.stubGlobal('fetch', fetch);
	const control = new AbortController();
	expect(await getSiteUsage('fixture-token', control.signal)).toEqual(fixture);
	expect(fetch.mock.calls[0][0]).toContain('/api/custom/usage/site');
	expect(fetch.mock.calls[0][1]).toMatchObject({
		signal: control.signal,
		cache: 'no-store',
		headers: { Authorization: 'Bearer fixture-token' }
	});
});
it.each([
	new Response('{}', { status: 503 }),
	new Response('{}'),
	new Response(JSON.stringify({ ...fixture, total_tokens: 999 })),
	new Response(JSON.stringify({ ...fixture, recorded_users: -1 }))
])('rejects missing and failed data instead of fabricating zero usage', async (response) => {
	vi.stubGlobal('fetch', vi.fn().mockResolvedValue(response));
	await expect(getSiteUsage('fixture-token', new AbortController().signal)).rejects.toThrow();
});
