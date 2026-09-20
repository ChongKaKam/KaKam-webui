export const codeThemes = {
	github: {
		label: 'GitHub',
		description: '清晰克制，跟随明暗模式',
		light: 'github-light',
		dark: 'github-dark'
	},
	vscode: {
		label: 'VS Code',
		description: '熟悉的编辑器配色',
		light: 'light-plus',
		dark: 'dark-plus'
	},
	catppuccin: {
		label: 'Catppuccin',
		description: '柔和的彩色语法高亮',
		light: 'catppuccin-latte',
		dark: 'catppuccin-mocha'
	},
	minimal: {
		label: 'Minimal',
		description: '简洁配色，突出代码内容',
		light: 'min-light',
		dark: 'min-dark'
	}
} as const;
export type CodeTheme = keyof typeof codeThemes;
export function normalizeCodeTheme(value: unknown): CodeTheme {
	return typeof value === 'string' && Object.hasOwn(codeThemes, value)
		? (value as CodeTheme)
		: 'github';
}
