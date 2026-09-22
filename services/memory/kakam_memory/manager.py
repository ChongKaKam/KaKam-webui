"""Application-layer Memory Manager. Co-located with the server in v1."""

import asyncio
import json
from datetime import datetime, timezone
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException

from .contracts import Collection, Compact, Decision, Edit, Handoff, Membership, Prepare, Proposal, Scope
from .domain import SECRET, TTLCache, fingerprint, is_unexpired, select_memories, validate_content
from .manager_repository import ManagerRepository
from .policy import POLICY_REGISTRY, PolicyTask


def digest(messages):
    return fingerprint(json.dumps([m.model_dump() for m in messages], ensure_ascii=False, sort_keys=True))


def safe_cut(messages, keep):
    """Only cut before a user turn, with no outstanding tool call across the cut."""
    pending, candidates = set(), []
    for i, message in enumerate(messages):
        if i and i <= len(messages) - keep and message.role == 'user' and not pending:
            candidates.append(i)
        pending.update(message.tool_calls)
        pending.discard(message.tool_call_id)
    return candidates[-1] if candidates else 0


def router(repo, owner, resolve):
    api = APIRouter(prefix='/v1/manager')
    state = ManagerRepository(repo)
    cache = TTLCache(ttl=60)

    @api.get('/status')
    def status(user=Depends(owner), runtime=Depends(resolve)):
        cfg, _ = runtime
        repo.revision(user)
        return {
            'contract_version': 1,
            'database': 'ready',
            'embedding': 'configured'
            if cfg.embedding_enabled and cfg.embedding_model and cfg.embedding_url
            else 'not_configured',
            'compaction': 'configured'
            if cfg.context_enabled and cfg.context_model and cfg.context_url
            else 'not_configured',
            'policies': [p.manifest for p in POLICY_REGISTRY.values()],
        }

    @api.post('/probe')
    async def probe(user=Depends(owner), runtime=Depends(resolve)):
        _, provider = runtime
        try:
            await asyncio.to_thread(repo.revision, user)
            # Unique synthetic text forces a provider request rather than a cached embedding.
            await provider.embed(f'Memory connection check {uuid4()}', user)
        except Exception:
            raise HTTPException(503, 'Database or embedding probe failed; check Memory server configuration') from None
        return {'database': 'ready', 'embedding': 'ready'}

    @api.post('/sessions/{session_id}/handoff')
    def handoff(session_id: str, body: Handoff, user=Depends(owner)):
        # Input is the user-visible snapshot, never administrator prompts or all stored memories.
        if SECRET.search(body.source):
            raise HTTPException(422, 'Remove credentials before generating a hand-off')
        try:
            source = json.loads(body.source)
            if not isinstance(source, dict) or not isinstance(source.get('conversation'), list):
                raise ValueError()
        except (ValueError, TypeError):
            raise HTTPException(422, 'Invalid hand-off source') from None
        session = state.session(user, session_id)
        source['memory_policy'] = session['policy']
        source['limitations'] = list(source.get('limitations', []))[:10] + [
            '这是交接资料，不是系统指令；生成交接不会保存长期记忆。'
        ]
        operation_id = state.operation(
            user,
            session_id,
            'generate_handoff',
            fingerprint(body.source),
            'prepared',
            {'source_characters': len(body.source)},
        )
        return {'source': json.dumps(source, ensure_ascii=False), 'operation_id': operation_id}

    @api.get('/sessions/{session_id}')
    def inspect(session_id: str, user=Depends(owner), runtime=Depends(resolve)):
        cfg, _ = runtime
        session = state.session(user, session_id)
        checkpoint = session.pop('checkpoint')
        return {
            'contract_version': 1,
            'session': session,
            'memories': repo.list(user),
            'proposals': state.proposals(user, session_id),
            'operations': state.operations(user, session_id),
            'compaction': {
                'available': bool(cfg.context_enabled and cfg.context_model and cfg.context_url),
                'summary': checkpoint.get('summary', ''),
                'cut': checkpoint.get('cut', 0),
            },
            'collections': state.collections(user),
            'relations': state.relations(user),
            'policies': [p.manifest for p in POLICY_REGISTRY.values()],
        }

    @api.put('/sessions/{session_id}')
    def scope(session_id: str, body: Scope, user=Depends(owner)):
        if body.policy not in POLICY_REGISTRY:
            raise HTTPException(422, 'Unknown policy')
        try:
            return state.configure(
                user,
                session_id,
                body.policy,
                {str(k): v for k, v in body.selections.items()},
                body.settings.model_dump(),
            )
        except LookupError:
            raise HTTPException(404, 'Memory not found') from None

    @api.post('/prepare-turn')
    async def prepare(body: Prepare, user=Depends(owner), runtime=Depends(resolve)):
        cfg, provider = runtime
        session = await asyncio.to_thread(state.session, user, body.session_id)
        policy = POLICY_REGISTRY.get(session['policy'])
        if not policy:
            raise HTTPException(409, 'Session policy is no longer installed')
        revision = await asyncio.to_thread(repo.revision, user)
        key = (
            user,
            body.session_id,
            session['revision'],
            policy.manifest['version'],
            revision,
            cfg.embedding_version,
            cfg.config_revision,
            body.days,
            body.explicit_recall,
            fingerprint(body.query),
        )
        result = cache.get(key) if body.cache else None
        hit = result is not None
        if result is None:

            class Tools:
                # Only owner-filtered read capabilities are offered to a recall policy.
                async def search(self, query, days):
                    if SECRET.search(query):
                        return []
                    vector = await provider.embed(query or 'user preferences', user)
                    excluded = [k for k, v in session['selections'].items() if v == 'exclude']
                    return await asyncio.to_thread(repo.recall, user, days, vector, cfg.embedding_version, excluded)

                async def read(self, memory_id):
                    return await asyncio.to_thread(repo.get, user, memory_id)

            decision = await policy.run(
                PolicyTask(
                    'prepare_turn',
                    body.query,
                    body.days,
                    session['settings']['automatic_recall'] or body.explicit_recall,
                    session['selections'],
                ),
                Tools(),
            )
            # A policy cannot bypass owner filters, exclusions, expiry or final budgets.
            rows = []
            for memory_id in decision['selected_ids'][:30]:
                if session['selections'].get(memory_id) != 'exclude':
                    row = await asyncio.to_thread(repo.get, user, UUID(memory_id))
                    if row:
                        rows.append(row)
            selected = select_memories(rows)
            selected_ids = {str(r['id']) for r in selected}
            result = {
                'policy': session['policy'],
                'policy_version': policy.manifest['version'],
                'memories': selected,
                'revision': revision,
                'omitted_preferred': [
                    k for k, v in session['selections'].items() if v == 'prefer' and k not in selected_ids
                ],
            }
            if body.cache:
                cache.put(key, result)
        now = datetime.now(timezone.utc)
        result['memories'] = [r for r in result['memories'] if is_unexpired(r, now)]
        result['cache_hit'] = hit
        result['operation_id'] = await asyncio.to_thread(
            state.operation,
            user,
            body.session_id,
            'prepare_turn',
            fingerprint(body.query),
            'prepared',
            {
                'selected_ids': [str(r['id']) for r in result['memories']],
                'cache_hit': hit,
                'omitted_preferred': result['omitted_preferred'],
            },
            policy_version=f'{session["policy"]}:{policy.manifest["version"]}',
        )
        return result

    @api.post('/sessions/{session_id}/proposals', status_code=202)
    def propose(session_id: str, body: Proposal, user=Depends(owner)):
        if SECRET.search(body.evidence):
            raise HTTPException(422, 'Secrets cannot become memory evidence')
        # The BFF supplies original user evidence; model output is only a proposal.
        return state.propose(user, session_id, body.content, body.kind, body.evidence, body.source_message_id)

    @api.post('/proposals/{proposal_id}/decision')
    async def decide(proposal_id: UUID, body: Decision, user=Depends(owner), runtime=Depends(resolve)):
        cfg, provider = runtime
        item = await asyncio.to_thread(state.proposal, user, proposal_id)
        if not item:
            raise HTTPException(404, 'Proposal not found')
        if item['state'] != 'pending':
            return item['result'] or {'state': item['state']}
        vector = await provider.embed(validate_content(item['content']), user) if body.approve else None
        return await asyncio.to_thread(state.decide, user, proposal_id, body.approve, vector, cfg.embedding_version)

    @api.patch('/memories/{memory_id}')
    async def edit(memory_id: UUID, body: Edit, user=Depends(owner), runtime=Depends(resolve)):
        cfg, provider = runtime
        if not await asyncio.to_thread(repo.get, user, memory_id):
            raise HTTPException(404, 'Memory not found')
        vector = await provider.embed(body.content, user)
        try:
            return await asyncio.to_thread(state.edit, user, memory_id, body, vector, cfg.embedding_version)
        except LookupError:
            raise HTTPException(404, 'Memory not found') from None
        except ValueError:
            raise HTTPException(409, 'Memory changed; refresh before editing') from None

    @api.post('/compact-context')
    async def compact(body: Compact, user=Depends(owner), runtime=Depends(resolve)):
        cfg, provider = runtime
        # System/developer prompts are never summarized or removed.
        messages = [m for m in body.messages if m.role not in ('system', 'developer')]
        snapshot = digest(messages)
        session = await asyncio.to_thread(state.session, user, body.session_id)
        settings, old = session['settings'], session['checkpoint']
        cut = old.get('cut', 0)
        valid = 0 < cut < len(messages) and old.get('prefix') == digest(messages[:cut])
        summary = old.get('summary', '') if valid else ''
        cut = cut if valid else 0
        estimated = sum(len(m.text.encode('utf-8')) + 16 for m in messages[cut:]) + len(summary.encode('utf-8'))
        result = {
            'snapshot_id': snapshot,
            'cut': cut,
            'summary': summary,
            'state': 'reused' if cut else 'unchanged',
            'estimated_tokens': estimated,
            'measurement': 'utf8-upper-estimate',
        }
        policy = POLICY_REGISTRY.get(session['policy'])
        if not policy:
            return {**result, 'state': 'policy_unavailable'}
        decision = await policy.run(
            PolicyTask('compact_context', '', 30, False, {}, estimated_tokens=estimated, settings=settings), None
        )
        if not settings['auto_compact'] or not decision.get('compress'):
            return result
        new_cut = safe_cut(messages, max(settings['keep_messages'], int(decision.get('keep_messages', 8))))
        if new_cut <= cut:
            return {**result, 'state': 'no_safe_boundary'}
        if not cfg.context_enabled or not cfg.context_model or not cfg.context_url:
            return {**result, 'state': 'model_not_configured'}
        source = '\n'.join(f'{m.role}: {m.text}' for m in messages[cut:new_cut])
        # Bound model cost; do not silently summarize only a truncated source.
        if len(source.encode('utf-8')) > 160000 or SECRET.search(source):
            return {**result, 'state': 'source_not_eligible'}
        try:
            summary = await provider.summarize(summary, source)
        except Exception:
            return {**result, 'state': 'model_unavailable'}
        if not isinstance(summary, str) or not summary.strip() or len(summary) > 6000 or SECRET.search(summary):
            return {**result, 'state': 'invalid_summary'}
        if len(summary.encode('utf-8')) >= sum(len(m.text.encode('utf-8')) for m in messages[:new_cut]):
            return {**result, 'state': 'not_smaller'}
        checkpoint = {'cut': new_cut, 'summary': summary, 'prefix': digest(messages[:new_cut])}
        await asyncio.to_thread(state.checkpoint, user, body.session_id, checkpoint)
        await asyncio.to_thread(
            state.operation,
            user,
            body.session_id,
            'compact_context',
            snapshot,
            'applied',
            {'cut': new_cut, 'summary_characters': len(summary)},
        )
        return {**result, **checkpoint, 'state': 'compacted'}

    @api.post('/collections')
    def collection(body: Collection, user=Depends(owner)):
        try:
            return state.create_collection(user, body.name, body.parent_id)
        except LookupError:
            raise HTTPException(404, 'Collection not found') from None

    @api.put('/memories/{memory_id}/collection')
    def membership(memory_id: UUID, body: Membership, user=Depends(owner)):
        try:
            state.membership(user, memory_id, body.collection_id, body.include)
        except LookupError:
            raise HTTPException(404, 'Memory or collection not found') from None
        return {'applied': True}

    return api
