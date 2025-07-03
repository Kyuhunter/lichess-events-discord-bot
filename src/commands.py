import os
import discord
from discord.ext import commands
from .sync import sync_events_for_guild


def setup_commands(bot: commands.Bot, SETTINGS: dict, save_settings: callable):
    async def log_to_notification_channel(guild: discord.Guild, message: str):
        gid = str(guild.id)
        chan_id = SETTINGS.get(gid, {}).get("notification_channel")
        if not chan_id:
            return
        channel = guild.get_channel(chan_id)
        if not isinstance(channel, discord.TextChannel):
            return
        perms = channel.permissions_for(guild.me or guild.get_member(bot.user.id))
        if not perms.send_messages:
            return
        try:
            await channel.send(message)
        except discord.Forbidden:
            print(f"[{guild.name}] 🚫 Forbidden sending to channel {chan_id}")

    @bot.tree.command(name="setup_team", description="Register your Lichess team")
    @discord.app_commands.describe(team="Lichess team slug (e.g., lichess-de)")
    async def setup_team(interaction: discord.Interaction, team: str):
        gid = str(interaction.guild_id)
        if not isinstance(SETTINGS.get(gid), dict):
            SETTINGS[gid] = {}
        SETTINGS[gid]["team"] = team.strip()
        save_settings()
        await interaction.response.send_message(f"✅ Team `{team}` saved.", ephemeral=True)
        await log_to_notification_channel(interaction.guild, f"Team `{team}` has been registered.")

    @bot.tree.command(name="remove_team", description="Remove the registration")
    async def remove_team(interaction: discord.Interaction):
        gid = str(interaction.guild_id)
        if SETTINGS.pop(gid, None):
            save_settings()
            await interaction.response.send_message("🗑️ Registration removed.", ephemeral=True)
            await log_to_notification_channel(interaction.guild, "Team registration has been removed.")
        else:
            await interaction.response.send_message("ℹ️ No team registered.", ephemeral=True)

    @bot.tree.command(name="sync", description="Manual sync (silent)")
    @discord.app_commands.checks.has_permissions(administrator=True)
    async def sync_cmd(interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        created, events = await sync_events_for_guild(interaction.guild, SETTINGS, bot, verbose=False)
        if created == 0:
            await interaction.followup.send("ℹ️ No team registered or no new events created.", ephemeral=True)
        else:
            await interaction.followup.send(f"✅ {created} new events created:\n" + "\n".join(events), ephemeral=True)

    @bot.tree.command(name="sync_verbose", description="Sync with detailed logging")
    @discord.app_commands.checks.has_permissions(administrator=True)
    async def sync_verbose_cmd(interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        created, events = await sync_events_for_guild(interaction.guild, SETTINGS, bot, verbose=True)
        if created == 0:
            await interaction.followup.send("ℹ️ No team registered or no new events created.", ephemeral=True)
        else:
            await interaction.followup.send(f"✅ {created} new events created:\n" + "\n".join(events), ephemeral=True)

    @bot.tree.command(name="set_notification_channel", description="Select a channel for notifications")
    @discord.app_commands.describe(channel="The channel where notifications will be sent")
    async def set_notification_channel(interaction: discord.Interaction, channel: discord.TextChannel):
        gid = str(interaction.guild_id)
        if not isinstance(SETTINGS.get(gid), dict):
            SETTINGS[gid] = {}
        SETTINGS[gid]["notification_channel"] = channel.id
        save_settings()
        await interaction.response.send_message(f"✅ Notification channel set to `{channel.name}`.", ephemeral=True)
        await log_to_notification_channel(interaction.guild, f"Notification channel set to `{channel.name}`.")
