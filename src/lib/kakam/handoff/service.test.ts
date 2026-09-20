import { describe, expect, it } from 'vitest';
import { buildHandoffInput, completionText } from './service';
import type { HandoffHistory } from './types';

describe('handoff source', () => {
	const history: HandoffHistory = {
		messages: {
			root: { role: 'user', content: 'Build a dashboard' },
			a: { parentId: 'root', role: 'assistant', content: 'Finished charts' },
			other: { parentId: 'root', role: 'assistant', content: 'OTHER BRANCH' },
			last: {
				parentId: 'a',
				role: 'user',
				content: [
					{ type: 'text', text: 'Next: mobile layout' },
					{ type: 'image_url', image_url: { url: 'PRIVATE IMAGE' } }
				]
			}
		}
	};
	it('uses the selected branch including its latest message, with no sibling or image data', () => {
		const input = buildHandoffInput(history, 'last', null);
		expect(input.count).toBe(3);
		expect(JSON.parse(input.text).conversation.map((m: { content: string }) => m.content)).toEqual([
			'Build a dashboard',
			'Finished charts',
			'Next: mobile layout'
		]);
		expect(input.text).not.toContain('OTHER BRANCH');
		expect(input.text).not.toContain('PRIVATE IMAGE');
	});
	it('never serializes system or restricted context, and rejects mismatched snapshots', () => {
		const sections = [
			{ kind: 'system' as const, content: 'PRIVATE SYSTEM', restricted: false, truncated: false },
			{ kind: 'long_term' as const, content: 'PRIVATE MEMORY', restricted: true, truncated: false }
		];
		expect(buildHandoffInput(history, 'last', { message_id: 'last', sections }).text).not.toContain(
			'PRIVATE'
		);
		sections[1].restricted = false;
		expect(buildHandoffInput(history, 'last', { message_id: 'other', sections }).hasMemory).toBe(
			false
		);
		expect(buildHandoffInput(history, 'last', { message_id: 'last', sections }).hasMemory).toBe(
			true
		);
	});
	it('omits hidden reasoning blocks from assistant text', () => {
		const input = buildHandoffInput(
			{
				messages: {
					a: {
						role: 'assistant',
						content:
							'<think>PRIVATE REASONING</think><details type="reasoning">PRIVATE TRACE</details>Visible answer'
					}
				}
			},
			'a',
			null
		);
		expect(input.text).toContain('Visible answer');
		expect(input.text).not.toContain('PRIVATE');
	});
	it('bounds long text while preserving the original goal and latest state', () => {
		const input = buildHandoffInput(
			{
				messages: {
					root: { role: 'user', content: 'ORIGINAL GOAL' },
					a: { role: 'assistant', parentId: 'root', content: 'x'.repeat(90_000) + 'LATEST STATE' }
				}
			},
			'a',
			null
		);
		expect(input.truncated).toBe(true);
		expect(input.text).toContain('ORIGINAL GOAL');
		expect(input.text).toContain('LATEST STATE');
		expect(input.text.length).toBeLessThan(30_000);
	});
	it('terminates on cycles and reports missing history', () => {
		expect(
			buildHandoffInput(
				{ messages: { a: { role: 'user', parentId: 'a', content: 'hi' } } },
				'a',
				null
			).truncated
		).toBe(true);
		expect(buildHandoffInput(history, 'missing', null).count).toBe(0);
	});
	it('handles normal, empty and incomplete provider responses', () => {
		expect(completionText({ choices: [{ message: { content: '  # Handoff  ' } }] })).toBe(
			'# Handoff'
		);
		expect(() => completionText({ choices: [] })).toThrow('没有返回');
		expect(
			completionText({ choices: [{ message: { content: 'Partial' }, finish_reason: 'length' }] })
		).toContain('可能不完整');
	});
});
