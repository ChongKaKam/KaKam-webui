"""Read-only UI analytics over WebUI-owned prompt snapshots, not Memory data."""

import datetime as dt
from typing import Literal

from pydantic import BaseModel

KINDS = ('system', 'long_term', 'session', 'current')
ROW_LIMIT = 5000


class ActivityDay(BaseModel):
    date: str
    requests: int = 0
    characters: dict[str, int]


class MemoryActivity(BaseModel):
    days: int
    timezone: Literal['UTC'] = 'UTC'
    measurement: Literal['characters'] = 'characters'
    requests: int
    total_characters: int
    characters: dict[str, int]
    heatmap: list[ActivityDay]
    truncated: bool = False


def summarize(rows, days, now=None, truncated=False):
    now = now or dt.datetime.now(dt.timezone.utc)
    start = now.date() - dt.timedelta(days=days - 1)
    buckets = {
        (start + dt.timedelta(days=offset)).isoformat(): ActivityDay(
            date=(start + dt.timedelta(days=offset)).isoformat(), characters=dict.fromkeys(KINDS, 0)
        )
        for offset in range(days)
    }
    totals = dict.fromkeys(KINDS, 0)
    requests = 0
    for meta, timestamp in rows:
        report = meta.get('kakamMemory') if isinstance(meta, dict) else None
        if not isinstance(report, dict) or not isinstance(report.get('segments'), list):
            continue
        values = {}
        for segment in report['segments']:
            if not isinstance(segment, dict):
                continue
            kind, count = segment.get('kind'), segment.get('characters')
            if kind in KINDS and type(count) is int and 0 <= count <= 100_000_000:
                values[kind] = count
        # Missing/legacy reports aren't zero usage.
        if len(values) != len(KINDS):
            continue
        try:
            date = dt.datetime.fromtimestamp(timestamp, dt.timezone.utc).date().isoformat()
        except (TypeError, ValueError, OverflowError, OSError):
            continue
        if date not in buckets:
            continue
        bucket = buckets[date]
        bucket.requests += 1
        requests += 1
        for kind in KINDS:
            bucket.characters[kind] += values[kind]
            totals[kind] += values[kind]
    return MemoryActivity(
        days=days,
        requests=requests,
        total_characters=sum(totals.values()),
        characters=totals,
        heatmap=list(buckets.values()),
        truncated=truncated,
    )


async def get_activity(user_id, days):
    # Lazy upstream imports keep the aggregation independently testable.
    from sqlalchemy import select

    from open_webui.internal.db import get_async_db_context
    from open_webui.models.chat_messages import ChatMessage
    from open_webui.models.chats import Chat

    now = dt.datetime.now(dt.timezone.utc)
    start = (now - dt.timedelta(days=days - 1)).replace(hour=0, minute=0, second=0, microsecond=0)
    end = now.replace(hour=0, minute=0, second=0, microsecond=0) + dt.timedelta(days=1)
    async with get_async_db_context() as db:
        rows = (
            await db.execute(
                select(ChatMessage.meta, ChatMessage.created_at)
                .join(Chat, Chat.id == ChatMessage.chat_id)
                .where(
                    Chat.user_id == user_id,
                    ChatMessage.user_id == user_id,
                    ChatMessage.role == 'assistant',
                    ChatMessage.meta.is_not(None),
                    ChatMessage.created_at >= int(start.timestamp()),
                    ChatMessage.created_at < int(end.timestamp()),
                )
                .order_by(ChatMessage.created_at.desc(), ChatMessage.id.desc())
                .limit(ROW_LIMIT + 1)
            )
        ).all()
    return summarize(rows[:ROW_LIMIT], days, now, truncated=len(rows) > ROW_LIMIT)
