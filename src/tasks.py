import os
import yaml
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from .sync import sync_events_for_guild
from .utils import ensure_file_handler, logger
from .cache import cache


def start_background_tasks(bot, SETTINGS):
    """
    Schedule periodic sync jobs based on cron settings from config/config.yaml.
    """
    # Load scheduler settings
    cfg_path = os.path.join(os.getcwd(), "config", "config.yaml")
    try:
        with open(cfg_path) as f:
            conf = yaml.safe_load(f)
    except Exception as e:
        logger.error(f"Failed to load scheduler config: {e}")
        conf = {}

    sched_conf = conf.get("scheduler", {})
    cron_expr = sched_conf.get("cron", "*/5 * * * *")
    default_auto = sched_conf.get("auto_sync", True)

    scheduler = AsyncIOScheduler()
    trigger = CronTrigger.from_crontab(cron_expr)

    async def sync_job():
        from .sync import fetch_scheduled_events_for_guilds
        
        # Fetch all events for all guilds in one batch
        try:
            guild_events = await fetch_scheduled_events_for_guilds(bot)
        except Exception as e:
            ensure_file_handler()
            logger.error(f"Error fetching events in bulk: {e}", exc_info=e)
            guild_events = {}
        
        # Process each guild
        for guild in bot.guilds:
            gid = str(guild.id)
            auto = SETTINGS.get(gid, {}).get("auto_sync", default_auto)
            if not auto:
                continue
            try:
                # Pass pre-fetched events if available
                prefetched_events = guild_events.get(guild.id, None)
                await sync_events_for_guild(guild, SETTINGS, bot, verbose=False, prefetched_events=prefetched_events)
            except Exception as e:
                ensure_file_handler()
                logger.error(f"Error syncing tournaments for guild {guild.id}", exc_info=e)

    scheduler.add_job(sync_job, trigger)
    scheduler.start()
