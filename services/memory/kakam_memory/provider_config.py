"""Tenant-scoped provider configuration with authenticated encryption at rest."""

import base64
import ipaddress
import json
import os
from dataclasses import replace
from typing import Literal
from urllib.parse import urlsplit

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator

ProviderKind = Literal['context', 'embedding']


class ProviderForm(BaseModel):
    model_config = ConfigDict(extra='forbid')
    base_url: str = Field(default='', max_length=2000)
    model: str = Field(default='', max_length=200)
    enabled: bool = True
    protocol: Literal['chat_completions', 'responses', 'embeddings']
    timeout_seconds: int = Field(default=20, ge=1, le=60)
    dimension: int = Field(default=1536, ge=1, le=16000)
    api_key_action: Literal['keep', 'replace', 'clear'] = 'keep'
    api_key: SecretStr = Field(default=SecretStr(''), max_length=8192)
    revision: int = Field(default=0, ge=0)
    acknowledge_reindex: bool = False

    @field_validator('base_url')
    @classmethod
    def validate_url(cls, value):
        value = value.strip().rstrip('/')
        if not value:
            return value
        url = urlsplit(value)
        if (
            url.scheme not in ('https', 'http')
            or not url.hostname
            or url.username
            or url.password
            or url.query
            or url.fragment
            or any(c.isspace() for c in value)
        ):
            raise ValueError('Use an HTTP(S) base URL without credentials, query or fragment')
        if url.path.endswith(('/responses', '/chat/completions', '/embeddings')):
            raise ValueError('Enter the base URL, not the full API endpoint')
        try:
            address = ipaddress.ip_address(url.hostname)
        except ValueError:
            address = None
        if address and (address.is_link_local or address.is_multicast or address.is_unspecified):
            raise ValueError('Metadata/link-local/multicast addresses are not allowed')
        if url.hostname.lower() in ('metadata.google.internal', 'metadata'):
            raise ValueError('Metadata addresses are not allowed')
        return value


class ResetForm(BaseModel):
    model_config = ConfigDict(extra='forbid')
    revision: int = Field(ge=0)
    acknowledge_reindex: bool = False


class ProviderView(BaseModel):
    base_url: str
    model: str
    enabled: bool
    protocol: Literal['chat_completions', 'responses', 'embeddings']
    timeout_seconds: int
    dimension: int
    api_key_set: bool
    revision: int
    source: Literal['environment', 'database']


class ConfigView(BaseModel):
    write_enabled: bool
    providers: dict[ProviderKind, ProviderView]


class ProbeResult(BaseModel):
    ok: bool
    status: Literal[
        'ready',
        'authentication_failed',
        'permission_denied',
        'not_found',
        'rate_limited',
        'provider_error',
        'timeout',
        'connection_failed',
        'invalid_response',
        'unsupported',
    ]
    message: str
    http_status: int | None
    elapsed_ms: int


class ModelsResult(ProbeResult):
    models: list[str] = Field(default_factory=list)
    truncated: bool = False


def tenant(owner):
    return owner.split(':', 1)[0]


class ConfigStore:
    def __init__(self, repo, defaults):
        self.repo, self.defaults = repo, defaults

    def cipher(self):
        try:
            key = bytes.fromhex(self.defaults.config_encryption_key)
            if len(key) != 32:
                raise ValueError()
            return AESGCM(key)
        except ValueError:
            raise HTTPException(
                503, 'Set MEMORY_CONFIG_ENCRYPTION_KEY to a permanent 64-character hex secret'
            ) from None

    def encrypt(self, owner, kind, payload):
        nonce = os.urandom(12)
        value = self.cipher().encrypt(nonce, json.dumps(payload).encode(), f'{tenant(owner)}:{kind}'.encode())
        return base64.urlsafe_b64encode(nonce + value).decode()

    def decrypt(self, owner, kind, payload):
        try:
            data = base64.urlsafe_b64decode(payload)
            return json.loads(self.cipher().decrypt(data[:12], data[12:], f'{tenant(owner)}:{kind}'.encode()))
        except HTTPException:
            raise
        except Exception:
            raise HTTPException(
                503, 'Stored Memory configuration cannot be decrypted; restore the original encryption key'
            ) from None

    def rows(self, owner):
        with self.repo.connect() as db:
            return {
                row['provider_kind']: row
                for row in db.execute(
                    'SELECT provider_kind,encrypted_payload,revision FROM memory_provider_config WHERE tenant_id=%s',
                    (tenant(owner),),
                ).fetchall()
            }

    def environment(self, kind):
        cfg = self.defaults
        return {
            'base_url': getattr(cfg, f'{kind}_url'),
            'model': getattr(cfg, f'{kind}_model'),
            'api_key': getattr(cfg, f'{kind}_key'),
            'enabled': getattr(cfg, f'{kind}_enabled'),
            'timeout_seconds': getattr(cfg, f'{kind}_timeout'),
            'protocol': cfg.context_protocol if kind == 'context' else 'embeddings',
            'dimension': cfg.embedding_dimension,
        }

    def current(self, owner, kind, rows):
        row = rows.get(kind)
        if row and row['encrypted_payload']:
            return self.decrypt(owner, kind, row['encrypted_payload'])
        return self.environment(kind)

    def effective(self, owner, rows=None):
        rows = self.rows(owner) if rows is None else rows
        changes = {'config_revision': sum(r['revision'] for r in rows.values())}
        for kind in ('embedding', 'context'):
            value = self.current(owner, kind, rows)
            changes.update(
                {
                    f'{kind}_url': value['base_url'],
                    f'{kind}_key': value['api_key'],
                    f'{kind}_model': value['model'],
                    f'{kind}_enabled': value['enabled'],
                    f'{kind}_timeout': value['timeout_seconds'],
                }
            )
            changes['context_protocol' if kind == 'context' else 'embedding_dimension'] = value[
                'protocol' if kind == 'context' else 'dimension'
            ]
        return replace(self.defaults, **changes)

    def view(self, owner):
        rows = self.rows(owner)
        try:
            self.cipher()
            writable = True
        except HTTPException:
            writable = False
        groups = {}
        for kind in ('context', 'embedding'):
            value = self.current(owner, kind, rows)
            groups[kind] = {k: v for k, v in value.items() if k != 'api_key'}
            groups[kind].update(
                api_key_set=bool(value['api_key']),
                revision=rows.get(kind, {}).get('revision', 0),
                source='database' if rows.get(kind, {}).get('encrypted_payload') else 'environment',
            )
        return {'write_enabled': writable, 'providers': groups}

    def candidate(self, owner, kind, form, rows=None):
        rows = self.rows(owner) if rows is None else rows
        current = self.current(owner, kind, rows)
        if (kind == 'context' and form.protocol == 'embeddings') or (
            kind == 'embedding' and form.protocol != 'embeddings'
        ):
            raise HTTPException(422, 'Protocol does not match provider type')
        value = form.model_dump(exclude={'api_key', 'api_key_action', 'revision', 'acknowledge_reindex'})
        if form.enabled and (not form.base_url or not form.model.strip()):
            raise HTTPException(422, 'Enabled providers require a base URL and model')
        if form.api_key_action == 'replace':
            value['api_key'] = form.api_key.get_secret_value().strip()
            if not value['api_key']:
                raise HTTPException(422, 'A replacement API key cannot be empty; use Clear instead')
        elif form.api_key_action == 'clear':
            value['api_key'] = ''
        else:
            old_origin, new_origin = urlsplit(current['base_url']), urlsplit(form.base_url)
            if current['api_key'] and (old_origin.scheme, old_origin.netloc) != (new_origin.scheme, new_origin.netloc):
                raise HTTPException(409, 'Changing provider origin requires replacing or clearing the API key')
            value['api_key'] = current['api_key']
        return value

    def settings_for(self, owner, kind, value):
        cfg = self.effective(owner)
        changes = {
            f'{kind}_url': value['base_url'],
            f'{kind}_key': value['api_key'],
            f'{kind}_model': value['model'],
            f'{kind}_enabled': value['enabled'],
            f'{kind}_timeout': value['timeout_seconds'],
        }
        changes['context_protocol' if kind == 'context' else 'embedding_dimension'] = value[
            'protocol' if kind == 'context' else 'dimension'
        ]
        return replace(cfg, **changes)

    def save(self, owner, kind, form, reset=False):
        # No provider/network calls while this transaction is open.
        self.cipher()
        with self.repo.connect() as db:
            db.execute(
                'INSERT INTO memory_provider_config(tenant_id,provider_kind,updated_by) VALUES (%s,%s,%s) ON CONFLICT DO NOTHING',
                (tenant(owner), kind, owner),
            )
            row = db.execute(
                'SELECT * FROM memory_provider_config WHERE tenant_id=%s AND provider_kind=%s FOR UPDATE',
                (tenant(owner), kind),
            ).fetchone()
            if row['revision'] != form.revision:
                raise HTTPException(409, 'Configuration changed; reload before saving')
            rows = {kind: row}
            value = self.environment(kind) if reset else self.candidate(owner, kind, form, rows)
            current = self.current(owner, kind, rows)
            space_changed = kind == 'embedding' and any(
                value[k] != current[k] for k in ('base_url', 'model', 'dimension')
            )
            if space_changed:
                count = db.execute(
                    """SELECT count(*) AS n FROM memory_item
                    WHERE tenant_id=%s AND status='active'
                    AND (expires_at IS NULL OR expires_at>now())""",
                    (tenant(owner),),
                ).fetchone()['n']
                if count and not form.acknowledge_reindex:
                    raise HTTPException(
                        409,
                        f'Embedding space changes affect {count} active memories; acknowledge reindexing before saving',
                    )
            revision = row['revision'] + 1
            payload = None if reset else self.encrypt(owner, kind, value)
            db.execute(
                'UPDATE memory_provider_config SET encrypted_payload=%s,revision=%s,updated_by=%s,updated_at=now() WHERE tenant_id=%s AND provider_kind=%s',
                (payload, revision, owner, tenant(owner), kind),
            )
            db.execute(
                'INSERT INTO memory_config_event(tenant_id,provider_kind,action,actor,revision) VALUES (%s,%s,%s,%s,%s)',
                (tenant(owner), kind, 'restore_environment' if reset else 'update', owner, revision),
            )
        return self.view(owner)
