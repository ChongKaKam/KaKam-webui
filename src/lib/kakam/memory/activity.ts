import type { MemoryActivityDay, SegmentKind } from './types';

export const segmentKinds: SegmentKind[] = ['system', 'long_term', 'session', 'current'];
export const segmentColors: Record<SegmentKind, string> = {
	system: '#8b5cf6',
	long_term: '#10b981',
	session: '#3b82f6',
	current: '#f59e0b'
};

export function proportions(characters: Record<SegmentKind, number>) {
	const total = segmentKinds.reduce((sum, kind) => sum + characters[kind], 0);
	return segmentKinds.map((kind) => ({
		kind,
		characters: characters[kind],
		percent: total ? (characters[kind] / total) * 100 : 0
	}));
}

export function dayColor(day: MemoryActivityDay, filter: SegmentKind | 'all') {
	const shares = proportions(day.characters);
	const segment =
		filter === 'all'
			? shares.reduce((best, next) => (next.percent > best.percent ? next : best))
			: shares.find((s) => s.kind === filter)!;
	return {
		kind: segment.kind,
		percent: segment.percent,
		color: day.requests && segment.characters ? segmentColors[segment.kind] : null,
		opacity: 0.2 + (segment.percent / 100) * 0.8
	};
}

export function activityCalendar(days: MemoryActivityDay[]) {
	if (!days.length) return { cells: [], columns: 1, months: [] };
	const offset = (new Date(`${days[0].date}T00:00:00Z`).getUTCDay() + 6) % 7;
	const cells: (MemoryActivityDay | null)[] = [...Array(offset).fill(null), ...days];
	while (cells.length % 7) cells.push(null);
	const columns = cells.length / 7;
	const months: { column: number; label: string }[] = [];
	for (let column = 0; column < columns; column++) {
		const first = cells.slice(column * 7, column * 7 + 7).find(Boolean);
		if (!first) continue;
		const label = `${Number(first.date.slice(5, 7))}月`;
		const previous = months[months.length - 1];
		if (!previous || (previous.label !== label && column - previous.column >= 3)) {
			months.push({ column, label });
		}
	}
	return { cells, columns, months };
}
