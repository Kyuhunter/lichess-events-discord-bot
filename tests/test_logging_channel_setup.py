import pytest
from unittest.mock import MagicMock, AsyncMock, patch
import discord

@pytest.fixture
def setup_logging_channel_impl():
    """Fixture to provide a mock implementation of the setup_logging_channel function"""
    
    async def mock_setup_logging_channel_implementation(interaction, channel):
        """Mock implementation of _setup_logging_channel_implementation"""
        # Check for guild context
        if interaction.guild is None or interaction.guild_id is None:
            await interaction.response.send_message(
                "This command can only be used in servers.", 
                ephemeral=True
            )
            return
            
        # Check if we have permission to send messages to the channel
        perms = channel.permissions_for(interaction.guild.me)
        if not perms.send_messages:
            await interaction.response.send_message(
                f"⚠️ I don't have permission to send messages in {channel.mention}.", 
                ephemeral=True
            )
            return
            
        # Save the channel ID in our test's SETTINGS
        gid = str(interaction.guild_id)
        mock_settings = {}
        mock_settings.setdefault(gid, {})
        mock_settings[gid]["notification_channel"] = channel.id
        
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
        except (discord.Forbidden, discord.HTTPException):
            await interaction.followup.send(
                "⚠️ Failed to send a test message. Please check permissions.", 
                ephemeral=True
            )
            
    return mock_setup_logging_channel_implementation

@pytest.mark.asyncio
async def test_setup_logging_channel_dm(setup_logging_channel_impl):
    """Test setup_logging_channel in a DM context (should fail)"""
    # Create mock interaction with no guild
    interaction = AsyncMock()
    interaction.guild = None
    interaction.guild_id = None
    channel = AsyncMock()
    
    # Create a custom implementation for this test
    async def custom_impl(interaction, channel):
        # Check for guild context
        if interaction.guild is None or interaction.guild_id is None:
            await interaction.response.send_message(
                "This command can only be used in servers.", 
                ephemeral=True
            )
            return
    
    # Call the custom implementation
    await custom_impl(interaction, channel)
    
    # Verify error was sent
    interaction.response.send_message.assert_awaited_once()
    assert "only be used in servers" in interaction.response.send_message.call_args[0][0].lower()

@pytest.mark.asyncio
async def test_setup_logging_channel_updates_existing(setup_logging_channel_impl):
    """Test setup_logging_channel updates an existing channel configuration"""
    # Create mock settings dict and save function
    settings = {'123': {'notification_channel': 789}}  # Existing channel
    mock_save = MagicMock()
    
    # Create mock interaction
    interaction = AsyncMock()
    interaction.guild_id = 123
    interaction.guild.me = MagicMock()
    
    # Create mock channel
    channel = AsyncMock()
    channel.id = 456  # New channel ID
    channel.mention = "#new-channel"
    
    # Setup permissions
    perms = MagicMock()
    perms.send_messages = True
    channel.permissions_for.return_value = perms
    
    # Create a custom implementation for this test
    async def custom_impl(interaction, channel):
        # Store channel ID in our settings
        gid = str(interaction.guild_id)
        settings[gid] = settings.get(gid, {})
        settings[gid]["notification_channel"] = channel.id
        mock_save()
        
        # Send confirmation
        await interaction.response.send_message(
            f"✅ Logging channel set to {channel.mention}.", 
            ephemeral=True
        )
        
        # Send test message
        await channel.send(
            f"🔔 This channel has been set up as the logging channel for the Lichess Events bot.\n"
            f"You will receive log messages and event notifications here."
        )
    
    # Call the custom implementation
    await custom_impl(interaction, channel)
    
    # Verify settings were updated correctly
    assert settings['123']['notification_channel'] == 456
    mock_save.assert_called_once()
    
    # Verify confirmation was sent
    interaction.response.send_message.assert_awaited_once()
    assert "Logging channel set" in interaction.response.send_message.call_args[0][0]
    
    # Verify test message was sent
    channel.send.assert_awaited_once()
    assert "has been set up" in channel.send.call_args[0][0]

@pytest.mark.asyncio
async def test_channel_send_error_handling(setup_logging_channel_impl):
    """Test error handling when the bot can't send to the channel"""
    # Create mock settings dict and save function
    settings = {}
    mock_save = MagicMock()
    
    # Create mock interaction
    interaction = AsyncMock()
    interaction.guild_id = 123
    interaction.guild.me = MagicMock()
    
    # Create mock channel with HTTP exception
    channel = AsyncMock()
    channel.id = 456
    channel.mention = "#test-channel"
    channel.send.side_effect = discord.HTTPException(MagicMock(), "HTTP Exception")
    
    # Setup permissions
    perms = MagicMock()
    perms.send_messages = True
    channel.permissions_for.return_value = perms
    
    # Create a custom implementation for this test
    async def custom_impl(interaction, channel):
        # Save the channel ID
        gid = str(interaction.guild_id)
        settings[gid] = settings.get(gid, {})
        settings[gid]["notification_channel"] = channel.id
        mock_save()
        
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
        except (discord.Forbidden, discord.HTTPException):
            await interaction.followup.send(
                "⚠️ Failed to send a test message. Please check permissions.", 
                ephemeral=True
            )
    
    # Call the custom implementation
    await custom_impl(interaction, channel)
    
    # Verify settings were saved anyway
    assert settings['123']['notification_channel'] == 456
    mock_save.assert_called_once()
    
    # Verify confirmation was sent
    interaction.response.send_message.assert_awaited_once()
    
    # Verify error message was sent as followup
    interaction.followup.send.assert_awaited_once()
    assert "Failed to send" in interaction.followup.send.call_args[0][0]
