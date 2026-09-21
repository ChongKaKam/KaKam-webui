"""Validate and expose only the bounded capability contract from admin discovery."""

VALUES = ('none', 'low', 'medium', 'high', 'xhigh', 'max')


def reasoning_capability(value):
    if not isinstance(value, dict):
        raise ValueError('思考能力信息格式不正确，请重新探测。')
    status, source, values = value.get('status'), value.get('source'), value.get('values')
    if (status not in ('supported', 'unsupported', 'unknown')
            or source not in ('metadata', 'official', 'unknown')
            or not isinstance(values, list)
            or len(values) > len(VALUES)
            or any(not isinstance(level, str) or level not in VALUES for level in values)
            or len(set(values)) != len(values)
            or (status == 'supported' and (source == 'unknown' or not any(level != 'none' for level in values)))
            or (status == 'unknown' and values)
            or (status == 'unsupported' and (source != 'metadata' or any(level != 'none' for level in values)))):
        raise ValueError('思考能力档位不正确，请重新探测。')
    return {'status': status, 'source': source, 'values': list(values)}


def public_reasoning(model):
    if 'reasoning' not in model:
        return {}
    try:
        return {'reasoning': reasoning_capability(model['reasoning'])}
    except ValueError:
        # Old/malformed persisted data must not break login or re-enable name guessing.
        return {'reasoning': {'status': 'unknown', 'source': 'unknown', 'values': []}}
