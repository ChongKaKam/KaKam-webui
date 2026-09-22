import { WEBUI_BASE_URL } from '$lib/constants';
import type {
	Capabilities,
	ContextDetails,
	Memory,
	MemoryActivity,
	ManagerView,
	SessionScope
} from './types';

async function request<T>(path: string, method = 'GET', body?: unknown): Promise<T> {
	const response = await fetch(`${WEBUI_BASE_URL}/api/custom/memory${path}`, {
		method,
		headers: { Authorization: `Bearer ${localStorage.token}`, 'Content-Type': 'application/json' },
		...(body === undefined ? {} : { body: JSON.stringify(body) })
	});
	if (!response.ok) throw new Error((await response.json()).detail ?? 'Memory service unavailable');
	return response.json();
}

export const getPolicies = () => request<Capabilities>('/policies');
export const getContextDetails = (id: string) =>
	request<ContextDetails>(`/context/${encodeURIComponent(id)}`);
export const getMemoryActivity = (days: number) =>
	request<MemoryActivity>(`/activity?days=${days}`);
export const getMemories = () => request<Memory[]>('');
export type MemorySource = { external_chat_id: string; external_message_id: string };
export const addMemory = (
	content: string,
	options: { kind?: 'episode'; source?: MemorySource } = {}
) => request<{ created: boolean; id?: string | null }>('', 'POST', { content, ...options });
export const deleteMemory = (id: string) => request(`/${encodeURIComponent(id)}`, 'DELETE');
export const inspectSession = (id: string) =>
	request<ManagerView>(`/manager/sessions/${encodeURIComponent(id)}`);
export const setSessionScope = (id: string, scope: SessionScope) =>
	request(`/manager/sessions/${encodeURIComponent(id)}`, 'PUT', scope);
export const decideProposal = (id: string, approve: boolean) =>
	request(`/manager/proposals/${encodeURIComponent(id)}/decision`, 'POST', { approve });
export const proposeMemory = (id: string, content: string, source_message_id: string) =>
	request(`/manager/sessions/${encodeURIComponent(id)}/proposals`, 'POST', {
		content,
		source_message_id
	});
export const editMemory = (memory: Memory) =>
	request(`/manager/memories/${encodeURIComponent(memory.id)}`, 'PATCH', {
		content: memory.content,
		kind: memory.kind,
		version: memory.version,
		tags: memory.tags ?? []
	});
export const createCollection = (name: string, parent_id: string | null = null) =>
	request<{ id: string }>(`/manager/collections`, 'POST', { name, parent_id });
export const assignCollection = (id: string, collection_id: string, include = true) =>
	request(`/manager/memories/${encodeURIComponent(id)}/collection`, 'PUT', {
		collection_id,
		include
	});
export const probeMemory = () => request<{ embedding: string }>('/manager/probe', 'POST');
export const prepareHandoff = (id: string, source: string) =>
	request<{ source: string }>(`/manager/sessions/${encodeURIComponent(id)}/handoff`, 'POST', {
		source
	});
