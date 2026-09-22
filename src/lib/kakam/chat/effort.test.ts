import { describe, expect, it } from 'vitest';
import {
	effortLevels,
	effortRequest,
	selectedEffort,
	selectEffort,
	supportedEfforts,
	type EffortModel
} from './effort';
const astra: EffortModel = { id: 'gpt-6-astra', owned_by: 'openai' };
const unknown: EffortModel = { id: 'dpsk-4.1-flash', owned_by: 'openai' };

describe('open reasoning effort selection and requests', () => {
	it.each(['dpsk-4.1-flash', 'custom-alias', 'gpt-6-astra', 'claude', 'minimax'])(
		'offers every level and defaults %s to high',
		(id) => {
			expect(supportedEfforts({ id })).toEqual(effortLevels);
			expect(selectedEffort({ id })).toBe('high');
		}
	);
	it('does not restrict choices based on metadata, provider discovery or ownership', () => {
		for (const model of [
			{ ...unknown, info: { meta: { reasoning_effort: false } } },
			{ ...unknown, info: { meta: { reasoning_effort: ['low'] } } },
			{ ...unknown, owned_by: 'arena' },
			{ ...unknown, owned_by: 'ollama' },
			{
				...unknown,
				kakam_provider: {
					id: 'supplier',
					alias: 'Supplier',
					model_id: unknown.id,
					reasoning: { status: 'unsupported' as const, source: 'metadata' as const, values: [] }
				}
			}
		]) {
			expect(supportedEfforts(model)).toEqual(effortLevels);
			expect(selectedEffort(model)).toBe('high');
			expect(selectedEffort(model, selectEffort({}, model, 'none'))).toBe('none');
		}
	});
	it('preserves choices independently across models, comparison requests and saved chats', () => {
		const params = selectEffort(
			selectEffort({ temperature: 0.6 }, astra, 'extra high'),
			unknown,
			'none'
		);
		expect(effortRequest(astra, params).params.reasoning_effort).toBe('xhigh');
		expect(effortRequest(unknown, params)._kakam_reasoning_effort).toBeNull();
		expect(selectedEffort(astra, JSON.parse(JSON.stringify(params)))).toBe('extra high');
		expect(selectedEffort(unknown, JSON.parse(JSON.stringify(params)))).toBe('none');
	});
	it('none removes stale global/custom and Responses effort without mutating settings', () => {
		const params = selectEffort(
			{
				reasoning_effort: 'high',
				reasoning: { effort: 'high', summary: 'auto' },
				temperature: 0.7,
				custom_params: {
					reasoning_effort: 'xhigh',
					reasoning: { effort: 'high', summary: 'auto' },
					other: 1
				}
			},
			unknown,
			'none'
		);
		const before = structuredClone(params);
		const result = effortRequest(unknown, params);
		expect(result.params).toEqual({
			temperature: 0.7,
			reasoning: { summary: 'auto' },
			custom_params: { reasoning: { summary: 'auto' }, other: 1 }
		});
		expect(result._kakam_reasoning_effort).toBeNull();
		expect(params).toEqual(before);
	});
	it('sends high for unknown models, including direct and custom providers', () => {
		for (const model of [unknown, { ...unknown, direct: true }, { id: 'custom' }]) {
			expect(effortRequest(model, {}).params.reasoning_effort).toBe('high');
			expect(effortRequest(model, {})._kakam_reasoning_effort).toBe('high');
			expect(effortRequest(model, selectEffort({}, model, 'none')).params).not.toHaveProperty(
				'reasoning_effort'
			);
		}
	});
	it('uses provider metadata only to preserve extra-high wire encoding', () => {
		const model = { ...unknown, info: { meta: { reasoning_effort: ['max'] } } };
		expect(
			effortRequest(model, selectEffort({}, model, 'extra high')).params.reasoning_effort
		).toBe('max');
	});
	it('has no effort without a model and rejects invalid selections', () => {
		expect(selectedEffort(undefined)).toBe('none');
		const params = {};
		expect(selectEffort(params, astra, 'ultra')).toBe(params);
	});
});
