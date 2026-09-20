import { afterEach, describe, expect, it, vi } from 'vitest';
vi.mock('$lib/constants', () => ({ WEBUI_BASE_URL: '' }));
import { generateHandoff } from './api';
afterEach(() => {
	vi.unstubAllGlobals();
});
describe('handoff streamed provider response', () => {
	it('shows text before the provider completes instead of waiting for response.json()', async () => {
		vi.stubGlobal('localStorage', { token: 'test-token' });
		let wire!: ReadableStreamDefaultController<Uint8Array>;
		const stream = new ReadableStream<Uint8Array>({
			start(controller) {
				wire = controller;
			}
		});
		const fetcher = vi
			.fn()
			.mockResolvedValue(
				new Response(stream, { headers: { 'Content-Type': 'text/event-stream' } })
			);
		vi.stubGlobal('fetch', fetcher);
		const onText = vi.fn();
		const completed = generateHandoff(
			{ id: 'test' },
			'sample',
			{},
			new AbortController().signal,
			undefined,
			{ onText }
		);
		void completed.catch(() => {});
		const encoder = new TextEncoder();
		wire.enqueue(
			encoder.encode('data: {"choices":[{"delta":{"content":"你将接手以下任务"}}]}\n\n')
		);
		try {
			await vi.waitFor(() => expect(onText).toHaveBeenCalledWith('你将接手以下任务'), {
				timeout: 250
			});
			expect(JSON.parse(fetcher.mock.calls[0][1].body).stream).toBe(true);
		} finally {
			wire.enqueue(encoder.encode('data: [DONE]\n\n'));
			wire.close();
			await completed.catch(() => {});
		}
	});
});

import { readHandoffResponse } from './response';
const event = (data: unknown) => `data: ${JSON.stringify(data)}\n\n`;
function response(raw: string, split = false) {
	const bytes = new TextEncoder().encode(raw);
	return new Response(
		new ReadableStream<Uint8Array>({
			start(controller) {
				if (split) for (const byte of bytes) controller.enqueue(Uint8Array.of(byte));
				else controller.enqueue(bytes);
				controller.close();
			}
		}),
		{ headers: { 'Content-Type': 'text/event-stream' } }
	);
}
const signal = () => new AbortController().signal;
describe('handoff stream safety and compatibility', () => {
	it('decodes split UTF-8 and SSE frames, reports reasoning without exposing it', async () => {
		const onText = vi.fn();
		const onPhase = vi.fn();
		const raw =
			': heartbeat\n\n' +
			event({ choices: [{ delta: { reasoning_content: 'private reasoning' } }] }) +
			event({ choices: [{ delta: { content: '交接🙂' } }] }) +
			'data: [DONE]\n\n';
		expect(await readHandoffResponse(response(raw, true), signal(), { onText, onPhase })).toBe(
			'交接🙂'
		);
		expect(onText).toHaveBeenCalledTimes(1);
		expect(onText).toHaveBeenCalledWith('交接🙂');
		expect(onPhase.mock.calls.flat()).toEqual(['waiting', 'thinking', 'writing']);
	});
	it('supports Responses deltas without duplicating the final snapshot', async () => {
		const raw =
			event({ type: 'response.output_text.delta', delta: '你好' }) +
			event({
				type: 'response.completed',
				response: {
					output: [{ type: 'message', content: [{ type: 'output_text', text: '你好' }] }]
				}
			});
		expect(await readHandoffResponse(response(raw), signal(), {})).toBe('你好');
	});
	it('supports final-only Responses events and marks incomplete output', async () => {
		const raw = event({
			type: 'response.incomplete',
			response: {
				output: [{ type: 'message', content: [{ type: 'output_text', text: '部分正文' }] }]
			}
		});
		expect(await readHandoffResponse(response(raw), signal(), {})).toContain('内容可能不完整');
	});
	it('reports an abrupt disconnect while keeping text already delivered', async () => {
		const onText = vi.fn();
		await expect(
			readHandoffResponse(
				response(event({ choices: [{ delta: { content: 'partial' } }] })),
				signal(),
				{ onText }
			)
		).rejects.toThrow('连接提前结束');
		expect(onText).toHaveBeenCalledWith('partial');
	});
	it.each([
		[event({ error: { message: 'provider details must not leak' } }), '模型服务返回错误'],
		[event({ type: 'response.failed' }), '模型服务返回错误'],
		['data: invalid\n\n', '无法解析'],
		[
			event({ choices: [{ delta: { reasoning_content: 'hidden' } }] }) + 'data: [DONE]\n\n',
			'没有返回交接正文'
		]
	])('reports stream failures without exposing provider internals (%#)', async (raw, message) => {
		await expect(readHandoffResponse(response(raw), signal(), {})).rejects.toThrow(message);
	});
	it('marks a chat completion length limit', async () => {
		const raw = event({ choices: [{ delta: { content: 'partial' }, finish_reason: 'length' }] });
		expect(await readHandoffResponse(response(raw), signal(), {})).toContain('内容可能不完整');
	});
	it('aborts an idle stream and cancels its underlying reader', async () => {
		const cancel = vi.fn();
		const controller = new AbortController();
		const pending = readHandoffResponse(
			new Response(new ReadableStream({ cancel }), {
				headers: { 'Content-Type': 'text/event-stream' }
			}),
			controller.signal,
			{}
		);
		controller.abort();
		await expect(pending).rejects.toHaveProperty('name', 'AbortError');
		await vi.waitFor(() => expect(cancel).toHaveBeenCalled());
	});
	it('surfaces JSON provider errors even with HTTP 200', async () => {
		await expect(
			readHandoffResponse(
				new Response(JSON.stringify({ error: 'secret provider details' })),
				signal(),
				{}
			)
		).rejects.toThrow('模型服务返回错误');
	});
});
