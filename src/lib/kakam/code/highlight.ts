import { codeThemes, normalizeCodeTheme } from './themes';

// Reuse Shiki's lazy singleton, also used by upstream file/notebook previews.
let shiki: Promise<typeof import('shiki')> | undefined;
const cache = new Map<string, string>();
let cacheCharacters = 0;
const aliases: Record<string, string> = {
	js: 'javascript',
	ts: 'typescript',
	py: 'python',
	sh: 'bash',
	shell: 'bash',
	yml: 'yaml',
	csharp: 'c#',
	'c++': 'cpp'
};
export function withinHighlightBudget(code: string): boolean {
	return code.length <= 40_000 && code.split('\n').length <= 1000;
}
export async function highlight(
	code: string,
	language: string,
	theme: unknown
): Promise<string | null> {
	if (!withinHighlightBudget(code)) return null;
	const selected = normalizeCodeTheme(theme);
	const key = JSON.stringify([selected, language, code]);
	const cached = cache.get(key);
	if (cached) return cached;
	shiki ??= import('shiki').catch((error) => {
		shiki = undefined;
		throw error;
	});
	const { codeToHtml, bundledLanguages } = await shiki;
	const requested = language.trim().toLowerCase();
	const resolved = aliases[requested] ?? requested;
	const lang = Object.hasOwn(bundledLanguages, resolved) ? resolved : 'text';
	const colors = codeThemes[selected];
	const html = await codeToHtml(code, {
		lang,
		themes: { light: colors.light, dark: colors.dark },
		defaultColor: 'light'
	});
	// Bound cached source and HTML; never persist code or send it to an external service.
	if (key.length + html.length <= 500_000) {
		if (!cache.has(key)) {
			cache.set(key, html);
			cacheCharacters += key.length + html.length;
		}
		while (cache.size > 24 || cacheCharacters > 1_000_000) {
			const oldest = cache.keys().next().value!;
			cacheCharacters -= oldest.length + cache.get(oldest)!.length;
			cache.delete(oldest);
		}
	}
	return html;
}
