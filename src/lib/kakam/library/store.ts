import { writable } from 'svelte/store';
import { deleteEntry, getEntries, getSummary } from './api';
import type { Entry, EntryPage, Kind, Summary } from './types';

export type Filters = { kind: Kind; q: string; offset: number; before?: number };
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
