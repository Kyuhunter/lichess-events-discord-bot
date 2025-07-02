import discord
from discord.ext import commands
from sync import sync_events_for_guild

def setup_commands(bot: commands.Bot, SETTINGS: dict, save_settings: callable):
    async def log_to_notification_channel(guild: discord.Guild, message: str):
        guild_id = str(guild.id)
        channel_id = SETTINGS.get(guild_id, {}).get("notification_channel")
        if channel_id:
            channel = guild.get_channel(channel_id)
            if channel:
                await channel.send(message)

    @bot.tree.command(name="setup_team", description="Register your Lichess team")
    @discord.app_commands.describe(team="Lichess team slug (e.g., lichess-de)")
    async def setup_team(interaction: discord.Interaction, team: str):
        guild_id = str(interaction.guild_id)
        if not isinstance(SETTINGS.get(guild_id), dict):
            SETTINGS[guild_id] = {}  # Ensure SETTINGS[guild_id] is a dictionary
        SETTINGS[guild_id]["team"] = team.strip()  # Store the team slug inside the guild dictionary
        save_settings()
        await interaction.response.send_message(f"✅ Team `{team}` saved.", ephemeral=True)
        await log_to_notification_channel(interaction.guild, f"Team `{team}` has been registered.")

    @bot.tree.command(name="remove_team", description="Remove the registration")
    async def remove_team(interaction: discord.Interaction):
        guild_id = str(interaction.guild_id)
        if SETTINGS.pop(guild_id, None):
            save_settings()
            await interaction.response.send_message("🗑️ Registration removed.", ephemeral=True)
            await log_to_notification_channel(interaction.guild, "Team registration has been removed.")
        else:
            await interaction.response.send_message("ℹ️ No team registered.", ephemeral=True)

    @bot.tree.command(name="sync", description="Manual sync (silent)")
    @discord.app_commands.checks.has_permissions(administrator=True)
    async def sync_cmd(interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        created, created_events = await sync_events_for_guild(interaction.guild, SETTINGS, bot, verbose=False)
        if created == 0:
            await interaction.followup.send("ℹ️ No team registered or no new events created.", ephemeral=True)
        else:
            event_list = "\n".join(created_events)
            await interaction.followup.send(f"✅ {created} new events created:\n{event_list}", ephemeral=True)

    @bot.tree.command(name="sync_verbose", description="Sync with detailed logging")
    @discord.app_commands.checks.has_permissions(administrator=True)
    async def sync_verbose_cmd(interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        created, created_events = await sync_events_for_guild(interaction.guild, SETTINGS, bot, verbose=True)
        if created == 0:
            await interaction.followup.send("ℹ️ No team registered or no new events created.", ephemeral=True)
        else:
            event_list = "\n".join(created_events)
            await interaction.followup.send(f"✅ {created} new events created:\n{event_list}", ephemeral=True)

    @bot.tree.command(name="set_notification_channel", description="Select a channel for notifications")
    @discord.app_commands.describe(channel="The channel where notifications will be sent")
    async def set_notification_channel(interaction: discord.Interaction, channel: discord.TextChannel):
        guild_id = str(interaction.guild_id)
        if not isinstance(SETTINGS.get(guild_id), dict):
            SETTINGS[guild_id] = {}  # Ensure SETTINGS[guild_id] is a dictionary
        SETTINGS[guild_id]["notification_channel"] = channel.id
        save_settings()
        await interaction.response.send_message(
            f"✅ Notification channel set to `{channel.name}`.", ephemeral=True
        )
        await log_to_notification_channel(interaction.guild, f"Notification channel set to `{channel.name}`.")

    @bot.command(name="sync")
    @commands.has_permissions(administrator=True)
    async def sync_prefix(ctx: commands.Context):
        guild_id = str(ctx.guild.id)
        if not isinstance(SETTINGS.get(guild_id), dict):
            SETTINGS[guild_id] = {}  # Ensure SETTINGS[guild_id] is a dictionary
        created, created_events = await sync_events_for_guild(ctx.guild, SETTINGS, bot, verbose=False)
        if created == 0:
            await ctx.send("ℹ️ No team registered or no new events created.")
        else:
            event_list = "\n".join(created_events)
            await ctx.send(f"✅ {created} new events created:\n{event_list}")

    @bot.command(name="sync_verbose")
    @commands.has_permissions(administrator=True)
    async def sync_verbose_prefix(ctx: commands.Context):
        guild_id = str(ctx.guild.id)
        if not isinstance(SETTINGS.get(guild_id), dict):
            SETTINGS[guild_id] = {}  # Ensure SETTINGS[guild_id] is a dictionary
        created, created_events = await sync_events_for_guild(ctx.guild, SETTINGS, bot, verbose=True)
        if created == 0:
            await ctx.send("ℹ️ No team registered or no new events created.")
        else:
            event_list = "\n".join(created_events)
            await ctx.send(f"✅ {created} new events created:\n{event_list}")