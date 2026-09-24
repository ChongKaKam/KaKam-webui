"""Shared server-side configuration. Browsers never receive a saved API key."""

import os

from pydantic import SecretStr

from open_webui.models.config import Config

from .client import JevClient, JevError
from .schemas import DEFAULT_BASE_URL, ConnectionInput, ConnectionView

CONFIG_KEY = 'kakam.jev.connection'


async def load_connection() -> ConnectionInput:
    data = await Config.get(CONFIG_KEY)
    if data is None:
        data = {
            'base_url': os.getenv('KAKAM_JEV_BASE_URL', DEFAULT_BASE_URL),
            'api_key': os.getenv('KAKAM_JEV_API_KEY') or None,
        }
    try:
        return ConnectionInput.model_validate(data)
    except ValueError:
        raise JevError('Jev 配置无效，请管理员重新保存。', 'invalid_config', 409) from None


def connection_view(connection: ConnectionInput) -> ConnectionView:
    return ConnectionView(base_url=connection.base_url, has_api_key=connection.api_key is not None)


def merge_connection(saved: ConnectionInput, draft: ConnectionInput) -> ConnectionInput:
    if draft.api_key is None and not draft.clear_api_key and saved.api_key and draft.base_url != saved.base_url:
        raise JevError('更换 Base URL 时请重新填写 API Key。', 'key_required', 422)
    key = None if draft.clear_api_key else (draft.api_key or saved.api_key)
    return ConnectionInput(base_url=draft.base_url, api_key=key)


async def save_connection(draft: ConnectionInput) -> ConnectionView:
    connection = await resolve_connection(draft)
    # One row keeps URL and key atomic for concurrent readers and future agents.
    await Config.upsert(
        {
            CONFIG_KEY: {
                'base_url': connection.base_url,
                'api_key': connection.api_key.get_secret_value() if connection.api_key else None,
            }
        }
    )
    return connection_view(connection)


async def resolve_connection(draft: ConnectionInput) -> ConnectionInput:
    try:
        saved = await load_connection()
    except JevError:
        # A malformed environment/imported config must be repairable from the UI.
        # Never salvage and forward an unknown old credential to a new address.
        if draft.api_key is None and not draft.clear_api_key:
            raise JevError('现有配置无效，请重新填写 API Key 后保存。', 'key_required', 422) from None
        saved = ConnectionInput()
    return merge_connection(saved, draft)


async def get_jev_client(connection: ConnectionInput | None = None) -> JevClient:
    """Internal entry point for schedulers/agents; reloads the active server configuration."""
    connection = connection or await load_connection()
    key = connection.api_key or SecretStr('')
    return JevClient(connection.base_url, key.get_secret_value())
