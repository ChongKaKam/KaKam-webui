import { afterEach, describe, expect, it, vi } from 'vitest';
import {
	extractArtifacts,
	fileId,
	messageFiles,
	messageText,
	previewDocument,
	exportChat,
	safeFilename,
	saveBlob
} from './service';
import type { Message } from './types';

afterEach(() => {
	vi.restoreAllMocks();
	vi.unstubAllGlobals();
	vi.useRealTimers();
});

it('delivers exact bytes through a named download link and releases its object URL', async () => {
	vi.useFakeTimers();
	const link = { href: '', download: '', click: vi.fn(), remove: vi.fn() };
	const appendChild = vi.fn();
	vi.stubGlobal('document', { createElement: () => link, body: { appendChild } });
	const create = vi.spyOn(URL, 'createObjectURL').mockReturnValue('blob:delivery');
	const revoke = vi.spyOn(URL, 'revokeObjectURL').mockImplementation(() => {});
	const blob = new Blob(['<!doctype html><html>网页</html>'], { type: 'text/html' });
	saveBlob(blob, '学习网站.html');
	expect(create).toHaveBeenCalledWith(blob);
	expect(await blob.text()).toContain('<html>网页</html>');
	expect(link.download).toBe('学习网站.html');
	expect(link.href).toBe('blob:delivery');
	expect(appendChild).toHaveBeenCalledWith(link);
	expect(link.click).toHaveBeenCalledOnce();
	expect(revoke).not.toHaveBeenCalled();
	vi.advanceTimersByTime(60_000);
	expect(revoke).toHaveBeenCalledWith('blob:delivery');
});

const message = (content: string): Message => ({
	id: 'm',
	role: 'assistant',
	content,
	files: [],
	output: [],
	timestamp: 0,
	parent_id: null
});

describe('actual artifact exports', () => {
	it('downloads raw HTML from a Markdown note, keeping scripts and styles', () => {
		const html =
			'<!DOCTYPE html><html><style>body{color:red}</style><script>let n=1</script></html>';
		const artifacts = extractArtifacts(`网站：\n\n\`\`\`html\n${html}\n\`\`\``, '学习网站');
		expect(artifacts).toEqual([
			{ name: '学习网站-1.html', content: html, mime: 'text/html', preview: true }
		]);
		expect(extractArtifacts('# A website description')).toEqual([]);
	});
	it('supports raw documents and does not rename SVG to HTML', () => {
		expect(extractArtifacts('<svg viewBox="0 0 1 1"></svg>')[0].name).toMatch(/\.svg$/);
		expect(extractArtifacts('<!doctype html><html>Hello</html>')[0].mime).toBe('text/html');
		expect(extractArtifacts('```json\n{"x":1}\n```')[0].preview).toBe(false);
	});
	it('parses long/nested fences without truncating code', () => {
		expect(extractArtifacts('````markdown\n```html\nhi\n```\n````')[0].content).toBe(
			'```html\nhi\n```'
		);
	});
	it('exports structured assistant text, all branches and attachment references', () => {
		const m = message('old');
		m.output = [{ type: 'message', content: [{ type: 'output_text', text: 'new' }] }];
		m.files = [{ id: 'file-id', name: 'report.pdf' }];
		expect(messageText(m)).toBe('new');
		const md = exportChat({
			id: 'chat',
			title: 'Test',
			messages: [m, { ...m, id: 'branch', parent_id: 'm' }],
			current_message_id: 'm'
		});
		expect(md).toContain('ID: branch · Parent: m');
		expect(md).toContain('report.pdf');
	});
	it('deduplicates native images and keeps external URLs away from authenticated fetch', () => {
		const m = message('![image](/api/v1/files/f1/content)');
		m.files = [{ id: 'f1', url: '/api/v1/files/f1/content' }];
		expect(messageFiles(m)).toHaveLength(1);
		expect(fileId({ url: 'https://evil.test/api/v1/files/f1/content' })).toBeNull();
		expect(fileId({ source: 'open_terminal', id: 'f1', path: '/tmp/file' })).toBeNull();
	});
	it('isolates preview networks and sanitizes download names', () => {
		expect(previewDocument('<script>alert(1)</script>')).toContain("connect-src 'none'");
		expect(safeFilename('../report\n.html')).not.toMatch(/[\n/]/);
	});
	it('retains terminal display_file provenance without treating a server path as native storage', () => {
		const m = message('');
		m.output = [
			{ type: 'function_call', call_id: 'tool', name: 'display_file', arguments: '{}' },
			{
				type: 'function_call_output',
				call_id: 'tool',
				output: [
					{
						type: 'text',
						text: JSON.stringify({
							type: 'file',
							source: 'open_terminal',
							path: '/workspace/report.pdf',
							terminal_selector: 'terminal-1',
							exists: true
						})
					}
				]
			}
		];
		const attachments = messageFiles(m);
		expect(attachments).toHaveLength(1);
		expect(attachments[0].path).toBe('/workspace/report.pdf');
		expect(fileId(attachments[0])).toBeNull();
	});
});
