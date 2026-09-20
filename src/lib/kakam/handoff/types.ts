import type { EffortModel } from '../chat/effort';
export type HandoffModel = EffortModel & {
	name?: string;
	info?: EffortModel['info'] & { meta?: { hidden?: boolean } };
};
export type HandoffMessage = { parentId?: string | null; role?: string; content?: unknown };
export type HandoffHistory = {
	currentId?: string | null;
	messages: Record<string, HandoffMessage>;
};
export type HandoffInput = { text: string; truncated: boolean; count: number; hasMemory: boolean };
