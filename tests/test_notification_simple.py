import pytest
from unittest.mock import MagicMock, AsyncMock, patch, Mock
import discord

@pytest.mark.asyncio
async def test_simplified_notification_channel():
    """A simplified test for the notification channel functionality"""
    # Import here to make sure patches work
    from src.sync import log_to_notification_channel
    
    # Set up mocks
    guild = MagicMock()
    guild.id = 123
    guild.name = "Test Guild"
    
    # Create mock channel
    channel = AsyncMock()
    channel.send = AsyncMock()
    guild.get_channel.return_value = channel
    
    # Set up settings
    settings = {'123': {'notification_channel': 456}}
    message = "Test message"
    
    # Mock permissions
    perms = MagicMock()
    perms.send_messages = True
    # Make permissions_for return a value, not a coroutine
    channel.permissions_for = MagicMock(return_value=perms)
    
    # Mock the guild.me property
    bot_user = MagicMock()
    guild.me = bot_user
    
    # Create a mock TextChannel class
    class MockTextChannel:
        pass
    
    # Patch necessary components
    with patch('src.sync.logger.handlers', []), \
         patch('src.sync.discord.TextChannel', MockTextChannel):
        # Ensure our channel passes isinstance check
        original_isinstance = isinstance
        def patched_isinstance(obj, class_or_tuple, /):
            if class_or_tuple is MockTextChannel:
                return True
            return original_isinstance(obj, class_or_tuple)
        
        # Apply patch to builtin isinstance
        with patch('builtins.isinstance', patched_isinstance):
            # Call the function
            await log_to_notification_channel(guild, settings, message)
            
            # Verify channel.send was called
            assert channel.send.call_count == 1
            assert channel.send.call_args[0][0] == message
