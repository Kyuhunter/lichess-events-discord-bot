import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock

import json
from datetime import datetime, timezone, timedelta

import src.sync as sync_mod

@pytest.fixture
def bot():
    return None  # bot not used in these tests

@pytest.mark.asyncio
async def test_sync_create_event(monkeypatch):
    # Prepare guild
    guild = MagicMock()
    guild.id = 5
    member = MagicMock()
    member.guild_permissions = MagicMock(manage_events=True)
    guild.me = member
    guild.get_member.return_value = member
    guild.fetch_scheduled_events = AsyncMock(return_value=[])
    # Prepare dummy event data (future tournament)
    future = datetime.now(timezone.utc) + timedelta(hours=1)
    future_ms = int(future.timestamp() * 1000)
    data = {"id": "t1", "startsAt": future_ms, "finishesAt": future_ms + 3600000,
            "minutes": 5, "clock": {"increment": 2}, "fullName": "Test Arena"}
    raw_line = json.dumps(data).encode() + b"\n"
    class DummyResp:
        def __init__(self):
            self.status = 200
            self._lines = [raw_line, b""]
            self.content = self
        async def __aenter__(self): return self
        async def __aexit__(self, exc_type, exc, tb): pass
        async def readline(self):
            return self._lines.pop(0)
    class DummySession:
        async def __aenter__(self): return self
        async def __aexit__(self, exc_type, exc, tb): pass
        def get(self, url): return DummyResp()
    monkeypatch.setattr(sync_mod.aiohttp, 'ClientSession', DummySession)
    # Capture created events
    guild.create_scheduled_event = AsyncMock()
    # Stub log_to_notification_channel to no-op
    monkeypatch.setattr(sync_mod, 'log_to_notification_channel', AsyncMock())
    SETTINGS = {"5": {"teams": ["team1"]}}
    created, updated, events = await sync_mod.sync_events_for_guild(guild, SETTINGS, None)
    assert created == 1
    assert updated == 0
    assert events == ["https://lichess.org/tournament/t1"]
    guild.create_scheduled_event.assert_awaited()

@pytest.mark.asyncio
async def test_sync_update_event(monkeypatch):
    # Prepare guild
    guild = MagicMock()
    guild.id = 6
    member = MagicMock()
    member.guild_permissions = MagicMock(manage_events=True)
    guild.me = member
    guild.get_member.return_value = member
    # Existing event stub
    ev = MagicMock()
    ev.location = "https://lichess.org/tournament/t2"
    # Set outdated attributes
    ev.name = "Old Name"
    ev.start_time = datetime.now(timezone.utc)
    ev.end_time = ev.start_time + timedelta(hours=1)
    ev.description = "old"
    guild.fetch_scheduled_events = AsyncMock(return_value=[ev])
    # Prepare updated tournament data
    future = datetime.now(timezone.utc) + timedelta(hours=2)
    future_ms = int(future.timestamp() * 1000)
    data = {"id": "t2", "startsAt": future_ms, "finishesAt": future_ms + 3600000,
            "minutes": 3, "clock": {"increment": 1}, "fullName": "New Arena"}
    raw_line = json.dumps(data).encode() + b"\n"
    class DummyResp:
        def __init__(self):
            self.status = 200
            self._lines = [raw_line, b""]
            self.content = self
        async def __aenter__(self): return self
        async def __aexit__(self, exc_type, exc, tb): pass
        async def readline(self):
            return self._lines.pop(0)
    class DummySession:
        async def __aenter__(self): return self
        async def __aexit__(self, exc_type, exc, tb): pass
        def get(self, url): return DummyResp()
    monkeypatch.setattr(sync_mod.aiohttp, 'ClientSession', DummySession)
    # Capture edits
    ev.edit = AsyncMock()
    # Stub log_to_notification_channel
    monkeypatch.setattr(sync_mod, 'log_to_notification_channel', AsyncMock())
    SETTINGS = {"6": {"teams": ["team1"]}}
    created, updated, events = await sync_mod.sync_events_for_guild(guild, SETTINGS, None, verbose=True)
    assert created == 0
    assert updated == 1
    assert events == ["https://lichess.org/tournament/t2"]
    ev.edit.assert_awaited()
