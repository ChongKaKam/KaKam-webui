import { EventSourceParserStream } from 'eventsource-parser/stream';
import { completionText, textContent } from './service';

export type HandoffProgress = {
	onText?: (text: string) => void;
	onPhase?: (phase: 'waiting' | 'thinking' | 'writing') => void;
	onActivity?: () => void;
};

const emptyMessage = '模型没有返回交接正文，请重试或更换模型。';
const providerError = '模型服务返回错误，请重试或更换模型。';

/** Read both the normal chat dispatcher SSE and JSON-only compatible providers. */
export async function readHandoffResponse(
	response: Response,
	signal: AbortSignal,
	progress: HandoffProgress
): Promise<string> {
	progress.onPhase?.('waiting');
	progress.onActivity?.();
	if (!response.headers.get('content-type')?.includes('text/event-stream')) {
		const data = await response.json();
		if (data?.error) throw new Error(providerError);
		const text = completionText(data);
		progress.onText?.(text);
		return text;
	}
	if (!response.body) throw new Error(emptyMessage);
	const decoder = new TextDecoder();
	const reader = response.body
		.pipeThrough(
			new TransformStream<Uint8Array, string>({
				transform(chunk, controller) {
					progress.onActivity?.();
					controller.enqueue(decoder.decode(chunk, { stream: true }));
				},
				flush(controller) {
					controller.enqueue(decoder.decode());
				}
			})
		)
		.pipeThrough(new EventSourceParserStream())
		.getReader();
	const abort = () => {
		void reader.cancel().catch(() => {});
	};
	signal.addEventListener('abort', abort, { once: true });
	let text = '';
	let finished = false;
	let limited = false;
	try {
		signal.throwIfAborted();
		while (!signal.aborted) {
			const { value, done } = await reader.read();
			signal.throwIfAborted();
			if (done) break;
			if (value.data === '[DONE]') {
				finished = true;
				break;
			}
			let data;
			try {
				data = JSON.parse(value.data);
			} catch {
				throw new Error('模型返回了无法解析的数据，请重试或更换模型。');
			}
			if (data.error || value.event === 'error' || ['error', 'response.failed'].includes(data.type))
				throw new Error(providerError);
			const choice = data.choices?.[0];
			const delta = choice?.delta;
			if (
				delta?.reasoning_content ||
				delta?.reasoning ||
				data.type?.startsWith('response.reasoning')
			)
				progress.onPhase?.('thinking');
			const addition =
				data.type === 'response.output_text.delta' ? data.delta : textContent(delta?.content);
			if (typeof addition === 'string' && addition) {
				text += addition;
				progress.onPhase?.('writing');
				progress.onText?.(text);
			}
			if (choice?.finish_reason) {
				finished = true;
				limited = choice.finish_reason === 'length';
				break;
			}
			if (data.type === 'response.completed' || data.type === 'response.incomplete') {
				if (!text) {
					text = (data.response?.output ?? [])
						.filter((item: { type?: string }) => item.type === 'message')
						.flatMap((item: { content?: { type?: string; text?: string }[] }) => item.content ?? [])
						.filter((item: { type?: string }) => item.type === 'output_text')
						.map((item: { text?: string }) => item.text ?? '')
						.join('');
					if (text) progress.onText?.(text);
				}
				finished = true;
				limited = data.type === 'response.incomplete';
				break;
			}
		}
		signal.throwIfAborted();
		if (!finished) throw new Error('连接提前结束，交接内容可能不完整，请重新生成。');
		if (!text.trim()) throw new Error(emptyMessage);
		return limited
			? `${text.trim()}\n\n> 注意：模型输出达到长度上限或提前结束，交接内容可能不完整。`
			: text.trim();
	} finally {
		signal.removeEventListener('abort', abort);
		await reader.cancel().catch(() => {});
		reader.releaseLock();
	}
}
