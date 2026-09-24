export type Kind = 'chat' | 'file' | 'note';
export type Source = { chat_id: string; title: string; message_id: string | null };
export type Entry = {
	id: string;
	kind: Kind;
	title: string;
	updated_at: number;
	size: number | null;
	content_type: string | null;
	origin: 'generated' | 'unknown';
	sources: Source[];
	archived: boolean;
};
export type EntryPage = { items: Entry[]; total: number };
export type Summary = {
	chats: number;
	files: number;
	notes: number;
	file_bytes: number;
	unknown_size_files: number;
	notes_enabled: boolean;
};
export type Attachment = {
	id?: string;
	name?: string;
	filename?: string;
	type?: string;
	url?: string;
	source?: string;
	path?: string;
};
export type Message = {
	id: string;
	role: string;
	content: unknown;
	output: import('$lib/components/chat/Messages/structuredOutput').OutputItem[];
	files: Attachment[];
	timestamp: number;
	parent_id: string | null;
};
export type ChatDetail = {
	id: string;
	title: string;
	messages: Message[];
	current_message_id: string | null;
};
export type NoteDetail = { id: string; title: string; content: string };
export type Artifact = { name: string; content: string; mime: string; preview: boolean };
