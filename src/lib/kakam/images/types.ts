export type ImageProbeDraft = {
	engine: 'openai' | 'gemini';
	base_url: string;
	api_key: string;
	api_version: string;
	model: string;
	size: string;
	method: 'predict' | 'generateContent';
	params: Record<string, unknown>;
};
export type ImageProbeResult = {
	models?: { id: string; name: string }[];
	complete?: boolean;
	model_status?: 'available' | 'not_listed' | 'unknown';
	generated?: boolean;
};
