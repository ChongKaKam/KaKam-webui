import asyncio
import json
from unittest.mock import AsyncMock

import pytest
from open_webui.kakam.jev.client import JevError
from open_webui.kakam.jev.schemas import EvaluationResponse, TurnRequest
from open_webui.kakam.jev.workflow import event_stream, run_turn
from test_contracts import answer_body, plan_body


def form():
    return TurnRequest(
        model_id='prompt-model', messages=[{'role': 'user', 'content': '重复扣费了，但还能用。请判断退款请求。'}]
    )


def jev():
    return AsyncMock(evaluate=AsyncMock(return_value=EvaluationResponse.model_validate(answer_body())))


@pytest.mark.asyncio
async def test_full_pipeline_skill_and_authoritative_numbers():
    complete = AsyncMock(side_effect=[json.dumps(plan_body()), '{"summary":"账务团队更合适，用户要求退款。"}'])
    client = jev()
    events = [event async for event in run_turn(form(), complete, client)]
    assert [e['stage'] for e in events if e['type'] == 'stage'] == ['preparing', 'deciding', 'polishing', 'done']
    result = next(e for e in events if e['type'] == 'result')
    assert result['response']['answers']['refund']['noul'] == 0.95
    assert result['response']['answers']['severity']['score'] == 1.25
    assert result['display']['team']['options']['billing'] == '账务'
    compiler_messages = complete.call_args_list[0].args[0]
    assert '<typesafe_skill>' in compiler_messages[0]['content']
    assert form().messages[0].content in compiler_messages[1]['content']
    assert client.evaluate.call_count == 1
    assert next(i for i, e in enumerate(events) if e['type'] == 'result') < next(
        i for i, e in enumerate(events) if e.get('stage') == 'polishing'
    )


@pytest.mark.asyncio
async def test_clarification_does_not_spend_jev_tokens():
    client = jev()
    events = [
        e
        async for e in run_turn(
            form(), AsyncMock(return_value='{"kind":"clarification","message":"选项有哪些？"}'), client
        )
    ]
    assert events[1]['type'] == 'clarification'
    client.evaluate.assert_not_called()


@pytest.mark.asyncio
async def test_invalid_plan_repaired_once_before_jev():
    complete = AsyncMock(side_effect=['{"kind":"evaluation"}', json.dumps(plan_body()), '{"summary":"已判断。"}'])
    client = jev()
    events = [e async for e in run_turn(form(), complete, client)]
    assert events[-1] == {'type': 'stage', 'stage': 'done'}
    assert complete.call_count == 3
    assert client.evaluate.call_count == 1


@pytest.mark.asyncio
async def test_repeated_bad_plan_stops_without_inference():
    complete = AsyncMock(return_value='bad JSON')
    client = jev()
    events = [e async for e in run_turn(form(), complete, client)]
    assert events[-1]['code'] == 'invalid_plan'
    assert complete.call_count == 2
    client.evaluate.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize('polish', [JevError('failed'), 'not JSON', '{"summary":""}'])
async def test_polishing_failure_preserves_all_jev_results(polish):
    complete = AsyncMock(side_effect=[json.dumps(plan_body()), polish])
    events = [e async for e in run_turn(form(), complete, jev())]
    assert any(e['type'] == 'result' for e in events)
    assert any(e['type'] == 'warning' for e in events)
    assert events[-1] == {'type': 'stage', 'stage': 'done'}


@pytest.mark.asyncio
async def test_provider_failure_never_polishes_or_reports_done():
    complete = AsyncMock(return_value=json.dumps(plan_body()))
    client = jev()
    client.evaluate.side_effect = JevError('Jev 不可用', 'unavailable')
    events = [e async for e in run_turn(form(), complete, client)]
    assert events[-1]['type'] == 'error'
    assert complete.call_count == 1
    assert not any(e.get('stage') == 'done' for e in events)


@pytest.mark.asyncio
async def test_disconnect_cancels_pending_work():
    started = asyncio.Event()
    cancelled = asyncio.Event()

    async def events():
        try:
            started.set()
            await asyncio.sleep(60)
            yield {'type': 'stage', 'stage': 'done'}
        finally:
            cancelled.set()

    stream = event_stream(events())
    task = asyncio.create_task(anext(stream))
    await started.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert cancelled.is_set()


@pytest.mark.asyncio
async def test_stream_keeps_deadline_bound_to_one_producer_task():
    tasks = []

    async def events():
        for stage in ('preparing', 'deciding', 'polishing', 'done'):
            tasks.append(asyncio.current_task())
            yield {'type': 'stage', 'stage': stage}

    frames = [frame async for frame in event_stream(events())]
    assert len(frames) == 4
    assert len(set(tasks)) == 1


@pytest.mark.asyncio
async def test_generator_timeout_still_fires_after_an_event():
    async def events():
        try:
            async with asyncio.timeout(0.01):
                yield {'type': 'stage', 'stage': 'preparing'}
                await asyncio.sleep(10)
        except TimeoutError:
            yield {'type': 'error', 'code': 'timeout', 'message': 'Timed out'}

    async with asyncio.timeout(1):
        frames = [frame async for frame in event_stream(events())]
    assert 'timeout' in frames[-1]


@pytest.mark.asyncio
async def test_unexpected_stream_error_is_sanitized():
    async def events():
        yield {'type': 'stage', 'stage': 'preparing'}
        raise RuntimeError('secret-provider-body')

    frames = [frame async for frame in event_stream(events())]
    assert 'internal_error' in frames[-1]
    assert 'secret-provider-body' not in ''.join(frames)
