# Lichess Events Discord Bot

This bot synchronizes Lichess arena tournaments with Discord events for registered teams.

## Features

- Automatically fetches Lichess tournaments for registered teams.
- Creates Discord events for upcoming tournaments.
- Supports manual sync and verbose logging.
- Slash commands and prefix-based commands for easy interaction.

## Prerequisites

- Python 3.8 or higher
- A Discord bot token
- A Lichess team slug
- `pip` for installing dependencies

## Setup Instructions

### 1. Clone the Repository

```bash
git clone https://github.com/your-repo/lichess-events-discord-bot.git
cd lichess-events-discord-bot
```

### 2. Create a config/.env File
Rename `config/.env.sample` to `config/.env` and add your Discord token:
```bash
mkdir -p config
mv config/.env.sample config/.env
nano config/.env
```

### 3. Setup the Python environment
```bash
python -m venv venv
source venv/bin/activate
pip install python-dotenv discord.py
```

### 4. Run the Bot
Start the bot using the package entrypoint:
```bash
python -m src.bot
```