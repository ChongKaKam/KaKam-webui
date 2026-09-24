"""Bounded orchestration over a completion port and JevClient, independent of WebUI."""

import asyncio
import json
import re
from collections.abc import AsyncIterator, Awaitable, Callable

from pydantic import TypeAdapter, ValidationError

from .client import JevClient, JevError
from .prompts import POLISH_PROMPT, compiler_prompt
from .schemas import Clarification, Plan, PolishedText, TurnRequest, json_data

Completion = Callable[[list[dict[str, str]]], Awaitable[str]]
plan_adapter = TypeAdapter(Plan)


def parse_json(text: str):
    if len(text) > 120000:
        raise ValueError('Completion is too large')
    text = re.sub(r'^\s*<think>[\s\S]*?</think>\s*', '', text, flags=re.IGNORECASE).strip()
    if text.startswith('```') and text.endswith('```'):
        text = re.sub(r'^```(?:json)?\s*', '', text, flags=re.IGNORECASE)[:-3].strip()
    return json.loads(text)


async def compile_plan(form: TurnRequest, complete: Completion):
    messages = [
        {'role': 'system', 'content': compiler_prompt()},
        {'role': 'user', 'content': json_data({'conversation': [m.model_dump() for m in form.messages]})},
    ]
    for attempt in range(2):
        text = await complete(messages)
        try:
            return plan_adapter.validate_python(parse_json(text))
        except (ValidationError, ValueError):
            if attempt:
                raise JevError('润色模型未能生成有效的 Jev 请求，请重试或更换模型。', 'invalid_plan', 422) from None
            # Preserve the original evidence; only one repair, never an unbounded agent loop.
            messages.extend(
                [
                    {'role': 'assistant', 'content': text[:120000]},
                    {
                        'role': 'user',
                        'content': (
                            'The previous output failed validation. Re-read the runtime contract and fix the JSON. '
                            'Include every display label with matching keys; use valid question types and criteria. '
                            'Preserve every fact, constraint and negation from the original conversation. '
                            'If information is missing return the clarification shape.'
                        ),
                    },
                ]
            )


async def run_turn(form: TurnRequest, complete: Completion, jev: JevClient) -> AsyncIterator[dict]:
    yield {'type': 'stage', 'stage': 'preparing'}
    try:
        async with asyncio.timeout(240):
            plan = await compile_plan(form, complete)
            if isinstance(plan, Clarification):
                yield {'type': 'clarification', 'message': plan.message}
                yield {'type': 'stage', 'stage': 'done'}
                return
            yield {'type': 'stage', 'stage': 'deciding'}
            result = await jev.evaluate(plan.evaluation())
            # Commit authoritative cards to the browser before the optional presentation pass.
            yield {
                'type': 'result',
                'evaluation': plan.evaluation().model_dump(exclude_none=True),
                'display': {key: value.model_dump() for key, value in plan.display.items()},
                'response': result.model_dump(exclude_none=True),
            }
            yield {'type': 'stage', 'stage': 'polishing'}
            try:
                text = await complete(
                    [
                        {'role': 'system', 'content': POLISH_PROMPT},
                        {
                            'role': 'user',
                            'content': json_data(
                                {
                                    'conversation': [m.model_dump() for m in form.messages],
                                    'evaluation': plan.model_dump(),
                                    'response': result.model_dump(),
                                }
                            ),
                        },
                    ]
                )
                summary = PolishedText.model_validate(parse_json(text)).summary
                yield {'type': 'summary', 'summary': summary}
            except (JevError, ValueError, TimeoutError):
                yield {'type': 'warning', 'message': '结果润色暂不可用，已保留 Jev 的原始判断与概率。'}
            yield {'type': 'stage', 'stage': 'done'}
    except TimeoutError:
        yield {'type': 'error', 'code': 'timeout', 'message': '本次判断超时，请稍后重试。'}
    except JevError as exc:
        yield {'type': 'error', 'code': exc.code, 'message': str(exc)}


async def event_stream(events: AsyncIterator[dict]) -> AsyncIterator[str]:
    """Keep proxy connections alive and cancel in-flight inference on disconnect."""
    queue: asyncio.Queue = asyncio.Queue(maxsize=1)

    async def produce():
        # Advance the generator in ONE task: asyncio.timeout is bound to the task
        # that enters it, and must remain effective across all progress events.
        try:
            async for event in events:
                await queue.put(event)
        except asyncio.CancelledError:
            raise
        except Exception:
            await queue.put({'type': 'error', 'code': 'internal_error', 'message': '判断流程暂不可用，请稍后重试。'})
        await queue.put(None)

    producer = asyncio.create_task(produce())
    pending = None
    try:
        while True:
            pending = asyncio.create_task(queue.get())
            while not (await asyncio.wait({pending}, timeout=10))[0]:
                yield ': keepalive\n\n'
            event = pending.result()
            if event is None:
                return
            yield f'data: {json_data(event)}\n\n'
    finally:
        if pending and not pending.done():
            pending.cancel()
            await asyncio.gather(pending, return_exceptions=True)
        producer.cancel()
        await asyncio.gather(producer, return_exceptions=True)
        await events.aclose()
