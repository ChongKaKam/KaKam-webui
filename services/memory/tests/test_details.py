import asyncio

from open_webui.kakam.memory import details
from open_webui.kakam.memory.composition import split_context


def test_sections_follow_actual_request_and_remove_memory_from_system():
    buckets = split_context(
        [
            {'role': 'system', 'content': 'rules\nMEMORY'},
            {'role': 'user', 'content': 'older'},
            {'role': 'tool', 'content': 'tool text'},
            {
                'role': 'user',
                'content': [{'type': 'text', 'text': 'latest'}, {'type': 'image_url', 'image_url': 'private'}],
            },
        ],
        'MEMORY',
        'model rules',
        label_roles=True,
    )
    assert buckets['long_term'] == ['MEMORY']
    assert buckets['system'] == ['[system]\nrules\n', 'model rules']
    assert buckets['session'] == ['[user]\nolder', '[tool]\ntool text']
    assert buckets['current'] == ['[user]\nlatest']


def test_cache_is_owner_scoped_bounded_and_expires(monkeypatch):
    monkeypatch.setattr(details, '_snapshots', details.OrderedDict())
    monkeypatch.setattr(details, 'MAX_ENTRIES', 2)
    clock = [100.0]
    monkeypatch.setattr(details.time, 'monotonic', lambda: clock[0])
    buckets = {'current': ['x' * 20000]}
    first = details.remember('alice', 'chat', 'msg', buckets)
    assert details.lookup(first, 'bob') is None
    result = details.lookup(first, 'alice')
    assert len(result['details'].sections[0].content) == 16000
    assert result['details'].sections[0].truncated
    result['details'].sections[0].content = 'mutated'
    assert details.lookup(first, 'alice')['details'].sections[0].content != 'mutated'
    second = details.remember('alice', 'chat', 'msg2', buckets)
    details.remember('alice', 'chat', 'msg3', buckets)
    assert details.lookup(first, 'alice') is None
    clock[0] += 901
    assert details.lookup(second, 'alice') is None
    assert len(details._snapshots) == 0


def test_idle_expiry_removes_text_without_next_request(monkeypatch):
    monkeypatch.setattr(details, '_snapshots', details.OrderedDict())
    monkeypatch.setattr(details, 'TTL_SECONDS', 0.01)

    async def check():
        key = details.remember('alice', 'chat', 'msg', {'current': ['private']})
        assert key in details._snapshots
        await asyncio.sleep(0.03)
        assert key not in details._snapshots

    asyncio.run(check())
