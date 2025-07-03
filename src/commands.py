import os
import discord
from discord.ext import commands
from .sync import sync_events_for_guild
from .utils import ensure_file_handler, logger


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
        """Remove a team, delete its events, and log errors to file if they occur."""
        gid = str(interaction.guild_id)
        teams = SETTINGS.get(gid, {}).get("teams", [])
        slug = team.strip()
        if slug not in teams:
            await interaction.response.send_message(
                f"⚠️ Team `{slug}` is not registered.", ephemeral=True
            )
            return
        await interaction.response.defer(ephemeral=True)
        try:
            # Remove team from settings
            teams.remove(slug)
            save_settings()
            # Identify and delete only this team's upcoming tournament events
            deleted = 0
            import aiohttp, json
            async with aiohttp.ClientSession() as session:
                url = f"https://lichess.org/api/team/{slug}/arena"
                async with session.get(url) as resp:
                    if resp.status == 200:
                        tourney_ids = []
                        async for line in resp.content:
                            try:
                                t = json.loads(line.decode().strip())
                                tourney_ids.append(t.get('id'))
                            except Exception:
                                continue
                        urls_to_delete = {f"https://lichess.org/tournament/{tid}" for tid in tourney_ids}
                        events = await interaction.guild.fetch_scheduled_events()
                        for ev in events:
                            if ev.location in urls_to_delete:
                                try:
                                    await ev.delete()
                                    deleted += 1
                                except Exception:
                                    pass
            # Send deletion summary
            await interaction.followup.send(
                f"🗑️ Team `{slug}` removed. Deleted {deleted} associated event(s).", ephemeral=True
            )
            await log_to_notification_channel(
                interaction.guild, f"Team `{slug}` removed and {deleted} events deleted."
            )
        except Exception as e:
            # Log error to file and inform user
            ensure_file_handler()
            logger.error(f"Failed to remove team {slug}", exc_info=e)
            await interaction.followup.send(
                f"❌ Failed to remove team `{slug}` due to an internal error.", ephemeral=True
            )

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

    @bot.tree.command(name="auto_sync", description="Enable or disable scheduled background sync")
    @discord.app_commands.describe(enable="True to enable, False to disable automatic sync")
    @discord.app_commands.checks.has_permissions(administrator=True)
    async def auto_sync_cmd(interaction: discord.Interaction, enable: bool):
        gid = str(interaction.guild_id)
        settings = SETTINGS.setdefault(gid, {})
        settings["auto_sync"] = enable
        save_settings()
        status = "enabled" if enable else "disabled"
        await interaction.response.send_message(
            f"🔄 Scheduled sync has been {status} for this server.", ephemeral=True
        )
        await log_to_notification_channel(
            interaction.guild, f"Scheduled sync {status} by user {interaction.user}"
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
        total_created, total_updated, all_events = 0, 0, []
        for slug in targets:
            created, updated, events = await sync_events_for_guild(
                interaction.guild, SETTINGS, bot, verbose=False, team_slug=slug
            )
            total_created += created
            total_updated += updated
            all_events.extend(events)
        # Construct feedback message
        if total_created == 0 and total_updated == 0:
            await interaction.followup.send("ℹ️ No new or updated events.", ephemeral=True)
        else:
            parts = []
            if total_created:
                parts.append(f"✅ {total_created} new events created")
            if total_updated:
                parts.append(f"🔄 {total_updated} events updated")
            summary = ", ".join(parts) + ":\n" + "\n".join(all_events)
            await interaction.followup.send(summary, ephemeral=True)

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
        total_created, total_updated, all_events = 0, 0, []
        for slug in targets:
            created, updated, events = await sync_events_for_guild(
                interaction.guild, SETTINGS, bot, verbose=True, team_slug=slug
            )
            total_created += created
            total_updated += updated
            all_events.extend(events)
        if total_created == 0 and total_updated == 0:
            await interaction.followup.send("ℹ️ No new or updated events.", ephemeral=True)
        else:
            parts = []
            if total_created:
                parts.append(f"✅ {total_created} new events created")
            if total_updated:
                parts.append(f"🔄 {total_updated} events updated")
            summary = ", ".join(parts) + ":\n" + "\n".join(all_events)
            await interaction.followup.send(summary, ephemeral=True)

    @bot.command(name="sync")
    @commands.has_permissions(administrator=True)
    async def sync_prefix(ctx: commands.Context):
        guild_id = str(ctx.guild.id)
        teams = SETTINGS.get(guild_id, {}).get("teams", [])
        total_created, total_updated, all_events = 0, 0, []
        for slug in teams:
            created, updated, events = await sync_events_for_guild(
                ctx.guild, SETTINGS, bot, verbose=False, team_slug=slug
            )
            total_created += created
            total_updated += updated
            all_events.extend(events)
        if total_created == 0 and total_updated == 0:
            await ctx.send("ℹ️ No new or updated events.")
        else:
            parts = []
            if total_created:
                parts.append(f"✅ {total_created} new events created")
            if total_updated:
                parts.append(f"🔄 {total_updated} events updated")
            summary = ", ".join(parts) + ":\n" + "\n".join(all_events)
            await ctx.send(summary)

    @bot.command(name="sync_verbose")
    @commands.has_permissions(administrator=True)
    async def sync_verbose_prefix(ctx: commands.Context):
        guild_id = str(ctx.guild.id)
        teams = SETTINGS.get(guild_id, {}).get("teams", [])
        total_created, total_updated, all_events = 0, 0, []
        for slug in teams:
            created, updated, events = await sync_events_for_guild(
                ctx.guild, SETTINGS, bot, verbose=True, team_slug=slug
            )
            total_created += created
            total_updated += updated
            all_events.extend(events)
        if total_created == 0 and total_updated == 0:
            await ctx.send("ℹ️ No new or updated events.")
        else:
            parts = []
            if total_created:
                parts.append(f"✅ {total_created} new events created")
            if total_updated:
                parts.append(f"🔄 {total_updated} events updated")
            summary = ", ".join(parts) + ":\n" + "\n".join(all_events)
            await ctx.send(summary)
