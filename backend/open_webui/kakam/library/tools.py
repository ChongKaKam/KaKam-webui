"""Publish text deliverables through native file storage, with explicit provenance."""

import io
import json
import logging
import re

from fastapi import Request, UploadFile
from starlette.datastructures import Headers

log = logging.getLogger(__name__)
FORMATS = {
    'html': 'text/html',
    'htm': 'text/html',
    'md': 'text/markdown',
    'txt': 'text/plain',
    'csv': 'text/csv',
    'json': 'application/json',
    'svg': 'image/svg+xml',
    'py': 'text/x-python',
    'js': 'text/javascript',
    'css': 'text/css',
    'xml': 'application/xml',
}
MAX_BYTES = 2 * 1024 * 1024


def validate_artifact(filename, content):
    if not filename or len(filename) > 120 or filename.startswith('.') or re.search(r'[\\/\x00-\x1f:*?"<>|]', filename):
        raise ValueError('Use a plain filename, at most 120 characters, with no path or control characters')
    extension = filename.rsplit('.', 1)[-1].lower()
    if '.' not in filename or extension not in FORMATS:
        raise ValueError('Supported extensions: ' + ', '.join(FORMATS))
    data = content.encode('utf-8')
    if not data or len(data) > MAX_BYTES:
        raise ValueError('Artifact must contain 1 byte to 2 MiB of UTF-8 text')
    if extension in ('html', 'htm', 'svg'):
        if content.lstrip().startswith(('```', '~~~')):
            raise ValueError('Provide raw file content without Markdown fences')
        tag = r'<svg\b' if extension == 'svg' else r'<(?:html|body)\b|<!doctype\s+html\b'
        if not re.search(tag, content, re.IGNORECASE):
            raise ValueError('Provide actual HTML/SVG source, not a Markdown description of a website')
    return data, FORMATS[extension]


async def publish_artifact(
    filename: str,
    content: str,
    __request__: Request = None,
    __user__: dict = None,
    __metadata__: dict = None,
    __event_emitter__=None,
) -> str:
    """Save a downloadable deliverable in the current chat's Files library.

    Use this for a requested HTML website, Markdown document, SVG, CSV, JSON or
    source code file. For a single-file website provide complete HTML including
    its CSS/JS. Content must be the raw file text without Markdown fences.
    Unlike a note, this creates a real file attachment with a download URL.
    Only claim delivery after status=success; include the returned download_url.

    :param filename: Filename including extension, e.g. explorer.html or report.md.
    :param content: Complete UTF-8 text of the file, maximum 2 MiB.
    """
    from open_webui.models.chats import Chats
    from open_webui.models.config import Config
    from open_webui.models.users import UserModel
    from open_webui.routers.files import upload_file_handler
    from open_webui.utils.access_control import has_permission
    from open_webui.utils.chat_id import is_saved_chat_id

    metadata = __metadata__ or {}
    chat_id, message_id = metadata.get('chat_id'), metadata.get('message_id')
    if not __request__ or not __user__ or not is_saved_chat_id(chat_id) or not message_id:
        return json.dumps({'error': 'A saved chat and message context are required'})
    user = UserModel.model_validate(__user__)
    if user.role != 'admin' and not await has_permission(
        user.id, 'chat.file_upload', await Config.get('user.permissions')
    ):
        return json.dumps({'error': 'File creation is not permitted'})
    if not await Chats.get_chat_by_id_and_user_id(chat_id, user.id):
        return json.dumps({'error': 'Chat not found'})
    try:
        data, mime = validate_artifact(filename, content)
    except ValueError as error:
        return json.dumps({'error': str(error)})
    upload = UploadFile(file=io.BytesIO(data), filename=filename, headers=Headers({'content-type': mime}))
    try:
        saved = await upload_file_handler(
            __request__,
            file=upload,
            metadata={'kakam_artifact': True, 'chat_id': chat_id, 'message_id': message_id},
            process=False,
            process_in_background=False,
            user=user,
        )
    finally:
        await upload.close()
    file_id = saved.id if hasattr(saved, 'id') else saved['id']
    linked = await Chats.insert_chat_files(chat_id, message_id, [file_id], user.id)
    url = f'/api/v1/files/{file_id}/content?attachment=true'
    attachment = {
        'id': file_id,
        'type': 'file',
        'name': filename,
        'url': url,
        'size': len(data),
        'content_type': mime,
        'status': 'uploaded',
    }
    notified = False
    if __event_emitter__:
        try:
            await __event_emitter__({'type': 'files', 'data': {'files': [attachment]}})
            notified = True
        except Exception:
            # The bytes already exist. Do not tell the model to regenerate them.
            log.warning('Artifact saved but attachment event failed for file %s', file_id)
    return json.dumps(
        {
            'status': 'success',
            'id': file_id,
            'filename': filename,
            'size': len(data),
            'download_url': url,
            'library_url': '/library',
            'expires_at': None,
            'chat_linked': bool(linked),
            'attachment_emitted': notified,
        },
        ensure_ascii=False,
    )
