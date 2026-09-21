import type { ImageProbeDraft } from './types';

export function imageProbeDraft(
	config: Record<string, unknown>,
	target: 'generation' | 'edit'
): ImageProbeDraft | null {
	const edit = target === 'edit';
	const engine = config[edit ? 'IMAGE_EDIT_ENGINE' : 'IMAGE_GENERATION_ENGINE'];
	if (engine !== 'openai' && engine !== 'gemini') return null;
	const prefix = `IMAGES_${edit ? 'EDIT_' : ''}${engine.toUpperCase()}_`;
	const string = (key: string) =>
		typeof config[key] === 'string' ? (config[key] as string).trim() : '';
	const raw = !edit && engine === 'openai' ? config.IMAGES_OPENAI_API_PARAMS : {};
	let params: unknown;
	try {
		params = typeof raw === 'string' ? (raw.trim() ? JSON.parse(raw) : {}) : (raw ?? {});
	} catch {
		throw new Error('附加参数不是有效的 JSON，请先修正。');
	}
	if (!params || typeof params !== 'object' || Array.isArray(params))
		throw new Error('附加参数必须是 JSON 对象。');
	return {
		engine,
		base_url: string(`${prefix}API_BASE_URL`).replace(/\/+$/, ''),
		api_key: string(`${prefix}API_KEY`),
		api_version: string(`${prefix}API_VERSION`),
		model: string(edit ? 'IMAGE_EDIT_MODEL' : 'IMAGE_GENERATION_MODEL'),
		size: string('IMAGE_SIZE'),
		method:
			edit || config.IMAGES_GEMINI_ENDPOINT_METHOD === 'generateContent'
				? 'generateContent'
				: 'predict',
		params: params as Record<string, unknown>
	};
}
