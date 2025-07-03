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
        settings = SETTINGS.setdefault(gid, {})
        teams = settings.setdefault("teams", [])
        slug = team.strip()
        if slug in teams:
            await interaction.response.send_message(f"⚠️ Team `{slug}` is already registered.", ephemeral=True)
            return
        teams.append(slug)
        save_settings()
        await interaction.response.send_message(f"✅ Team `{slug}` added.", ephemeral=True)
        await log_to_notification_channel(interaction.guild, f"Team `{slug}` has been registered.")

    @bot.tree.command(name="remove_team", description="Remove a registered Lichess team")
    @discord.app_commands.describe(team="Registered team slug to remove")
    async def remove_team(interaction: discord.Interaction, team: str):
        gid = str(interaction.guild_id)
        teams = SETTINGS.get(gid, {}).get("teams", [])
        slug = team.strip()
        if slug in teams:
            teams.remove(slug)
            save_settings()
            await interaction.response.send_message(f"🗑️ Team `{slug}` removed.", ephemeral=True)
            await log_to_notification_channel(interaction.guild, f"Team `{slug}` has been removed.")
        else:
            await interaction.response.send_message(f"⚠️ Team `{slug}` is not registered.", ephemeral=True)

    @bot.tree.command(name="list_teams", description="List registered Lichess teams in this guild")
    @discord.app_commands.checks.has_permissions(administrator=True)
    async def list_teams_cmd(interaction: discord.Interaction):
        gid = str(interaction.guild_id)
        teams = SETTINGS.get(gid, {}).get("teams", [])
        if not teams:
            await interaction.response.send_message("ℹ️ No teams registered.", ephemeral=True)
        else:
            await interaction.response.send_message(
                "📋 Registered teams:\n" + "\n".join(f"- {t}" for t in teams),
                ephemeral=True
            )

    @bot.tree.command(name="sync", description="Manual sync for teams")
    @discord.app_commands.describe(team="Optional specific team slug to sync")
    @discord.app_commands.checks.has_permissions(administrator=True)
    async def sync_cmd(interaction: discord.Interaction, team: str = None):
        await interaction.response.defer(ephemeral=True)
        gid = str(interaction.guild_id)
        teams = SETTINGS.get(gid, {}).get("teams", [])
        if team:
            slug = team.strip()
            if slug not in teams:
                await interaction.followup.send(f"⚠️ Team `{slug}` is not registered.", ephemeral=True)
                return
            targets = [slug]
        else:
            targets = teams
        if not targets:
            await interaction.followup.send("ℹ️ No teams registered.", ephemeral=True)
            return
        total, all_events = 0, []
        for slug in targets:
            created, events = await sync_events_for_guild(
                interaction.guild, SETTINGS, bot, verbose=False, team_slug=slug
            )
            total += created
            all_events.extend(events)
        if total == 0:
            await interaction.followup.send("ℹ️ No new events created.", ephemeral=True)
        else:
            await interaction.followup.send(
                f"✅ {total} new events created:\n" + "\n".join(all_events),
                ephemeral=True
            )

    @bot.tree.command(name="sync_verbose", description="Sync with detailed logging for teams")
    @discord.app_commands.describe(team="Optional specific team slug to sync")
    @discord.app_commands.checks.has_permissions(administrator=True)
    async def sync_verbose_cmd(interaction: discord.Interaction, team: str = None):
        await interaction.response.defer(ephemeral=True)
        gid = str(interaction.guild_id)
        teams = SETTINGS.get(gid, {}).get("teams", [])
        if team:
            slug = team.strip()
            if slug not in teams:
                await interaction.followup.send(f"⚠️ Team `{slug}` is not registered.", ephemeral=True)
                return
            targets = [slug]
        else:
            targets = teams
        if not targets:
            await interaction.followup.send("ℹ️ No teams registered.", ephemeral=True)
            return
        total, all_events = 0, []
        for slug in targets:
            created, events = await sync_events_for_guild(
                interaction.guild, SETTINGS, bot, verbose=True, team_slug=slug
            )
            total += created
            all_events.extend(events)
        if total == 0:
            await interaction.followup.send("ℹ️ No new events created.", ephemeral=True)
        else:
            await interaction.followup.send(
                f"✅ {total} new events created:\n" + "\n".join(all_events),
                ephemeral=True
            )

    @bot.command(name="sync")
    @commands.has_permissions(administrator=True)
    async def sync_prefix(ctx: commands.Context):
        guild_id = str(ctx.guild.id)
        teams = SETTINGS.get(guild_id, {}).get("teams", [])
        total, all_events = 0, []
        for slug in teams:
            created, events = await sync_events_for_guild(
                ctx.guild, SETTINGS, bot, verbose=False, team_slug=slug
            )
            total += created
            all_events.extend(events)
        if created == 0:
            await ctx.send("ℹ️ No team registered or no new events created.")
        else:
            event_list = "\n".join(all_events)
            await ctx.send(f"✅ {total} new events created:\n{event_list}")

    @bot.command(name="sync_verbose")
    @commands.has_permissions(administrator=True)
    async def sync_verbose_prefix(ctx: commands.Context):
        guild_id = str(ctx.guild.id)
        teams = SETTINGS.get(guild_id, {}).get("teams", [])
        total, all_events = 0, []
        for slug in teams:
            created, events = await sync_events_for_guild(
                ctx.guild, SETTINGS, bot, verbose=True, team_slug=slug
            )
            total += created
            all_events.extend(events)
        if created == 0:
            await ctx.send("ℹ️ No team registered or no new events created.")
        else:
            event_list = "\n".join(all_events)
            await ctx.send(f"✅ {total} new events created:\n{event_list}")
