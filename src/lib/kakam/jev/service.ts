import type { Answer, Message, QuestionDisplay, ResultBundle, Turn } from './types';

export const stageLabels = {
	preparing: 'LLM 处理中',
	deciding: 'Jev 判断中',
	polishing: 'LLM 整理结果',
	done: 'Done',
	error: '未完成',
	cancelled: '已停止'
};

export function probability(value: number) {
	if (value > 0 && value < 0.0001) return '<0.01%';
	if (value < 1 && value > 0.9999) return '>99.99%';
	return `${new Intl.NumberFormat('zh-CN', { maximumFractionDigits: 2 }).format(value * 100)}%`;
}

export function answerRows(answer: Answer, display: QuestionDisplay) {
	if (answer.type === 'noul')
		return [
			{ key: 'true', label: display.options.true || '是', value: answer.noul },
			{ key: 'false', label: display.options.false || '否', value: 1 - answer.noul }
		];
	return Object.entries(answer.probabilities)
		.sort(([a, av], [b, bv]) => (answer.type === 'score' ? Number(a) - Number(b) : bv - av))
		.map(([key, value]) => ({
			key,
			label: display.options[key] || (answer.type === 'score' ? answer.legend[key] : key),
			value
		}));
}

export function resultContext(result: ResultBundle) {
	return JSON.stringify({ questions: result.display, jev: result.response.answers });
}

export function conversation(turns: Turn[], input: string): Message[] {
	const messages: Message[] = [];
	for (const turn of turns) {
		if (!turn.result && !turn.clarification) continue;
		messages.push({ role: 'user', content: turn.input });
		messages.push({
			role: 'assistant',
			content: turn.clarification || resultContext(turn.result!)
		});
	}
	messages.push({ role: 'user', content: input });
	if (
		messages.length > 40 ||
		messages.some((m) => m.content.length > 12000) ||
		messages.reduce((n, m) => n + m.content.length, 0) > 24000
	)
		throw new Error('当前对话内容较长，请开始新对话，以完整保留本次输入。');
	return messages;
}

export const notifyJevConfigChanged = () =>
	window.dispatchEvent(new Event('kakam-jev-config-changed'));
