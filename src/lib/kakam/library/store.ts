import { writable } from 'svelte/store';
import { deleteEntry, getChat, getEntries, getSummary } from './api';
import type { ChatDetail, Entry, EntryPage, Kind, Summary } from './types';

export type Filters = {
	kind: Kind;
	q: string;
	offset: number;
	before?: number;
	group_id?: string;
	ungrouped?: boolean;
};
export function createLibraryStore(token: () => string) {
	const state = writable<{
		page: EntryPage;
		summary: Summary | null;
		loading: boolean;
		error: string;
	}>({
		page: { items: [], total: 0 },
		summary: null,
		loading: false,
		error: ''
	});
	let request: AbortController | undefined;
	let summaryRequest: AbortController | undefined;
	let filters: Filters = { kind: 'chat', q: '', offset: 0 };
	async function refreshSummary() {
		summaryRequest?.abort();
		const active = (summaryRequest = new AbortController());
		try {
			const summary = await getSummary(token(), active.signal);
			if (!active.signal.aborted) state.update((s) => ({ ...s, summary }));
		} catch (e) {
			if (!active.signal.aborted) state.update((s) => ({ ...s, error: String(e) }));
		}
	}
	async function load(next = filters) {
		filters = next;
		request?.abort();
		const active = (request = new AbortController());
		state.update((s) => ({ ...s, loading: true, error: '', page: { items: [], total: 0 } }));
		try {
			const page = await getEntries(token(), next, active.signal);
			if (!active.signal.aborted) state.update((s) => ({ ...s, page, loading: false }));
		} catch (e) {
			if (!active.signal.aborted) state.update((s) => ({ ...s, loading: false, error: String(e) }));
		}
	}
	async function remove(entries: Entry[]) {
		const failed: string[] = [];
		let deleted = 0;
		for (const entry of entries) {
			try {
				await deleteEntry(token(), entry.kind, entry.id);
				deleted++;
			} catch (e) {
				failed.push(`${entry.title}: ${String(e)}`);
			}
		}
		await Promise.all([load({ ...filters, offset: 0 }), refreshSummary()]);
		return { deleted, failed };
	}
	return {
		subscribe: state.subscribe,
		load,
		refreshSummary,
		remove,
		destroy: () => {
			request?.abort();
			summaryRequest?.abort();
		}
	};
}

export function createChatAssetsStore(token: () => string, chatId: string) {
	const state = writable<{
		chat: ChatDetail | null;
		files: Entry[];
		total: number;
		loading: boolean;
		loadingMore: boolean;
		error: string;
		filesError: string;
	}>({
		chat: null,
		files: [],
		total: 0,
		loading: true,
		loadingMore: false,
		error: '',
		filesError: ''
	});
	const controller = new AbortController();
	let offset = 0;
	let pending = false;
	async function loadFiles() {
		if (pending || controller.signal.aborted) return;
		pending = true;
		state.update((s) => ({ ...s, loadingMore: true, filesError: '' }));
		try {
			const result = await getEntries(
				token(),
				{ kind: 'file', q: '', offset, chat_id: chatId },
				controller.signal
			);
			if (controller.signal.aborted) return;
			offset += result.items.length;
			state.update((s) => ({
				...s,
				files: [...new Map([...s.files, ...result.items].map((file) => [file.id, file])).values()],
				total: result.total
			}));
		} catch (e) {
			if (!controller.signal.aborted) state.update((s) => ({ ...s, filesError: String(e) }));
		} finally {
			pending = false;
			if (!controller.signal.aborted) state.update((s) => ({ ...s, loadingMore: false }));
		}
	}
	async function load() {
		state.update((s) => ({ ...s, loading: true, error: '' }));
		try {
			const chat = await getChat(token(), chatId, controller.signal);
			if (controller.signal.aborted) return;
			state.update((s) => ({ ...s, chat }));
			await loadFiles();
		} catch (e) {
			if (!controller.signal.aborted) state.update((s) => ({ ...s, error: String(e) }));
		} finally {
			if (!controller.signal.aborted) state.update((s) => ({ ...s, loading: false }));
		}
	}
	return { subscribe: state.subscribe, load, loadFiles, destroy: () => controller.abort() };
}
