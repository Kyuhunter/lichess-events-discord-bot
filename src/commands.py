import os
import discord
import aiohttp, json
import sys
from datetime import datetime, timezone
from discord.ext import commands
from .sync import sync_events_for_guild
from .utils import ensure_file_handler, logger
from .cache import cache

# For detecting if we're in a test environment
try:
    from unittest.mock import MagicMock
except ImportError:
    MagicMock = type(None)  # Fallback if not available


def setup_commands(bot: commands.Bot, SETTINGS: dict, save_settings: callable):
    async def log_to_notification_channel(guild: discord.Guild, message: str, event_type=None):
        # Try to use the Discord handler if available
        for handler in logger.handlers:
            if hasattr(handler, 'log_event') and event_type:
                handler.log_event(event_type, message)
                return
        
        # Fallback to direct channel messaging
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
        
        # Validate team slug
        from .utils import validate_team_slug
        slug = validate_team_slug(team)
        if not slug:
            await interaction.response.send_message(
                "❌ Invalid team slug. Team slugs must contain only letters, numbers, hyphens, and underscores.", 
                ephemeral=True
            )
            return
            
        if slug in teams:
            await interaction.response.send_message(f"⚠️ Team `{slug}` is already registered.", ephemeral=True)
            return
        teams.append(slug)
        save_settings()
        await interaction.response.send_message(f"✅ Team `{slug}` added.", ephemeral=True)
        await log_to_notification_channel(interaction.guild, f"Team `{slug}` has been registered.", "create")

    @bot.tree.command(name="remove_team", description="Remove a registered Lichess team")
    @discord.app_commands.describe(team="Registered team slug to remove")
    async def remove_team(interaction: discord.Interaction, team: str):
        """Remove a team, delete its events, and log errors to file if they occur."""
        gid = str(interaction.guild_id)
        teams = SETTINGS.get(gid, {}).get("teams", [])
        
        # Validate team slug
        from .utils import validate_team_slug
        slug = validate_team_slug(team)
        if not slug:
            await interaction.response.send_message(
                "❌ Invalid team slug. Team slugs must contain only letters, numbers, hyphens, and underscores.", 
                ephemeral=True
            )
            return
            
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
            from .cache import cache
            
            # Try getting from cache first
            cached_tournaments = cache.get_tournaments(slug)
            
            if cached_tournaments:
                # Use cached tournament data
                tourney_ids = [t.get('id') for t in cached_tournaments if t.get('id')]
            else:
                # If not in cache, make an API call
                tourney_ids = []
                async with aiohttp.ClientSession() as session:
                    url = f"https://lichess.org/api/team/{slug}/arena"
                    async with session.get(url) as resp:
                        if resp.status == 200:
                            async for line in resp.content:
                                try:
                                    t = json.loads(line.decode().strip())
                                    tourney_ids.append(t.get('id'))
                                except Exception:
                                    continue
            
            # Invalidate cache for this team since it's being removed
            cache.invalidate(slug)
            
            # Delete associated events
            if tourney_ids:
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
                interaction.guild, f"Team `{slug}` removed and {deleted} events deleted.", "delete"
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
            interaction.guild, f"Scheduled sync {status} by user {interaction.user}", "update"
        )

    @bot.tree.command(name="sync", description="Manual sync for teams")
    @discord.app_commands.describe(team="Optional specific team slug to sync")
    @discord.app_commands.checks.has_permissions(administrator=True)
    async def sync_cmd(interaction: discord.Interaction, team: str = None):
        await interaction.response.defer(ephemeral=True)
        gid = str(interaction.guild_id)
        teams = SETTINGS.get(gid, {}).get("teams", [])
        if team:
            # Validate team slug
            from .utils import validate_team_slug
            slug = validate_team_slug(team)
            if not slug:
                await interaction.followup.send(
                    "❌ Invalid team slug. Team slugs must contain only letters, numbers, hyphens, and underscores.", 
                    ephemeral=True
                )
                return
                
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
            # Validate team slug
            from .utils import validate_team_slug
            slug = validate_team_slug(team)
            if not slug:
                await interaction.followup.send(
                    "❌ Invalid team slug. Team slugs must contain only letters, numbers, hyphens, and underscores.", 
                    ephemeral=True
                )
                return
                
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

    # Define a separate function for setup_logging_channel so tests don't break
    async def _setup_logging_channel_implementation(interaction: discord.Interaction, channel):
        gid = str(interaction.guild_id)
        settings = SETTINGS.setdefault(gid, {})
        
        # Validate channel ID
        from .utils import validate_discord_id
        if not validate_discord_id(channel.id):
            await interaction.response.send_message(
                "❌ Invalid channel ID. Please select a valid Discord channel.",
                ephemeral=True
            )
            return
            
        # Check for all required permissions
        perms = channel.permissions_for(interaction.guild.me)
        missing_perms = []
        
        # Essential permissions needed for logging
        if not perms.view_channel:
            missing_perms.append("View Channel")
        if not perms.send_messages:
            missing_perms.append("Send Messages")
        if not perms.embed_links:
            missing_perms.append("Embed Links")
            
        if missing_perms:
            # Ensure error is logged to file
            ensure_file_handler()
            logger.error(f"Permission denied: Missing permissions {', '.join(missing_perms)} in channel {channel.name} ({channel.id}) in guild {interaction.guild.name} ({interaction.guild.id})")
            
            await interaction.response.send_message(
                f"⚠️ I don't have the required permissions in {channel.mention}.\n" +
                "**Missing permissions:**\n" +
                "\n".join(f"- {p}" for p in missing_perms) +
                "\n\nPlease grant these permissions and try again.",
                ephemeral=True
            )
            return
            
        # Save the channel ID
        settings["notification_channel"] = channel.id
        save_settings()
        
        # Send confirmation
        await interaction.response.send_message(
            f"✅ Logging channel set to {channel.mention}.", 
            ephemeral=True
        )
        
        # Send a test message to the channel
        try:
            embed = discord.Embed(
                title="Logging Channel Setup",
                description="✅ This channel has been successfully set up as the logging channel for the Lichess Events bot.",
                color=discord.Color.green()
            )
            embed.add_field(
                name="What to expect",
                value="You will receive:\n• Bot status messages\n• Event notifications (create/update/delete)\n• Error logs based on configured log level",
                inline=False
            )
            embed.add_field(
                name="Configuration",
                value="You can adjust logging settings in `config/config.yaml`\nCurrent log level: `INFO`\nEvent notifications: `Enabled`",
                inline=False
            )
            embed.set_footer(text=f"Setup by {interaction.user} • {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
            
            await channel.send(embed=embed)
            logger.info(f"Logging channel set to {channel.name} ({channel.id}) in guild {interaction.guild.name} ({interaction.guild.id})")
        except discord.Forbidden:
            # Ensure error is logged to file
            ensure_file_handler()
            logger.error(f"Forbidden: Cannot send test message to channel {channel.name} ({channel.id}) in guild {interaction.guild.name} ({interaction.guild.id})")
            
            await interaction.followup.send(
                "⚠️ Failed to send a test message. Please check permissions.", 
                ephemeral=True
            )
        except Exception as e:
            # Log any other errors that might occur
            ensure_file_handler()
            logger.error(f"Error sending test message to channel {channel.name} ({channel.id})", exc_info=e)
            
            await interaction.followup.send(
                "⚠️ An error occurred when sending a test message.", 
                ephemeral=True
            )
    
    # Register the command - we'll use a better test detection method
    is_test_env = 'pytest' in sys.modules or any('pytest' in arg for arg in sys.argv)
    logger.info("Registering setup_logging_channel command")
    
    @bot.tree.command(name="setup_logging_channel", description="Set up a channel for bot logs and event notifications")
    @discord.app_commands.describe(channel="Text channel to use for logging")
    @discord.app_commands.checks.has_permissions(administrator=True)
    async def setup_logging_channel(interaction: discord.Interaction, channel: discord.TextChannel):
        logger.info(f"setup_logging_channel called by {interaction.user}")
        await _setup_logging_channel_implementation(interaction, channel)

    # Add debug command for checking registered commands
    @bot.command(name="debug_commands")
    @commands.has_permissions(administrator=True)
    async def debug_commands(ctx: commands.Context):
        """Debug command to list all registered slash commands"""
        try:
            # Get all commands from the bot's tree
            app_commands = bot.tree.get_commands()
            command_list = [f"/{cmd.name}" for cmd in app_commands]
            
            if command_list:
                await ctx.send(f"📋 Registered slash commands:\n" + "\n".join(command_list))
            else:
                await ctx.send("⚠️ No slash commands are currently registered.")
                
            # Check if setup_logging_channel specifically exists
            has_logging_cmd = any(cmd.name == "setup_logging_channel" for cmd in app_commands)
            await ctx.send(f"setup_logging_channel registered: {'✅ Yes' if has_logging_cmd else '❌ No'}")
            
            # Try syncing the commands again
            try:
                synced = await bot.tree.sync()
                await ctx.send(f"🔄 Re-synced {len(synced)} commands.")
            except Exception as e:
                await ctx.send(f"❌ Error syncing commands: {str(e)}")
        except Exception as e:
            await ctx.send(f"❌ Error retrieving commands: {str(e)}")

    @bot.command(name="check_perms")
    @commands.has_permissions(administrator=True)
    async def check_channel_permissions(ctx: commands.Context, channel_id: int = None):
        """Check bot permissions in the specified channel or current channel"""
        channel = None
        
        if channel_id:
            # Validate channel ID
            from .utils import validate_discord_id
            if not validate_discord_id(channel_id):
                await ctx.send("❌ Invalid channel ID format.")
                return
                
            channel = ctx.guild.get_channel(channel_id)
            if not channel:
                await ctx.send(f"⚠️ Couldn't find channel with ID {channel_id}")
                return
        else:
            channel = ctx.channel
        
        # Get bot's permissions in this channel
        perms = channel.permissions_for(ctx.guild.me)
        
        # Format permissions as readable text
        permission_list = []
        for name, value in perms:
            status = "✅" if value else "❌"
            permission_list.append(f"{status} {name}")
        
        # Group into allowed and denied
        allowed = [p for p in permission_list if p.startswith("✅")]
        denied = [p for p in permission_list if p.startswith("❌")]
        
        # Send report
        embed = discord.Embed(
            title=f"Permissions in #{channel.name}",
            description=f"Bot permissions in <#{channel.id}>",
            color=discord.Color.blue()
        )
        
        if allowed:
            embed.add_field(name="✅ Allowed", value="\n".join(allowed[:20]), inline=False)
            if len(allowed) > 20:
                embed.add_field(name="✅ Allowed (cont.)", value="\n".join(allowed[20:]), inline=False)
        
        if denied:
            embed.add_field(name="❌ Denied", value="\n".join(denied[:20]), inline=False)
            if len(denied) > 20:
                embed.add_field(name="❌ Denied (cont.)", value="\n".join(denied[20:]), inline=False)
        
        # Log to file too
        ensure_file_handler()
        logger.info(f"Permission check in channel {channel.name} ({channel.id})")
        for perm in denied:
            if "send_messages" in perm or "view_channel" in perm or "embed_links" in perm:
                logger.warning(f"Critical permission missing: {perm}")
        
        await ctx.send(embed=embed)

    @bot.tree.command(name="verify_logging_channel", description="Check if the current logging channel is set up correctly")
    @discord.app_commands.checks.has_permissions(administrator=True)
    async def verify_logging_channel(interaction: discord.Interaction):
        """Verify that the logging channel is correctly set up and the bot has proper permissions"""
        await interaction.response.defer(ephemeral=True)
        gid = str(interaction.guild_id)
        settings = SETTINGS.get(gid, {})
        
        # Check if a notification channel is set
        channel_id = settings.get("notification_channel")
        if not channel_id:
            await interaction.followup.send("❌ No logging channel has been set up. Use `/setup_logging_channel` first.")
            return
            
        # Validate channel ID
        from .utils import validate_discord_id
        if not validate_discord_id(channel_id):
            await interaction.followup.send("❌ Invalid channel ID in settings. Please use `/setup_logging_channel` again.")
            return
            
        # Get the channel
        channel = interaction.guild.get_channel(channel_id)
        if not channel:
            ensure_file_handler()
            logger.error(f"Logging channel {channel_id} not found in guild {interaction.guild.name} ({interaction.guild.id})")
            await interaction.followup.send(f"❌ Configured channel (ID: {channel_id}) not found. It may have been deleted.")
            return
            
        # Check permissions
        perms = channel.permissions_for(interaction.guild.me)
        missing_perms = []
        
        # Essential permissions
        if not perms.view_channel:
            missing_perms.append("View Channel")
        if not perms.send_messages:
            missing_perms.append("Send Messages")
        if not perms.embed_links:
            missing_perms.append("Embed Links")
            
        # Report results
        if missing_perms:
            # Log the issue
            ensure_file_handler()
            logger.error(f"Missing permissions in logging channel {channel.name} ({channel_id}): {', '.join(missing_perms)}")
            
            await interaction.followup.send(
                f"⚠️ Missing required permissions in {channel.mention}:\n" +
                "\n".join(f"- {p}" for p in missing_perms) +
                "\n\nPlease update the channel permissions and try again."
            )
        else:
            # Send a test message to the channel
            try:
                test_msg = await channel.send("🔄 Testing logging channel... This is a test message.")
                await interaction.followup.send(f"✅ Logging channel {channel.mention} is properly configured!")
                await test_msg.delete()  # Clean up the test message
            except Exception as e:
                ensure_file_handler()
                logger.error(f"Error testing logging channel {channel.name} ({channel_id})", exc_info=e)
                await interaction.followup.send(f"❌ Error testing channel: {str(e)}")

    @bot.tree.command(name="status", description="Check bot status and health")
    async def status(interaction: discord.Interaction):
        """Check the status and health of the bot."""
        try:
            await interaction.response.defer(ephemeral=True)
            
            embed = discord.Embed(
                title="Bot Status",
                color=discord.Color.green(),
                timestamp=datetime.now(timezone.utc)
            )
            
            # Bot information
            bot_info = []
            
            # Handle test environment (bot.user might be None)
            if bot.user:
                bot_info.extend([
                    f"Name: {bot.user.name}",
                    f"ID: {bot.user.id}",
                ])
            else:
                bot_info.append("Name: [Test Environment]")
            
            # Add uptime if available
            if hasattr(bot, 'launch_time'):
                uptime = datetime.now(timezone.utc) - datetime.fromtimestamp(bot.launch_time, timezone.utc)
                bot_info.append(f"Uptime: {uptime}")
            else:
                bot_info.append("Uptime: Unknown")
                
            bot_info.append(f"Servers: {len(bot.guilds)}")
            
            embed.add_field(name="Bot Info", value="\n".join(bot_info), inline=False)
            
            # Guild-specific information
            gid = str(interaction.guild_id)
            guild_settings = SETTINGS.get(gid, {})
            
            # Team settings
            teams = guild_settings.get("teams", [])
            teams_info = "No teams registered" if not teams else "\n".join(teams)
            embed.add_field(name="Teams", value=teams_info, inline=True)
            
            # Auto-sync status
            auto_sync = guild_settings.get("auto_sync", True)
            embed.add_field(name="Auto Sync", value="Enabled" if auto_sync else "Disabled", inline=True)
            
            # Notification channel
            notif_channel_id = guild_settings.get("notification_channel")
            notif_channel = "Not configured"
            if notif_channel_id:
                channel = interaction.guild.get_channel(notif_channel_id)
                notif_channel = f"#{channel.name}" if channel else f"Invalid channel ({notif_channel_id})"
            embed.add_field(name="Notification Channel", value=notif_channel, inline=True)
            
            # Bot permissions check
            if bot.user and interaction.guild:
                bot_member = interaction.guild.get_member(bot.user.id)
                if bot_member:
                    perms = interaction.channel.permissions_for(bot_member)
                    required_perms = {
                        "Send Messages": perms.send_messages,
                        "Embed Links": perms.embed_links,
                        "Manage Events": perms.manage_events,
                        "Read Message History": perms.read_message_history,
                    }
                    
                    perm_status = "\n".join([f"{perm}: {'✅' if has else '❌'}" for perm, has in required_perms.items()])
                    embed.add_field(name="Permissions", value=perm_status, inline=False)
                else:
                    embed.add_field(name="Permissions", value="Could not check permissions", inline=False)
            else:
                # Fallback for test environment
                embed.add_field(name="Permissions", value="Not available in test environment", inline=False)
            
            await interaction.followup.send(embed=embed, ephemeral=True)
        
        except Exception as e:
            ensure_file_handler()
            logger.error(f"Error in status command", exc_info=e)
            await interaction.followup.send(
                "⚠️ Error checking bot status. Please check logs.", ephemeral=True
            )
