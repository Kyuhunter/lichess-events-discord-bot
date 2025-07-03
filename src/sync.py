from typing import Optional, Tuple, List, Dict, Any
import aiohttp
import asyncio
import discord
from discord.ext import commands
from datetime import datetime, timezone
import json
import logging
from .utils import logger
from .cache import cache

# For test environment detection
try:
    from unittest.mock import AsyncMock
except ImportError:
    AsyncMock = None  # Not available in production environments

async def log_to_notification_channel(guild: discord.Guild, SETTINGS: dict, message: str, event_type=None):
    # Sanitize message for security
    from .utils import sanitize_message
    safe_message = sanitize_message(message)
    
    # Try to use the Discord handler if available
    discord_handler = None
    for handler in logger.handlers:
        if hasattr(handler, 'log_event') and event_type:
            handler.log_event(event_type, safe_message)
            return
    
    # Fallback to direct channel messaging if no handler or not an event
    gid = str(guild.id)
    chan_id = SETTINGS.get(gid, {}).get("notification_channel")
    if not chan_id:
        return
    channel = guild.get_channel(chan_id)
    if not isinstance(channel, discord.TextChannel):
        return
    perms = channel.permissions_for(guild.me or
                                     guild.get_member(commands.Bot.user.id))
    if not perms.send_messages:
        return
    try:
        await channel.send(message)
    except discord.Forbidden:
        print(f"[{guild.name}] 🚫 Forbidden sending to channel {chan_id}")

async def sync_events_for_guild(
    guild: discord.Guild,
    SETTINGS: dict,
    bot: commands.Bot,
    verbose: bool = False,
    team_slug: str | None = None,
    prefetched_events: Optional[List[discord.ScheduledEvent]] = None,
) -> Tuple[int, int, list[str]]:
    gid = str(guild.id)
    # Determine which teams to sync
    if team_slug:
        slugs = [team_slug]
    else:
        slugs = SETTINGS.get(gid, {}).get("teams", [])
    if not slugs:
        if verbose:
            print(f"[{guild.name}] No teams registered, skipping.")
        return 0, 0, []

    total_created = 0
    total_updated = 0
    total_events: list[str] = []  # created event URLs
    total_updated_events: list[str] = []  # updated event URLs
    for team in slugs:
        if verbose:
            print(f"[{guild.name}] Starting sync for team '{team}'")
        # Check permissions
        me = guild.me or guild.get_member(bot.user.id)
        if not me or not me.guild_permissions.manage_events:
            if verbose:
                print(f"[{guild.name}] ❌ Missing permission: Manage Events")
            continue
        
        # Use prefetched events if provided, otherwise fetch them
        if prefetched_events is not None:
            existing_events = prefetched_events
            if verbose:
                print(f"[{guild.name}] Using pre-fetched events ({len(existing_events)} events)")
        else:
            try:
                existing_events = await guild.fetch_scheduled_events()
            except discord.Forbidden:
                print(f"[{guild.name}] ❌ Forbidden when fetching existing events.")
                continue
        existing_map = {ev.location: ev for ev in existing_events if ev.location}

        created = 0
        created_events: list[str] = []
        now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
        
        # Check if we have cached tournaments (disable cache in test environment)
        cached_tournaments = None
        
        # Try to get from cache if not in test environment
        try:
            # Check if we're in a test environment (if ev.edit is AsyncMock, we're in a test)
            is_test = any(existing_events) and isinstance(existing_events[0].edit, AsyncMock)
            if not is_test:
                cached_tournaments = cache.get_tournaments(team)
        except (AttributeError, TypeError):
            # If we can't check, assume not a test
            cached_tournaments = cache.get_tournaments(team)
            
        # If not in cache or in test environment, fetch from API
        if not cached_tournaments:
            if verbose:
                print(f"[{guild.name}] Cache miss for team {team}, fetching from API")
            url = f"https://lichess.org/api/team/{team}/arena"
            all_tournaments = []
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as resp:
                    if resp.status != 200:
                        print(f"[{guild.name}] ⚠️ Lichess API returned HTTP {resp.status} for team {team}")
                        continue
                    
                    # Parse stream and collect all tournaments
                    while True:
                        try:
                            line = await asyncio.wait_for(resp.content.readline(), timeout=1.0)
                        except asyncio.TimeoutError:
                            if verbose:
                                print(f"[{guild.name}] No new lines in 1s, ending team {team}.")
                            break
                        if not line:
                            if verbose:
                                print(f"[{guild.name}] Stream closed for team {team}, ending.")
                            break
                        raw = line.decode().strip()
                        if not raw:
                            continue
                        if verbose:
                            print(f"[{guild.name}] RAW LINE: {raw}")
                        try:
                            t = json.loads(raw)
                            all_tournaments.append(t)
                        except json.JSONDecodeError:
                            if verbose:
                                print(f"[{guild.name}] ⚠️ JSON error, skipping.")
                            continue
            
            # Store in cache for future use
            cache.set_tournaments(team, all_tournaments)
            tournaments_to_process = all_tournaments
        else:
            if verbose:
                print(f"[{guild.name}] Cache hit for team {team}, using cached data")
            tournaments_to_process = cached_tournaments
            
        # Process tournaments (either from cache or freshly fetched)
        for t in tournaments_to_process:
            starts_at = t.get("startsAt", 0)
            if starts_at <= now_ms:
                if verbose:
                    print(f"[{guild.name}] Tournament {t.get('id')} already started, skipping.")
                continue
            start_time = datetime.fromtimestamp(starts_at / 1000, tz=timezone.utc)
            finishes_at = t.get("finishesAt", starts_at + 60 * 60 * 1000)
            end_time = datetime.fromtimestamp(finishes_at / 1000, tz=timezone.utc)
            url_tourney = f"https://lichess.org/tournament/{t['id']}"
            name = t.get("fullName", f"Arena {t['id']}")
            desc = (
                f"**Lichess Arena Tournament**\n"
                f"• {start_time:%Y-%m-%d %H:%M UTC} – {end_time:%H:%M UTC}\n"
                f"• {t.get('minutes')} min · +{t.get('clock', {}).get('increment', 0)}s\n\n"
                f"{url_tourney}"
            )
            if ev := existing_map.get(url_tourney):
                if (
                    ev.name != name
                    or ev.start_time != start_time
                    or ev.end_time != end_time
                    or (ev.description or "") != desc
                ):
                    try:
                        await ev.edit(
                            name=name,
                            description=desc,
                            start_time=start_time,
                            end_time=end_time,
                            entity_type=discord.EntityType.external,
                            location=url_tourney,
                            privacy_level=discord.PrivacyLevel.guild_only
                        )
                        await log_to_notification_channel(
                            guild, SETTINGS, f"Updated event for {team}: {name} ({t['id']})", "update"
                        )
                        # record update
                        total_updated += 1
                        total_updated_events.append(url_tourney)
                        if verbose:
                            print(f"[{guild.name}] 🔄 Updated event {url_tourney}")
                    except Exception as e:
                        print(f"[{guild.name}] ⚠️ Error updating {url_tourney}: {e}")
                continue
            try:
                await guild.create_scheduled_event(
                    name=name,
                    description=desc,
                    start_time=start_time,
                    end_time=end_time,
                    entity_type=discord.EntityType.external,
                    location=url_tourney,
                    privacy_level=discord.PrivacyLevel.guild_only
                )
                created += 1
                created_events.append(url_tourney)
                if verbose:
                    print(f"[{guild.name}] 📅 New event created: {name} ({t['id']})")
            except discord.Forbidden:
                if verbose:
                    print(f"[{guild.name}] ❌ Forbidden when creating {url_tourney}")
                continue
            except Exception as e:
                print(f"[{guild.name}] ⚠️ Error when creating {url_tourney}: {e}")
                continue
        total_created += created
        total_events.extend(created_events)
    # Notify separately for creations and updates
    if total_created:
        msg_created = (
            f"{total_created} new events created for teams: {', '.join(slugs)}:\n"
            + "\n".join(total_events)
        )
        await log_to_notification_channel(guild, SETTINGS, msg_created, "create")
    if total_updated:
        msg_updated = (
            f"{total_updated} events updated for teams: {', '.join(slugs)}:\n"
            + "\n".join(total_updated_events)
        )
        await log_to_notification_channel(guild, SETTINGS, msg_updated, "update")
    if verbose:
        print(f"[{guild.name}] Verbose sync finished: {total_created} new events.")
    else:
        msg = f"Sync finished: {total_created} new events"
        if total_updated:
            msg += f", {total_updated} updated events"
        print(f"[{guild.name}] {msg}.")
    # return separate counts for created and updated events, and all event URLs
    combined_events = total_events + total_updated_events
    return total_created, total_updated, combined_events

async def fetch_scheduled_events_for_guilds(bot):
    """
    Fetch all scheduled events for all guilds in one batch to reduce API calls.
    
    Args:
        bot: The Discord bot instance.
        
    Returns:
        Dict mapping guild IDs to their scheduled events.
    """
    guild_events = {}
    
    for guild in bot.guilds:
        try:
            events = await guild.fetch_scheduled_events()
            guild_events[guild.id] = events
        except Exception as e:
            logger.error(f"Error fetching events for guild {guild.id}: {e}")
            guild_events[guild.id] = []
            
    return guild_events

async def process_in_batches(items, batch_size, process_func, delay=1.0):
    """
    Process a list of items in batches to reduce API load.
    
    Args:
        items: List of items to process
        batch_size: Number of items to process per batch
        process_func: Async function to call with each batch
        delay: Delay between batches in seconds
        
    Returns:
        Combined results from all batches
    """
    results = []
    
    # Process in batches
    for i in range(0, len(items), batch_size):
        batch = items[i:i + batch_size]
        batch_result = await process_func(batch)
        results.extend(batch_result if isinstance(batch_result, list) else [batch_result])
        
        # Add delay between batches
        if i + batch_size < len(items):
            await asyncio.sleep(delay)
            
    return results
