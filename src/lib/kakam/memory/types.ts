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
export type Memory = { id: string; content: string; kind: string; expires_at: string };
export type Composition = {
	policy: string;
	days: number;
	cache_hit: boolean;
	status: 'ready' | 'unavailable' | 'disabled' | 'shadow';
	memory_count: number;
	model: string;
	message_id: string;
	detail_id?: string;
	segments: { kind: SegmentKind; characters: number; estimated_tokens: number }[];
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
