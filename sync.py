from typing import Optional, Tuple
import aiohttp
import asyncio
import discord
from discord.ext import commands
from datetime import datetime, timezone
import json

async def log_to_notification_channel(guild: discord.Guild, SETTINGS: dict, message: str):
    guild_id = str(guild.id)
    channel_id = SETTINGS.get(guild_id, {}).get("notification_channel")
    if channel_id:
        channel = guild.get_channel(channel_id)
        if channel:
            await channel.send(message)

async def sync_events_for_guild(
    guild: discord.Guild, SETTINGS: dict, bot: commands.Bot, verbose: bool = False
) -> Tuple[int, list[str]]:
    gid = str(guild.id)
    team = SETTINGS.get(gid, {}).get("team")  # Ensure team is fetched from the dictionary
    if not team:
        if verbose:
            print(f"[{guild.name}] No team registered, skipping.")
        return 0, []

    # Check permissions
    me = guild.me or guild.get_member(bot.user.id)
    if not me or not me.guild_permissions.manage_events:
        print(f"[{guild.name}] ❌ Missing permission: Manage Events")
        return 0, []

    # Fetch existing events
    try:
        existing_events = await guild.fetch_scheduled_events()
    except discord.Forbidden:
        print(f"[{guild.name}] ❌ Forbidden when fetching existing events.")
        return 0, []
    existing_map = {ev.location: ev for ev in existing_events if ev.location}

    created = 0
    created_events = []
    url = f"https://lichess.org/api/team/{team}/arena"
    now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)

    if verbose:
        print(f"[{guild.name}] Starting verbose sync for team '{team}'")

    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            if resp.status != 200:
                print(f"[{guild.name}] ⚠️ Lichess API returned HTTP {resp.status}")
                return created, created_events

            # Read line by line with timeout
            while True:
                try:
                    line = await asyncio.wait_for(resp.content.readline(), timeout=1.0)
                except asyncio.TimeoutError:
                    if verbose:
                        print(f"[{guild.name}] No new lines in 1s, ending.")
                    break
                if not line:
                    if verbose:
                        print(f"[{guild.name}] Stream closed, ending.")
                    break

                raw = line.decode().strip()
                if not raw:
                    continue
                if verbose:
                    print(f"[{guild.name}] RAW LINE: {raw}")

                try:
                    t = json.loads(raw)
                except json.JSONDecodeError:
                    if verbose:
                        print(f"[{guild.name}] ⚠️ JSON error, skipping.")
                    continue

                starts_at = t.get("startsAt", 0)
                if starts_at <= now_ms:
                    if verbose:
                        print(f"[{guild.name}] Tournament {t.get('id')} already started, skipping.")
                    continue

                # Convert times (must happen before update logic)
                start_time = datetime.fromtimestamp(starts_at / 1000, tz=timezone.utc)
                finishes_at = t.get("finishesAt", starts_at + 60 * 60 * 1000)
                end_time = datetime.fromtimestamp(finishes_at / 1000, tz=timezone.utc)

                # Build URL and check for duplicates
                url_tourney = f"https://lichess.org/tournament/{t['id']}"
                name = t.get("fullName", f"Arena {t['id']}")
                desc = (
                    f"**Lichess Arena Tournament**\n"
                    f"• {start_time:%Y-%m-%d %H:%M UTC} – {end_time:%H:%M UTC}\n"
                    f"• {t.get('minutes')} min · +{t.get('clock', {}).get('increment', 0)}s\n\n"
                    f"{url_tourney}"
                )

                # if already exists by URL, update its details
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
                                guild, SETTINGS, f"🔄 Updated event: {name} ({t['id']})"
                            )
                            if verbose:
                                print(f"[{guild.name}] 🔄 Updated event {url_tourney}")
                        except Exception as e:
                            print(f"[{guild.name}] ⚠️ Error updating {url_tourney}: {e}")
                    continue

                # Create event
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
                    print(f"[{guild.name}] 📅 New event created: {t.get('fullName')} ({t['id']})")
                except discord.Forbidden:
                    print(f"[{guild.name}] ❌ Forbidden when creating {url_tourney}")
                    return created, created_events
                except Exception as e:
                    print(f"[{guild.name}] ⚠️ Error when creating {url_tourney}: {e}")
                    continue

    if created > 0:
        event_list = "\n".join(created_events)
        await log_to_notification_channel(
            guild, SETTINGS, f"✅ Sync completed: {created} new events created:\n{event_list}"
        )

    if verbose:
        print(f"[{guild.name}] Verbose sync finished: {created} new events.")
    else:
        print(f"[{guild.name}] Sync finished: {created} new events.")
    return created, created_events