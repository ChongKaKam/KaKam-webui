"""Authenticated browser API. The Jev key stays behind this boundary."""

import time

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from starlette.responses import StreamingResponse

from open_webui.utils.auth import get_admin_user, get_verified_user

from .client import JevError
from .config import connection_view, get_jev_client, load_connection, resolve_connection, save_connection
from .llm import completion_port, prompt_models
from .schemas import (
    ConnectionInput,
    ConnectionStatus,
    ConnectionView,
    EvaluationRequest,
    EvaluationResponse,
    TurnRequest,
)
from .workflow import event_stream, run_turn

router = APIRouter()


def fail(exc: JevError):
    raise HTTPException(exc.status, {'code': exc.code, 'message': str(exc)}) from None


@router.get('/config', response_model=ConnectionView)
async def read_config(response: Response, user=Depends(get_admin_user)):
    response.headers['Cache-Control'] = 'no-store'
    try:
        return connection_view(await load_connection())
    except JevError as exc:
        fail(exc)


@router.put('/config', response_model=ConnectionView)
async def update_config(form: ConnectionInput, response: Response, user=Depends(get_admin_user)):
    response.headers['Cache-Control'] = 'no-store'
    try:
        return await save_connection(form)
    except JevError as exc:
        fail(exc)


@router.post('/test', response_model=ConnectionStatus)
async def test_connection(form: ConnectionInput, response: Response, user=Depends(get_admin_user)):
    response.headers['Cache-Control'] = 'no-store'
    try:
        connection = await resolve_connection(form)
        client = await get_jev_client(connection)
        started = time.monotonic()
        result = await client.evaluate(
            EvaluationRequest(
                state='This is a connection test.',
                questions={'connection': {'type': 'noul', 'instructions': 'Is this a connection test?'}},
            )
        )
        return ConnectionStatus(
            configured=True,
            connected=True,
            model=result.model,
            checked_at=time.time(),
            latency_ms=round((time.monotonic() - started) * 1000),
            message='连接成功，Jev 已完成测试判断。',
        )
    except JevError as exc:
        fail(exc)


@router.get('/status', response_model=ConnectionStatus)
async def connection_status(response: Response, user=Depends(get_verified_user)):
    response.headers['Cache-Control'] = 'no-store'
    configured = False
    try:
        connection = await load_connection()
        configured = connection.api_key is not None
        client = await get_jev_client(connection)
        latency = await client.check_connection()
        return ConnectionStatus(
            configured=True,
            connected=True,
            checked_at=time.time(),
            latency_ms=latency,
            message='Jev 连接正常',
        )
    except JevError as exc:
        return ConnectionStatus(configured=configured, connected=False, checked_at=time.time(), message=str(exc))


@router.get('/prompt-models')
async def list_prompt_models(request: Request, user=Depends(get_verified_user)):
    return {'models': await prompt_models(request, user)}


@router.post('/evaluate', response_model=EvaluationResponse)
async def evaluate(form: EvaluationRequest, response: Response, user=Depends(get_verified_user)):
    """Typed direct judgments for authenticated internal clients; no LLM step needed."""
    response.headers['Cache-Control'] = 'no-store'
    try:
        return await (await get_jev_client()).evaluate(form)
    except JevError as exc:
        fail(exc)


@router.post('/turn')
async def turn(form: TurnRequest, request: Request, user=Depends(get_verified_user)):
    if form.model_id not in {model['id'] for model in await prompt_models(request, user)}:
        raise HTTPException(403, '无权使用此润色模型，或该模型不支持服务端调用。')
    try:
        connection = await load_connection()
        if not connection.api_key:
            raise JevError('请先由管理员配置 Jev API Key。', 'not_configured', 409)
        client = await get_jev_client(connection)
    except JevError as exc:
        fail(exc)
    return StreamingResponse(
        event_stream(run_turn(form, completion_port(request, user, form.model_id), client)),
        media_type='text/event-stream',
        headers={'Cache-Control': 'no-store', 'X-Accel-Buffering': 'no'},
    )
