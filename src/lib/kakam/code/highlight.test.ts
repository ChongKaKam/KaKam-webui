import { describe, it, expect } from 'vitest';
import { highlight, withinHighlightBudget } from './highlight';
import { normalizeCodeTheme, codeThemes } from './themes';

describe('Shiki chat rendering', () => {
	it('escapes untrusted code and falls back for unknown languages', async () => {
		const html = await highlight(
			'<script>alert("x")</script><img onerror="x">',
			'not-a-language',
			'github'
		);
		expect(html).toMatch(/&(?:lt|#x3C);script/i);
		expect(html).not.toContain('<script>');
		expect(html).not.toContain('<img');
	});
	it('renders paired light/dark colors for each selectable theme', async () => {
		const outputs = [];
		for (const theme of Object.keys(codeThemes)) {
			const html = await highlight('const count = 42;', 'ts', theme);
			expect(html).toContain('--shiki-dark');
			expect(html).toContain('42');
			outputs.push(html);
		}
		expect(new Set(outputs).size).toBe(4);
	});
	it('bounds expensive work for huge or very long code', async () => {
		expect(withinHighlightBudget('x'.repeat(40_001))).toBe(false);
		expect(await highlight('\n'.repeat(1001), 'python', 'github')).toBeNull();
	});
	it('normalizes corrupt preferences without interpreting object prototype keys', () => {
		for (const value of [null, {}, 'constructor', '__proto__', 'missing'])
			expect(normalizeCodeTheme(value)).toBe('github');
		expect(normalizeCodeTheme('catppuccin')).toBe('catppuccin');
	});
});
