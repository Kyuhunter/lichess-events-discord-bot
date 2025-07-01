import os
import json
import asyncio
import discord
from discord.ext import tasks, commands
import aiohttp
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv()

DISCORD_TOKEN   = os.getenv("DISCORD_TOKEN")
CHECK_INTERVAL  = int(os.getenv("CHECK_INTERVAL", 300))
SETTINGS_FILE   = "settings.json"

intents = discord.Intents.default()
intents.message_content = True  # nur, um die Warnung zu unterdrücken

bot = commands.Bot(command_prefix="!", intents=intents)

# Einstellungen laden
if os.path.isfile(SETTINGS_FILE):
    with open(SETTINGS_FILE, "r") as f:
        SETTINGS = json.load(f)
else:
    SETTINGS = {}

def save_settings():
    with open(SETTINGS_FILE, "w") as f:
        json.dump(SETTINGS, f, indent=2)

async def sync_events_for_guild(guild: discord.Guild, verbose: bool = False) -> int | None:
    gid = str(guild.id)
    team = SETTINGS.get(gid)
    if not team:
        if verbose:
            print(f"[{guild.name}] Kein Team registriert, überspringe.")
        return None

    # Rechte prüfen
    me = guild.me or guild.get_member(bot.user.id)
    if not me or not me.guild_permissions.manage_events:
        print(f"[{guild.name}] ❌ Fehlende Berechtigung: Manage Events")
        return 0

    # Bereits existierende Event-URLs einmalig laden
    try:
        existing_events = await guild.fetch_scheduled_events()
    except discord.Forbidden:
        print(f"[{guild.name}] ❌ Forbidden beim Abruf existierender Events.")
        return 0
    seen_urls = {ev.location for ev in existing_events if ev.location}

    created = 0
    url = f"https://lichess.org/api/team/{team}/arena"
    now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)

    if verbose:
        print(f"[{guild.name}] sync_verbose startet für Team '{team}'")

    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            if resp.status != 200:
                print(f"[{guild.name}] ⚠️ Lichess-API returned HTTP {resp.status}")
                return created

            # Zeile für Zeile lesen, bis 1s Timeout
            while True:
                try:
                    line = await asyncio.wait_for(resp.content.readline(), timeout=1.0)
                except asyncio.TimeoutError:
                    if verbose:
                        print(f"[{guild.name}] Keine neuen Zeilen in 1s, beendet.")
                    break
                if not line:
                    if verbose:
                        print(f"[{guild.name}] Stream geschlossen, beendet.")
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
                        print(f"[{guild.name}] ⚠️ JSON-Fehler, skip.")
                    continue

                starts_at = t.get("startsAt", 0)
                if starts_at <= now_ms:
                    if verbose:
                        print(f"[{guild.name}] Tournament {t.get('id')} schon gestartet, skip.")
                    continue

                # Baue URL und prüfe auf Duplikat
                url_tourney = f"https://lichess.org/tournament/{t['id']}"
                if url_tourney in seen_urls:
                    if verbose:
                        print(f"[{guild.name}] Event {url_tourney} existiert schon, skip.")
                    continue

                # Konvertiere Zeiten
                start_time   = datetime.fromtimestamp(starts_at / 1000, tz=timezone.utc)
                finishes_at  = t.get("finishesAt", starts_at + 60*60*1000)
                end_time     = datetime.fromtimestamp(finishes_at / 1000, tz=timezone.utc)

                # Event anlegen
                try:
                    await guild.create_scheduled_event(
                        name=t.get("fullName", f"Arena {t['id']}"),
                        description=(
                            f"**Lichess Arena-Turnier**\n"
                            f"• {start_time.strftime('%Y-%m-%d %H:%M UTC')} – "
                            f"{end_time.strftime('%H:%M UTC')}\n"
                            f"• {t.get('minutes')} min · +{t.get('clock', {}).get('increment',0)}s\n\n"
                            f"{url_tourney}"
                        ),
                        start_time=start_time,
                        end_time=end_time,
                        entity_type=discord.EntityType.external,
                        location=url_tourney,
                        privacy_level=discord.PrivacyLevel.guild_only
                    )
                    created += 1
                    seen_urls.add(url_tourney)
                    print(f"[{guild.name}] 📅 Neues Event erstellt: {t.get('fullName')} ({t['id']})")
                except discord.Forbidden:
                    print(f"[{guild.name}] ❌ Forbidden beim Erstellen von {url_tourney}")
                    return created
                except Exception as e:
                    print(f"[{guild.name}] ⚠️ Fehler beim Erstellen von {url_tourney}: {e}")
                    continue

    if verbose:
        print(f"[{guild.name}] sync_verbose fertig: {created} neue Events.")
    return created

@bot.event
async def on_ready():
    # einmalig Slash-Commands syncen
    await bot.tree.sync()
    print(f"✅ Eingeloggt als {bot.user} (ID: {bot.user.id})")
    check_tournaments.start()

# Slash-Commands
@bot.tree.command(name="setup_team", description="Registriere dein Lichess-Team")
@discord.app_commands.describe(team="Lichess-Team-Slug (z.B. lichess-de)")
async def setup_team(interaction: discord.Interaction, team: str):
    SETTINGS[str(interaction.guild_id)] = team.strip()
    save_settings()
    await interaction.response.send_message(f"✅ Team `{team}` gespeichert.", ephemeral=True)

@bot.tree.command(name="remove_team", description="Entferne die Registrierung")
async def remove_team(interaction: discord.Interaction):
    if SETTINGS.pop(str(interaction.guild_id), None):
        save_settings()
        await interaction.response.send_message("🗑️ Registrierung entfernt.", ephemeral=True)
    else:
        await interaction.response.send_message("ℹ️ Kein Team registriert.", ephemeral=True)

@bot.tree.command(name="sync", description="Manueller Sync (still)")
@discord.app_commands.checks.has_permissions(administrator=True)
async def sync_cmd(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    result = await sync_events_for_guild(interaction.guild, verbose=False)
    if result is None:
        await interaction.followup.send("ℹ️ Kein Team registriert. Nutze `/setup_team`.", ephemeral=True)
    else:
        await interaction.followup.send(f"✅ {result} neue Events.", ephemeral=True)

@bot.tree.command(name="sync_verbose", description="Sync + ausführliches Logging")
@discord.app_commands.checks.has_permissions(administrator=True)
async def sync_verbose_cmd(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    result = await sync_events_for_guild(interaction.guild, verbose=True)
    if result is None:
        await interaction.followup.send("ℹ️ Kein Team registriert. Nutze `/setup_team`.", ephemeral=True)
    else:
        await interaction.followup.send(
            f"✅ sync_verbose: {result} neue Events. Details in Konsole.",
            ephemeral=True
        )

# Prefix-Fallbacks
@bot.command(name="sync")
@commands.has_permissions(administrator=True)
async def sync_prefix(ctx: commands.Context):
    created = await sync_events_for_guild(ctx.guild, verbose=False)
    if created is None:
        await ctx.send("ℹ️ Kein Team registriert. Verwende `!setup_team`.")
    else:
        await ctx.send(f"✅ {created} neue Events erstellt.")

@bot.command(name="sync_verbose")
@commands.has_permissions(administrator=True)
async def sync_verbose_prefix(ctx: commands.Context):
    created = await sync_events_for_guild(ctx.guild, verbose=True)
    if created is None:
        await ctx.send("ℹ️ Kein Team registriert. Verwende `!setup_team`.")
    else:
        await ctx.send("✅ sync_verbose abgeschlossen. Sieh die Console-Logs.")

# Hintergrund-Task
@tasks.loop(seconds=CHECK_INTERVAL)
async def check_tournaments():
    for guild in bot.guilds:
        await sync_events_for_guild(guild, verbose=False)

if __name__ == "__main__":
    bot.run(DISCORD_TOKEN)

