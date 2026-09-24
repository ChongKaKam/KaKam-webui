import { marked } from 'marked';
import {
	buildOutputDisplayItems,
	getOutputText
} from '$lib/components/chat/Messages/structuredOutput';
import type { Artifact, Attachment, ChatDetail, Message } from './types';

export function safeFilename(name: string): string {
	return (
		Array.from(name, (character) => (character.charCodeAt(0) < 32 ? '-' : character))
			.join('')
			.replace(/[\\/:*?"<>|]/g, '-')
			.replace(/^\.+/, '')
			.trim()
			.slice(0, 140) || 'download'
	);
}

export function messageText(message: Message): string {
	if (message.output?.length) {
		const text = getOutputText(message.output);
		if (text) return text;
	}
	if (typeof message.content === 'string') return message.content;
	if (Array.isArray(message.content))
		return message.content.map((p) => (typeof p?.text === 'string' ? p.text : '')).join('\n');
	return '';
}

// Export the actual source, never pretend Markdown prose is a working website.
export function extractArtifacts(text: string, title = 'artifact'): Artifact[] {
	const result: Artifact[] = [];
	const types: Record<string, [string, string]> = {
		html: ['html', 'text/html'],
		svg: ['svg', 'image/svg+xml'],
		markdown: ['md', 'text/markdown'],
		md: ['md', 'text/markdown'],
		json: ['json', 'application/json'],
		csv: ['csv', 'text/csv'],
		css: ['css', 'text/css'],
		javascript: ['js', 'text/javascript'],
		js: ['js', 'text/javascript'],
		python: ['py', 'text/x-python'],
		py: ['py', 'text/x-python'],
		text: ['txt', 'text/plain']
	};
	const blocks: { lang: string; text: string }[] = [];
	marked.walkTokens(marked.lexer(text), (token) => {
		if (token.type === 'code')
			blocks.push({ lang: (token.lang || '').split(/\s+/)[0].toLowerCase(), text: token.text });
	});
	if (!blocks.length && /^\s*(<!doctype\s+html\b|<html\b)/i.test(text))
		blocks.push({ lang: 'html', text });
	if (!blocks.length && /^\s*<svg\b/i.test(text)) blocks.push({ lang: 'svg', text });
	for (const block of blocks) {
		const format = types[block.lang];
		if (!format) continue;
		const [ext, mime] = format;
		result.push({
			name: `${safeFilename(title)}-${result.length + 1}.${ext}`,
			content: block.text,
			mime,
			preview: ext === 'html' || ext === 'svg'
		});
	}
	return result;
}

export function fileId(file: Attachment): string | null {
	if (!file || typeof file !== 'object') return null;
	// Only relative native file URLs are authenticated with our bearer token.
	const match =
		typeof file.url === 'string'
			? file.url.match(/^\/api\/v1\/files\/([^/?#]+)\/content(?:[?#].*)?$/)
			: null;
	if (match) return match[1];
	if (file.source === 'open_terminal' || file.path) return null;
	return typeof file.id === 'string' && /^[a-zA-Z0-9_-]+$/.test(file.id) ? file.id : null;
}

export function messageFiles(message: Message): Attachment[] {
	const files = [...(message.files || [])].filter((file) => file && typeof file === 'object');
	for (const item of message.output || []) {
		if (Array.isArray(item?.files)) files.push(...(item.files as Attachment[]));
	}
	for (const item of buildOutputDisplayItems(message.output || [])) {
		if (item.type === 'file') files.push(item.item as Attachment);
	}
	// Older image responses may only contain a Markdown image or native file link.
	for (const match of messageText(message).matchAll(/\[[^\]]*\]\((\/api\/v1\/files\/[^\s)]+)\)/g))
		files.push({ url: match[1] });
	const validFiles = files.filter((file) => file && typeof file === 'object');
	return validFiles.filter(
		(f, i) =>
			f &&
			validFiles.findIndex(
				(x) => (fileId(x) || x.url || x.path) === (fileId(f) || f.url || f.path)
			) === i
	);
}

export function exportChat(chat: ChatDetail): string {
	return (
		`# ${chat.title}\n\n会话 ID：${chat.id}\n\n包含全部消息分支；各消息保留 ID 与父消息 ID。\n\n` +
		chat.messages
			.map(
				(m) =>
					`## ${m.role}\n\nID: ${m.id} · Parent: ${m.parent_id || '—'}\n\n${messageText(m)}\n\n` +
					messageFiles(m)
						.map(
							(f) => `附件引用：${f.name || f.filename || f.id || f.path || 'file'} ${f.url || ''}`
						)
						.join('\n')
			)
			.join('\n\n---\n\n')
	);
}

export function saveBlob(blob: Blob, name: string): void {
	const url = URL.createObjectURL(blob);
	const link = document.createElement('a');
	link.href = url;
	link.download = safeFilename(name);
	document.body.appendChild(link);
	link.click();
	link.remove();
	setTimeout(() => URL.revokeObjectURL(url), 60_000);
}
export const saveText = (text: string, name: string, mime = 'text/markdown') =>
	saveBlob(new Blob([text], { type: `${mime};charset=utf-8` }), name);
export function formatBytes(bytes: number | null): string {
	if (bytes === null) return '大小未记录';
	if (bytes < 1024) return `${bytes} B`;
	const unit = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), 3);
	return `${(bytes / 1024 ** unit).toFixed(1)} ${['B', 'KB', 'MB', 'GB'][unit]}`;
}

export const previewDocument = (content: string) =>
	`<!doctype html><meta http-equiv="Content-Security-Policy" content="default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; img-src data: blob:; font-src data:; connect-src 'none'; frame-src 'none'; form-action 'none'; base-uri 'none'">${content}`;
