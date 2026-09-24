export type Stage = 'preparing' | 'deciding' | 'polishing' | 'done' | 'error' | 'cancelled';
export type Description = string | Record<string, unknown> | unknown[];
export type Question =
	| { type: 'noul'; instructions: Description; criteria?: Record<string, Description> }
	| { type: 'choice'; instructions: Description; criteria: Record<string, Description | null> }
	| { type: 'score'; instructions: Description; criteria: Description[] };
export type Answer =
	| { type: 'noul'; noul: number }
	| { type: 'choice'; choice: string; probabilities: Record<string, number>; confidence?: number }
	| {
			type: 'score';
			score: number;
			legend: Record<string, string>;
			probabilities: Record<string, number>;
			confidence?: number;
	  };
export type QuestionDisplay = { title: string; options: Record<string, string> };
export type ResultBundle = {
	evaluation: { state: Description; model: string; questions: Record<string, Question> };
	display: Record<string, QuestionDisplay>;
	response: {
		model: string;
		answers: Record<string, Answer>;
		usage: { input_tokens: number; output_tokens: number };
	};
};
export type TurnEvent =
	| { type: 'stage'; stage: 'preparing' | 'deciding' | 'polishing' | 'done' }
	| ({ type: 'result' } & ResultBundle)
	| { type: 'summary'; summary: string }
	| { type: 'clarification'; message: string }
	| { type: 'warning'; message: string }
	| { type: 'error'; message: string; code: string };
export type Message = { role: 'user' | 'assistant'; content: string };
export type PromptModel = { id: string; name: string };
export type ConnectionView = { base_url: string; has_api_key: boolean; model: string };
export type ConnectionInput = { base_url: string; api_key?: string; clear_api_key?: boolean };
export type ConnectionStatus = {
	configured: boolean;
	connected: boolean;
	model: string;
	checked_at: number;
	latency_ms?: number;
	message: string;
};
export type Turn = {
	id: string;
	input: string;
	modelName: string;
	stage: Stage;
	startedAt: number;
	result?: ResultBundle;
	summary?: string;
	clarification?: string;
	warning?: string;
	error?: string;
};
export type SessionState = {
	turns: Turn[];
	running: boolean;
	loading: boolean;
	error: string;
	models: PromptModel[];
	modelsLoaded: boolean;
	modelId: string;
	connection: ConnectionStatus | null;
};
