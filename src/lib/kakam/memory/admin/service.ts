import type { ProviderForm, ProviderView } from './types';

export function toForm(value: ProviderView): ProviderForm {
	return {
		base_url: value.base_url,
		model: value.model,
		enabled: value.enabled,
		protocol: value.protocol,
		timeout_seconds: value.timeout_seconds,
		dimension: value.dimension,
		revision: value.revision,
		api_key_action: 'keep',
		api_key: '',
		acknowledge_reindex: false
	};
}

export function payload(form: ProviderForm): ProviderForm {
	return { ...form, api_key: form.api_key_action === 'replace' ? form.api_key : '' };
}
