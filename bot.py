import os
import json
import discord
from discord.ext import commands
from dotenv import load_dotenv
from commands import setup_commands
from tasks import start_background_tasks

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
SETTINGS_FILE = "settings.json"

intents = discord.Intents.default()
intents.message_content = False  # Disable privileged intent if not needed

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

if __name__ == "__main__":
    bot.run(DISCORD_TOKEN)

