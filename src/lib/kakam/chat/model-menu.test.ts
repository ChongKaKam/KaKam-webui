import { describe, it, expect } from 'vitest';
import { menuItems, chooseModel, type ModelMenuItem } from './model-menu';
const items: ModelMenuItem[] = [
	{ value: 'a', label: 'Alpha', model: { id: 'a', info: { meta: { description: 'Fast model' } } } },
	{ value: 'b', label: 'Beta', model: { id: 'b' } },
	{ value: 'hidden', label: 'Hidden', model: { id: 'hidden', info: { meta: { hidden: true } } } }
];
describe('cascading model menu', () => {
	it('preserves hidden-model policy and pinned ordering without mutating source', () => {
		expect(menuItems(items, '', ['hidden', 'b']).map((item) => item.value)).toEqual(['b', 'a']);
		expect(items.map((item) => item.value)).toEqual(['a', 'b', 'hidden']);
	});
	it('searches model labels, IDs and descriptions', () => {
		expect(menuItems(items, ' FAST ', []).map((item) => item.value)).toEqual(['a']);
		expect(menuItems(items, 'Beta', []).map((item) => item.value)).toEqual(['b']);
		expect(menuItems(items, 'missing', [])).toEqual([]);
	});
	it('keeps comparison selections when setting effort and replaces them in single mode', () => {
		expect(chooseModel(['', 'a', 'b'], 'b', true)).toEqual(['a', 'b']);
		expect(chooseModel(['a'], 'b', true)).toEqual(['a', 'b']);
		expect(chooseModel(['a', 'b'], 'b', false)).toEqual(['b']);
	});
});
