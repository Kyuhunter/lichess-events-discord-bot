import os
import json
import discord
import logging
from datetime import datetime, timezone
from discord.ext import commands
from dotenv import load_dotenv
from .commands import setup_commands
from .tasks import start_background_tasks
from .utils import ensure_file_handler, logger, setup_discord_handler

# Ensure config directory for .env
CONFIG_DIR = "config"
os.makedirs(CONFIG_DIR, exist_ok=True)
load_dotenv(dotenv_path=os.path.join(CONFIG_DIR, ".env"))

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
# Ensure runtime files go under data/ only
DATA_DIR = "data"
os.makedirs(DATA_DIR, exist_ok=True)

# settings stored in data/
SETTINGS_FILE = os.path.join(DATA_DIR, "settings.json")

intents = discord.Intents.default()
# Enable privileged intent for message content so commands function correctly
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

# Track launch time for status command
bot.launch_time = datetime.now(timezone.utc).timestamp()

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
    # Sync command tree and log available commands
    commands = await bot.tree.sync()
    command_names = [cmd.name for cmd in commands]
    print(f"✅ Logged in as {bot.user} (ID: {bot.user.id})")
    print(f"🔄 Synced {len(command_names)} commands: {', '.join(command_names)}")
    logger.info(f"Bot ready with commands: {', '.join(command_names)}")
    
    # Set up Discord logging handler
    discord_handler = setup_discord_handler(bot, SETTINGS)
    logger.info("Discord logging handler initialized")
    
    # Start background tasks
    start_background_tasks(bot, SETTINGS)

# Setup commands
setup_commands(bot, SETTINGS, save_settings)

# Run bot
bot.run(DISCORD_TOKEN)

# global error handlers - ensure file handler before logging
@bot.event
async def on_command_error(ctx, error):
    ensure_file_handler()
    logger.error(f"Error in command {ctx.command}: {error}", exc_info=error)

@bot.event
async def on_error(event_method, *args, **kwargs):
    ensure_file_handler()
    logger.error(f"Unhandled exception in event {event_method}", exc_info=True)
