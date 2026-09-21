from typing import Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, Field, SecretStr, field_validator


class ImageProbe(BaseModel):
    engine: Literal['openai', 'gemini']
    action: Literal['models', 'generate'] = 'models'
    base_url: str = Field(min_length=1, max_length=2048)
    api_key: SecretStr = SecretStr('')
    api_version: str = Field(default='', max_length=100)
    model: str = Field(default='', max_length=512)
    size: str = Field(default='', max_length=30)
    method: Literal['predict', 'generateContent'] = 'predict'
    params: dict = Field(default_factory=dict)

    @field_validator('base_url')
    @classmethod
    def valid_url(cls, value):
        parsed = urlsplit(value.strip())
        parsed.port  # Validate malformed/out-of-range ports before making a request.
        if (
            parsed.scheme not in ('http', 'https')
            or not parsed.hostname
            or parsed.username
            or parsed.password
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError('Base URL 必须是无凭据、查询参数或片段的 HTTP(S) 地址。')
        return value.strip().rstrip('/')
