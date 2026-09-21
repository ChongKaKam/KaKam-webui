import importlib
import sys
import types
from unittest.mock import AsyncMock

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient


def test_bff_admin_only_all_routes(monkeypatch):
    user = types.SimpleNamespace(id='admin', role='user')

    async def admin():
        if user.role != 'admin':
            raise HTTPException(403, 'Admin only')
        return user

    monkeypatch.setitem(sys.modules, 'open_webui.utils.auth', types.SimpleNamespace(get_admin_user=admin))
    monkeypatch.delitem(sys.modules, 'open_webui.kakam.memory.admin', raising=False)
    module = importlib.import_module('open_webui.kakam.memory.admin')
    monkeypatch.setenv('KAKAM_MEMORY_ENABLED', 'true')
    call = AsyncMock(return_value={'write_enabled': True})
    monkeypatch.setattr(module.client, 'call', call)
    app = FastAPI()
    app.include_router(module.router)
    with TestClient(app) as c:
        for method, path in [
            ('GET', ''),
            ('GET', '/ownership'),
            ('PUT', '/context'),
            ('POST', '/context/test'),
            ('POST', '/embedding/models'),
            ('POST', '/embedding/reset'),
        ]:
            assert c.request(method, '/admin/config' + path, json={}).status_code == 403
        call.assert_not_called()
        user.role = 'admin'
        response = c.get('/admin/config')
        assert response.status_code == 200 and response.headers['cache-control'] == 'no-store'
        assert call.call_args.kwargs['admin'] and call.call_args.args[2] == 'admin'
        assert c.get('/admin/config/ownership').json() == {'manager_enabled': True}
        assert c.post('/admin/config/embedding/models', json={'model': ''}).status_code == 200
        assert call.call_args.args[1] == '/v1/admin/config/embedding/models'
        assert call.call_args.kwargs['admin']
        assert c.put('/admin/config/unknown', json={}).status_code == 422
        assert c.put('/admin/config/context', json={'api_key': 'x' * 20001}).status_code == 413
        monkeypatch.setenv('KAKAM_MEMORY_ENABLED', 'false')
        assert c.get('/admin/config/ownership').json() == {'manager_enabled': False}
        assert c.get('/admin/config').status_code == 503
