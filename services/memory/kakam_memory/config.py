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
    extraction_url: str = os.getenv('MEMORY_EXTRACTION_BASE_URL', '').rstrip('/')
    extraction_key: str = os.getenv('MEMORY_EXTRACTION_API_KEY', '')
    extraction_model: str = os.getenv('MEMORY_EXTRACTION_MODEL', '')

    def validate(self):
        if not self.database_url or len(self.service_key) < 32:
            raise RuntimeError('Set MEMORY_DATABASE_URL and a MEMORY_SERVICE_KEY of at least 32 characters')
        if not self.embedding_url or not self.embedding_model:
            raise RuntimeError('Set MEMORY_EMBEDDING_BASE_URL and MEMORY_EMBEDDING_MODEL')
        if not 1 <= self.embedding_dimension <= 16000:
            raise RuntimeError('Invalid embedding dimension')

    @property
    def embedding_version(self):
        endpoint = hashlib.sha256(self.embedding_url.encode()).hexdigest()[:12]
        return f'{endpoint}:{self.embedding_model}:{self.embedding_dimension}:v1'
