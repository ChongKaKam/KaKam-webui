import { WEBUI_BASE_URL } from '$lib/constants';
import type { ChatDetail, EntryPage, Kind, NoteDetail, Summary } from './types';

async function request<T>(path: string, token: string, signal?: AbortSignal): Promise<T> {
	const response = await fetch(`${WEBUI_BASE_URL}/api/custom/library${path}`, {
		headers: { Authorization: `Bearer ${token}` },
		cache: 'no-store',
		signal
	});
	if (!response.ok) throw new Error(`读取失败（${response.status}），请刷新或重新登录`);
	return response.json();
}

export const getSummary = (token: string, signal?: AbortSignal) =>
	request<Summary>('/summary', token, signal);
export function getEntries(
	token: string,
	filters: {
		kind: Kind;
		q: string;
		offset: number;
		before?: number;
		chat_id?: string;
	},
	signal?: AbortSignal
) {
	const params = new URLSearchParams();
	for (const [key, value] of Object.entries(filters))
		if (value !== undefined && value !== '') params.set(key, String(value));
	return request<EntryPage>(`/entries?${params}`, token, signal);
}
export const getChat = (token: string, id: string, signal?: AbortSignal) =>
	request<ChatDetail>(`/chats/${encodeURIComponent(id)}`, token, signal);
export const getNote = (token: string, id: string, signal?: AbortSignal) =>
	request<NoteDetail>(`/notes/${encodeURIComponent(id)}`, token, signal);

export async function getFileBlob(
	token: string,
	id: string
): Promise<{ blob: Blob; filename: string }> {
	const response = await fetch(
		`${WEBUI_BASE_URL}/api/v1/files/${encodeURIComponent(id)}/content?attachment=true`,
		{
			headers: { Authorization: `Bearer ${token}` },
			cache: 'no-store'
		}
	);
	if (!response.ok) throw new Error(`文件下载失败（${response.status}），可能已删除或权限已变更`);
	let filename = '';
	const disposition = response.headers.get('Content-Disposition') || '';
	const encoded = disposition.match(/filename\*=UTF-8''([^;]+)/i)?.[1];
	try {
		filename = encoded ? decodeURIComponent(encoded) : '';
	} catch {
		/* use caller fallback */
	}
	return { blob: await response.blob(), filename };
}

// Native routes enforce deletion permissions and clean up storage and indexes.
export async function deleteEntry(token: string, kind: Kind, id: string): Promise<void> {
	const path =
		kind === 'note'
			? `notes/${encodeURIComponent(id)}/delete`
			: `${kind}s/${encodeURIComponent(id)}`;
	const response = await fetch(`${WEBUI_BASE_URL}/api/v1/${path}`, {
		method: 'DELETE',
		headers: { Authorization: `Bearer ${token}` }
	});
	if (!response.ok)
		throw new Error(`删除失败（${response.status}）。请刷新检查；已成功删除的项目不会恢复。`);
	const result = await response.json();
	if (result === false) throw new Error('服务端未完成删除，请刷新后重试');
}
