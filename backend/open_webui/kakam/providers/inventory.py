"""Pure adapter for an explicit supplier allowlist in native connection configuration."""
from copy import deepcopy
from .reasoning import public_reasoning, reasoning_capability


def validate_suppliers(configs: dict) -> None:
    if not any('kakam_supplier' in config for config in configs.values()):
        return
    aliases, suppliers, model_ids = set(), set(), set()
    for config in configs.values():
        supplier = config.get('kakam_supplier')
        if supplier is None:
            continue
        if not isinstance(supplier, dict):
            raise ValueError('供应商配置格式不正确。')
        alias, supplier_id = supplier.get('alias'), supplier.get('id')
        if not isinstance(alias, str) or not alias.strip() or len(alias) > 80:
            raise ValueError('供应商别名须为 1–80 个字符。')
        if alias.strip().casefold() in aliases:
            raise ValueError('供应商别名重复，请使用不同别名。')
        aliases.add(alias.strip().casefold())
        if not isinstance(supplier_id, str) or not supplier_id or len(supplier_id) > 100 or supplier_id in suppliers:
            raise ValueError('供应商标识无效或重复。')
        suppliers.add(supplier_id)
        rows = supplier.get('models')
        if not isinstance(rows, list) or len(rows) > 10000:
            raise ValueError('供应商模型白名单格式不正确。')
        ids = []
        for model in rows:
            if not isinstance(model, dict) or not isinstance(model.get('id'), str) or not model['id'].strip() or len(model['id']) > 512:
                raise ValueError('模型 ID 无效。')
            ids.append(model['id'])
            if 'reasoning' in model:
                reasoning_capability(model['reasoning'])
        if len(ids) != len(set(ids)) or config.get('model_ids') != ids:
            raise ValueError('模型白名单与探测快照不一致。')
    # Explicit inventories must never silently shadow another supplier.
    for config in configs.values():
        for model_id in config.get('model_ids', []):
            prefix = config.get('prefix_id')
            qualified = f'{prefix}.{model_id}' if prefix else model_id
            if qualified in model_ids:
                raise ValueError('模型标识冲突，请为供应商设置不同的模型标识前缀。')
            model_ids.add(qualified)


def supplier_inventory(config: dict, index: int) -> dict | None:
    supplier = config.get('kakam_supplier')
    if not isinstance(supplier, dict):
        return None
    allowed = set(config.get('model_ids', []))
    return {'object': 'list', 'data': [
        {'id': model['id'], 'name': model.get('name') or model['id'], 'owned_by': 'openai',
         'openai': {'id': model['id']}, 'urlIdx': index,
         'kakam_provider': {'id': supplier['id'], 'alias': supplier['alias'], 'model_id': model['id'],
                            **public_reasoning(model)}}
        for model in supplier.get('models', []) if model['id'] in allowed
    ]}


def inherit_supplier(base_model: dict | None) -> dict:
    """Presets retain provenance without disclosing the URL, key or connection settings."""
    if base_model and base_model.get('kakam_provider'):
        return {'kakam_provider': deepcopy(base_model['kakam_provider'])}
    return {}
