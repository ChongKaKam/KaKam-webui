"""Default policy: bounded, evidence-backed memories within a rolling window."""

import hashlib
import json
import re
import time
from collections import OrderedDict
from copy import deepcopy
from dataclasses import dataclass

POLICIES = [
    {
        'id': 'default',
        'name': 'Default',
        'version': '1',
        'description': 'System + recent long-term memory + current session + current prompt',
        'min_days': 7,
        'max_days': 30,
    }
]
KINDS = {'profile', 'preference', 'instruction', 'fact', 'episode'}
SECRET = re.compile(
    r'sk-[\w-]{12,}|-----BEGIN .*PRIVATE KEY|(?:password|passwd|api[_ -]?key|token|密码|密钥)\s*[:=：]\s*\S+', re.I
)


def fingerprint(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def validate_content(content: str) -> str:
    content = content.strip()
    if not content or len(content) > 2000:
        raise ValueError('Memory must contain 1–2000 characters')
    if SECRET.search(content):
        raise ValueError('Secrets cannot be stored in memory')
    return content


def accepted_candidates(candidates: list, evidence: str) -> list[dict]:
    """An extractor proposes facts; policy requires verbatim user evidence."""
    result = []
    if SECRET.search(evidence):
        return result
    for candidate in candidates[:8]:
        if not isinstance(candidate, dict):
            continue
        quote = candidate.get('evidence', '')
        if not isinstance(quote, str) or not quote.strip() or quote not in evidence:
            continue
        if candidate.get('kind') not in KINDS or candidate.get('durable') is not True:
            continue
        try:
            content = validate_content(candidate.get('content', ''))
        except (ValueError, TypeError, AttributeError):
            continue
        # Instruction memories require an explicit user request, not model inference.
        if candidate['kind'] == 'instruction' and not re.search(
            r'记住|以后|始终|remember|always|from now on', quote, re.I
        ):
            continue
        result.append({'content': content, 'kind': candidate['kind'], 'evidence': quote})
    return result


@dataclass
class CacheEntry:
    expires: float
    value: object


class TTLCache:
    """Bounded process-local LRU. Keys contain user, settings and DB revision."""

    def __init__(self, capacity=256, ttl=60, clock=time.monotonic):
        self.capacity, self.ttl, self.clock = capacity, ttl, clock
        self.entries = OrderedDict()

    def get(self, key):
        entry = self.entries.pop(key, None)
        if entry is None or entry.expires <= self.clock():
            return None
        self.entries[key] = entry
        return deepcopy(entry.value)

    def put(self, key, value):
        self.entries[key] = CacheEntry(self.clock() + self.ttl, deepcopy(value))
        self.entries.move_to_end(key)
        while len(self.entries) > self.capacity:
            self.entries.popitem(last=False)


def select_memories(rows: list[dict], budget=6000) -> list[dict]:
    # SQL supplies relevance order; retain a bounded set, render in stable ID order
    # to avoid gratuitous prefix changes between otherwise identical requests.
    selected, seen, used = [], set(), 0
    for row in rows:
        key = fingerprint(row['content'].strip().casefold())
        if key in seen:
            continue
        # Bound serialized UTF-8 too: escaping untrusted delimiters and non-ASCII
        # text must not silently multiply the injected context budget.
        encoded = json.dumps(row['content'], ensure_ascii=False).replace('<', '\\u003c').replace('>', '\\u003e')
        size = len(encoded.encode('utf-8')) + 80
        if used + size > budget:
            continue
        seen.add(key)
        used += size
        selected.append(row)
        if len(selected) >= 12:
            break
    return sorted(selected, key=lambda item: str(item['id']))
