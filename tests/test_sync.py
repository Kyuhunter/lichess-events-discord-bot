import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock

import discord
from discord.ext import commands

from src.sync import sync_events_for_guild, log_to_notification_channel

# Fixture for a dummy bot
@pytest.fixture
def bot():
    intents = discord.Intents.default()
    return commands.Bot(command_prefix="!", intents=intents)

@pytest.mark.asyncio
async def test_sync_no_teams(bot):
    guild = MagicMock()
    guild.id = 1
    # No teams in SETTINGS
    created, updated, events = await sync_events_for_guild(guild, {}, bot)
    assert created == 0 and updated == 0 and events == []

@pytest.mark.asyncio
async def test_sync_missing_permission(bot):
    guild = MagicMock()
    guild.id = 2
    # Member without manage_events
    member = MagicMock()
    member.guild_permissions = MagicMock(manage_events=False)
    guild.me = member
    guild.get_member.return_value = member
    guild.fetch_scheduled_events = AsyncMock()
    SETTINGS = {"2": {"teams": ["team1"]}}
    created, updated, events = await sync_events_for_guild(guild, SETTINGS, bot)
    assert created == 0 and updated == 0 and events == []

@pytest.mark.asyncio
async def test_sync_http_error(monkeypatch, bot):
    guild = MagicMock()
    guild.id = 3
    # Member with permission
    member = MagicMock()
    member.guild_permissions = MagicMock(manage_events=True)
    guild.me = member
    guild.get_member.return_value = member
    guild.fetch_scheduled_events = AsyncMock(return_value=[])
    # Dummy HTTP classes
    class DummyResponse:
        def __init__(self):
            self.status = 500
            self.content = MagicMock()
        async def __aenter__(self): return self
        async def __aexit__(self, *_): pass
    class DummySession:
        async def __aenter__(self): return self
        async def __aexit__(self, *_): pass
        def get(self, url): return DummyResponse()
    monkeypatch.setattr('src.sync.aiohttp.ClientSession', DummySession)
    SETTINGS = {"3": {"teams": ["team1"]}}
    created, updated, events = await sync_events_for_guild(guild, SETTINGS, bot)
    assert created == 0 and updated == 0 and events == []

@pytest.mark.asyncio
async def test_log_to_notification_channel(monkeypatch):
    guild = MagicMock()
    guild.id = 4
    # No channel configured
    await log_to_notification_channel(guild, {}, "hi")
    # Configure a fake channel
    dummy = MagicMock()
    # Make it pass isinstance check by patching TextChannel
    monkeypatch.setattr('src.sync.discord.TextChannel', type(dummy))
    # Stub get_channel and permissions
    guild.get_channel.return_value = dummy
    dummy.permissions_for.return_value = MagicMock(send_messages=True)
    dummy.send = AsyncMock()
    SETTINGS = {"4": {"notification_channel": 999}}
    await log_to_notification_channel(guild, SETTINGS, "hello")
    dummy.send.assert_awaited_with("hello")
