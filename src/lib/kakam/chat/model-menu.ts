import type { Effort, EffortModel } from './effort';
export type ModelMenuItem = {
	value: string;
	label: string;
	model: EffortModel & { info?: { meta?: { description?: string; hidden?: boolean } } };
};
export const effortDescriptions: Record<Effort, string> = {
	none: '不发送思考强度参数，使用供应商默认行为',
	low: '更快响应，适合轻量任务',
	medium: '兼顾响应速度与推理深度',
	high: '深入思考，适合复杂任务',
	'extra high': '投入更多思考，响应可能更慢'
};
export function menuItems(
	items: ModelMenuItem[],
	search: string,
	pinned: string[]
): ModelMenuItem[] {
	const query = search.trim().toLocaleLowerCase();
	return items
		.filter((item) => !item.model.info?.meta?.hidden)
		.filter((item) =>
			[item.label, item.value, item.model.info?.meta?.description ?? '']
				.join(' ')
				.toLocaleLowerCase()
				.includes(query)
		)
		.sort((a, b) => Number(pinned.includes(b.value)) - Number(pinned.includes(a.value)));
}
export function chooseModel(values: string[], id: string, compare: boolean): string[] {
	return compare ? [...new Set([...values.filter(Boolean), id])] : [id];
}
