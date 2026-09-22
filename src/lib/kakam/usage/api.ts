import { WEBUI_BASE_URL } from '$lib/constants';
import type { SiteUsage } from './types';

export async function getSiteUsage(token: string, signal: AbortSignal): Promise<SiteUsage> {
	const response = await fetch(`${WEBUI_BASE_URL}/api/custom/usage/site`, {
		signal,
		cache: 'no-store',
		headers: { Authorization: `Bearer ${token}` }
	});
	if (!response.ok) throw new Error(`Usage request failed (${response.status})`);
	const data = await response.json();
	const fields = [
		'input_tokens',
		'output_tokens',
		'total_tokens',
		'recorded_messages',
		'recorded_users'
	];
	if (
		!data ||
		fields.some((key) => !Number.isSafeInteger(data[key]) || data[key] < 0) ||
		data.total_tokens !== data.input_tokens + data.output_tokens
	)
		throw new Error('Invalid usage response');
	return data;
}
