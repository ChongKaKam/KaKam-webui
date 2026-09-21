import ast
import asyncio
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock

from .inventory import supplier_inventory, validate_suppliers, inherit_supplier
from open_webui.utils.model_ids import strip_provider_model_prefix


def connection(alias='Official', prefix='supplier_a', ids=None):
    ids = ['gpt-6-astra'] if ids is None else ids
    return {'prefix_id': prefix, 'model_ids': ids, 'kakam_supplier': {
        'id': prefix or 'legacy', 'alias': alias,
        'models': [{'id': mid, 'name': mid} for mid in ids]}}


def upstream_function(path, name, namespace):
    source = Path(__file__).parents[2] / path
    tree = ast.parse(source.read_text())
    node = next(n for n in tree.body if isinstance(n, ast.AsyncFunctionDef) and n.name == name)
    node.decorator_list = []
    node.returns = None
    for arg in node.args.args:
        arg.annotation = None
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(source), 'exec'), namespace)
    return namespace[name]


class SupplierInventoryTest(unittest.TestCase):
    def test_empty_whitelist_does_not_autodiscover(self):
        self.assertEqual(supplier_inventory(connection(ids=[]), 0)['data'], [])
        self.assertIsNone(supplier_inventory({'model_ids': []}, 0))

    def test_only_selected_models_and_safe_provenance_are_exposed(self):
        config = connection()
        config.update(key='secret', headers={'Authorization': 'secret'})
        config['kakam_supplier']['models'].append({'id': 'not-selected', 'name': 'Hidden'})
        inventory = supplier_inventory(config, 3)
        self.assertEqual(len(inventory['data']), 1)
        self.assertEqual(inventory['data'][0]['kakam_provider']['alias'], 'Official')
        self.assertNotIn('secret', str(inventory))

    def test_collisions_and_inconsistent_snapshots_are_rejected(self):
        with self.assertRaises(ValueError):
            validate_suppliers({'0': connection(), '1': connection()})
        invalid = connection(); invalid['model_ids'] = []
        with self.assertRaises(ValueError): validate_suppliers({'0': invalid})
        with self.assertRaises(ValueError): validate_suppliers({'0': connection(alias='')})
        validate_suppliers({'0': connection(), '1': connection('Partner', 'supplier_b')})

    def test_presets_inherit_copy_of_provenance(self):
        base = supplier_inventory(connection(), 0)['data'][0]
        result = inherit_supplier(base)
        result['kakam_provider']['alias'] = 'Changed'
        self.assertEqual(base['kakam_provider']['alias'], 'Official')
        self.assertEqual(inherit_supplier(None), {})


class SupplierDispatchTest(unittest.IsolatedAsyncioTestCase):
    async def test_native_inventory_keeps_duplicates_distinct_and_dispatch_strips_only_own_prefix(self):
        configs = {'0': connection(), '1': connection('Partner', 'supplier_b'), '2': connection('Empty', 'supplier_c', [])}
        probe = AsyncMock()
        namespace = {'asyncio': asyncio, 'get_openai_runtime_config': AsyncMock(return_value=(True, ['a','b','c'], ['key']*3, configs)), 'supplier_inventory': supplier_inventory, 'get_models_request': probe, 'log': SimpleNamespace(debug=lambda *a: None)}
        handler = upstream_function('routers/openai.py', 'get_all_models_responses', namespace)
        responses = await handler(SimpleNamespace(), SimpleNamespace())
        models = [m for r in responses for m in r['data']]
        self.assertEqual([m['id'] for m in models], ['supplier_a.gpt-6-astra', 'supplier_b.gpt-6-astra'])
        self.assertEqual([m['name'] for m in models], ['gpt-6-astra']*2)
        self.assertEqual([m['kakam_provider']['alias'] for m in models], ['Official', 'Partner'])
        probe.assert_not_called()
        self.assertEqual(strip_provider_model_prefix(models[1]['id'], 'supplier_b'), 'gpt-6-astra')
        self.assertNotEqual(strip_provider_model_prefix(models[1]['id'], 'supplier_a'), 'gpt-6-astra')

    async def test_native_acl_keeps_each_supplier_independent(self):
        a, b = 'supplier_a.gpt-6-astra', 'supplier_b.gpt-6-astra'
        grants = AsyncMock(return_value={b})
        namespace = {'BYPASS_ADMIN_ACCESS_CONTROL': True, 'BYPASS_MODEL_ACCESS_CONTROL': False,
            'Groups': SimpleNamespace(get_groups_by_member_id=AsyncMock(return_value=[])),
            'AccessGrants': SimpleNamespace(get_accessible_resource_ids=grants)}
        handler = upstream_function('utils/models.py', 'get_filtered_models', namespace)
        rows = [{'id': mid, 'info': {'id': mid, 'user_id': 'admin'}} for mid in (a,b)]
        unconfigured = {'id':'supplier_c.gpt-6-astra'}
        result = await handler(rows + [unconfigured], SimpleNamespace(role='user', id='member'))
        self.assertEqual([m['id'] for m in result], [b])
        self.assertEqual(grants.call_args.kwargs['resource_ids'], [a,b])
