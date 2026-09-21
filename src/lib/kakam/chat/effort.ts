export const effortLevels = ['none', 'low', 'medium', 'high', 'extra high'] as const;
export type Effort = (typeof effortLevels)[number];

export type EffortModel = {
	id: string;
	kakam_provider?: { id: string; alias: string; model_id: string };
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
	if (value === 'xhigh') return 'extra high';
	return effortLevels.includes(value as Effort) ? (value as Effort) : undefined;
}

/** Explicit metadata wins. Unknown IDs and marketing/display names are not capabilities. */
export function supportedEfforts(model?: EffortModel): Effort[] {
	if (!model || model.owned_by === 'ollama' || model.owned_by === 'arena') return [];
	const declared =
		model.info?.meta?.reasoning_effort ?? model.info?.meta?.capabilities?.reasoning_effort;
	if (declared === false) return [];
	if (Array.isArray(declared)) {
		return effortLevels.filter((level) =>
			declared.some((value) => normalizeEffort(value) === level)
		);
	}
	if (declared === true) return ['low', 'medium', 'high'];
	const id = (
		model.kakam_provider?.model_id ||
		model.info?.base_model_id ||
		model.id
	).toLowerCase();
	if (/^gpt-6-astra(?:-\d{4}-\d{2}-\d{2})?$/.test(id)) {
		return ['low', 'medium', 'high', 'extra high'];
	}
	if (/^gpt-5\.(2|5)(?:-\d{4}-\d{2}-\d{2})?$/.test(id)) return [...effortLevels];
	if (/^gpt-5(?:-\d{4}-\d{2}-\d{2})?$/.test(id)) return ['low', 'medium', 'high'];
	return [];
}

export function selectedEffort(model: EffortModel | undefined, params: ChatParams = {}): Effort {
	const supported = supportedEfforts(model);
	if (!supported.length) return 'none';
	const requested = normalizeEffort(model && params.kakam_effort?.[model.id]);
	return requested && supported.includes(requested)
		? requested
		: supported.includes('high')
			? 'high'
			: supported[supported.length - 1];
}

export function selectEffort(params: ChatParams, model: EffortModel, value: unknown): ChatParams {
	const effort = normalizeEffort(value);
	if (!effort || !supportedEfforts(model).includes(effort)) return params;
	return { ...params, kakam_effort: { ...params.kakam_effort, [model.id]: effort } };
}

/** Each request resolves independently, including compare mode and @model overrides. */
export function effortRequest(model: EffortModel, params: ChatParams) {
	const outgoing = { ...params };
	delete outgoing.kakam_effort;
	delete outgoing.reasoning_effort;
	if (outgoing.custom_params && typeof outgoing.custom_params === 'object') {
		const custom = { ...outgoing.custom_params } as Record<string, unknown>;
		delete custom.reasoning_effort;
		delete custom.kakam_effort;
		outgoing.custom_params = custom;
	}
	const effort = supportedEfforts(model).length ? selectedEffort(model, params) : null;
	const apiValue = effort === 'extra high' ? 'xhigh' : effort;
	if (apiValue !== null) outgoing.reasoning_effort = apiValue;
	return {
		params: outgoing,
		// Consumed at the BFF egress, after upstream global/model defaults are merged.
		...(model.owned_by === 'openai' || model.direct ? { _kakam_reasoning_effort: apiValue } : {})
	};
}
