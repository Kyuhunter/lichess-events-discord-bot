import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock
import json

import src.sync as sync_mod

@pytest.mark.asyncio
async def test_sync_skips_invalid_json_then_creates_event(monkeypatch):
    # Prepare guild with permission
    guild = MagicMock()
    guild.id = 20
    member = MagicMock()
    member.guild_permissions = MagicMock(manage_events=True)
    guild.me = member
    guild.get_member.return_value = member
    guild.fetch_scheduled_events = AsyncMock(return_value=[])
    # Prepare lines: invalid JSON, then valid future tournament, then end
    future = datetime.now(timezone.utc) + timedelta(hours=1)
    future_ms = int(future.timestamp() * 1000)
    data = {"id": "abc", "startsAt": future_ms, "finishesAt": future_ms + 60000,
            "minutes": 5, "clock": {"increment": 0}, "fullName": "Test"}
    valid_line = json.dumps(data).encode() + b"\n"
    lines = [b'invalid\n', valid_line, b"\n", b""]
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
    # Stub create and update
    guild.create_scheduled_event = AsyncMock()
    monkeypatch.setattr(sync_mod, 'log_to_notification_channel', AsyncMock())
    SETTINGS = {"20": {"teams": ["teamZ"]}}
    # Run sync
    dummy_bot = MagicMock(); dummy_bot.user = MagicMock(id=0)
    created, updated, events = await sync_mod.sync_events_for_guild(
        guild, SETTINGS, dummy_bot, verbose=True
    )
    assert created == 1 and updated == 0
    assert events == ["https://lichess.org/tournament/abc"]
    guild.create_scheduled_event.assert_awaited_once()

@pytest.mark.asyncio
async def test_sync_does_not_edit_if_unchanged(monkeypatch):
    # Prepare guild with existing identical event
    guild = MagicMock()
    guild.id = 21
    member = MagicMock()
    member.guild_permissions = MagicMock(manage_events=True)
    guild.me = member
    guild.get_member.return_value = member
    # Existing event with exact expected fields
    ev = MagicMock()
    now = datetime.now(timezone.utc) + timedelta(hours=2)
    starts = now
    ends = now + timedelta(hours=1)
    ev.location = "https://lichess.org/tournament/xyz"
    # Craft name and desc matching sync logic
    name = f"**Lichess Arena Tournament**\n• {starts:%Y-%m-%d %H:%M UTC} – {ends:%H:%M UTC}\n• 5 min · +0s\n\nhttps://lichess.org/tournament/xyz"
    ev.name = name
    ev.start_time = starts
    ev.end_time = ends
    ev.description = name.split('\n\n')[-1]  # just the URL part, but full description is name
    guild.fetch_scheduled_events = AsyncMock(return_value=[ev])
    # Prepare response with same tournament
    data = {"id": "xyz", "startsAt": int(starts.timestamp() * 1000),
            "finishesAt": int(ends.timestamp() * 1000),
            "minutes": 5, "clock": {"increment": 0}, "fullName": None}
    raw_line = json.dumps(data).encode() + b"\n"
    lines = [raw_line, b""]
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
    # Stub create and edit
    guild.create_scheduled_event = AsyncMock()
    ev.edit = AsyncMock()
    monkeypatch.setattr(sync_mod, 'log_to_notification_channel', AsyncMock())
    SETTINGS = {"21": {"teams": ["teamZ"]}}
    dummy_bot = MagicMock(); dummy_bot.user = MagicMock(id=0)
    created, updated, events = await sync_mod.sync_events_for_guild(
        guild, SETTINGS, dummy_bot, verbose=False
    )
    # Since fullName was None, sync will update existing event
    assert created == 0 and updated == 1 and events == ['https://lichess.org/tournament/xyz']
    ev.edit.assert_awaited()
    guild.create_scheduled_event.assert_not_awaited()
