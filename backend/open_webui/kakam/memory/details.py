"""Bounded, ephemeral prompt previews. Never persist text in chat metadata."""

import asyncio
import time
from collections import OrderedDict
from copy import deepcopy
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel

TTL_SECONDS = 900
MAX_ENTRIES = 128
SECTION_LIMIT = 16000
_snapshots = OrderedDict()


class DetailSection(BaseModel):
    kind: Literal['system', 'long_term', 'session', 'current']
    content: str
    truncated: bool = False
    restricted: bool = False


class ContextDetails(BaseModel):
    message_id: str
    sections: list[DetailSection]


def prune():
    now = time.monotonic()
    for key in list(_snapshots):
        if _snapshots[key]['expires'] <= now:
            discard(key)


def discard(key):
    item = _snapshots.pop(key, None)
    if item and item.get('timer'):
        item['timer'].cancel()


def remember(owner, chat_id, message_id, buckets):
    prune()
    sections = []
    for kind, texts in buckets.items():
        # Each source is labelled by role before this boundary; previews are
        # bounded independently of the full character counts.
        content = '\n\n'.join(texts)
        sections.append(
            DetailSection(kind=kind, content=content[:SECTION_LIMIT], truncated=len(content) > SECTION_LIMIT)
        )
    key = str(uuid4())
    _snapshots[key] = {
        'owner': owner,
        'chat_id': chat_id,
        'expires': time.monotonic() + TTL_SECONDS,
        'details': ContextDetails(message_id=message_id, sections=sections),
    }
    # The production async hook expires text even when no later request arrives.
    try:
        _snapshots[key]['timer'] = asyncio.get_running_loop().call_later(TTL_SECONDS, discard, key)
    except RuntimeError:
        pass  # Synchronous unit tests use monotonic-time pruning.
    while len(_snapshots) > MAX_ENTRIES:
        discard(next(iter(_snapshots)))
    return key


def lookup(key, owner):
    prune()
    item = _snapshots.get(key)
    return (
        {'chat_id': item['chat_id'], 'details': deepcopy(item['details'])} if item and item['owner'] == owner else None
    )
