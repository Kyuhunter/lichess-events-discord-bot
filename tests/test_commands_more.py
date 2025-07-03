import discord
from discord.ext import commands
from unittest.mock import AsyncMock, MagicMock
import pytest
import json

from src.commands import setup_commands

# Positive sync command tests
def setup_sync(monkeypatch):
    # Patch sync_events_for_guild to return sample data
    monkeypatch.setattr(
        'src.commands.sync_events_for_guild',
        AsyncMock(return_value=(2, 1, ['url1', 'url2', 'url3']))
    )

@pytest.mark.asyncio
async def test_sync_cmd_positive(bot, interaction, settings, save_settings, monkeypatch):
    # Register one team
    settings[str(interaction.guild_id)] = {'teams': ['team1']}
    setup_commands(bot, settings, save_settings)
    setup_sync(monkeypatch)

    cmd = bot.tree.get_command('sync')
    await cmd.callback(interaction)
    # response deferred
    interaction.response.defer.assert_awaited()
    # Should summarize creations and updates
    expected = "✅ 2 new events created, 🔄 1 events updated:\nurl1\nurl2\nurl3"
    interaction.followup.send.assert_awaited_with(expected, ephemeral=True)

@pytest.mark.asyncio
async def test_sync_verbose_cmd_positive(bot, interaction, settings, save_settings, monkeypatch):
    # Register one team
    settings[str(interaction.guild_id)] = {'teams': ['team1']}
    setup_commands(bot, settings, save_settings)
    # Patch for verbose
    monkeypatch.setattr(
        'src.commands.sync_events_for_guild',
        AsyncMock(return_value=(0, 2, ['u1', 'u2']))
    )

    cmd = bot.tree.get_command('sync_verbose')
    await cmd.callback(interaction)
    interaction.response.defer.assert_awaited()
    expected = "🔄 2 events updated:\nu1\nu2"
    interaction.followup.send.assert_awaited_with(expected, ephemeral=True)

@pytest.mark.asyncio
async def test_prefix_sync_positive(bot, settings, save_settings, monkeypatch):
    setup_commands(bot, settings, save_settings)
    settings['123'] = {'teams': ['t']}
    cmd = bot.get_command('sync')
    # Patch underlying sync
    monkeypatch.setattr(
        'src.commands.sync_events_for_guild',
        AsyncMock(return_value=(1, 0, ['u']))
    )
    # Prepare context using MagicMock
    ctx = MagicMock()
    ctx.guild = MagicMock()
    ctx.guild.id = 123
    ctx.send = AsyncMock()
    await cmd.callback(ctx)
    ctx.send.assert_awaited_with("✅ 1 new events created:\nu")

@pytest.mark.asyncio
async def test_prefix_sync_verbose_positive(bot, settings, save_settings, monkeypatch):
    setup_commands(bot, settings, save_settings)
    settings['456'] = {'teams': ['x']}
    cmd = bot.get_command('sync_verbose')
    monkeypatch.setattr(
        'src.commands.sync_events_for_guild',
        AsyncMock(return_value=(0, 1, ['v']))
    )
    ctx = MagicMock()
    ctx.guild = MagicMock()
    ctx.guild.id = 456
    ctx.send = AsyncMock()
    await cmd.callback(ctx)
    ctx.send.assert_awaited_with("🔄 1 events updated:\nv")

# Tests for remove_team deleting events successfully
@pytest.mark.asyncio
async def test_remove_team_deletes_events(monkeypatch, bot, interaction, settings, save_settings):
    # Setup a registered team
    settings[str(interaction.guild_id)] = {'teams': ['teamX']}
    # Dummy response with one tournament ID
    data = {'id': 'xyz'}
    raw = json.dumps(data).encode() + b"\n"
    class DummyResp:
        def __init__(self):
            self.status = 200
            self._lines = [raw]
            self.content = self
        async def __aenter__(self): return self
        async def __aexit__(self, exc_type, exc, tb): pass
        async def readline(self):
            return self._lines.pop(0) if self._lines else b""
        def __aiter__(self):
            return self
        async def __anext__(self):
            if self._lines:
                return self._lines.pop(0)
            raise StopAsyncIteration
    class DummySession:
        async def __aenter__(self): return self
        async def __aexit__(self, exc_type, exc, tb): pass
        def get(self, url): return DummyResp()
    # Patch aiohttp.ClientSession
    import src.commands as cmd_mod
    monkeypatch.setattr(cmd_mod.aiohttp, 'ClientSession', DummySession)
    # Mock fetch_scheduled_events to return one event
    ev = MagicMock()
    ev.location = 'https://lichess.org/tournament/xyz'
    ev.delete = AsyncMock()
    interaction.guild.fetch_scheduled_events = AsyncMock(return_value=[ev])
    # Run command
    setup_commands(bot, settings, save_settings)
    cmd = bot.tree.get_command('remove_team')
    await cmd.callback(interaction, team='teamX')
    # Check deletion and messages
    ev.delete.assert_awaited()
    interaction.followup.send.assert_awaited_with(
        "🗑️ Team `teamX` removed. Deleted 1 associated event(s).", ephemeral=True
    )

# Tests for notification channel logging
@pytest.mark.asyncio
async def test_setup_team_logs_to_channel(bot, interaction, settings, save_settings, monkeypatch):
    # Setup commands first - important to do this before monkeypatching
    setup_commands(bot, settings, save_settings)
    
    # Now monkeypatch TextChannel for the test
    import discord
    original_TextChannel = discord.TextChannel
    monkeypatch.setattr(discord, 'TextChannel', MagicMock)
    
    try:
        # Prepare a notification channel
        channel = MagicMock()
        channel.send = AsyncMock()
        perms = MagicMock(send_messages=True)
        channel.permissions_for.return_value = perms
        interaction.guild.get_channel.return_value = channel
        
        # Prepare settings
        settings[str(interaction.guild_id)] = {'notification_channel': 99, 'teams': []}
        
        # Execute the command
        cmd = bot.tree.get_command('setup_team')
        await cmd.callback(interaction, team='chanteam')
        
        # Assert notification was sent
        channel.send.assert_awaited_with('Team `chanteam` has been registered.')
    finally:
        # Restore the original TextChannel class
        monkeypatch.setattr(discord, 'TextChannel', original_TextChannel)

@pytest.mark.asyncio
async def test_auto_sync_logs_to_channel(bot, interaction, settings, save_settings, monkeypatch):
    # Setup commands first - important to do this before monkeypatching
    setup_commands(bot, settings, save_settings)
    
    # Now monkeypatch TextChannel for the test
    import discord
    original_TextChannel = discord.TextChannel
    monkeypatch.setattr(discord, 'TextChannel', MagicMock)
    
    try:
        # Prepare a notification channel
        channel = MagicMock()
        channel.send = AsyncMock()
        perms = MagicMock(send_messages=True)
        channel.permissions_for.return_value = perms
        interaction.guild.get_channel.return_value = channel
        
        # Prepare settings
        settings[str(interaction.guild_id)] = {'notification_channel': 123}
        
        # Execute the command
        cmd = bot.tree.get_command('auto_sync')
        await cmd.callback(interaction, enable=False)
        
        # Assert notification was sent
        channel.send.assert_awaited_with(f'Scheduled sync disabled by user {interaction.user}')
    finally:
        # Restore the original TextChannel class
        monkeypatch.setattr(discord, 'TextChannel', original_TextChannel)
