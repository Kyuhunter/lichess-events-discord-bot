@echo off
:: setup.bat - Setup script for Lichess Events Discord Bot on Windows
:: Usage: setup.bat [--with-dev]

echo ===== Lichess Events Discord Bot Setup =====
echo.

:: Check if Python is installed
where python >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo Error: Python is not found in PATH.
    echo Please install Python 3.8 or higher and try again.
    exit /b 1
)

:: Create configuration directories
echo Creating configuration directories...
if not exist config mkdir config
if not exist data mkdir data
if not exist data\log mkdir data\log

:: Create sample .env file if it doesn't exist
if not exist config\.env.sample (
    echo Creating sample .env file...
    echo # Discord Bot Token > config\.env.sample
    echo DISCORD_TOKEN=your_token_here >> config\.env.sample
    echo Sample .env file created at config\.env.sample
)

:: Create .env file if it doesn't exist
if not exist config\.env (
    echo Creating .env file...
    copy config\.env.sample config\.env
    echo Please edit config\.env to add your Discord bot token.
    echo You can open it with Notepad or any text editor.
)

:: Create config.yaml file if it doesn't exist
if not exist config\config.yaml (
    echo Creating config.yaml file...
    echo logging: > config\config.yaml
    echo   level: INFO >> config\config.yaml
    echo   verbose: false >> config\config.yaml
    echo   file: >> config\config.yaml
    echo     filename_pattern: "error_log_%%Y_%%m_%%d.log" >> config\config.yaml
    echo     level: ERROR >> config\config.yaml
    echo   console: >> config\config.yaml
    echo     level: INFO >> config\config.yaml
    echo   discord: >> config\config.yaml
    echo     level: INFO >> config\config.yaml
    echo     events: true >> config\config.yaml
    echo. >> config\config.yaml
    echo scheduler: >> config\config.yaml
    echo   auto_sync: true >> config\config.yaml
    echo   cron: "0 3 * * *" >> config\config.yaml
    echo Default config.yaml created at config\config.yaml
)

:: Create virtual environment
echo Setting up Python virtual environment...
if not exist venv (
    python -m venv venv
    echo Virtual environment created.
) else (
    echo Virtual environment already exists.
)

:: Install dependencies
echo Installing dependencies...
call venv\Scripts\activate.bat

if "%1"=="--with-dev" (
    echo Installing all dependencies including development tools...
    pip install -r requirements.txt
) else (
    echo Installing production dependencies only...
    pip install -r requirements-prod.txt
)

echo.
echo ===== Setup Complete =====
echo To run the bot, use: start.bat
echo.
echo Make sure to:
echo 1. Edit config\.env to add your Discord bot token
echo 2. Use /setup_logging_channel in Discord to configure logging
echo 3. Use /setup_team to register your Lichess team(s)
echo.

exit /b 0
