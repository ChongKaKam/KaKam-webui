import { describe, expect, it } from 'vitest';
import { detectReasoning, reasoningSummary } from './reasoning';
import { discoveredModels, poolConnection } from './service';
import { effortRequest, selectedEffort, selectEffort, supportedEfforts } from '../chat/effort';

describe('automatic reasoning capability discovery', () => {
	it('requires both the official endpoint and an exact known model ID', () => {
		const model = { id: 'deepseek-flash' };
		expect(detectReasoning(model, 'https://api.deepseek.com/v1/').values).toEqual([
			'none',
			'low',
			'high',
			'max'
		]);
		for (const url of [
			'https://reseller.test/v1',
			'https://api.deepseek.com.evil.test',
			'http://api.deepseek.com',
			'https://api.deepseek.com/proxy',
			'https://api.deepseek.com:8443'
		])
			expect(detectReasoning(model, url).status).toBe('unknown');
		expect(detectReasoning({ id: 'dpsk-4.1-flash' }, 'https://api.deepseek.com').status).toBe(
			'unknown'
		);
	});
	it('recognizes explicit levels for aliases, but not generic reasoning or accepted parameter flags', () => {
		expect(
			detectReasoning({
				id: 'dpsk-4.1-flash',
				capabilities: { reasoning_effort: ['low', 'high', 'max'] }
			}).status
		).toBe('supported');
		for (const model of [
			{ capabilities: { reasoning: true } },
			{ reasoning_effort: true },
			{ supported_parameters: ['reasoning_effort'] },
			{ reasoning_effort: ['automatic', 'high'] }
		])
			expect(detectReasoning(model).status).toBe('unknown');
	});
	it('honors explicit negative metadata over official rules and validates value lists', () => {
		expect(
			detectReasoning(
				{ id: 'deepseek-flash', info: { meta: { reasoning_effort: false } } },
				'https://api.deepseek.com'
			).status
		).toBe('unsupported');
		expect(
			detectReasoning({ reasoning_effort: { supported: false, values: ['high'] } }).status
		).toBe('unsupported');
		expect(
			detectReasoning({ reasoning_effort: { values: ['high', 'low', 'high'] } }).values
		).toEqual(['low', 'high']);
		expect(detectReasoning(null).status).toBe('unknown');
	});
	it('persists capability with the selected supplier model and encodes max correctly', () => {
		const connection = { url: 'https://api.deepseek.com/v1', key: 'secret', config: {} };
		const rows = discoveredModels(
			{ data: [{ id: 'deepseek-flash', secret: 'never store me' }] },
			connection.url
		);
		const saved = poolConnection(connection, 'Official', rows, ['deepseek-flash']);
		const reasoning = saved.config.kakam_supplier!.models[0].reasoning;
		const model = {
			id: 'supplier.deepseek-flash',
			owned_by: 'openai',
			kakam_provider: { id: 'supplier', alias: 'Official', model_id: 'deepseek-flash', reasoning }
		};
		expect(JSON.stringify(rows)).not.toContain('secret');
		expect(supportedEfforts(model)).toEqual(['none', 'low', 'medium', 'high', 'extra high']);
		expect(selectedEffort(model)).toBe('high');
		expect(
			effortRequest(model, selectEffort({}, model, 'extra high'))._kakam_reasoning_effort
		).toBe('max');
		expect(effortRequest(model, selectEffort({}, model, 'none'))._kakam_reasoning_effort).toBe(
			null
		);
		const overridden = { ...model, info: { meta: { reasoning_effort: ['high', 'xhigh'] } } };
		expect(
			effortRequest(overridden, selectEffort({}, overridden, 'extra high'))._kakam_reasoning_effort
		).toBe('xhigh');
		expect(supportedEfforts({ ...model, info: { meta: { reasoning_effort: false } } })).toContain(
			'high'
		);
	});
	it('keeps discovery advisory and allows high for unknown suppliers', () => {
		const model = {
			id: 'supplier.gpt-6-astra',
			owned_by: 'openai',
			kakam_provider: {
				id: 'supplier',
				alias: 'Partner',
				model_id: 'gpt-6-astra',
				reasoning: detectReasoning({ id: 'gpt-6-astra' }, 'https://partner.test')
			}
		};
		expect(supportedEfforts(model)).toContain('high');
		expect(effortRequest(model, {})._kakam_reasoning_effort).toBe('high');
		expect(reasoningSummary(model.kakam_provider.reasoning)).toContain('未确认');
		expect(reasoningSummary(detectReasoning({ reasoning_effort: false }))).toContain('不支持');
	});
});
