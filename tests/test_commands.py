import pytest
from unittest.mock import AsyncMock, MagicMock

import discord
from discord.ext import commands

from src.commands import setup_commands

# Fixtures
@pytest.fixture
def bot():
    # Create a bot instance without connecting to Discord
    intents = discord.Intents.default()
    bot = commands.Bot(command_prefix='!', intents=intents)
    return bot

@pytest.fixture
def interaction():
    # Create a mock interaction with necessary attributes
    interc = MagicMock()
    interc.guild_id = 123
    interc.guild = MagicMock()
    interc.guild.id = 123
    interc.guild.fetch_scheduled_events = AsyncMock(return_value=[])
    interc.response = MagicMock()
    interc.response.send_message = AsyncMock()
    interc.response.defer = AsyncMock()
    interc.followup = MagicMock()
    interc.followup.send = AsyncMock()
    interc.user = MagicMock()
    interc.user.__str__ = lambda self: "TestUser"
    return interc

@pytest.fixture
def settings():
    # In-memory settings store
    return {}

@pytest.fixture
def save_settings():
    calls = []
    def _save():
        calls.append(True)
    _save.was_called = calls
    return _save

# Tests for setup_team
@pytest.mark.asyncio
async def test_setup_team_new(bot, interaction, settings, save_settings):
    setup_commands(bot, settings, save_settings)
    cmd = bot.tree.get_command('setup_team')
    await cmd.callback(interaction, team='newteam')
    # Verify settings updated and save called
    assert 'newteam' in settings[str(interaction.guild_id)]['teams']
    assert save_settings.was_called
    interaction.response.send_message.assert_awaited_with(
        "✅ Team `newteam` added.", ephemeral=True
    )

@pytest.mark.asyncio
async def test_setup_team_duplicate(bot, interaction, settings, save_settings):
    settings[str(interaction.guild_id)] = {'teams': ['dup']}
    setup_commands(bot, settings, save_settings)
    cmd = bot.tree.get_command('setup_team')
    await cmd.callback(interaction, team='dup')
    interaction.response.send_message.assert_awaited_with(
        "⚠️ Team `dup` is already registered.", ephemeral=True
    )

# Tests for remove_team
@pytest.mark.asyncio
async def test_remove_team_not_registered(bot, interaction, settings, save_settings):
    setup_commands(bot, settings, save_settings)
    cmd = bot.tree.get_command('remove_team')
    await cmd.callback(interaction, team='noexist')
    interaction.response.send_message.assert_awaited_with(
        "⚠️ Team `noexist` is not registered.", ephemeral=True
    )

@pytest.mark.asyncio
async def test_remove_team_registered_no_events(monkeypatch, bot, interaction, settings, save_settings):
    # Prepare settings with one team
    settings[str(interaction.guild_id)] = {'teams': ['team1']}

    # Dummy HTTP session and response to simulate no HTTP data
    class DummyResponse:
        def __init__(self):
            self.status = 404
            self.content = []

        async def __aenter__(self): return self
        async def __aexit__(self, exc_type, exc, tb): pass

    class DummySession:
        async def __aenter__(self): return self
        async def __aexit__(self, exc_type, exc, tb): pass
        def get(self, url): return DummyResponse()

    # Patch aiohttp.ClientSession
    monkeypatch.setattr('src.commands.aiohttp.ClientSession', DummySession)

    setup_commands(bot, settings, save_settings)
    cmd = bot.tree.get_command('remove_team')
    await cmd.callback(interaction, team='team1')

    # Should defer then followup with zero deletions
    interaction.response.defer.assert_awaited()
    interaction.followup.send.assert_awaited_with(
        "🗑️ Team `team1` removed. Deleted 0 associated event(s).", ephemeral=True
    )

# Tests for list_teams
@pytest.mark.asyncio
async def test_list_teams_empty(bot, interaction, settings, save_settings):
    setup_commands(bot, settings, save_settings)
    cmd = bot.tree.get_command('list_teams')
    await cmd.callback(interaction)
    interaction.response.send_message.assert_awaited_with(
        "ℹ️ No teams registered.", ephemeral=True
    )

@pytest.mark.asyncio
async def test_list_teams_nonempty(bot, interaction, settings, save_settings):
    settings[str(interaction.guild_id)] = {'teams': ['a', 'b']}
    setup_commands(bot, settings, save_settings)
    cmd = bot.tree.get_command('list_teams')
    await cmd.callback(interaction)
    interaction.response.send_message.assert_awaited_with(
        "📋 Registered teams:\n- a\n- b", ephemeral=True
    )

# Tests for auto_sync command
@pytest.mark.asyncio
async def test_auto_sync_toggle(bot, interaction, settings, save_settings):
    setup_commands(bot, settings, save_settings)
    cmd = bot.tree.get_command('auto_sync')
    # Enable auto sync
    await cmd.callback(interaction, enable=True)
    gid = str(interaction.guild_id)
    assert settings[gid]['auto_sync'] is True
    interaction.response.send_message.assert_awaited_with(
        "🔄 Scheduled sync has been enabled for this server.", ephemeral=True
    )
    # Disable auto sync
    settings.clear()
    save_settings.was_called.clear()
    await cmd.callback(interaction, enable=False)
    assert settings[gid]['auto_sync'] is False
    interaction.response.send_message.assert_awaited_with(
        "🔄 Scheduled sync has been disabled for this server.", ephemeral=True
    )

# Tests for sync and sync_verbose commands
@pytest.mark.asyncio
async def test_sync_cmd_not_registered(bot, interaction, settings, save_settings):
    setup_commands(bot, settings, save_settings)
    cmd = bot.tree.get_command('sync')
    await cmd.callback(interaction, team='noexist')
    interaction.response.defer.assert_awaited()
    interaction.followup.send.assert_awaited_with(
        "⚠️ Team `noexist` is not registered.", ephemeral=True
    )

@pytest.mark.asyncio
async def test_sync_cmd_no_teams(bot, interaction, settings, save_settings):
    setup_commands(bot, settings, save_settings)
    cmd = bot.tree.get_command('sync')
    await cmd.callback(interaction)
    interaction.response.defer.assert_awaited()
    interaction.followup.send.assert_awaited_with(
        "ℹ️ No teams registered.", ephemeral=True
    )

@pytest.mark.asyncio
async def test_sync_verbose_cmd_no_teams(bot, interaction, settings, save_settings):
    setup_commands(bot, settings, save_settings)
    cmd = bot.tree.get_command('sync_verbose')
    await cmd.callback(interaction)
    interaction.response.defer.assert_awaited()
    interaction.followup.send.assert_awaited_with(
        "ℹ️ No teams registered.", ephemeral=True
    )

# Tests for prefix sync commands
@pytest.mark.asyncio
async def test_sync_prefix_no_events(bot, settings, save_settings):
    # Register commands
    setup_commands(bot, settings, save_settings)
    cmd = bot.get_command('sync')
    # Prepare context
    ctx = MagicMock()
    ctx.guild = MagicMock()
    ctx.guild.id = 123
    ctx.send = AsyncMock()
    settings[str(ctx.guild.id)] = {'teams': []}
    # Call prefix sync
    await cmd.callback(ctx)
    ctx.send.assert_awaited_with("ℹ️ No new or updated events.")

@pytest.mark.asyncio
async def test_sync_verbose_prefix_no_events(bot, settings, save_settings):
    # Register commands
    setup_commands(bot, settings, save_settings)
    cmd = bot.get_command('sync_verbose')
    # Prepare context
    ctx = MagicMock()
    ctx.guild = MagicMock()
    ctx.guild.id = 123
    ctx.send = AsyncMock()
    settings[str(ctx.guild.id)] = {'teams': []}
    # Call prefix verbose sync
    await cmd.callback(ctx)
    ctx.send.assert_awaited_with("ℹ️ No new or updated events.")
