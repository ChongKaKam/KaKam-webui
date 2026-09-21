import { WEBUI_BASE_URL } from '$lib/constants';
import type { ImageProbeDraft, ImageProbeResult } from './types';

export async function probeImages(
	token: string,
	draft: ImageProbeDraft,
	action: 'models' | 'generate',
	signal: AbortSignal
): Promise<ImageProbeResult> {
	const response = await fetch(`${WEBUI_BASE_URL}/api/custom/images/probe`, {
		method: 'POST',
		signal,
		headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
		body: JSON.stringify({ ...draft, action })
	});
	const data = await response.json().catch(() => null);
	if (!response.ok)
		throw new Error(
			typeof data?.detail === 'string'
				? data.detail
				: `测试失败（HTTP ${response.status}），请检查配置和管理员登录状态。`
		);
	if (!data || typeof data !== 'object') throw new Error('测试服务返回格式不正确。');
	return data;
}
