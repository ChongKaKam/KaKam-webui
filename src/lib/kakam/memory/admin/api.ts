import { WEBUI_BASE_URL } from '$lib/constants';
import type { ConfigView, ModelsResult, ProbeResult, ProviderForm, ProviderKind } from './types';

async function request<T>(path = '', method = 'GET', body?: unknown): Promise<T> {
	const response = await fetch(`${WEBUI_BASE_URL}/api/custom/memory/admin/config${path}`, {
		method,
		cache: 'no-store',
		headers: { Authorization: `Bearer ${localStorage.token}`, 'Content-Type': 'application/json' },
		...(body === undefined ? {} : { body: JSON.stringify(body) })
	});
	const data = await response.json().catch(() => null);
	if (!response.ok) {
		throw new Error(
			typeof data?.detail === 'string' ? data.detail : `Memory 配置请求失败 (${response.status})`
		);
	}
	return data;
}

export const getConfig = () => request<ConfigView>();
export const getOwnership = () => request<{ manager_enabled: boolean }>('/ownership');
export const discoverModels = (kind: ProviderKind, form: ProviderForm) =>
	request<ModelsResult>(`/${kind}/models`, 'POST', form);
export const saveProvider = (kind: ProviderKind, form: ProviderForm) =>
	request<ConfigView>(`/${kind}`, 'PUT', form);
export const testProvider = (kind: ProviderKind, form: ProviderForm) =>
	request<ProbeResult>(`/${kind}/test`, 'POST', form);
export const resetProvider = (kind: ProviderKind, revision: number, acknowledge_reindex: boolean) =>
	request<ConfigView>(`/${kind}/reset`, 'POST', { revision, acknowledge_reindex });
