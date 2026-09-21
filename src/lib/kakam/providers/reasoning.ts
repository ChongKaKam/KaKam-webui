/** Capability evidence, not an inference-quality or parameter-effectiveness test. */
export const wireEfforts = ['none', 'low', 'medium', 'high', 'xhigh', 'max'] as const;
export type WireEffort = (typeof wireEfforts)[number];
export type ReasoningCapability = {
	status: 'supported' | 'unsupported' | 'unknown';
	source: 'metadata' | 'official' | 'unknown';
	values: WireEffort[];
};

const unknown = (): ReasoningCapability => ({ status: 'unknown', source: 'unknown', values: [] });
const record = (value: unknown): Record<string, unknown> =>
	value && typeof value === 'object' && !Array.isArray(value)
		? (value as Record<string, unknown>)
		: {};

export function detectReasoning(model: unknown, baseUrl = ''): ReasoningCapability {
	const row = record(model);
	const meta = record(record(row.info).meta);
	// Missing fields and generic "reasoning: true" do not establish effort control.
	const declared =
		meta.reasoning_effort ??
		record(meta.capabilities).reasoning_effort ??
		row.reasoning_effort ??
		record(row.capabilities).reasoning_effort;
	if (declared !== undefined && declared !== null) {
		if (declared === false || record(declared).supported === false)
			return { status: 'unsupported', source: 'metadata', values: [] };
		const levels = Array.isArray(declared) ? declared : record(declared).values;
		if (Array.isArray(levels)) {
			// Reject unrecognized values instead of guessing how to encode them.
			if (levels.some((value) => !wireEfforts.includes(value)))
				return { ...unknown(), source: 'metadata' };
			const values = wireEfforts.filter((value) => levels.includes(value));
			return {
				status: values.some((value) => value !== 'none') ? 'supported' : 'unsupported',
				source: 'metadata',
				values
			};
		}
		return { ...unknown(), source: 'metadata' };
	}
	if (
		Array.isArray(row.supported_parameters) &&
		row.supported_parameters.includes('reasoning_effort')
	)
		return { ...unknown(), source: 'metadata' };

	let url: URL;
	try {
		url = new URL(baseUrl);
	} catch {
		return unknown();
	}
	// Endpoint AND exact model ID are required. Never infer a reseller alias from its name.
	if (url.protocol !== 'https:' || url.port || !['', '/', '/v1', '/v1/'].includes(url.pathname))
		return unknown();
	if (
		url.hostname === 'api.deepseek.com' &&
		[
			'deepseek-flash',
			'deepseek-v4-flash',
			'deepseek-v4-flash-vision-exp',
			'deepseek-v4-pro'
		].includes(String(row.id))
	) {
		// https://api-docs.deepseek.com/guides/thinking_mode/ (2026-09-21)
		return { status: 'supported', source: 'official', values: ['none', 'low', 'high', 'max'] };
	}
	if (url.hostname === 'api.openai.com') {
		const id = String(row.id);
		if (/^gpt-6-astra(?:-\d{4}-\d{2}-\d{2})?$/.test(id))
			return {
				status: 'supported',
				source: 'official',
				values: ['low', 'medium', 'high', 'xhigh']
			};
		if (/^gpt-5\.(2|5)(?:-\d{4}-\d{2}-\d{2})?$/.test(id))
			return {
				status: 'supported',
				source: 'official',
				values: ['none', 'low', 'medium', 'high', 'xhigh']
			};
		if (/^gpt-5(?:-\d{4}-\d{2}-\d{2})?$/.test(id))
			return { status: 'supported', source: 'official', values: ['low', 'medium', 'high'] };
	}
	return unknown();
}

export function reasoningSummary(capability?: ReasoningCapability): string {
	if (!capability || capability.status === 'unknown')
		return capability?.source === 'metadata'
			? '思考强度未确认 · 供应商未提供可用的明确档位'
			: '思考强度未确认 · 未提供能力信息';
	if (capability.status === 'unsupported') return '供应商声明不支持可调思考强度';
	return `思考强度：${capability.values
		.map((value) => (value === 'max' || value === 'xhigh' ? 'extra high' : value))
		.filter((value, index, values) => values.indexOf(value) === index)
		.join(' / ')} · ${capability.source === 'official' ? '官方接口规则' : '供应商能力声明'}`;
}
