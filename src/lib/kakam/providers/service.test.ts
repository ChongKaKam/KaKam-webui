import { describe, it, expect } from 'vitest';
import {
	discoveredModels,
	newConnection,
	poolConnection,
	connectionsFrom,
	connectionsTo,
	connectionFingerprint,
	supplierModelLabel
} from './service';
import { supportedEfforts } from '../chat/effort';
describe('supplier inventories', () => {
	it('normalizes model discovery, rejects invalid payloads and deduplicates IDs', () => {
		expect(
			discoveredModels({
				data: [{ id: 'a', name: 'A' }, { id: 'a', name: 'A' }, { no: 'id' }, 'b', null]
			})
		).toEqual([
			{ id: 'a', name: 'A' },
			{ id: 'b', name: 'b' }
		]);
		expect(() => discoveredModels({ error: 'bad key' })).toThrow('有效');
		expect(discoveredModels({ data: [] })).toEqual([]);
	});
	it('allocates distinct stable identities for the same model at different suppliers', () => {
		const discovered = [{ id: 'gpt-6-astra', name: 'GPT-6 Astra' }];
		const first = poolConnection(newConnection(), 'Official', discovered, ['gpt-6-astra']);
		const second = poolConnection(newConnection(), 'Partner', discovered, ['gpt-6-astra']);
		expect(first.config.prefix_id).not.toBe(second.config.prefix_id);
		const renamed = poolConnection(first, 'Renamed', discovered, ['gpt-6-astra']);
		expect(renamed.config.prefix_id).toBe(first.config.prefix_id);
		expect(renamed.config.kakam_supplier?.id).toBe(first.config.kakam_supplier?.id);
	});
	it('preserves legacy IDs and extra settings; empty whitelist stays explicitly empty', () => {
		const legacy = {
			url: 'https://example.test/v1/',
			key: 'test',
			config: { prefix_id: '', api_type: 'responses', headers: { 'X-Test': '1' } }
		};
		const saved = poolConnection(legacy, 'Legacy', [{ id: 'a', name: 'A' }], []);
		expect(saved.config.prefix_id).toBe('');
		expect(saved.config.model_ids).toEqual([]);
		expect(saved.config.kakam_supplier?.models).toEqual([]);
		expect(saved.config.headers).toEqual(legacy.config.headers);
		expect(legacy).not.toHaveProperty('config.kakam_supplier');
	});
	it('rejects an unverified model and an empty alias', () => {
		expect(() => poolConnection(newConnection(), 'A', [], ['injected'])).toThrow('未通过探测');
		expect(() => poolConnection(newConnection(), ' ', [], [])).toThrow('别名');
	});
	it('retains provider identity and credentials when deleting/reindexing connections', () => {
		const a = { ...newConnection(), url: 'https://a.test', key: 'a-key' };
		const b = { ...newConnection(), url: 'https://b.test', key: 'b-key' };
		const config = {
			ENABLE_OPENAI_API: true,
			OPENAI_API_BASE_URLS: [],
			OPENAI_API_KEYS: [],
			OPENAI_API_CONFIGS: {}
		};
		const loaded = connectionsFrom(connectionsTo(config, [a, b]));
		expect(connectionsFrom(connectionsTo(config, loaded.slice(1)))[0]).toEqual(b);
	});
	it('invalidates verification for transport changes but not aliases or allowlists', () => {
		const connection = newConnection();
		const before = connectionFingerprint(connection);
		connection.config.kakam_supplier!.alias = 'Renamed';
		connection.config.model_ids = ['new'];
		expect(connectionFingerprint(connection)).toBe(before);
		connection.key = 'changed';
		expect(connectionFingerprint(connection)).not.toBe(before);
	});
	it('labels provider models distinctly and retains reasoning capability via original ID', () => {
		const model = {
			id: 'supplier_id.gpt-6-astra',
			name: 'GPT-6 Astra',
			owned_by: 'openai',
			kakam_provider: { id: 'supplier_id', alias: 'Official', model_id: 'gpt-6-astra' }
		};
		expect(supplierModelLabel(model)).toBe('GPT-6 Astra · Official');
		expect(supportedEfforts(model)).toContain('high');
		expect(supportedEfforts({ ...model, info: { meta: { reasoning_effort: false } } })).toEqual([]);
	});
});
