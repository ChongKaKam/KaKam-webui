import { WEBUI_BASE_URL } from '$lib/constants';
import type { Capabilities, Memory, MemoryActivity } from './types';

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
export const getMemoryActivity = (days: number) =>
	request<MemoryActivity>(`/activity?days=${days}`);
export const getMemories = () => request<Memory[]>('');
export const addMemory = (content: string) =>
	request<{ created: boolean }>('', 'POST', { content });
export const deleteMemory = (id: string) => request(`/${encodeURIComponent(id)}`, 'DELETE');
