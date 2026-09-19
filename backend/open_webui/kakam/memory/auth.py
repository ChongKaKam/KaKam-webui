from fastapi import HTTPException

from open_webui.models.config import Config
from open_webui.utils.access_control import has_permission


async def allowed(user):
    return user.role == 'admin' or await has_permission(
        user.id, 'features.memories', await Config.get('user.permissions')
    )


async def require_permission(user):
    if not await allowed(user):
        raise HTTPException(403, 'Memory access is not permitted')


def preferences(user):
    stored = user.settings
    if hasattr(stored, 'model_dump'):
        stored = stored.model_dump()
    stored = stored if isinstance(stored, dict) else {}
    ui = stored.get('ui') or {}
    ui = ui if isinstance(ui, dict) else {}
    value = ui.get('kakamMemory') or {}
    if not isinstance(value, dict):
        value = {}
    try:
        days = max(7, min(30, int(value.get('days', 30))))
    except (ValueError, TypeError):
        days = 30
    return {
        'enabled': value.get('enabled', True) is True,
        'policy': value.get('policy', 'default'),
        'days': days,
        'cache': value.get('cache', True) is True,
    }
