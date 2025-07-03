import os
from discord.ext import tasks
from .sync import sync_events_for_guild
from .utils import ensure_file_handler, logger


def start_background_tasks(bot, SETTINGS):
    @tasks.loop(seconds=int(os.getenv("CHECK_INTERVAL", 300)))
    async def check_tournaments():
        for guild in bot.guilds:
            try:
                # sync_events_for_guild now returns (created, updated, events)
                created, updated, events = await sync_events_for_guild(guild, SETTINGS, bot, verbose=False)
            except Exception as e:
                # ensure file handler is attached before logging
                ensure_file_handler()
                logger.error(f"Error syncing tournaments for guild {guild.id}", exc_info=e)
            # notification logging (created/updated) is done inside sync_events_for_guild

    check_tournaments.start()
