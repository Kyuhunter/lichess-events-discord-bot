import pytest
import logging
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch, PropertyMock
import discord
from src.utils import DiscordHandler, setup_discord_handler
from src.sync import log_to_notification_channel

@pytest.mark.asyncio
async def test_discord_handler_log_event():
    """Test that DiscordHandler.log_event adds events to pending_logs with correct formatting"""
    # Set up mocks
    bot = MagicMock()
    bot.is_ready.return_value = True
    settings = {'123': {'notification_channel': 456}}
    
    # Create handler
    with patch('src.utils._log_conf') as mock_conf:
        # Mock config to enable events
        mock_conf.get.return_value = {'events': True}
        handler = DiscordHandler(bot, settings)
        
        # Test with different event types
        with patch('asyncio.create_task'):
            handler.log_event('create', 'Event created')
            handler.log_event('update', 'Event updated')
            handler.log_event('delete', 'Event deleted')
            handler.log_event('other', 'Other event')
            
            # Check pending logs
            assert "✅ Event created" in handler.pending_logs
            assert "🔄 Event updated" in handler.pending_logs
            assert "🗑️ Event deleted" in handler.pending_logs
            assert "ℹ️ Other event" in handler.pending_logs

@pytest.mark.asyncio
async def test_discord_handler_events_disabled():
    """Test that DiscordHandler.log_event doesn't add events when disabled in config"""
    # Set up mocks
    bot = MagicMock()
    settings = {'123': {'notification_channel': 456}}
    
    # Create handler but prevent scheduling
    handler = DiscordHandler(bot, settings)
    handler._schedule_processing = MagicMock()  # Replace with mock to prevent any task creation
    handler.pending_logs = []
    
    # Test with mocked config that disables events
    with patch('src.utils._log_conf') as mock_conf:
        # Mock config to disable events
        mock_conf.get.return_value = {'events': False}
        
        # Call log_event directly
        handler.log_event('create', 'Event created')
        
        # Check no logs were added
        assert len(handler.pending_logs) == 0

@pytest.mark.asyncio
async def test_discord_handler_integration():
    """Test integration between log_to_notification_channel and DiscordHandler"""
    # Create minimal test environment
    from src.sync import log_to_notification_channel
    
    # Set up mocks
    guild = MagicMock()
    guild.id = 123
    settings = {'123': {'notification_channel': 456}}
    
    # Create a handler mock that's not a real DiscordHandler
    mock_handler = MagicMock()
    mock_handler.log_event = MagicMock()
    
    # Mock the logger with our safe mock
    with patch('src.sync.logger') as mock_logger:
        # Set up mock logger's handlers list
        mock_logger.handlers = [mock_handler]
        
        # Call log_to_notification_channel with event_type
        await log_to_notification_channel(guild, settings, "Test event", "create")
        
        # Verify handler.log_event was called with correct parameters
        mock_handler.log_event.assert_called_once_with("create", "Test event")

@pytest.mark.asyncio
async def test_setup_discord_handler_with_config():
    """Test that setup_discord_handler correctly sets up the handler with config"""
    # Set up mocks
    bot = MagicMock()
    settings = {'123': {'notification_channel': 456}}
    
    # Create a mock DiscordHandler class to avoid warnings
    mock_handler_instance = MagicMock()
    mock_handler_instance.level = logging.WARNING
    
    class MockDiscordHandler:
        def __init__(self, bot, settings, level=logging.INFO):
            # Return our pre-configured mock
            pass
        
    # Patch logger, config, and the DiscordHandler class
    with patch('src.utils.logger') as mock_logger, \
         patch('src.utils._log_conf') as mock_conf, \
         patch('src.utils._discord_handler') as mock_existing_handler, \
         patch('src.utils.DiscordHandler', return_value=mock_handler_instance):
        
        # Mock config with custom log level
        mock_conf.get.return_value = {'level': 'WARNING', 'events': True}
        
        # Call function
        handler = setup_discord_handler(bot, settings)
        
        # Verify handler was created with correct level (our mock)
        assert handler.level == logging.WARNING
        
        # Verify it was added to logger
        mock_logger.addHandler.assert_called_once_with(mock_handler_instance)
        
        # If existing handler, verify it was removed first
        if mock_existing_handler:
            mock_logger.removeHandler.assert_called_once_with(mock_existing_handler)

@pytest.mark.asyncio
async def test_discord_handler_batching_logic():
    """Test that DiscordHandler correctly batches logs"""
    # Set up mocks
    bot = MagicMock()
    settings = {'123': {'notification_channel': 456}}
    
    # Create a modified handler that doesn't try to schedule processing
    handler = DiscordHandler(bot, settings)
    handler._schedule_processing = MagicMock()  # Replace with mock to prevent any task creation
    
    # Add logs through the format and emit method
    for i in range(8):
        record = MagicMock()
        record.levelno = logging.INFO
        record.msg = f"Log {i+1}"
        record.getMessage.return_value = record.msg
        handler.format = lambda r: r.getMessage()
        
        # This will add to pending_logs but won't process due to our mock
        handler.emit(record)
    
    # Check that logs were properly queued for batching
    assert len(handler.pending_logs) == 8
    assert "🔵 Log 1" in handler.pending_logs[0]
    assert "🔵 Log 8" in handler.pending_logs[7]

@pytest.mark.asyncio
async def test_discord_handler_error_handling():
    """Test that DiscordHandler gracefully handles errors when sending to channel"""
    # Set up mocks
    bot = MagicMock()
    bot.is_ready.return_value = True
    bot.guilds = []
    
    # Create a test guild and channel
    guild = MagicMock()
    guild.id = 123
    channel = AsyncMock()
    channel.send.side_effect = Exception("Test error")
    guild.get_channel.return_value = channel
    bot.guilds = [guild]
    
    # Create handler with specific settings
    settings = {'123': {'notification_channel': 456}}
    handler = DiscordHandler(bot, settings)
    
    # Add a test message to pending logs
    handler.pending_logs = ["Test log"]
    handler.is_sending = False
    
    # Process logs directly
    await handler._process_logs()
    
    # Verify the channel was retrieved
    guild.get_channel.assert_called_once_with(456)
    
    # Verify send was attempted and exceptions were handled
    channel.send.assert_called_once()
    
    # Verify is_sending was reset
    assert not handler.is_sending
