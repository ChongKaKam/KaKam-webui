import type { ReasoningCapability } from './reasoning';
export type DiscoveredModel = { id: string; name: string; reasoning?: ReasoningCapability };
export type Supplier = { id: string; alias: string; models: DiscoveredModel[] };
export type ConnectionConfig = Record<string, unknown> & {
	enable?: boolean;
	api_type?: string;
	auth_type?: string;
	provider?: string;
	api_version?: string;
	azure?: boolean;
	headers?: Record<string, string>;
	prefix_id?: string;
	model_ids?: string[];
	kakam_supplier?: Supplier;
};
export type Connection = { url: string; key: string; config: ConnectionConfig };
export type ProviderConfig = {
	ENABLE_OPENAI_API: boolean;
	OPENAI_API_BASE_URLS: string[];
	OPENAI_API_KEYS: string[];
	OPENAI_API_CONFIGS: Record<string, ConnectionConfig>;
};
export type ProviderModel = {
	id: string;
	name?: string;
	kakam_provider?: { id: string; alias: string; model_id: string };
};
