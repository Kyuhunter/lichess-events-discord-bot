import pytest
import json
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock

import src.sync as sync_mod

@pytest.mark.asyncio
async def test_sync_http_non200(monkeypatch):
    # Guild with permission
    guild = MagicMock()
    guild.id = 7
    member = MagicMock()
    member.guild_permissions = MagicMock(manage_events=True)
    guild.me = member
    guild.get_member.return_value = member
    guild.fetch_scheduled_events = AsyncMock(return_value=[])
    # Dummy response with non-200 status
    class DummyResp:
        def __init__(self):
            self.status = 404
            self.content = MagicMock()
        async def __aenter__(self): return self
        async def __aexit__(self, exc_type, exc, tb): pass
    class DummySession:
        async def __aenter__(self): return self
        async def __aexit__(self, exc_type, exc, tb): pass
        def get(self, url): return DummyResp()
    monkeypatch.setattr(sync_mod.aiohttp, 'ClientSession', DummySession)
    SETTINGS = {"7": {"teams": ["teamA"]}}
    created, updated, events = await sync_mod.sync_events_for_guild(guild, SETTINGS, None)
    assert (created, updated, events) == (0, 0, [])

@pytest.mark.asyncio
async def test_sync_invalid_and_past_tournament(monkeypatch):
    # Guild with permission
    guild = MagicMock()
    guild.id = 8
    member = MagicMock()
    member.guild_permissions = MagicMock(manage_events=True)
    guild.me = member
    guild.get_member.return_value = member
    guild.fetch_scheduled_events = AsyncMock(return_value=[])
    # Prepare raw lines: invalid JSON, past tournament, then empty
    past = datetime.now(timezone.utc) - timedelta(hours=2)
    past_ms = int(past.timestamp() * 1000)
    data_past = {"id": "old", "startsAt": past_ms, "finishesAt": past_ms + 3600000,
                 "minutes": 10, "clock": {"increment": 5}}
    lines = [b'invalid\n', json.dumps(data_past).encode() + b"\n", b""]
    class DummyResp:
        def __init__(self):
            self.status = 200
            self._lines = lines.copy()
            self.content = self
        async def __aenter__(self): return self
        async def __aexit__(self, exc_type, exc, tb): pass
        async def readline(self): return self._lines.pop(0)
    class DummySession:
        async def __aenter__(self): return self
        async def __aexit__(self, exc_type, exc, tb): pass
        def get(self, url): return DummyResp()
    monkeypatch.setattr(sync_mod.aiohttp, 'ClientSession', DummySession)
    SETTINGS = {"8": {"teams": ["teamB"]}}
    created, updated, events = await sync_mod.sync_events_for_guild(guild, SETTINGS, None)
    # Should skip invalid and past, so no events
    assert (created, updated, events) == (0, 0, [])
