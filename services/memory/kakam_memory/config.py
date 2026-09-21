import hashlib
import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    database_url: str = os.getenv('MEMORY_DATABASE_URL', '')
    service_key: str = os.getenv('MEMORY_SERVICE_KEY', '')
    embedding_url: str = os.getenv('MEMORY_EMBEDDING_BASE_URL', '').rstrip('/')
    embedding_key: str = os.getenv('MEMORY_EMBEDDING_API_KEY', '')
    embedding_model: str = os.getenv('MEMORY_EMBEDDING_MODEL', '')
    embedding_dimension: int = int(os.getenv('MEMORY_EMBEDDING_DIMENSION', '1536'))
    context_url: str = os.getenv('MEMORY_CONTEXT_BASE_URL', '').rstrip('/')
    context_key: str = os.getenv('MEMORY_CONTEXT_API_KEY', '')
    context_model: str = os.getenv('MEMORY_CONTEXT_MODEL', '')
    config_encryption_key: str = os.getenv('MEMORY_CONFIG_ENCRYPTION_KEY', '')
    context_protocol: str = os.getenv('MEMORY_CONTEXT_PROTOCOL', 'chat_completions')
    context_enabled: bool = os.getenv('MEMORY_CONTEXT_ENABLED', 'true').lower() == 'true'
    context_timeout: int = int(os.getenv('MEMORY_CONTEXT_TIMEOUT_SECONDS', '20'))
    embedding_enabled: bool = os.getenv('MEMORY_EMBEDDING_ENABLED', 'true').lower() == 'true'
    embedding_timeout: int = int(os.getenv('MEMORY_EMBEDDING_TIMEOUT_SECONDS', '25'))
    config_revision: int = 0

    def validate(self):
        if not self.database_url or len(self.service_key) < 32:
            raise RuntimeError('Set MEMORY_DATABASE_URL and a MEMORY_SERVICE_KEY of at least 32 characters')
        # Bootstrap can start without model credentials; configure them in the admin UI.
        if not 1 <= self.embedding_dimension <= 16000:
            raise RuntimeError('Invalid embedding dimension')

    @property
    def embedding_version(self):
        endpoint = hashlib.sha256(self.embedding_url.encode()).hexdigest()[:12]
        return f'{endpoint}:{self.embedding_model}:{self.embedding_dimension}:v1'
