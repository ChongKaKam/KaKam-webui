"""Provider protocol adapter. `fetch` is injected; tests never call paid services."""

import base64
import binascii
import re
from urllib.parse import quote, urlsplit


class ProbeError(Exception):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


def model_rows(data, engine):
    rows = data.get('data' if engine == 'openai' else 'models') if isinstance(data, dict) else None
    if not isinstance(rows, list):
        raise ProbeError('服务返回的模型列表格式不正确。', 502)
    result = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        model_id = row.get('id') if engine == 'openai' else row.get('name')
        if not isinstance(model_id, str) or not model_id or len(model_id) > 512:
            continue
        if engine == 'gemini':
            model_id = model_id.removeprefix('models/')
        if not model_id:
            continue
        name = row.get('displayName', row.get('name', model_id))
        result.append({'id': model_id, 'name': name if isinstance(name, str) else model_id})
    return result


def rows(value):
    return value if isinstance(value, list) else []


def image_bytes(value):
    if not isinstance(value, str):
        return False
    try:
        raw = base64.b64decode(value, validate=True)
        return raw.startswith((b'\x89PNG\r\n\x1a\n', b'\xff\xd8\xff', b'GIF87a', b'GIF89a')) or (
            raw[:4] == b'RIFF' and raw[8:12] == b'WEBP'
        )
    except (ValueError, binascii.Error):
        return False


def image_url(value):
    try:
        return isinstance(value, str) and urlsplit(value).scheme in ('https', 'http') and bool(urlsplit(value).hostname)
    except ValueError:
        return False


def has_image(data, engine, method):
    if not isinstance(data, dict):
        return False
    if engine == 'openai':
        for item in rows(data.get('data')):
            if isinstance(item, dict) and (image_bytes(item.get('b64_json')) or image_url(item.get('url'))):
                return True
    elif method == 'predict':
        return any(
            isinstance(item, dict) and image_bytes(item.get('bytesBase64Encoded'))
            for item in rows(data.get('predictions'))
        )
    else:
        return has_inline_image(data)
    return False


def has_inline_image(data):
    for candidate in rows(data.get('candidates')):
        if not isinstance(candidate, dict):
            continue
        content = candidate.get('content')
        if not isinstance(content, dict):
            continue
        for part in rows(content.get('parts')):
            image = part.get('inlineData', {}) if isinstance(part, dict) else {}
            if isinstance(image, dict) and image_bytes(image.get('data')):
                return True
    return False


async def probe(form, fetch, url_response_pattern='^gpt-image'):
    key = form.api_key.get_secret_value()
    headers = {'Authorization': f'Bearer {key}'} if form.engine == 'openai' else {'x-goog-api-key': key}
    params = {'api-version': form.api_version} if form.api_version and form.engine == 'openai' else {}
    model = form.model.strip()
    if form.engine == 'gemini':
        model = model.removeprefix('models/')
    if form.action == 'models':
        found, complete = {}, True
        for page in range(10):
            data = await fetch('GET', f'{form.base_url}/models', headers=headers, params=params)
            for row in model_rows(data, form.engine):
                found[row['id']] = row
            if len(found) > 5000:
                complete = False
                break
            next_page = data.get('nextPageToken') if form.engine == 'gemini' else None
            if not next_page:
                complete = not bool(data.get('has_more'))
                break
            params = {**params, 'pageToken': str(next_page)}
        else:
            complete = False
        models = list(found.values())[:5000]
        return {
            'models': models,
            'complete': complete,
            'model_status': 'available'
            if model in {row['id'] for row in models}
            else 'not_listed'
            if model and complete
            else 'unknown',
        }
    if not model:
        raise ProbeError('请先填写需要验证的图片模型。')
    prompt = 'A plain blue circle on a white background, no text.'
    if form.engine == 'openai':
        # Same additional parameters as the saved generation config; never generate >1 image.
        body = {
            **({'size': form.size} if form.size else {}),
            **({} if re.match(url_response_pattern, model) else {'response_format': 'b64_json'}),
            **form.params,
            'model': model,
            'prompt': prompt,
            'n': 1,
        }
        body.pop('stream', None)
        url = f'{form.base_url}/images/generations'
    else:
        url = f'{form.base_url}/models/{quote(model, safe="")}:{form.method}'
        body = (
            {
                'instances': {'prompt': prompt},
                'parameters': {'sampleCount': 1, 'outputOptions': {'mimeType': 'image/png'}},
            }
            if form.method == 'predict'
            else {'contents': [{'parts': [{'text': prompt}]}]}
        )
    data = await fetch('POST', url, headers=headers, params=params, json=body)
    if not has_image(data, form.engine, form.method):
        raise ProbeError('接口已响应，但没有返回图片数据或图片链接；不能确认模型可用于图片生成。', 422)
    return {'generated': True}
