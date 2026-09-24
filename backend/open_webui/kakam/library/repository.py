"""Owner-scoped read adapter. Native tables remain the only source of truth.

No retention worker or new storage copy is introduced. Deletes/downloads use
the native APIs so storage-provider cleanup and existing permissions still apply.
"""

from sqlalchemy import func, or_, select

from .schemas import ChatDetail, Entry, EntryPage, Message, NoteDetail, Source, Summary


def file_size(meta):
    value = (meta if isinstance(meta, dict) else {}).get('size')
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else None


def seconds(value):
    value = int(value or 0)
    # Notes use nanoseconds, messages may come from older millisecond exports.
    if value > 10**17:
        return value // 10**9
    if value > 10**11:
        return value // 1000
    return value


def models():
    from open_webui.models.chats import Chat, ChatFile
    from open_webui.models.files import File
    from open_webui.models.notes import Note

    return Chat, ChatFile, File, Note


async def summary(db, user_id, notes_enabled):
    Chat, _, File, Note = models()
    counts = []
    for model in (Chat, File, Note):
        counts.append(await db.scalar(select(func.count()).select_from(model).where(model.user_id == user_id)))
    # Read only small metadata, never file bytes or extracted document text.
    result = await db.stream(select(File.meta).where(File.user_id == user_id))
    total_bytes = unknown = 0
    async for meta in result.scalars():
        size = file_size(meta)
        total_bytes += size or 0
        unknown += size is None
    return Summary(
        chats=counts[0],
        files=counts[1],
        notes=counts[2] if notes_enabled else 0,
        file_bytes=total_bytes,
        unknown_size_files=unknown,
        notes_enabled=notes_enabled,
    )


async def entries(db, user_id, kind, q='', offset=0, limit=30, before=None, chat_id=None):
    Chat, ChatFile, File, Note = models()
    model = {'chat': Chat, 'file': File, 'note': Note}[kind]
    title = File.filename if kind == 'file' else model.title
    columns = [model.id, title.label('title'), model.updated_at]
    columns += [File.meta] if kind == 'file' else ([Chat.archived] if kind == 'chat' else [])
    conditions = [model.user_id == user_id]
    if q:
        # Literal search, not caller-controlled SQL wildcards.
        pattern = q.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')
        conditions.append(title.ilike(f'%{pattern}%', escape='\\'))
    if before:
        conditions.append(model.updated_at < before * (10**9 if kind == 'note' else 1))
    if chat_id:
        if kind == 'file':
            owned_chat = select(Chat.id).where(Chat.user_id == user_id, Chat.id == chat_id)
            conditions.append(
                or_(
                    File.id.in_(select(ChatFile.file_id).where(ChatFile.chat_id.in_(owned_chat))),
                    File.meta['data']['chat_id'].as_string().in_(owned_chat),
                )
            )
        elif kind == 'chat':
            conditions.append(Chat.id == chat_id)
        else:
            return EntryPage(items=[], total=0)
    total = await db.scalar(select(func.count()).select_from(model).where(*conditions))
    rows = (
        (
            await db.execute(
                select(*columns)
                .where(*conditions)
                .order_by(model.updated_at.desc(), model.id)
                .offset(offset)
                .limit(limit)
            )
        )
        .mappings()
        .all()
    )
    sources = await file_sources(db, user_id, rows) if kind == 'file' and rows else {}
    items = []
    for row in rows:
        meta = row.get('meta') if isinstance(row.get('meta'), dict) else {}
        data = meta.get('data') if isinstance(meta.get('data'), dict) else {}
        content_type = meta.get('content_type')
        items.append(
            Entry(
                id=row['id'],
                kind=kind,
                title=row['title'] or 'Untitled',
                updated_at=seconds(row['updated_at']),
                size=file_size(meta) if kind == 'file' else None,
                content_type=content_type if isinstance(content_type, str) else None,
                origin='generated' if data.get('kakam_artifact') is True else 'unknown',
                sources=sources.get(row['id'], []),
                archived=bool(row.get('archived')),
            )
        )
    return EntryPage(items=items, total=total)


async def file_sources(db, user_id, rows):
    Chat, ChatFile, _, _ = models()
    sources = {}
    refs = await db.execute(
        select(ChatFile.file_id, Chat.id, Chat.title, ChatFile.message_id)
        .join(Chat, Chat.id == ChatFile.chat_id)
        .where(Chat.user_id == user_id, ChatFile.file_id.in_([r['id'] for r in rows]))
    )
    for file_id, cid, name, mid in refs:
        sources.setdefault(file_id, []).append(Source(chat_id=cid, title=name, message_id=mid))
    # Native images and generated files may have provenance only in metadata.
    metadata_refs = {}
    for row in rows:
        meta = row.get('meta')
        data = meta.get('data') if isinstance(meta, dict) else None
        if isinstance(data, dict) and isinstance(data.get('chat_id'), str):
            metadata_refs[row['id']] = data
    if metadata_refs:
        chats = dict(
            (
                await db.execute(
                    select(Chat.id, Chat.title).where(
                        Chat.user_id == user_id, Chat.id.in_([d['chat_id'] for d in metadata_refs.values()])
                    )
                )
            ).all()
        )
        for fid, data in metadata_refs.items():
            cid = data['chat_id']
            if cid in chats and not any(s.chat_id == cid for s in sources.get(fid, [])):
                mid = data.get('message_id')
                sources.setdefault(fid, []).append(
                    Source(chat_id=cid, title=chats[cid], message_id=mid if isinstance(mid, str) else None)
                )
    return sources


async def chat_detail(db, user_id, chat_id):
    from open_webui.models.chat_messages import ChatMessage

    Chat, _, _, _ = models()
    chat = (await db.execute(select(Chat).where(Chat.id == chat_id, Chat.user_id == user_id))).scalar_one_or_none()
    if chat is None:
        return None
    rows = (
        (
            await db.execute(
                select(ChatMessage)
                .where(ChatMessage.chat_id == chat_id)
                .order_by(ChatMessage.created_at, ChatMessage.id)
            )
        )
        .scalars()
        .all()
    )
    if rows:
        messages = [
            Message(
                id=r.id.removeprefix(f'{chat_id}-'),
                role=r.role,
                content=r.content,
                output=r.output or [],
                files=r.files or [],
                timestamp=seconds(r.created_at),
                parent_id=r.parent_id,
            )
            for r in rows
        ]
    else:
        # Imported/legacy chats may not have a normalized message index yet.
        data = chat.chat or {}
        history = (data.get('history') or {}).get('messages') or {}
        raw = history.values() if history else data.get('messages', [])
        messages = [
            Message(
                id=str(m.get('id', i)),
                role=m.get('role', 'user'),
                content=m.get('content', ''),
                output=m.get('output') or [],
                files=m.get('files') or [],
                timestamp=seconds(m.get('timestamp')),
                parent_id=m.get('parentId'),
            )
            for i, m in enumerate(raw)
            if isinstance(m, dict)
        ]
    return ChatDetail(
        id=chat.id,
        title=chat.title,
        messages=messages,
        current_message_id=chat.current_message_id or ((chat.chat or {}).get('history') or {}).get('currentId'),
    )


async def note_detail(db, user_id, note_id):
    _, _, _, Note = models()
    row = (
        await db.execute(select(Note.id, Note.title, Note.data).where(Note.id == note_id, Note.user_id == user_id))
    ).first()
    if row is None:
        return None
    data = row.data if isinstance(row.data, dict) else {}
    note_content = data.get('content') if isinstance(data.get('content'), dict) else {}
    content = note_content.get('md', '')
    return NoteDetail(id=row.id, title=row.title, content=content if isinstance(content, str) else str(content))
