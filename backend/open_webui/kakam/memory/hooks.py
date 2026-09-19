import asyncio
import logging
import os

from open_webui.models.chats import Chats
from open_webui.utils.chat_id import is_saved_chat_id
from open_webui.utils.misc import add_or_update_system_message

from . import client
from .auth import allowed, preferences
from .composition import composition, render, split_context, text_content
from .details import remember

log = logging.getLogger(__name__)


def mode(name):
    value = os.getenv(f'KAKAM_MEMORY_{name}_MODE', 'on')
    return value if value in {'off', 'shadow', 'on'} else 'off'


async def prepare(request, form_data, user, metadata, model):
    if not client.enabled():
        return form_data
    prefs = preferences(user)
    report = {
        'policy': 'default',
        'days': prefs['days'],
        'cache_hit': False,
        'status': 'disabled',
        'memory_count': 0,
        'memory_text': '',
    }
    metadata['kakam_memory'] = report
    # Temporary and channel chats don't read private cross-session memory either.
    eligible = (
        prefs['enabled']
        and prefs['policy'] == 'default'
        and not metadata.get('task')
        and is_saved_chat_id(metadata.get('chat_id'))
        and (model.get('info', {}).get('meta', {}).get('capabilities') or {}).get('memory', True)
    )
    if metadata.get('task') or not is_saved_chat_id(metadata.get('chat_id')):
        return form_data
    query = next((text_content(m) for m in reversed(form_data['messages']) if m.get('role') == 'user'), '')[-8000:]
    try:
        # Hard overall deadline includes network setup, reads and retries.
        timeout = max(0.1, min(30, int(os.getenv('KAKAM_MEMORY_TIMEOUT_MS', '1500')) / 1000))
        async with asyncio.timeout(timeout):
            if not await allowed(user):
                return form_data
            if not await Chats.is_chat_owner(metadata['chat_id'], user.id):
                return form_data
            metadata['kakam_detail_owner'] = user.id
            if not eligible or mode('RECALL') == 'off':
                return form_data
            result = await client.call(
                'POST',
                '/v1/recall',
                user.id,
                {'query': query, 'days': prefs['days'], 'policy': prefs['policy'], 'cache': prefs['cache']},
            )
        report.update(status='shadow' if mode('RECALL') == 'shadow' else 'ready', cache_hit=result['cache_hit'])
        if mode('RECALL') == 'on':
            context = render(result['memories'])
            if context:
                form_data['messages'] = add_or_update_system_message(context, form_data['messages'], append=True)
            report.update(memory_text=context, memory_count=len(result['memories']))
    except Exception as exc:
        report['status'] = 'unavailable'
        log.warning('KaKam recall skipped (%s)', type(exc).__name__)
    return form_data


async def emit_composition(form_data, metadata, emitter, model_system=''):
    report = metadata.get('kakam_memory')
    if report is None:
        return
    payload = {key: value for key, value in report.items() if key != 'memory_text'}
    payload.update(
        segments=composition(form_data.get('messages', []), report['memory_text'], model_system),
        measurement='text-estimate',
        message_id=metadata.get('message_id'),
        model=form_data.get('model'),
    )
    metadata['kakam_composition'] = payload
    if metadata.get('kakam_detail_owner') and metadata.get('message_id'):
        try:
            payload['detail_id'] = remember(
                metadata['kakam_detail_owner'],
                metadata['chat_id'],
                metadata['message_id'],
                split_context(form_data.get('messages', []), report['memory_text'], model_system, label_roles=True),
            )
        except Exception as exc:
            log.warning('KaKam context preview skipped (%s)', type(exc).__name__)
    if emitter:
        try:
            await emitter({'type': 'kakam:memory', 'data': payload})
        except Exception:
            log.debug('Unable to emit memory composition')


async def after_turn(request, user, model, metadata, messages):
    if not client.enabled():
        return
    # Store only counts, never recalled content. Existing message.meta is the
    # upstream extension point, so reload/branch switching preserve the matrix.
    try:
        if (
            metadata.get('kakam_composition')
            and is_saved_chat_id(metadata.get('chat_id'))
            and await Chats.is_chat_owner(metadata['chat_id'], user.id)
        ):
            response = await Chats.get_message_by_id_and_message_id(metadata['chat_id'], metadata['message_id'])
            if response:
                await Chats.upsert_message_to_chat_by_id_and_message_id(
                    metadata['chat_id'],
                    metadata['message_id'],
                    {'meta': {**(response.get('meta') or {}), 'kakamMemory': metadata['kakam_composition']}},
                    touch=False,
                )
            if response and response.get('error'):
                return
    except Exception as exc:
        log.warning('KaKam composition persistence skipped (%s)', type(exc).__name__)
    if mode('WRITE') == 'off':
        return
    prefs = preferences(user)
    if (
        not prefs['enabled']
        or prefs['policy'] != 'default'
        or metadata.get('task')
        or not is_saved_chat_id(metadata.get('chat_id'))
        or not (model.get('info', {}).get('meta', {}).get('capabilities') or {}).get('memory', True)
    ):
        return
    # Fetch the persisted USER message, not system-injected/retrieved content or
    # assistant guesses. Ownership is checked again for event ingestion.
    try:
        if not await allowed(user):
            return
        if not await Chats.is_chat_owner(metadata['chat_id'], user.id):
            return
        message_id = metadata.get('user_message_id')
        if not message_id:
            return
        original = await Chats.get_message_by_id_and_message_id(metadata['chat_id'], message_id)
        evidence = text_content(original or {})[:8000]
        if not evidence or (original or {}).get('role') != 'user':
            return
        # Shadow writes use a separate identity namespace and never enter live recall.
        owner = 'shadow:' + user.id if mode('WRITE') == 'shadow' else user.id
        async with asyncio.timeout(3):
            await client.call(
                'POST',
                '/v1/events/turn-completed',
                owner,
                {'chat_id': metadata['chat_id'], 'message_id': message_id, 'evidence': evidence},
            )
    except Exception as exc:
        log.warning('KaKam turn delivery failed (%s)', type(exc).__name__)
