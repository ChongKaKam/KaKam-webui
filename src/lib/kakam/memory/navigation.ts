type MemoryUser = { role?: string; permissions?: { features?: { memories?: boolean } } };

export const memoryPolicyTab = {
	id: 'memory-policy',
	title: 'Memory Policy',
	keywords: ['memory policy', 'memory', '记忆', '记忆占比', '策略', 'activity']
};

export function canAccessMemoryPolicy(user: MemoryUser | null | undefined): boolean {
	return (
		user?.role === 'admin' ||
		(user?.role === 'user' && user.permissions?.features?.memories !== false)
	);
}
