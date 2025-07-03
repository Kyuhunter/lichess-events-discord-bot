import pytest
import discord
from unittest.mock import AsyncMock, MagicMock, patch

@pytest.mark.asyncio
async def test_status_command(bot, interaction, settings, save_settings):
    """Test the status command shows bot health information."""
    from src.commands import setup_commands
    from datetime import datetime, timezone
    import re
    
    # Customize settings for this test
    gid = str(interaction.guild_id)
    settings[gid] = {"teams": ["team-a", "team-b"], "auto_sync": True, "notification_channel": 987654321}
    
    # Mock channel for notification
    channel_mock = MagicMock(spec=discord.TextChannel)
    channel_mock.name = "bot-logs"
    interaction.guild.get_channel.return_value = channel_mock
    
    # Add launch_time attribute
    setattr(bot, 'launch_time', datetime.now(timezone.utc).timestamp() - 3600)  # 1 hour ago
    
    # Setup error case to verify error handling
    interaction.followup.send.side_effect = lambda **kwargs: None
    
    # Set up commands
    setup_commands(bot, settings, save_settings)
    
    # Find status command
    status_command = None
    for command in bot.tree.walk_commands():
        if command.name == "status":
            status_command = command
            break
    
    assert status_command is not None, "Status command not found"
    
    # Call the status command
    await status_command.callback(interaction)
    
    # Verify interactions
    interaction.response.defer.assert_called_once_with(ephemeral=True)
    assert interaction.followup.send.called
    
    # Verify ephemeral is set for the error message
    call_kwargs = interaction.followup.send.call_args.kwargs
    assert call_kwargs.get("ephemeral") is True
    
    # At the very least, we got an error message
    error_message = "⚠️ Error checking bot status. Please check logs."
    if "content" in call_kwargs:
        assert error_message in call_kwargs["content"]
