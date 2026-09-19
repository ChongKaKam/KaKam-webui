import { describe, expect, it } from 'vitest';
import { activityCalendar, dayColor, proportions } from './activity';
import { canAccessMemoryPolicy, memoryPolicyTab } from './navigation';
import type { MemoryActivityDay } from './types';

const day: MemoryActivityDay = {
	date: '2026-09-19',
	requests: 2,
	characters: { system: 10, long_term: 20, session: 60, current: 10 }
};
describe('memory activity', () => {
	it('computes weighted character shares, not request averages', () => {
		expect(proportions(day.characters).map((s) => s.percent)).toEqual([10, 20, 60, 10]);
	});
	it('handles empty days without NaN or invented usage', () => {
		const empty = {
			...day,
			requests: 0,
			characters: { system: 0, long_term: 0, session: 0, current: 0 }
		};
		expect(proportions(empty.characters).map((s) => s.percent)).toEqual([0, 0, 0, 0]);
		expect(dayColor(empty, 'all').color).toBeNull();
	});
	it('colors by dominant type or chosen category and share', () => {
		expect(dayColor(day, 'all').kind).toBe('session');
		expect(dayColor(day, 'long_term').percent).toBe(20);
		expect(dayColor(day, 'long_term').opacity).toBeLessThan(dayColor(day, 'all').opacity);
	});
	it('aligns UTC calendar to Monday and preserves all dates', () => {
		const days = Array.from({ length: 30 }, (_, i) => ({
			...day,
			date: new Date(Date.UTC(2026, 8, 19 + i)).toISOString().slice(0, 10)
		}));
		const calendar = activityCalendar(days);
		expect(calendar.cells.indexOf(days[0])).toBe(5); // Saturday
		expect(calendar.cells.filter(Boolean)).toEqual(days);
		expect(calendar.cells.length % 7).toBe(0);
		expect(calendar.months.map((m) => m.label)).toEqual(['9月', '10月']);
	});
	it('handles no calendar data', () => expect(activityCalendar([]).cells).toEqual([]));
});

describe('Memory Policy navigation', () => {
	it('uses a dedicated settings tab', () => expect(memoryPolicyTab.id).toBe('memory-policy'));
	it('keeps authorized entry visible even without a service feature flag', () => {
		expect(canAccessMemoryPolicy({ role: 'admin' })).toBe(true);
		expect(canAccessMemoryPolicy({ role: 'user' })).toBe(true);
	});
	it('hides the entry from pending, signed-out and denied users', () => {
		expect(canAccessMemoryPolicy(null)).toBe(false);
		expect(canAccessMemoryPolicy({ role: 'pending' })).toBe(false);
		expect(
			canAccessMemoryPolicy({ role: 'user', permissions: { features: { memories: false } } })
		).toBe(false);
	});
});
