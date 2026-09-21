import { OPENAI_API_BASE_URL } from '$lib/constants';
import { getModels } from '$lib/apis';
import { getOpenAIConfig, updateOpenAIConfig } from '$lib/apis/openai';
import { discoveredModels } from './service';
import type { Connection, ProviderConfig } from './types';
export const loadProviders = (token: string): Promise<ProviderConfig> => getOpenAIConfig(token);
export async function saveProviders(token: string, config: ProviderConfig) {
	await updateOpenAIConfig(token, config);
}
export const reloadModelPool = (token: string, directConnections: object | null = null) =>
	getModels(token, directConnections, false, true);
export async function probeProvider(token: string, connection: Connection, signal: AbortSignal) {
	const response = await fetch(`${OPENAI_API_BASE_URL}/verify`, {
		method: 'POST',
		signal,
		headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
		body: JSON.stringify({
			url: connection.url.replace(/\/+$/, ''),
			key: connection.key,
			config: connection.config
		})
	});
	if (!response.ok)
		throw new Error(
			response.status === 401 || response.status === 403
				? '探测未通过：请检查 API Key、模型读取权限和管理员登录状态。'
				: `探测失败（HTTP ${response.status}），请检查 Base URL 和服务状态。`
		);
	return discoveredModels(await response.json(), connection.url);
}
