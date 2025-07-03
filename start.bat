@echo off
:: start.bat - Start the Lichess Events Discord Bot on Windows
:: This script starts the bot in a new window

echo Starting Lichess Events Discord Bot...

:: Check if the virtual environment exists
if not exist venv (
    echo Error: Virtual environment not found. Please run setup.bat first.
    exit /b 1
)

:: Check if .env file exists
if not exist config\.env (
    echo Error: config\.env file not found. Please run setup.bat first.
    exit /b 1
)

:: Check if config.yaml exists
if not exist config\config.yaml (
    echo Error: config\config.yaml file not found. Please run setup.bat first.
    exit /b 1
)

:: Create logs directory if it doesn't exist
if not exist data\log mkdir data\log

:: Start the bot in a new window
echo Starting bot in a new window...
start "Lichess Events Discord Bot" cmd /k "call venv\Scripts\activate.bat && python -m src.bot"

echo Bot started in a new window.
echo Close that window to stop the bot.
echo.

exit /b 0
