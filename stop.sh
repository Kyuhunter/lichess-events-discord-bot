#!/bin/bash
# stop.sh - Stop the Lichess Events Discord Bot
# Usage: ./stop.sh

# Get the script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# Check if PID file exists
PID_FILE="$SCRIPT_DIR/bot.pid"
if [ ! -f "$PID_FILE" ]; then
    echo "Bot is not running (no PID file found)"
    exit 0
fi

# Read the PID
PID=$(cat "$PID_FILE")

# Check if process is running
if ! ps -p "$PID" > /dev/null; then
    echo "Bot is not running (PID $PID not found)"
    rm "$PID_FILE"
    exit 0
fi

# Stop the process
echo "Stopping Lichess Events Discord Bot (PID $PID)..."
kill "$PID"

# Wait for process to terminate
for i in {1..10}; do
    if ! ps -p "$PID" > /dev/null; then
        break
    fi
    sleep 1
done

# Check if process is still running
if ps -p "$PID" > /dev/null; then
    echo "Warning: Bot did not shut down gracefully. Forcing termination..."
    kill -9 "$PID"
    sleep 1
fi

# Remove PID file
rm "$PID_FILE"
echo "Bot stopped successfully"

exit 0
