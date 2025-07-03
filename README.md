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
- Discord bot with the following:
  - **Message Content Intent** enabled under Privileged Gateway Intents
  - Bot permissions: Manage Events, Send Messages, Embed Links, Read Message History
  - OAuth2 scopes: `bot` and `applications.commands`
- A Lichess team slug (e.g., "lichess-de" - find this in the URL of your team page)
- `pip` for installing dependencies

## Setup Instructions

### 1. Clone the Repository

```bash
git clone https://github.com/your-repo/lichess-events-discord-bot.git
cd lichess-events-discord-bot
```

### 2. Configure the Bot

The repository comes with sensible default configuration files. You just need to add your Discord bot token:

```bash
# Copy the sample .env file and add your Discord token
cp config/.env.sample config/.env
nano config/.env
```

In the .env file, add your Discord bot token:
```
DISCORD_TOKEN=your_token_here
```

The default `config/config.yaml` file already contains sensible settings for:
- Logging levels (console, file, and Discord)
- Daily error log file pattern
- Background sync schedule (daily at 3 AM)
- Event notifications

You can adjust these settings as needed for your server.
```

### 3. Setup the Python Environment

Create a virtual environment and install the required dependencies:

```bash
# Create and activate virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# OPTION 1: For production use only (no testing capabilities)
pip install -r requirements-prod.txt
# OR install production packages individually
# pip install python-dotenv discord.py aiohttp pyyaml apscheduler

# OPTION 2: For development with testing capabilities
pip install -r requirements.txt
```

### 4. Set Up the Discord Bot

1. **Create a bot application** in the [Discord Developer Portal](https://discord.com/developers/applications)
   - Create a new application
   - Navigate to the "Bot" tab
   - Click "Add Bot"
   - Under "Privileged Gateway Intents," enable:
     - Presence Intent
     - Server Members Intent
     - Message Content Intent

2. **Invite the bot to your server** with the necessary permissions:
   - Navigate to OAuth2 > URL Generator
   - Select the following scopes:
     - `bot`
     - `applications.commands`
   - Select the following bot permissions:
     - Manage Events
     - Send Messages
     - Embed Links
     - Read Message History
     - View Channels
   - Copy and open the generated URL to invite the bot to your server

### 5. Run the Bot

Start the bot using the package entrypoint:

```bash
python -m src.bot
```

To start the bot as a background process:
```bash
./start.sh
```

The bot will run in the background and output logs to `data/log/bot_output.log`.

To stop the bot:
```bash
./stop.sh
```

### 6. Initial Setup in Discord

After the bot is running and joined your server:

1. Create a dedicated channel for logging (e.g., #bot-logs)
2. Ensure the bot has permissions to send messages in this channel
3. Use the `/setup_logging_channel` command to configure this channel for logs
4. Register your Lichess team(s) using the `/setup_team` command
5. Use `/sync` to perform an initial synchronization of events

## Discord Commands

The bot offers several slash commands for managing teams and event synchronization:

- `/setup_team <team>` - Register a Lichess team to track tournaments
- `/remove_team <team>` - Remove a registered team and delete its events
- `/list_teams` - Show all registered teams in the server
- `/sync [team]` - Manually sync events for all teams or a specific team
- `/sync_verbose [team]` - Sync with detailed logging output
- `/auto_sync <enable>` - Enable or disable scheduled background sync
- `/setup_logging_channel <channel>` - Set a channel to receive bot logs and event notifications
- `/lichess_status` - Check the bot's status, permissions, and configuration

After setting up a logging channel with `/setup_logging_channel`, the bot will post:
- Log messages based on the configured log level
- Notifications when events are created, updated, or deleted
- Information about team registrations and removals

## Configuration

The repository includes a pre-configured `config/config.yaml` file with sensible defaults. You can edit this file to customize the bot's behavior without changing any code.

```yaml
# Default configuration
logging:
  level: ERROR           # Global log level: DEBUG, INFO, WARNING, ERROR, CRITICAL
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

performance:
  cache:
    ttl_minutes: 15      # How long to cache tournament data (in minutes)
  batch_size: 5          # Number of items to process in each batch
  batch_delay: 1         # Delay between batches in seconds
```

Configuration options explained:

- **Logging Settings**
  - `logging.level`: Sets the overall verbosity of log messages (defaults to ERROR which is appropriate for production use)
  - `logging.verbose`: When set to true, enables DEBUG-level logging globally (useful for troubleshooting)
  - `logging.file.*`: Controls error logging to files in the data/log directory
  - `logging.console.*`: Controls what appears in the terminal when running the bot
  - `logging.discord.*`: Controls what gets sent to your configured Discord logging channel

- **Scheduler Settings**
  - `scheduler.auto_sync`: Default setting for new guilds (can be overridden per guild with `/auto_sync`)
  - `scheduler.cron`: When to run scheduled syncs; uses standard cron syntax
    - Default `0 3 * * *` runs daily at 3 AM
    - Other examples:
      - `*/30 * * * *` - Every 30 minutes
      - `0 */2 * * *` - Every 2 hours
      - `0 12,18 * * *` - At 12 PM and 6 PM daily

- **Performance Settings**
  - `performance.cache.ttl_minutes`: How long to keep tournament data in memory cache (15 minutes by default)
  - `performance.batch_size`: Number of API operations to perform in a batch before pausing
  - `performance.batch_delay`: Delay in seconds between processing batches

## Performance Optimization

The bot includes several optimizations to reduce API calls and improve performance:

### Caching

- Tournament data is cached for 15 minutes (configurable via `performance.cache.ttl_minutes`)
- This significantly reduces the number of API calls made to Lichess during frequent syncs
- Cache is automatically invalidated when teams are removed

### Batch Processing

- Events are processed in batches to avoid hitting rate limits
- Background sync pre-fetches all guild events in one operation instead of separate calls
- Configurable batch size and delay between batches

### Efficient Synchronization

- Only upcoming tournaments are synced (past tournaments are skipped)
- Events are compared with existing ones before making update API calls
- Update operations are skipped if no actual changes are detected

## Quick Setup

For convenience, the repository includes scripts to automate the setup process and running the bot.

### Linux/macOS

#### Using the Setup Script

```bash
# Make the script executable
chmod +x setup.sh

# Run setup (production only)
./setup.sh

# OR run setup with development dependencies
./setup.sh --with-dev
```

This script:
1. Validates the existing configuration files or creates them if missing
2. Sets up a Python virtual environment
3. Installs dependencies based on your choice
4. Prompts for your Discord bot token if not already configured

#### Running the Bot

To start the bot as a background process:
```bash
# Make script executable if you haven't already
chmod +x start.sh

# Start the bot
./start.sh
```

The bot will run in the background and output logs to `data/log/bot_output.log`.

To stop the bot:
```bash
# Make script executable if you haven't already
chmod +x stop.sh

# Stop the bot
./stop.sh
```

### Windows

#### Using the Setup Script

Run the setup script from Command Prompt or PowerShell:
```
setup.bat
```

For development setup with testing capabilities:
```
setup.bat --with-dev
```

Just like the Linux/macOS script, this will set up your environment and prompt for any missing configuration.

#### Running the Bot

To start the bot in a visible console window:
```
start.bat
```

To start the bot in the background (no visible window):
```
start-background.bat
```

When running in the background, logs will be written to `data\log\bot_output.log`.

## Testing

> Note: This section is relevant only if you installed the development dependencies. Skip if you installed only the production dependencies.

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

If you didn't install the full requirements.txt, you'll need to install the test dependencies first:
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

## Troubleshooting

### Common Issues

#### Command Permissions

- **Problem**: Some commands like `/setup_logging_channel` or `/sync` don't appear in Discord.
- **Solution**: Make sure your bot has the `applications.commands` scope enabled when you invited it. You may need to re-invite the bot with the correct scopes.

#### Permission Errors

- **Problem**: Error message "⚠️ I don't have permission to send messages in [channel]"
- **Solution**: Check the bot's permissions in that specific channel:
  1. Right-click the channel > Edit Channel > Permissions
  2. Find your bot's role and ensure it has "Send Messages" and "Embed Links" permissions
  3. Use the `!check_perms` command to view all bot permissions in the current channel

#### Bot Not Responding

- **Problem**: The bot is online but doesn't respond to commands
- **Solution**: 
  1. Ensure you've enabled the Message Content Intent in Discord Developer Portal
  2. Check the console output for any error messages
  3. Look in `data/log/error_log_YYYY_MM_DD.log` for detailed error information

#### Events Not Syncing

- **Problem**: No events are being created for your team
- **Solution**:
  1. Verify that your team slug is correct (e.g., "lichess-de" not "Lichess Deutschland")
  2. Check if the team has any upcoming tournaments on Lichess
  3. Run `/sync_verbose [team]` to see detailed output of the sync process
  4. Ensure your bot has "Manage Events" permission

### Diagnostic Commands

The bot includes several diagnostic commands to help troubleshoot issues:

- `!check_perms [channel_id]` - Check the bot's permissions in a channel
- `!debug_commands` - List all registered slash commands and re-sync them
- `/verify_logging_channel` - Test if the logging channel is properly configured