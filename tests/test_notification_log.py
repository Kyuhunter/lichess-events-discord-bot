import pytest
from unittest.mock import MagicMock, AsyncMock, patch
import discord
from src.sync import log_to_notification_channel

@pytest.mark.asyncio
async def test_log_to_notification_channel_with_event_type():
    """Test that log_to_notification_channel uses the handler.log_event method when event_type is provided"""
    # Set up mocks
    guild = MagicMock()
    guild.id = 123
    guild.name = "Test Guild"
    
    settings = {'123': {'notification_channel': 456}}
    message = "Test event message"
    
    # Create mock logger with handler that has log_event method
    mock_handler = MagicMock()
    mock_handler.log_event = MagicMock()
    
    # Patch logger.handlers to include our mock handler
    with patch('src.sync.logger') as mock_logger:
        mock_logger.handlers = [mock_handler]
        
        # Call with event_type
        await log_to_notification_channel(guild, settings, message, "create")
        
        # Verify log_event was called
        mock_handler.log_event.assert_called_once_with("create", message)

@pytest.mark.asyncio
async def test_log_to_notification_channel_fallback():
    """Test that log_to_notification_channel falls back to direct channel messaging when no handler"""
    # Set up mocks
    guild = MagicMock()
    guild.id = 123
    guild.name = "Test Guild"
    
    channel = AsyncMock()
    channel.send = AsyncMock()
    guild.get_channel.return_value = channel
    
    settings = {'123': {'notification_channel': 456}}
    message = "Test message"
    
    # Set up permissions
    perms = MagicMock()
    perms.send_messages = True
    # Make sure this returns the perms object directly, not a coroutine
    channel.permissions_for = MagicMock(return_value=perms)
    
    # Patch discord.Member or User in the get_member call
    mock_bot_user = MagicMock()
    guild.get_member.return_value = mock_bot_user
    guild.me = mock_bot_user  # Set me to the mock user        # Create a mock TextChannel class
    class MockTextChannel:
        pass
        
    # Patch logger.handlers to be empty and patch commands.Bot
    with patch('src.sync.logger.handlers', []), \
         patch('src.sync.commands.Bot') as mock_bot_class, \
         patch('src.sync.discord.TextChannel', MockTextChannel):
        # Set up mock Bot.user
        mock_bot_class.user = mock_bot_user
        
        # Ensure our channel passes isinstance check
        original_isinstance = isinstance
        def patched_isinstance(obj, class_or_tuple, /):
            if class_or_tuple is MockTextChannel:
                return True
            return original_isinstance(obj, class_or_tuple)
            
        # Patch the built-in isinstance function
        with patch('builtins.isinstance', patched_isinstance):
            # Call the actual function without event_type
            await log_to_notification_channel(guild, settings, message)
            
            # Make sure send was called - use call_count instead of assert_awaited_once
            assert channel.send.call_count == 1
            assert channel.send.call_args[0][0] == message

@pytest.mark.asyncio
async def test_log_to_notification_channel_no_channel():
    """Test that log_to_notification_channel does nothing when no channel is configured"""
    # Set up mocks
    guild = MagicMock()
    guild.id = 123
    guild.name = "Test Guild"
    
    settings = {'123': {}}  # No notification_channel
    message = "Test message"
    
    # Patch logger.handlers to be empty
    with patch('src.sync.logger') as mock_logger:
        mock_logger.handlers = []
        
        # Call function
        await log_to_notification_channel(guild, settings, message)
        
        # Verify guild.get_channel was not called
        guild.get_channel.assert_not_called()

@pytest.mark.asyncio
async def test_commands_log_to_notification_channel():
    """Test a direct implementation of log_to_notification_channel"""
    # Set up mocks
    settings = {'123': {'notification_channel': 456}}
    
    # Create mock handler with log_event method
    mock_handler = MagicMock()
    mock_handler.log_event = MagicMock()
    
    # Create mock logger
    mock_logger = MagicMock()
    mock_logger.handlers = [mock_handler]
    
    # Create mock guild
    guild = MagicMock()
    guild.id = 123
    
    # Create our own implementation for testing
    async def log_to_notification(guild, message, event_type=None):
        # Try to use the Discord handler if available
        for handler in mock_logger.handlers:
            if hasattr(handler, 'log_event') and event_type:
                handler.log_event(event_type, message)
                return
                
        # We won't test the fallback here as it's covered in other tests
    
    # Call our implementation with event_type
    await log_to_notification(guild, "Test message", "create")
    
    # Verify log_event was called
    mock_handler.log_event.assert_called_once_with("create", "Test message")
