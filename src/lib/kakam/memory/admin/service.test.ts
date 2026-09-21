import { describe, expect, it } from 'vitest';
import { discoverySource, payload, toForm } from './service';
import type { ProviderView } from './types';

const value: ProviderView = {
	base_url: 'https://fixture.invalid/v1',
	model: 'test',
	enabled: true,
	protocol: 'responses',
	timeout_seconds: 20,
	dimension: 3,
	revision: 2,
	api_key_set: true,
	source: 'database'
};

describe('admin Memory configuration', () => {
	it('invalidates discovery on endpoint or credential changes but not model selection', () => {
		const form = toForm(value);
		const source = discoverySource(form);
		expect(discoverySource({ ...form, model: 'other' })).toBe(source);
		expect(discoverySource({ ...form, base_url: 'https://other.invalid/v1' })).not.toBe(source);
		expect(discoverySource({ ...form, api_key_action: 'clear' })).not.toBe(source);
		expect(discoverySource({ ...form, api_key_action: 'replace', api_key: 'fixture' })).not.toBe(
			source
		);
	});
	it('never pre-fills a stored key and strips read-only fields', () => {
		const form = toForm(value);
		expect(form.api_key).toBe('');
		expect(form.api_key_action).toBe('keep');
		expect(form).not.toHaveProperty('source');
		expect(form).not.toHaveProperty('api_key_set');
		expect(form.revision).toBe(2);
	});
	it('sends a replacement only when explicitly selected', () => {
		const form = { ...toForm(value), api_key: 'draft-secret' };
		expect(payload(form).api_key).toBe('');
		expect(payload({ ...form, api_key_action: 'clear' }).api_key).toBe('');
		expect(payload({ ...form, api_key_action: 'replace' }).api_key).toBe('draft-secret');
	});
});
