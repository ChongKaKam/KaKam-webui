import type { Connection, DiscoveredModel, ProviderConfig, ProviderModel } from './types';

export function discoveredModels(data: unknown): DiscoveredModel[] {
	const rows = Array.isArray(data) ? data : (data as { data?: unknown })?.data;
	if (!Array.isArray(rows)) throw new Error('models 接口没有返回有效的模型列表。');
	const models = new Map<string, DiscoveredModel>();
	for (const item of rows) {
		const id = typeof item === 'string' ? item : item?.id;
		if (typeof id !== 'string' || !id.trim() || id.length > 512) continue;
		models.set(id, { id, name: typeof item?.name === 'string' ? item.name : id });
	}
	if (rows.length && !models.size) throw new Error('models 接口没有返回有效的模型 ID。');
	return [...models.values()].sort((a, b) => a.id.localeCompare(b.id));
}
export function connectionsFrom(config: ProviderConfig): Connection[] {
	return config.OPENAI_API_BASE_URLS.map((url, index) => ({
		url,
		key: config.OPENAI_API_KEYS[index] ?? '',
		config: structuredClone(
			config.OPENAI_API_CONFIGS[index] ?? config.OPENAI_API_CONFIGS[url] ?? {}
		)
	}));
}
export function connectionsTo(config: ProviderConfig, connections: Connection[]): ProviderConfig {
	return {
		...config,
		OPENAI_API_BASE_URLS: connections.map((c) => c.url.replace(/\/+$/, '')),
		OPENAI_API_KEYS: connections.map((c) => c.key),
		OPENAI_API_CONFIGS: Object.fromEntries(connections.map((c, i) => [String(i), c.config]))
	};
}
export function newConnection(): Connection {
	const id = `supplier_${crypto.randomUUID().replaceAll('-', '')}`;
	return {
		url: '',
		key: '',
		config: {
			enable: true,
			auth_type: 'bearer',
			prefix_id: id,
			model_ids: [],
			kakam_supplier: { id, alias: '', models: [] }
		}
	};
}
export function supplierModelLabel(model: ProviderModel): string {
	return `${model.name || model.id}${model.kakam_provider ? ` · ${model.kakam_provider.alias}` : ''}`;
}
/** Credentials remain only in component memory; never persist this fingerprint or log it. */
export function connectionFingerprint(connection: Connection): string {
	const transport = { ...connection.config };
	for (const field of ['enable', 'prefix_id', 'model_ids', 'kakam_supplier'])
		delete transport[field];
	return JSON.stringify([connection.url.replace(/\/+$/, ''), connection.key, transport]);
}
export function poolConnection(
	connection: Connection,
	alias: string,
	discovered: DiscoveredModel[],
	selected: string[]
): Connection {
	if (!alias.trim()) throw new Error('请填写供应商别名。');
	const chosen = new Set(selected);
	const models = discovered.filter((m) => chosen.has(m.id));
	if (models.length !== chosen.size) throw new Error('白名单中存在未通过探测的模型，请重新探测。');
	return {
		...connection,
		url: connection.url.replace(/\/+$/, ''),
		config: {
			...connection.config,
			model_ids: models.map((m) => m.id),
			kakam_supplier: {
				id:
					connection.config.kakam_supplier?.id ??
					`supplier_${crypto.randomUUID().replaceAll('-', '')}`,
				alias: alias.trim(),
				models
			}
		}
	};
}
