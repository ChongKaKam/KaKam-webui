import { createParser } from 'eventsource-parser';
import { WEBUI_BASE_URL } from '$lib/constants';
import type {
	ConnectionInput,
	ConnectionStatus,
	ConnectionView,
	Message,
	PromptModel,
	TurnEvent
} from './types';

const endpoint = `${WEBUI_BASE_URL}/api/custom/jev`;

async function request(path: string, method = 'GET', body?: unknown, signal?: AbortSignal) {
	const response = await fetch(`${endpoint}${path}`, {
		method,
		signal,
		credentials: 'include',
		cache: 'no-store',
		headers: { Authorization: `Bearer ${localStorage.token}`, 'Content-Type': 'application/json' },
		...(body === undefined ? {} : { body: JSON.stringify(body) })
	});
	if (!response.ok) {
		const data = await response.json().catch(() => null);
		const message = typeof data?.detail === 'string' ? data.detail : data?.detail?.message;
		throw new Error(
			message ||
				(response.status === 422
					? '输入格式或长度不符合要求，请检查后重试。'
					: `请求失败（${response.status}），请检查登录状态与访问权限。`)
		);
	}
	return response;
}

export const getJevConfig = async (): Promise<ConnectionView> => (await request('/config')).json();
export const saveJevConfig = async (form: ConnectionInput): Promise<ConnectionView> =>
	(await request('/config', 'PUT', form)).json();
export const testJevConnection = async (form: ConnectionInput): Promise<ConnectionStatus> =>
	(await request('/test', 'POST', form)).json();
export const getJevStatus = async (signal?: AbortSignal): Promise<ConnectionStatus> =>
	(await request('/status', 'GET', undefined, signal)).json();
export const getPromptModels = async (signal?: AbortSignal): Promise<{ models: PromptModel[] }> =>
	(await request('/prompt-models', 'GET', undefined, signal)).json();

export async function readTurnEvents(
	response: Response,
	signal: AbortSignal,
	receive: (event: TurnEvent) => void
) {
	if (!response.body || !response.headers.get('content-type')?.includes('text/event-stream'))
		throw new Error('服务没有返回有效的进度流。');
	const reader = response.body.getReader();
	const decoder = new TextDecoder();
	let finished = false;
	let bytes = 0;
	const parser = createParser((event) => {
		if (event.type !== 'event') return;
		const data: TurnEvent = JSON.parse(event.data);
		if (data.type === 'error' || (data.type === 'stage' && data.stage === 'done')) finished = true;
		if (!signal.aborted) receive(data);
	});
	const abort = () => {
		void reader.cancel().catch(() => {});
	};
	signal.addEventListener('abort', abort, { once: true });
	try {
		while (!signal.aborted) {
			const { value, done } = await reader.read();
			if (done) break;
			bytes += value.byteLength;
			if (bytes > 2_000_000) throw new Error('响应内容过大，已停止读取。');
			parser.feed(decoder.decode(value, { stream: true }));
		}
		parser.feed(decoder.decode());
		if (signal.aborted) throw new DOMException('Aborted', 'AbortError');
		if (!finished) throw new Error('连接中断，已收到的判断结果仍保留。');
	} finally {
		signal.removeEventListener('abort', abort);
		await reader.cancel().catch(() => {});
		reader.releaseLock();
	}
}

export async function runJevTurn(
	modelId: string,
	messages: Message[],
	signal: AbortSignal,
	receive: (event: TurnEvent) => void
) {
	const response = await request('/turn', 'POST', { model_id: modelId, messages }, signal);
	await readTurnEvents(response, signal, receive);
}
