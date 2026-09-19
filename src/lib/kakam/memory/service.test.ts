import { describe, expect, it } from 'vitest';
import { getComposition, makeCells } from './service';
import type { Composition, SegmentKind } from './types';

const kinds: SegmentKind[] = ['system', 'long_term', 'session', 'current'];
function report(counts: number[]): Composition {
	return {
		policy: 'default',
		days: 30,
		cache_hit: false,
		status: 'ready',
		memory_count: 1,
		model: 'test',
		message_id: 'reply',
		segments: counts.map((characters, i) => ({ kind: kinds[i], characters, estimated_tokens: 0 }))
	};
}

describe('prompt contribution matrix', () => {
	it('selects only the current response and clears on a new session', () => {
		const composition = report([1, 2, 3, 4]);
		const messages = { reply: { meta: { kakamMemory: composition } }, pending: {} };
		expect(getComposition({ currentId: 'reply', messages })).toBe(composition);
		expect(getComposition({ currentId: 'pending', messages })).toBeNull();
		expect(getComposition({ currentId: null, messages })).toBeNull();
	});
	it('preserves text quantities and four categories', () => {
		const counts = [401, 991, 3450, 25];
		const matrix = makeCells(report(counts));
		expect(matrix.total).toBe(counts.reduce((a, b) => a + b, 0));
		for (const [i, kind] of kinds.entries()) {
			expect(
				matrix.cells.filter((c) => c.kind === kind).reduce((n, c) => n + c.characters, 0)
			).toBe(counts[i]);
		}
	});
	it('bounds huge contexts without losing small segments', () => {
		const matrix = makeCells(report([1, 1, 500000, 1]));
		expect(matrix.cells.length).toBeLessThanOrEqual(224);
		expect(new Set(matrix.cells.map((c) => c.kind)).size).toBe(4);
	});
	it('handles empty context', () => expect(makeCells(report([0, 0, 0, 0])).cells).toEqual([]));
});
