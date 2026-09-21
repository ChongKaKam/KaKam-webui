import { describe, expect, it } from 'vitest';
import { imageProbeDraft } from './service';

describe('unsaved image probe configuration', () => {
	it('uses the current OpenAI generation fields without changing the saved draft', () => {
		const config = {
			IMAGE_GENERATION_ENGINE: 'openai',
			IMAGE_GENERATION_MODEL: 'image-model',
			IMAGES_OPENAI_API_BASE_URL: 'https://images.test/v1/',
			IMAGES_OPENAI_API_KEY: 'edited-key',
			IMAGES_OPENAI_API_VERSION: 'preview',
			IMAGES_OPENAI_API_PARAMS: '{"quality":"low"}',
			IMAGE_SIZE: '1024x1024'
		};
		const before = JSON.stringify(config);
		expect(imageProbeDraft(config, 'generation')).toMatchObject({
			engine: 'openai',
			base_url: 'https://images.test/v1',
			api_key: 'edited-key',
			api_version: 'preview',
			model: 'image-model',
			size: '1024x1024',
			params: { quality: 'low' }
		});
		expect(JSON.stringify(config)).toBe(before);
	});
	it('keeps editing credentials separate from generation credentials', () => {
		expect(
			imageProbeDraft(
				{
					IMAGE_EDIT_ENGINE: 'gemini',
					IMAGE_EDIT_MODEL: 'edit-model',
					IMAGES_EDIT_GEMINI_API_BASE_URL: 'https://edit.test/v1beta',
					IMAGES_EDIT_GEMINI_API_KEY: 'edit-key',
					IMAGES_GEMINI_API_KEY: 'wrong-key'
				},
				'edit'
			)
		).toMatchObject({
			engine: 'gemini',
			model: 'edit-model',
			api_key: 'edit-key',
			base_url: 'https://edit.test/v1beta',
			method: 'generateContent',
			params: {}
		});
	});
	it.each(['invalid', '[]', 'null'])('rejects invalid additional parameters: %s', (params) => {
		expect(() =>
			imageProbeDraft(
				{ IMAGE_GENERATION_ENGINE: 'openai', IMAGES_OPENAI_API_PARAMS: params },
				'generation'
			)
		).toThrow('JSON');
	});
	it('preserves native local provider validation', () => {
		expect(imageProbeDraft({ IMAGE_GENERATION_ENGINE: 'comfyui' }, 'generation')).toBeNull();
	});
});
