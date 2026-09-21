export type ProviderKind = 'context' | 'embedding';
export type ProviderSettings = {
	base_url: string;
	model: string;
	enabled: boolean;
	protocol: 'chat_completions' | 'responses' | 'embeddings';
	timeout_seconds: number;
	dimension: number;
	revision: number;
};
export type ProviderView = ProviderSettings & {
	api_key_set: boolean;
	source: 'database' | 'environment';
};
export type ProviderForm = ProviderSettings & {
	api_key_action: 'keep' | 'replace' | 'clear';
	api_key: string;
	acknowledge_reindex: boolean;
};
export type ConfigView = { write_enabled: boolean; providers: Record<ProviderKind, ProviderView> };
export type ProbeResult = {
	ok: boolean;
	status: string;
	message: string;
	http_status: number | null;
	elapsed_ms: number;
};
export type ModelsResult = ProbeResult & { models: string[]; truncated: boolean };
