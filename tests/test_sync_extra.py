import pytest
import json
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock
import discord

import src.sync as sync_mod

@pytest.mark.asyncio
async def test_log_notification_no_channel():
    guild = MagicMock()
    guild.id = 100
    # No settings entry
    await sync_mod.log_to_notification_channel(guild, {}, 'msg')
    # Should not raise

@pytest.mark.asyncio
async def test_log_notification_no_permissions(monkeypatch):
    guild = MagicMock()
    guild.id = 101
    channel = MagicMock()
    # Patch TextChannel to match channel type
    monkeypatch.setattr(sync_mod.discord, 'TextChannel', MagicMock)
    guild.get_channel.return_value = channel
    # Permissions false
    perms = MagicMock(send_messages=False)
    channel.permissions_for.return_value = perms
    await sync_mod.log_to_notification_channel(guild, {'101': {'notification_channel': 1}}, 'hi')
    # send should not be called
    assert not channel.send.called

@pytest.mark.asyncio
async def test_sync_with_team_slug(monkeypatch):
    # Setup guild
    guild = MagicMock()
    guild.id = 9
    member = MagicMock()
    member.guild_permissions = MagicMock(manage_events=True)
    guild.me = member
    guild.get_member.return_value = member
    guild.fetch_scheduled_events = AsyncMock(return_value=[])
    # Prepare future tournament
    future = datetime.now(timezone.utc) + timedelta(hours=1)
    future_ms = int(future.timestamp() * 1000)
    data = {'id': 'tz1', 'startsAt': future_ms, 'finishesAt': future_ms + 3600000,
            'minutes': 10, 'clock': {'increment': 3}}
    raw_line = json.dumps(data).encode() + b"\n"
    class DummyResp:
        def __init__(self):
            self.status = 200
            self._lines = [raw_line]
            self.content = self
        async def __aenter__(self): return self
        async def __aexit__(self, exc_type, exc, tb): pass
        async def readline(self): return self._lines.pop(0) if self._lines else b""
    class DummySession:
        async def __aenter__(self): return self
        async def __aexit__(self, exc_type, exc, tb): pass
        def get(self, url): return DummyResp()
    monkeypatch.setattr(sync_mod.aiohttp, 'ClientSession', DummySession)
    # Stub create_scheduled_event and logging to avoid errors
    guild.create_scheduled_event = AsyncMock()
    monkeypatch.setattr(sync_mod, 'log_to_notification_channel', AsyncMock())
    # Use a dummy bot with user id to avoid AttributeError
    dummy_bot = MagicMock(); dummy_bot.user = MagicMock(id=0)
    created, updated, events = await sync_mod.sync_events_for_guild(
        guild, {}, dummy_bot, team_slug='teamZ'
    )
    assert created == 1 and updated == 0 and events == ['https://lichess.org/tournament/tz1']

@pytest.mark.asyncio
async def test_sync_fetch_forbidden(monkeypatch):
    guild = MagicMock()
    guild.id = 11
    member = MagicMock()
    member.guild_permissions = MagicMock(manage_events=True)
    guild.me = member
    guild.get_member.return_value = member
    # fetch_scheduled_events raises Forbidden
    # Raise Forbidden with a dummy response object having a status
    resp = MagicMock()
    resp.status = 403
    guild.fetch_scheduled_events = AsyncMock(side_effect=discord.Forbidden(resp, None))
    SETTINGS = {'11': {'teams': ['teamA']}}
    # Pass dummy bot to satisfy code path
    dummy_bot = MagicMock(); dummy_bot.user = MagicMock(id=1)
    created, updated, events = await sync_mod.sync_events_for_guild(guild, SETTINGS, dummy_bot)
    assert (created, updated, events) == (0, 0, [])

@pytest.mark.asyncio
async def test_sync_missing_manage_events_verbose(capfd):
    guild = MagicMock(name='GUILD')
    guild.id = 12
    # No member guild_permissions
    guild.me = None
    guild.get_member.return_value = None
    SETTINGS = {'12': {'teams': ['teamB']}}
    # Use dummy bot to avoid AttributeError
    dummy_bot = MagicMock(); dummy_bot.user = MagicMock(id=2)
    # Capture print for verbose mode
    created, updated, events = await sync_mod.sync_events_for_guild(
        guild, SETTINGS, dummy_bot, verbose=True
    )
    captured = capfd.readouterr()
    assert 'Missing permission' in captured.out
    assert (created, updated, events) == (0, 0, [])
