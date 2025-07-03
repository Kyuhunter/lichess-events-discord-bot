import os
import json
import discord
import logging
from datetime import datetime, timezone
from discord.ext import commands
from dotenv import load_dotenv
from .commands import setup_commands
from .tasks import start_background_tasks

# Ensure config directory for .env
CONFIG_DIR = "config"
os.makedirs(CONFIG_DIR, exist_ok=True)
load_dotenv(dotenv_path=os.path.join(CONFIG_DIR, ".env"))

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
# Ensure runtime files go under data/ only
DATA_DIR = "data"
os.makedirs(DATA_DIR, exist_ok=True)
import logging
# Delay creating the log file until first error is logged
LOG_DIR = os.path.join(DATA_DIR, "log")
os.makedirs(LOG_DIR, exist_ok=True)
logger = logging.getLogger()
logger.setLevel(logging.INFO)
_file_handler = None

def _ensure_file_handler():
    global _file_handler
    if _file_handler is None:
        log_file = os.path.join(LOG_DIR, f"error_log_{datetime.now(timezone.utc):%Y_%m_%d}.log")
        handler = logging.FileHandler(log_file)
        handler.setLevel(logging.ERROR)
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
        logger.addHandler(handler)
        _file_handler = handler

# settings stored in data/
SETTINGS_FILE = os.path.join(DATA_DIR, "settings.json")

intents = discord.Intents.default()
# Enable privileged intent for message content so commands function correctly
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

# Load settings
if os.path.isfile(SETTINGS_FILE):
    with open(SETTINGS_FILE, "r") as f:
        SETTINGS = json.load(f)
else:
    SETTINGS = {}

def save_settings():
    with open(SETTINGS_FILE, "w") as f:
        json.dump(SETTINGS, f, indent=2)

@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"✅ Logged in as {bot.user} (ID: {bot.user.id})")
    start_background_tasks(bot, SETTINGS)

# Setup commands
setup_commands(bot, SETTINGS, save_settings)

# Run bot
bot.run(DISCORD_TOKEN)

# global error handlers - ensure file handler before logging
@bot.event
async def on_command_error(ctx, error):
    _ensure_file_handler()
    logger.error(f"Error in command {ctx.command}: {error}", exc_info=error)

@bot.event
async def on_error(event_method, *args, **kwargs):
    _ensure_file_handler()
    logger.error(f"Unhandled exception in event {event_method}", exc_info=True)
