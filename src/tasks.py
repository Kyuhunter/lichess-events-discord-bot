import os
from discord.ext import tasks
from .sync import sync_events_for_guild


def start_background_tasks(bot, SETTINGS):
    @tasks.loop(seconds=int(os.getenv("CHECK_INTERVAL", 300)))
    async def check_tournaments():
        for guild in bot.guilds:
            created, created_events = await sync_events_for_guild(guild, SETTINGS, bot, verbose=False)
            # Notification logging is already handled in sync_events_for_guild

    check_tournaments.start()
