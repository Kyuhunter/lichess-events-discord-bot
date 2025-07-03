import os
import json
import discord
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
