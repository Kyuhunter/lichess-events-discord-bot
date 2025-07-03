from typing import Optional, Tuple
import aiohttp
import asyncio
import discord
from discord.ext import commands
from datetime import datetime, timezone
import json

async def log_to_notification_channel(guild: discord.Guild, SETTINGS: dict, message: str):
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
        # Fetch existing events
        try:
            existing_events = await guild.fetch_scheduled_events()
        except discord.Forbidden:
            print(f"[{guild.name}] ❌ Forbidden when fetching existing events.")
            continue
        existing_map = {ev.location: ev for ev in existing_events if ev.location}

        created = 0
        created_events: list[str] = []
        url = f"https://lichess.org/api/team/{team}/arena"
        now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)

        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                if resp.status != 200:
                    print(f"[{guild.name}] ⚠️ Lichess API returned HTTP {resp.status} for team {team}")
                    continue
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
                    except json.JSONDecodeError:
                        if verbose:
                            print(f"[{guild.name}] ⚠️ JSON error, skipping.")
                        continue
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
                                    guild, SETTINGS, f"🔄 Updated event for {team}: {name} ({t['id']})"
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
            f"✅ {total_created} new events created for teams: {', '.join(slugs)}:\n"
            + "\n".join(total_events)
        )
        await log_to_notification_channel(guild, SETTINGS, msg_created)
    if total_updated:
        msg_updated = (
            f"🔄 {total_updated} events updated for teams: {', '.join(slugs)}:\n"
            + "\n".join(total_updated_events)
        )
        await log_to_notification_channel(guild, SETTINGS, msg_updated)
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
