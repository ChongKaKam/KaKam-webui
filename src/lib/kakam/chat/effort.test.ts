import { describe, expect, it } from 'vitest';
import {
	effortRequest,
	selectedEffort,
	selectEffort,
	supportedEfforts,
	type EffortModel
} from './effort';

const astra: EffortModel = { id: 'gpt-6-astra', owned_by: 'openai' };
const unknown: EffortModel = { id: 'custom-alias', owned_by: 'openai' };

describe('reasoning effort capability and requests', () => {
	it('defaults supported models to high and does not invent support for aliases', () => {
		expect(selectedEffort(astra)).toBe('high');
		for (const id of [
			'custom-alias',
			'gpt-6-unknown',
			'gpt-6-astra-pro',
			'deepseek-v4',
			'minimax'
		]) {
			expect(selectedEffort({ id })).toBe('none');
		}
		expect(supportedEfforts(astra)).not.toContain('none');
	});
	it('uses explicit metadata and base IDs, with a negative override taking precedence', () => {
		expect(supportedEfforts({ ...unknown, info: { base_model_id: astra.id } })).toContain('high');
		expect(supportedEfforts({ ...astra, info: { meta: { reasoning_effort: false } } })).toEqual([]);
		expect(
			supportedEfforts({
				...unknown,
				info: { meta: { reasoning_effort: ['none', 'high', 'xhigh', 'invalid'] } }
			})
		).toEqual(['none', 'high', 'extra high']);
		expect(
			supportedEfforts({ ...unknown, info: { meta: { capabilities: { reasoning_effort: true } } } })
		).toEqual(['low', 'medium', 'high']);
	});
	it('keeps choices per model and resolves each comparison request independently', () => {
		const params = selectEffort({ temperature: 0.6 }, astra, 'extra high');
		expect(effortRequest(astra, params).params.reasoning_effort).toBe('xhigh');
		expect(selectedEffort(unknown, params)).toBe('none');
		expect(selectedEffort(astra, JSON.parse(JSON.stringify(params)))).toBe('extra high');
		expect(selectEffort(params, astra, 'none')).toBe(params);
	});
	it('removes stale global/custom effort and private UI state without mutating saved settings', () => {
		const params = {
			reasoning_effort: 'high',
			temperature: 0.7,
			custom_params: { reasoning_effort: 'xhigh', other: 1 },
			kakam_effort: { [astra.id]: 'high' as const }
		};
		const before = structuredClone(params);
		const result = effortRequest(unknown, params);
		expect(result.params).toEqual({ temperature: 0.7, custom_params: { other: 1 } });
		expect(result._kakam_reasoning_effort).toBeNull();
		expect(params).toEqual(before);
	});
	it('distinguishes supported none from unsupported omission, including direct connections', () => {
		const model = {
			...unknown,
			direct: true,
			info: { meta: { reasoning_effort: ['none', 'high'] } }
		};
		expect(effortRequest(model, selectEffort({}, model, 'none'))._kakam_reasoning_effort).toBe(
			'none'
		);
		expect(effortRequest({ ...unknown, direct: true }, {})._kakam_reasoning_effort).toBeNull();
		expect(effortRequest({ ...unknown, owned_by: 'ollama' }, {})).not.toHaveProperty(
			'_kakam_reasoning_effort'
		);
	});
	it('falls back safely when saved effort is unsupported or capability changes', () => {
		expect(selectedEffort(astra, { kakam_effort: { [astra.id]: 'none' } })).toBe('high');
		expect(selectedEffort({ ...astra, info: { meta: { reasoning_effort: ['low'] } } })).toBe('low');
	});
});
