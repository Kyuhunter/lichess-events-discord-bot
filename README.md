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
- Enable the **Message Content Intent** under Privileged Gateway Intents in your Discord Developer Portal
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

## Configuration

A `config/config.yaml` file lets you control the bot’s logging and scheduling behavior without touching code.

```yaml
logging:
  level: INFO            # Global log level: DEBUG, INFO, WARNING, ERROR, CRITICAL
  verbose: false         # If true, enables DEBUG-level logging globally
  file:
    filename_pattern: "error_log_%Y_%m_%d.log"  # Daily error log filename pattern
    level: ERROR         # Log level written to the file handler
  console:
    level: INFO          # Log level printed to the console

scheduler:
  auto_sync: true        # Enable or disable background sync (default true)
  cron: "0 3 * * *"     # Cron schedule (crontab format) for running sync jobs
```

- `logging.level` sets the overall verbosity of log messages.
- `logging.verbose` toggles detailed debug output.
- `logging.file.filename_pattern` and `logging.file.level` configure file-based error logging.
- `logging.console.level` configures on-screen log output.
- `scheduler.auto_sync` is the default for new guilds; individual guilds can override it with the `/auto_sync` command.
- `scheduler.cron` follows standard cron syntax. For example, `0 3 * * *` runs daily at 3 AM.