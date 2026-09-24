import { beforeEach, expect, it, vi } from 'vitest';
import { get } from 'svelte/store';
import { createChatAssetsStore, createLibraryStore } from './store';
import { deleteEntry, getChat, getEntries, getSummary } from './api';
import type { ChatDetail, Entry } from './types';
vi.mock('./api', () => ({
	deleteEntry: vi.fn(),
	getChat: vi.fn(),
	getEntries: vi.fn(),
	getSummary: vi.fn()
}));
beforeEach(() => {
	vi.resetAllMocks();
});

it('keeps recovered artifacts when file listing fails and retries the same page', async () => {
	vi.mocked(getChat).mockResolvedValue({
		id: 'a',
		title: 'Demo',
		messages: [],
		current_message_id: null
	});
	vi.mocked(getEntries)
		.mockRejectedValueOnce(new Error('offline'))
		.mockResolvedValueOnce({ items: [], total: 0 });
	const store = createChatAssetsStore(() => 'token', 'a');
	await store.load();
	expect(get(store).chat?.title).toBe('Demo');
	expect(get(store).filesError).toContain('offline');
	await store.loadFiles();
	expect(get(store).filesError).toBe('');
	expect(vi.mocked(getEntries).mock.calls[1][1]).toMatchObject({ offset: 0, chat_id: 'a' });
	store.destroy();
});

it('does not update a closed collection or fetch its files after the chat arrives', async () => {
	let resolve: (chat: ChatDetail) => void = () => {};
	vi.mocked(getChat).mockImplementationOnce(() => new Promise((done) => (resolve = done)));
	const store = createChatAssetsStore(() => 'token', 'a');
	const loading = store.load();
	store.destroy();
	resolve({ id: 'a', title: 'closed', messages: [], current_message_id: null });
	await loading;
	expect(get(store).chat).toBeNull();
	expect(getEntries).not.toHaveBeenCalled();
});

it('ignores an old request when switching filters quickly', async () => {
	let resolveOld: (value: { items: Entry[]; total: number }) => void = () => {};
	vi.mocked(getEntries).mockImplementationOnce(
		() => new Promise((resolve) => (resolveOld = resolve))
	);
	vi.mocked(getEntries).mockResolvedValueOnce({ items: [], total: 20 });
	const library = createLibraryStore(() => 'token');
	const old = library.load({ kind: 'chat', q: '', offset: 0 });
	await library.load({ kind: 'file', q: '', offset: 0 });
	resolveOld({ items: [], total: 10 });
	await old;
	expect(get(library).page.total).toBe(20);
	library.destroy();
});

it('reports partial cleanup, refreshes counts and never retries successful deletes', async () => {
	vi.mocked(deleteEntry).mockResolvedValueOnce().mockRejectedValueOnce(new Error('denied'));
	vi.mocked(getEntries).mockResolvedValue({ items: [], total: 0 });
	vi.mocked(getSummary).mockResolvedValue({
		chats: 0,
		files: 1,
		notes: 0,
		file_bytes: 10,
		unknown_size_files: 0,
		notes_enabled: false
	});
	const library = createLibraryStore(() => 'token');
	const entries = ['one', 'two'].map(
		(id): Entry => ({
			id,
			kind: 'file',
			title: id,
			updated_at: 0,
			size: 10,
			content_type: 'text/plain',
			origin: 'unknown',
			sources: [],
			archived: false
		})
	);
	const result = await library.remove(entries);
	expect(result.deleted).toBe(1);
	expect(result.failed).toEqual(['two: Error: denied']);
	expect(deleteEntry).toHaveBeenCalledTimes(2);
	expect(get(library).summary?.files).toBe(1);
	library.destroy();
});
