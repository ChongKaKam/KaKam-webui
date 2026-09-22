"""Policies propose decisions; the Manager retains authorization and persistence."""

from dataclasses import dataclass, field
from typing import Protocol

from .domain import POLICIES, select_memories


@dataclass(frozen=True)
class PolicyTask:
    operation: str
    query: str
    days: int
    automatic_recall: bool
    selections: dict
    budget: int = 6000
    estimated_tokens: int = 0
    settings: dict = field(default_factory=dict)


class PolicyTools(Protocol):
    async def search(self, query: str, days: int) -> list[dict]: ...
    async def read(self, memory_id: str) -> dict | None: ...


class DefaultPolicy:
    manifest = {**POLICIES[0], 'capabilities': ['recall', 'scope', 'compact', 'propose']}

    async def run(self, task: PolicyTask, tools: PolicyTools):
        if task.operation == 'compact_context':
            return {
                'compress': task.estimated_tokens >= task.settings['token_budget'],
                'keep_messages': task.settings['keep_messages'],
            }
        rows = []
        for memory_id, mode in task.selections.items():
            if mode == 'prefer':
                row = await tools.read(memory_id)
                if row:
                    rows.append(row)
        if task.automatic_recall:
            rows.extend(await tools.search(task.query, task.days))
        candidates = [r for r in rows if task.selections.get(str(r['id'])) != 'exclude']
        selected = select_memories(candidates, budget=task.budget)
        return {'selected_ids': [str(r['id']) for r in selected]}


POLICY_REGISTRY = {'default': DefaultPolicy()}
