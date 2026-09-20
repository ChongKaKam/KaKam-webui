import { WEBUI_BASE_URL } from '$lib/constants';
import { effortRequest, type ChatParams } from '../chat/effort';
import { completionText, handoffInstruction } from './service';
import type { HandoffModel } from './types';

/** Ephemeral completion through the existing authenticated provider dispatcher. */
export async function generateHandoff(
	model: HandoffModel,
	source: string,
	params: ChatParams,
	signal: AbortSignal,
	sessionId?: string
): Promise<string> {
	const response = await fetch(`${WEBUI_BASE_URL}/api/chat/completions`, {
		method: 'POST',
		signal,
		credentials: 'include',
		headers: { Authorization: `Bearer ${localStorage.token}`, 'Content-Type': 'application/json' },
		body: JSON.stringify({
			model: model.id,
			model_item: model,
			session_id: sessionId,
			stream: false,
			messages: [
				{ role: 'system', content: handoffInstruction },
				{ role: 'user', content: source }
			],
			...effortRequest(model, { kakam_effort: params.kakam_effort }),
			features: {},
			tool_ids: [],
			filter_ids: [],
			background_tasks: {}
			// No parent_id/chat_id: no new chat, no writes or automatic KaKam Memory recall.
		})
	});
	if (!response.ok) {
		if (response.status === 401 || response.status === 403)
			throw new Error('登录已过期或无权使用此模型，请重新登录或选择其他模型。');
		throw new Error(`生成失败（${response.status}），请重试或更换模型。`);
	}
	return completionText(await response.json());
}
