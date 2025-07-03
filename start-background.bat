@echo off
:: start-background.bat - Start the Lichess Events Discord Bot in the background on Windows
:: This script starts the bot without keeping a console window open

echo Starting Lichess Events Discord Bot in background...

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

:: Start the bot hidden in the background with logging
echo Starting bot in background (logs will be written to data\log\bot_output.log)
start /min "" cmd /c "call venv\Scripts\activate.bat && python -m src.bot > data\log\bot_output.log 2>&1"

echo Bot started in the background.
echo To check the logs, open: data\log\bot_output.log
echo To stop the bot, use Task Manager to end the Python process.
echo.

exit /b 0
