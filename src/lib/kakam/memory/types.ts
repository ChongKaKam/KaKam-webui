export type SegmentKind = 'system' | 'long_term' | 'session' | 'current';
export type MemoryPreferences = { enabled: boolean; policy: string; days: number; cache: boolean };
export type Policy = {
	id: string;
	name: string;
	description: string;
	min_days: number;
	max_days: number;
};
export type Capabilities = { enabled: boolean; available: boolean; policies: Policy[] };
export type Memory = {
	id: string;
	content: string;
	kind: string;
	expires_at: string | null;
	version?: number;
	tags?: string[];
};
export type Composition = {
	policy: string;
	days: number;
	cache_hit: boolean;
	status: 'ready' | 'unavailable' | 'disabled' | 'shadow';
	memory_count: number;
	model: string;
	message_id: string;
	detail_id?: string;
	compaction?: { state: string; cut?: number; estimated_tokens?: number };
	omitted_preferred?: string[];
	segments: { kind: SegmentKind; characters: number; estimated_tokens: number }[];
};

export type SessionScope = {
	policy: string;
	selections: Record<string, 'prefer' | 'exclude'>;
	settings: {
		automatic_recall: boolean;
		auto_compact: boolean;
		token_budget: number;
		keep_messages: number;
	};
};
export type ManagerView = {
	contract_version: number;
	session: SessionScope;
	memories: Memory[];
	proposals: { id: string; content: string; kind: string; evidence: string; state: string }[];
	operations: {
		id: string;
		operation: string;
		state: string;
		created_at: string;
		facts: { selected_ids?: string[]; omitted_preferred?: string[]; cut?: number };
	}[];
	compaction: { available: boolean; summary: string; cut: number };
	collections: { id: string; name: string; parent_id: string | null }[];
	relations: { memory_id: string; collection_id: string }[];
	policies: Policy[];
};

export type ContextDetails = {
	message_id: string;
	sections: { kind: SegmentKind; content: string; truncated: boolean; restricted: boolean }[];
};

export type MemoryActivityDay = {
	date: string;
	requests: number;
	characters: Record<SegmentKind, number>;
};
export type MemoryActivity = {
	days: number;
	timezone: 'UTC';
	measurement: 'characters';
	requests: number;
	total_characters: number;
	characters: Record<SegmentKind, number>;
	heatmap: MemoryActivityDay[];
	truncated: boolean;
};
