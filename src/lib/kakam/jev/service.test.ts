import { describe, expect, it } from 'vitest';
import { answerRows, conversation, probability } from './service';
import type { Turn } from './types';

describe('Jev presentation semantics', () => {
	it('shows probabilities including zero without turning Score into a percentage', () => {
		const rows = answerRows(
			{
				type: 'score',
				score: 1.2,
				legend: { '0': 'Low', '1': 'Medium', '2': 'High' },
				probabilities: { '2': 0.2, '0': 0, '1': 0.8 }
			},
			{ title: '评分', options: { '0': '低', '1': '中', '2': '高' } }
		);
		expect(rows.map((r) => r.key)).toEqual(['0', '1', '2']);
		expect(rows[0].value).toBe(0);
		expect(rows[1].label).toBe('中');
	});
	it('keeps Noul as P(yes) and computes its complement', () => {
		const rows = answerRows(
			{ type: 'noul', noul: 0.1 },
			{ title: '是否？', options: { true: '是', false: '否' } }
		);
		expect(rows.map((r) => r.value)).toEqual([0.1, 0.9]);
		expect(probability(0)).toBe('0%');
		expect(probability(1)).toBe('100%');
		expect(probability(0.000001)).toBe('<0.01%');
		expect(probability(0.999999)).toBe('>99.99%');
	});
	it('sorts Choice probabilities while retaining the original option identifiers', () => {
		expect(
			answerRows(
				{ type: 'choice', choice: 'b', probabilities: { a: 0.05, b: 0.95 } },
				{ title: '选谁', options: { a: '甲', b: '乙' } }
			)[0]
		).toEqual({ key: 'b', label: '乙', value: 0.95 });
	});
	it('preserves clarification context and all original text without hidden truncation', () => {
		const old: Turn = {
			id: '1',
			input: '不能超过三天，也不能遗漏任何条件。',
			modelName: 'm',
			stage: 'done',
			startedAt: 0,
			clarification: '有哪些选项？'
		};
		expect(conversation([old], '甲方案或者乙方案')).toEqual([
			{ role: 'user', content: old.input },
			{ role: 'assistant', content: old.clarification },
			{ role: 'user', content: '甲方案或者乙方案' }
		]);
		expect(() => conversation([], 'a'.repeat(12001))).toThrow('完整保留');
	});
});
