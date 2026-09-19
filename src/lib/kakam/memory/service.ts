import type { Composition, SegmentKind } from './types';

export const labels: Record<SegmentKind, string> = {
	system: 'System',
	long_term: '长期记忆',
	session: 'Session 记忆',
	current: '当前 Prompt'
};

export function getComposition(history: {
	currentId: string | null;
	messages: Record<string, { meta?: { kakamMemory?: Composition } }>;
}): Composition | null {
	return history.currentId
		? (history.messages[history.currentId]?.meta?.kakamMemory ?? null)
		: null;
}

export function makeCells(report: Composition) {
	const total = report.segments.reduce((sum, segment) => sum + segment.characters, 0);
	// Each nonempty type keeps at least one square, with a bounded DOM size.
	const unit = Math.max(64, Math.ceil(total / 220));
	return {
		unit,
		total,
		cells: report.segments.flatMap((segment) =>
			Array.from({ length: Math.ceil(segment.characters / unit) }, (_, index) => ({
				kind: segment.kind,
				characters: Math.min(unit, segment.characters - index * unit)
			}))
		)
	};
}
