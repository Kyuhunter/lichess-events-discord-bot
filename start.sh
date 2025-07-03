#!/bin/bash
# start.sh - Start the Lichess Events Discord Bot in the background
# Usage: ./start.sh

# Get the script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# Check if the virtual environment exists
if [ ! -d venv ]; then
    echo "Error: Virtual environment not found. Please run setup.sh first."
    exit 1
fi

# Check if .env file exists
if [ ! -f config/.env ]; then
    echo "Error: config/.env file not found. Please run setup.sh first."
    exit 1
fi

# Check if config.yaml exists
if [ ! -f config/config.yaml ]; then
    echo "Error: config/config.yaml file not found. Please run setup.sh first."
    exit 1
fi

# Create logs directory if it doesn't exist
mkdir -p data/log

# Check if a process is already running
PID_FILE="$SCRIPT_DIR/bot.pid"
if [ -f "$PID_FILE" ]; then
    PID=$(cat "$PID_FILE")
    if ps -p "$PID" > /dev/null; then
        echo "Bot is already running with PID $PID"
        echo "To stop the bot, use: ./stop.sh"
        exit 1
    else
        echo "Stale PID file found. Previous instance was not stopped properly."
        rm "$PID_FILE"
    fi
fi

echo "Starting Lichess Events Discord Bot..."
echo "Logs will be written to data/log/bot_output.log"
echo "To check the logs: tail -f data/log/bot_output.log"
echo "To stop the bot: ./stop.sh"

# Start the bot in the background
nohup venv/bin/python -m src.bot > data/log/bot_output.log 2>&1 &

# Save the PID to the file
echo $! > "$PID_FILE"
echo "Bot started with PID $!"

# Save the PID
echo $! > "$PID_FILE"
echo "Bot started with PID $!"
echo "Use ./stop.sh to stop the bot"

exit 0
