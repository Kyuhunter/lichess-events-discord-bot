#!/bin/bash
# setup.sh - Automates the setup of the Lichess Events Discord Bot
# Usage: ./setup.sh [--with-dev]
# Options:
#   --with-dev    Install development dependencies (for testing)

# Exit on error
set -e

echo "===== Lichess Events Discord Bot Setup ====="
echo

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo "Error: Python 3 is required but not installed."
    echo "Please install Python 3.8 or higher and try again."
    exit 1
fi

# Ensure required directories exist
echo "Ensuring required directories exist..."
mkdir -p data
mkdir -p data/log

# Check if configuration files exist
echo "Checking configuration files..."

if [ ! -f config/.env ]; then
    echo "Creating .env file from the provided sample..."
    if [ -f config/.env.sample ]; then
        cp config/.env.sample config/.env
        echo "Please edit config/.env to add your Discord bot token."
        echo "You can open it with a text editor or run: nano config/.env"
    else
        echo "Warning: config/.env.sample not found. Creating a minimal .env file..."
        echo "DISCORD_TOKEN=" > config/.env
        echo "Please add your Discord bot token to config/.env"
    fi
else
    echo "Found existing config/.env file"
fi

if [ ! -f config/config.yaml ]; then
    echo "Warning: config/config.yaml not found!"
    echo "The bot requires this file to run properly."
    echo "Please restore it from the repository or see the README for configuration details."
    exit 1
else
    echo "Found existing config/config.yaml file"
fi

# Create virtual environment
echo "Setting up Python virtual environment..."
if [ ! -d venv ]; then
    python3 -m venv venv
    echo "Virtual environment created."
else
    echo "Virtual environment already exists."
fi

# Activate virtual environment
source venv/bin/activate

# Install dependencies
echo "Installing dependencies..."
if [ "$1" == "--with-dev" ]; then
    echo "Installing all dependencies including development tools..."
    pip install -r requirements.txt
else
    echo "Installing production dependencies only..."
    pip install -r requirements-prod.txt
fi

echo
echo "===== Setup Complete ====="
echo "To run the bot, use: ./start.sh"
echo "To stop the bot, use: ./stop.sh"
echo
echo "Make sure to:"
echo "1. Edit config/.env to add your Discord bot token"
echo "2. Use /setup_logging_channel in Discord to configure logging"
echo "3. Use /setup_team to register your Lichess team(s)"
echo

# Make start and stop scripts executable
chmod +x start.sh
chmod +x stop.sh

exit 0
