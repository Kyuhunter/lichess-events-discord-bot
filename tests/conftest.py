import sys
import os

# Ensure project root is on sys.path so imports like 'src.*' work
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

# Fixture definitions for all tests
import pytest
import discord
from discord.ext import commands
from unittest.mock import AsyncMock, MagicMock

@pytest.fixture
def bot():
    # Create a bot instance for test modules
    intents = discord.Intents.default()
    bot = commands.Bot(command_prefix='!', intents=intents)
    return bot

@pytest.fixture
def interaction():
    # Mock interaction for slash commands
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
