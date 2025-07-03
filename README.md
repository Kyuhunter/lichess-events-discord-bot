# Lichess Events Discord Bot

This bot synchronizes Lichess arena tournaments with Discord events for registered teams.

## Features

- Automatically fetches Lichess tournaments for registered teams.
- Creates Discord events for upcoming tournaments.
- Supports manual sync and verbose logging.
- Slash commands and prefix-based commands for easy interaction.
- Discord channel logging for bot activity and event notifications.

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

## Discord Commands

The bot offers several slash commands for managing teams and event synchronization:

- `/setup_team <team>` - Register a Lichess team to track tournaments
- `/remove_team <team>` - Remove a registered team and delete its events
- `/list_teams` - Show all registered teams in the server
- `/sync [team]` - Manually sync events for all teams or a specific team
- `/sync_verbose [team]` - Sync with detailed logging output
- `/auto_sync <enable>` - Enable or disable scheduled background sync
- `/setup_logging_channel <channel>` - Set a channel to receive bot logs and event notifications

After setting up a logging channel with `/setup_logging_channel`, the bot will post:
- Log messages based on the configured log level
- Notifications when events are created, updated, or deleted
- Information about team registrations and removals

## Configuration

A `config/config.yaml` file lets you control the bot's logging and scheduling behavior without touching code.

```yaml
logging:
  level: INFO            # Global log level: DEBUG, INFO, WARNING, ERROR, CRITICAL
  verbose: false         # If true, enables DEBUG-level logging globally
  file:
    filename_pattern: "error_log_%Y_%m_%d.log"  # Daily error log filename pattern
    level: ERROR         # Log level written to the file handler
  console:
    level: INFO          # Log level printed to the console
  discord:
    level: INFO          # Log level for messages sent to Discord channels
    events: true         # Whether to post event notifications (create/update/delete)

scheduler:
  auto_sync: true        # Enable or disable background sync (default true)
  cron: "0 3 * * *"     # Cron schedule (crontab format) for running sync jobs
```

- `logging.level` sets the overall verbosity of log messages.
- `logging.verbose` toggles detailed debug output.
- `logging.file.filename_pattern` and `logging.file.level` configure file-based error logging.
- `logging.console.level` configures on-screen log output.
- `logging.discord.level` sets the minimum level for logs sent to Discord channels.
- `logging.discord.events` controls whether event notifications (create/update/delete) are sent to Discord.
- `scheduler.auto_sync` is the default for new guilds; individual guilds can override it with the `/auto_sync` command.
- `scheduler.cron` follows standard cron syntax. For example, `0 3 * * *` runs daily at 3 AM.

## Testing

The project includes a comprehensive test suite with >80% test coverage. Tests are organized by module and functionality:

### Test Structure

- `tests/test_commands.py` & `tests/test_commands_more.py`: Tests for all Discord commands, user interactions, and response handling
- `tests/test_sync.py`, `tests/test_sync_flow.py`, `tests/test_sync_additional.py`, `tests/test_sync_extra.py`, `tests/test_sync_more.py`: Tests for Lichess tournament synchronization logic
- `tests/test_tasks.py`: Tests for scheduled background tasks and error handling
- `tests/test_utils.py`: Tests for configuration and logging utilities
- `tests/test_discord_logging.py`: Tests for Discord logging handler
- `tests/test_notification_log.py` & `tests/test_notification_simple.py`: Tests for event notifications
- `tests/test_discord_events.py`: Tests for Discord event handlers
- `tests/test_logging_channel_setup.py`: Tests for logging channel setup command
- `tests/conftest.py`: Shared test fixtures and mocks

### Running Tests

Install test dependencies:
```bash
pip install pytest pytest-asyncio pytest-cov
```

Run the full test suite:
```bash
python -m pytest
```

Generate coverage report:
```bash
python -m pytest --cov=src --cov-report=html
```

This will create a coverage report in the `htmlcov/` directory that you can view in a browser.

### VS Code Integration

The project includes a VS Code task for running tests directly from the editor:

1. Open the Command Palette (`Ctrl+Shift+P`)
2. Type "Tasks: Run Task"
3. Select "Run Tests"

This will execute the test suite using the virtual environment's Python interpreter.