import { afterEach, describe, expect, it, vi } from 'vitest';
import { getJevConfig, readTurnEvents, runJevTurn, saveJevConfig } from './api';
import type { TurnEvent } from './types';

afterEach(() => {
	vi.unstubAllGlobals();
});

function stream(chunks: Uint8Array[]) {
	return new Response(
		new ReadableStream({
			start(controller) {
				chunks.forEach((chunk) => controller.enqueue(chunk));
				controller.close();
			}
		}),
		{ headers: { 'Content-Type': 'text/event-stream' } }
	);
}

describe('Jev API and streaming', () => {
	it('parses fragmented UTF-8, CRLF and heartbeats with final completion', async () => {
		const bytes = new TextEncoder().encode(
			': keepalive\r\n\r\ndata: {"type":"clarification","message":"有哪些选项？"}\r\n\r\ndata: {"type":"stage","stage":"done"}\n\n'
		);
		const events: TurnEvent[] = [];
		await readTurnEvents(
			stream(Array.from(bytes, (b) => new Uint8Array([b]))),
			new AbortController().signal,
			(e) => events.push(e)
		);
		expect(events).toEqual([
			{ type: 'clarification', message: '有哪些选项？' },
			{ type: 'stage', stage: 'done' }
		]);
	});
	it('does not report a broken stream as completed', async () => {
		const events: TurnEvent[] = [];
		await expect(
			readTurnEvents(
				stream([new TextEncoder().encode('data: {"type":"stage","stage":"deciding"}\n\n')]),
				new AbortController().signal,
				(e) => events.push(e)
			)
		).rejects.toThrow('连接中断');
		expect(events).toHaveLength(1);
	});
	it('handles explicit server failures without claiming success', async () => {
		const events: TurnEvent[] = [];
		await readTurnEvents(
			stream([
				new TextEncoder().encode('data: {"type":"error","code":"timeout","message":"超时"}\n\n')
			]),
			new AbortController().signal,
			(e) => events.push(e)
		);
		expect(events[0].type).toBe('error');
	});
	it('aborts an idle stream and releases its reader', async () => {
		const controller = new AbortController();
		const cancel = vi.fn();
		const response = new Response(new ReadableStream({ cancel }), {
			headers: { 'Content-Type': 'text/event-stream' }
		});
		const pending = readTurnEvents(response, controller.signal, vi.fn());
		controller.abort();
		await expect(pending).rejects.toMatchObject({ name: 'AbortError' });
		expect(cancel).toHaveBeenCalledOnce();
	});
	it('calls only the authenticated BFF and omits unchanged keys', async () => {
		vi.stubGlobal('localStorage', { token: 'webui-token' });
		const fetcher = vi.fn().mockResolvedValue(
			new Response(
				JSON.stringify({
					base_url: 'https://api.typesafe.ai/v1',
					has_api_key: true,
					model: 'jev-latest'
				})
			)
		);
		vi.stubGlobal('fetch', fetcher);
		await saveJevConfig({ base_url: 'https://api.typesafe.ai/v1' });
		const [url, init] = fetcher.mock.calls[0];
		expect(url).toBe('/api/custom/jev/config');
		expect(init.headers.Authorization).toBe('Bearer webui-token');
		expect(JSON.parse(init.body)).not.toHaveProperty('api_key');
		expect(init.cache).toBe('no-store');
	});
	it('surfaces authorization failure before trying to read an event stream', async () => {
		vi.stubGlobal('localStorage', { token: 'webui-token' });
		vi.stubGlobal(
			'fetch',
			vi
				.fn()
				.mockResolvedValue(
					new Response(JSON.stringify({ detail: '无权使用模型' }), { status: 403 })
				)
		);
		await expect(
			runJevTurn(
				'private',
				[{ role: 'user', content: 'hello' }],
				new AbortController().signal,
				vi.fn()
			)
		).rejects.toThrow('无权使用模型');
	});
	it('handles a non-JSON gateway error', async () => {
		vi.stubGlobal('localStorage', { token: 'webui-token' });
		vi.stubGlobal(
			'fetch',
			vi.fn().mockResolvedValue(new Response('<html>Bad Gateway</html>', { status: 502 }))
		);
		await expect(getJevConfig()).rejects.toThrow('502');
	});
});
