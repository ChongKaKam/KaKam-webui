import { textContent } from '../handoff/service';

export const memoryContentLimit = 2000;
type TurnMessage = {
	role?: string;
	parentId?: string | null;
	content?: unknown;
	files?: unknown[];
};
export type RememberHistory = { messages: Record<string, TurnMessage> };

export function rememberDraft(history: RememberHistory, messageId: string, answer: string) {
	const response = history.messages[messageId];
	const question = response?.parentId ? history.messages[response.parentId] : undefined;
	if (response?.role !== 'assistant' || question?.role !== 'user') return null;
	const visible = answer
		.replace(/<think\b[^>]*>[\s\S]*?(?:<\/think>|$)/gi, '')
		.replace(/<details\b[^>]*\btype=["']reasoning["'][^>]*>[\s\S]*?(?:<\/details>|$)/gi, '')
		.trim();
	if (!visible) return null;
	const prompt = textContent(question.content).trim();
	return {
		content: `用户确认保留的问答记录（回答未经独立验证）\n\n问题：\n${prompt || '（本轮问题无可保存的文字）'}\n\n回答：\n${visible}`,
		hasAttachments:
			!!question.files?.length ||
			(Array.isArray(question.content) && question.content.some((p) => p?.type !== 'text'))
	};
}

export function isSavedMemoryChat(chatId: string) {
	return !!chatId && !/^(temporary:|local:|channel:)/.test(chatId);
}

export function memoryContentError(content: string) {
	const length = Array.from(content.trim()).length;
	return !length
		? '请填写要保存的记忆。'
		: length > memoryContentLimit
			? '记忆最多 2,000 字，请精简后保存；内容尚未写入。'
			: '';
}
