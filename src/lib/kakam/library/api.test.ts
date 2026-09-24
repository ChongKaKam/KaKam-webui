import { afterEach, expect, it, vi } from 'vitest';
import { deleteEntry, getEntries, getFileBlob, getGroups } from './api';
afterEach(() => {
	vi.unstubAllGlobals();
});

it('requests server-side group filtering and authenticated group names', async () => {
	const fetch = vi
		.fn()
		.mockImplementation(async () => new Response(JSON.stringify({ items: [], total: 0 })));
	vi.stubGlobal('fetch', fetch);
	await getEntries('token', { kind: 'chat', q: '', offset: 30, group_id: 'group&id' });
	expect(fetch.mock.calls[0][0]).toContain('group_id=group%26id');
	await getEntries('token', { kind: 'chat', q: '', offset: 0, ungrouped: true });
	expect(fetch.mock.calls[1][0]).toContain('ungrouped=true');
	await getGroups('token');
	expect(fetch.mock.calls[2][0]).toMatch(/\/library\/groups$/);
	expect(fetch.mock.calls[2][1]).toMatchObject({
		cache: 'no-store',
		headers: { Authorization: 'Bearer token' }
	});
});

it('encodes names and scopes reads through authenticated no-store requests', async () => {
	const fetch = vi.fn().mockResolvedValue(new Response(JSON.stringify({ items: [], total: 0 })));
	vi.stubGlobal('fetch', fetch);
	await getEntries('secret', { kind: 'file', q: 'a&user_id=b', offset: 30 });
	expect(fetch.mock.calls[0][0]).toContain('q=a%26user_id%3Db');
	expect(fetch.mock.calls[0][1]).toMatchObject({
		cache: 'no-store',
		headers: { Authorization: 'Bearer secret' }
	});
});
it('preserves a Unicode download filename and reports missing files', async () => {
	const fetch = vi
		.fn()
		.mockResolvedValueOnce(
			new Response('html', {
				headers: { 'Content-Disposition': "attachment; filename*=UTF-8''%E7%BD%91%E9%A1%B5.html" }
			})
		)
		.mockResolvedValueOnce(new Response('', { status: 404 }));
	vi.stubGlobal('fetch', fetch);
	expect((await getFileBlob('token', 'file')).filename).toBe('网页.html');
	await expect(getFileBlob('token', 'missing')).rejects.toThrow('404');
});
it('does not interpret deletion failures or false results as success', async () => {
	const fetch = vi
		.fn()
		.mockResolvedValueOnce(new Response('false'))
		.mockResolvedValueOnce(new Response('', { status: 403 }));
	vi.stubGlobal('fetch', fetch);
	await expect(deleteEntry('token', 'note', 'id')).rejects.toThrow('未完成删除');
	expect(fetch.mock.calls[0][0]).toMatch(/\/notes\/id\/delete$/);
	await expect(deleteEntry('token', 'file', 'id')).rejects.toThrow('403');
});
