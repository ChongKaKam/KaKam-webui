import { describe, expect, it } from 'vitest';
import { rememberDraft, memoryContentError, isSavedMemoryChat } from './remember';
import { canAccessMemoryPolicy } from './navigation';
const history = {
	messages: {
		q: { role: 'user', content: '如何备份？' },
		a: { role: 'assistant', parentId: 'q', content: '回答 A' },
		other: { role: 'assistant', parentId: 'q', content: '不要混入' },
		system: { role: 'system', content: '秘密系统消息' }
	}
};
describe('Remember it preview', () => {
	it('includes only the selected turn and visible answer, never sibling/history/system', () => {
		const result = rememberDraft(history, 'a', '<think>隐藏推理</think>备份数据库。');
		expect(result?.content).toContain('如何备份？');
		expect(result?.content).toContain('备份数据库。');
		for (const forbidden of ['隐藏推理', '不要混入', '秘密系统消息'])
			expect(result?.content).not.toContain(forbidden);
		expect(result?.content).toContain('未经独立验证');
	});
	it('keeps long content intact until the user edits it', () => {
		const result = rememberDraft(history, 'a', '长'.repeat(2100));
		expect(result?.content).toContain('长'.repeat(2100));
		expect(memoryContentError(result!.content)).toContain('精简');
		expect(memoryContentError('')).toContain('填写');
		expect(memoryContentError('😀'.repeat(2000))).toBe('');
	});
	it('ignores attachments and does not invent missing parent turns', () => {
		expect(rememberDraft(history, 'missing', 'answer')).toBeNull();
		expect(
			rememberDraft({ messages: { ...history.messages, q: { role: 'system' } } }, 'a', 'answer')
		).toBeNull();
		const media = {
			messages: {
				...history.messages,
				q: {
					role: 'user',
					content: [
						{ type: 'text', text: '看图' },
						{ type: 'image_url', image_url: 'secret-url' }
					]
				}
			}
		};
		expect(rememberDraft(media, 'a', '图片说明')?.content).not.toContain('secret-url');
	});
	it('excludes read-ineligible roles and identifies unsaved chats', () => {
		for (const user of [
			null,
			{ role: 'pending' },
			{ role: 'user', permissions: { features: { memories: false } } }
		])
			expect(canAccessMemoryPolicy(user)).toBe(false);
		for (const id of ['', 'temporary:1', 'local:1', 'channel:1'])
			expect(isSavedMemoryChat(id)).toBe(false);
		expect(isSavedMemoryChat('saved-chat')).toBe(true);
	});
});
