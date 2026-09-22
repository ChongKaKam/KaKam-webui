import type { ReasoningCapability } from '../providers/reasoning';

export const effortLevels = ['none', 'low', 'medium', 'high', 'extra high'] as const;
export type Effort = (typeof effortLevels)[number];

export type EffortModel = {
	id: string;
	kakam_provider?: { id: string; alias: string; model_id: string; reasoning?: ReasoningCapability };
	owned_by?: string;
	direct?: boolean;
	info?: {
		base_model_id?: string | null;
		meta?: {
			reasoning_effort?: unknown;
			capabilities?: { reasoning_effort?: unknown };
		};
	};
};

export type ChatParams = Record<string, unknown> & { kakam_effort?: Record<string, Effort> };

export function normalizeEffort(value: unknown): Effort | undefined {
	if (value === 'xhigh' || value === 'max') return 'extra high';
	return effortLevels.includes(value as Effort) ? (value as Effort) : undefined;
}

/** UI choices are open for every model; provider discovery is advisory only. */
export function supportedEfforts(model?: EffortModel): Effort[] {
	return model ? [...effortLevels] : [];
}

export function selectedEffort(model: EffortModel | undefined, params: ChatParams = {}): Effort {
	return model ? (normalizeEffort(params.kakam_effort?.[model.id]) ?? 'high') : 'none';
}

function clearEffort(params: Record<string, unknown>) {
	delete params.kakam_effort;
	delete params.reasoning_effort;
	if (
		params.reasoning &&
		typeof params.reasoning === 'object' &&
		!Array.isArray(params.reasoning)
	) {
		const reasoning = { ...params.reasoning } as Record<string, unknown>;
		delete reasoning.effort;
		if (Object.keys(reasoning).length) params.reasoning = reasoning;
		else delete params.reasoning;
	}
}

export function selectEffort(params: ChatParams, model: EffortModel, value: unknown): ChatParams {
	const effort = normalizeEffort(value);
	if (!effort || !supportedEfforts(model).includes(effort)) return params;
	return { ...params, kakam_effort: { ...params.kakam_effort, [model.id]: effort } };
}

/** Each request resolves independently, including compare mode and @model overrides. */
export function effortRequest(model: EffortModel, params: ChatParams) {
	const outgoing = { ...params };
	clearEffort(outgoing);
	if (outgoing.custom_params && typeof outgoing.custom_params === 'object') {
		const custom = { ...outgoing.custom_params } as Record<string, unknown>;
		clearEffort(custom);
		outgoing.custom_params = custom;
	}
	const effort = selectedEffort(model, params);
	const declared =
		model.info?.meta?.reasoning_effort ?? model.info?.meta?.capabilities?.reasoning_effort;
	const wireValues = Array.isArray(declared) ? declared : model.kakam_provider?.reasoning?.values;
	const apiValue =
		effort === 'none'
			? null
			: effort === 'extra high'
				? wireValues?.includes('max')
					? 'max'
					: 'xhigh'
				: effort;
	if (apiValue !== null) outgoing.reasoning_effort = apiValue;
	return {
		params: outgoing,
		// Consumed at the BFF egress, after upstream global/model defaults are merged.
		...(model.owned_by !== 'ollama' || model.direct ? { _kakam_reasoning_effort: apiValue } : {})
	};
}
