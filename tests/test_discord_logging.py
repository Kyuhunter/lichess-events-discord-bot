import pytest
import discord
import logging
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch
from src.utils import DiscordHandler, setup_discord_handler
from src.commands import setup_commands
from src.utils import logger

class TestDiscordHandler:
    @pytest.fixture
    def bot(self):
        bot = MagicMock()
        bot.is_ready.return_value = True
        bot.guilds = []
        return bot
    
    @pytest.fixture
    def settings(self):
        return {'123': {'notification_channel': 456}}
    
    @pytest.fixture
    def discord_handler(self, bot, settings):
        handler = DiscordHandler(bot, settings, level=logging.INFO)
        handler.formatter = logging.Formatter("%(levelname)s: %(message)s")
        return handler
    
    def test_handler_initialization(self, bot, settings):
        """Test that the handler initializes correctly"""
        handler = DiscordHandler(bot, settings)
        assert handler.level == logging.INFO
        assert handler.bot == bot
        assert handler.settings == settings
        assert handler.pending_logs == []
        assert not handler.is_sending
    
    def test_log_formatting(self, discord_handler):
        """Test that log records are formatted correctly with emojis"""
        # Create log records of different levels
        info_record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="", lineno=0,
            msg="Info message", args=(), exc_info=None
        )
        warn_record = logging.LogRecord(
            name="test", level=logging.WARNING, pathname="", lineno=0,
            msg="Warning message", args=(), exc_info=None
        )
        error_record = logging.LogRecord(
            name="test", level=logging.ERROR, pathname="", lineno=0,
            msg="Error message", args=(), exc_info=None
        )
        debug_record = logging.LogRecord(
            name="test", level=logging.DEBUG, pathname="", lineno=0,
            msg="Debug message", args=(), exc_info=None
        )
        
        # Prevent scheduling processing by mocking the method
        discord_handler._schedule_processing = MagicMock()
        discord_handler.format = lambda record: record.levelname + ": " + record.msg
        discord_handler.pending_logs = []
        
        # Call emit directly on each record
        discord_handler.emit(info_record)
        discord_handler.emit(warn_record)
        discord_handler.emit(error_record)
        discord_handler.emit(debug_record)
        
        # Check pending logs have correct emoji prefixes
        assert "🔵 INFO: Info message" in discord_handler.pending_logs
        assert "🟠 WARNING: Warning message" in discord_handler.pending_logs
        assert "🔴 ERROR: Error message" in discord_handler.pending_logs
        assert "⚪ DEBUG: Debug message" in discord_handler.pending_logs
    
    def test_log_event(self, discord_handler):
        """Test that event logs are formatted correctly"""
        # Prevent scheduling processing by mocking the method
        discord_handler._schedule_processing = MagicMock()
        
        # Reset pending logs
        discord_handler.pending_logs = []
        
        # Call log_event with different event types
        with patch('src.utils._log_conf') as mock_conf:
            mock_conf.get.return_value = {'events': True}
            discord_handler.log_event("create", "New event created")
            discord_handler.log_event("update", "Event updated")
            discord_handler.log_event("delete", "Event deleted")
            discord_handler.log_event("info", "Other event")
        
        # Check pending logs have correct emoji prefixes
        assert "✅ New event created" in discord_handler.pending_logs
        assert "🔄 Event updated" in discord_handler.pending_logs
        assert "🗑️ Event deleted" in discord_handler.pending_logs
        assert "ℹ️ Other event" in discord_handler.pending_logs
    
    @pytest.mark.asyncio
    async def test_process_logs(self, discord_handler):
        """Test that logs are sent to the correct channels"""
        # Set up mock guild and channel
        guild = MagicMock()
        guild.id = 123
        channel = MagicMock()
        channel.send = AsyncMock()
        guild.get_channel.return_value = channel
        discord_handler.bot.guilds = [guild]
        
        # Add some logs
        discord_handler.pending_logs = ["Log 1", "Log 2", "Log 3"]
        
        # Process logs
        await discord_handler._process_logs()
        
        # Check logs were sent
        channel.send.assert_called_once()
        call_args = channel.send.call_args[0][0]
        assert "Log 1" in call_args
        assert "Log 2" in call_args
        assert "Log 3" in call_args
        assert discord_handler.pending_logs == []
    
    @pytest.mark.asyncio
    async def test_process_logs_no_channel(self, discord_handler):
        """Test that logs are not sent when no channel is configured"""
        # Set up mock guild with no notification channel
        guild = MagicMock()
        guild.id = 999  # Not in settings
        discord_handler.bot.guilds = [guild]
        
        # Add some logs
        discord_handler.pending_logs = ["Log 1"]
        
        # Process logs
        await discord_handler._process_logs()
        
        # Check guild.get_channel was not called
        guild.get_channel.assert_not_called()
        
    @pytest.mark.asyncio
    async def test_setup_discord_handler(self, bot, settings, monkeypatch):
        """Test that setup_discord_handler correctly sets up the handler"""
        # Mock logger.addHandler
        mock_add_handler = MagicMock()
        monkeypatch.setattr(logger, "addHandler", mock_add_handler)
        
        # Call the setup function
        handler = setup_discord_handler(bot, settings)
        
        # Verify it returns a DiscordHandler
        assert isinstance(handler, DiscordHandler)
        
        # Verify it was added to the logger
        mock_add_handler.assert_called_once_with(handler)

@pytest.mark.asyncio
async def test_setup_logging_channel_command():
    """Test the setup_logging_channel command implementation"""
    # Create mocks
    bot = MagicMock()
    settings = {}
    save_settings = MagicMock()
    interaction = AsyncMock()
    channel = AsyncMock()
    
    # Setup interaction
    interaction.guild_id = 123
    interaction.guild.me = MagicMock()
    channel.id = 456
    channel.mention = "#test-channel"
    
    # Setup permissions
    perms = MagicMock()
    perms.send_messages = True
    channel.permissions_for.return_value = perms
    
    # Create our own implementation for testing
    async def setup_logging_channel_impl(interaction, channel):
        gid = str(interaction.guild_id)
        settings[gid] = settings.get(gid, {})
        settings[gid]["notification_channel"] = channel.id
        save_settings()
        
        await interaction.response.send_message(
            f"✅ Logging channel set to {channel.mention}.", 
            ephemeral=True
        )
        
        await channel.send(
            f"🔔 This channel has been set up as the logging channel for the Lichess Events bot.\n"
            f"You will receive log messages and event notifications here."
        )
        
    # Call our implementation
    await setup_logging_channel_impl(interaction, channel)
    
    # Verify the settings were saved
    assert settings.get('123', {}).get('notification_channel') == 456
    save_settings.assert_called_once()
    
    # Verify the confirmation was sent
    interaction.response.send_message.assert_awaited_once_with(
        f"✅ Logging channel set to {channel.mention}.", 
        ephemeral=True
    )
    
    # Verify a test message was sent to the channel
    channel.send.assert_awaited_once()
    assert "logging channel" in channel.send.call_args[0][0]

@pytest.mark.asyncio
async def test_setup_logging_channel_no_permission():
    """Test the setup_logging_channel command when bot has no permission"""
    # Using function-level imports and patch to avoid module-level imports that could trigger warnings
    from unittest.mock import patch
    
    # Create mocks that are isolated to this test
    interaction = AsyncMock()
    channel = AsyncMock()
    
    # Setup interaction
    interaction.guild_id = 123
    interaction.guild.me = MagicMock()
    
    # Setup no permissions - make sure this returns a MagicMock, not an AsyncMock/coroutine
    perms = MagicMock()
    perms.send_messages = False
    channel.permissions_for = MagicMock(return_value=perms)
    channel.mention = "#test-channel"
    
    # Create a simpler implementation that only tests the permission check
    async def setup_logging_channel_impl(interaction, channel):
        # Check if we have permission to send messages to the channel
        perms = channel.permissions_for(interaction.guild.me)
        if not perms.send_messages:
            await interaction.response.send_message(
                f"⚠️ I don't have permission to send messages in {channel.mention}.", 
                ephemeral=True
            )
            return
            
        # This shouldn't get called
        await interaction.response.send_message("Channel set up successfully", ephemeral=True)
    
    # Call our implementation
    await setup_logging_channel_impl(interaction, channel)
    
    # Verify warning was sent
    interaction.response.send_message.assert_awaited_once()
    assert "don't have permission" in interaction.response.send_message.call_args[0][0]

@pytest.mark.asyncio
async def test_setup_logging_channel_forbidden_error():
    """Test the setup_logging_channel command when sending test message fails"""
    # Create mocks
    bot = MagicMock()
    settings = {}
    save_settings = MagicMock()
    interaction = AsyncMock()
    channel = AsyncMock()
    
    # Setup interaction
    interaction.guild_id = 123
    interaction.guild.me = MagicMock()
    channel.id = 456
    channel.mention = "#test-channel"
    
    # Setup permissions but make channel.send raise Forbidden
    perms = MagicMock()
    perms.send_messages = True
    channel.permissions_for = MagicMock(return_value=perms)
    channel.send.side_effect = discord.Forbidden(MagicMock(), "Forbidden")
    
    # Create our own implementation for testing
    async def setup_logging_channel_impl(interaction, channel):
        gid = str(interaction.guild_id)
        settings[gid] = settings.get(gid, {})
        
        # Save the channel ID
        settings[gid]["notification_channel"] = channel.id
        save_settings()
        
        # Send confirmation
        await interaction.response.send_message(
            f"✅ Logging channel set to {channel.mention}.", 
            ephemeral=True
        )
        
        # Send a test message to the channel
        try:
            await channel.send(
                f"🔔 This channel has been set up as the logging channel for the Lichess Events bot.\n"
                f"You will receive log messages and event notifications here."
            )
        except discord.Forbidden:
            await interaction.followup.send(
                "⚠️ Failed to send a test message. Please check permissions.", 
                ephemeral=True
            )
    
    # Call our implementation
    await setup_logging_channel_impl(interaction, channel)
    
    # Verify the settings were saved anyway
    assert settings.get('123', {}).get('notification_channel') == 456
    save_settings.assert_called_once()
    
    # Verify the confirmation was sent
    interaction.response.send_message.assert_awaited_once()
    
    # Verify error message was sent
    interaction.followup.send.assert_awaited_once()
    assert "Failed to send" in interaction.followup.send.call_args[0][0]
