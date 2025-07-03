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

:: Ensure required directories exist
echo Ensuring required directories exist...
if not exist data mkdir data
if not exist data\log mkdir data\log

:: Check if configuration files exist
echo Checking configuration files...

if not exist config\.env (
    echo Creating .env file from the provided sample...
    if exist config\.env.sample (
        copy config\.env.sample config\.env
        echo Please edit config\.env to add your Discord bot token.
        echo You can open it with Notepad or any text editor.
        echo Setting secure file permissions for .env file...
        :: Use icacls to set permissions (Windows equivalent of chmod)
        icacls config\.env /inheritance:r /grant:r "%USERNAME%:F" > nul 2>&1
        if !ERRORLEVEL! NEQ 0 (
            echo Warning: Failed to set secure permissions on config\.env file.
            echo Please restrict access to this file manually.
        )
    ) else (
        echo Warning: config\.env.sample not found. Creating a minimal .env file...
        echo DISCORD_TOKEN= > config\.env
        echo Please add your Discord bot token to config\.env
        :: Secure permissions
        icacls config\.env /inheritance:r /grant:r "%USERNAME%:F" > nul 2>&1
    )
) else (
    echo Found existing config\.env file
    :: Secure existing .env file
    icacls config\.env /inheritance:r /grant:r "%USERNAME%:F" > nul 2>&1
)

if not exist config\config.yaml (
    echo Warning: config\config.yaml not found!
    echo The bot requires this file to run properly.
    echo Please restore it from the repository or see the README for configuration details.
    exit /b 1
) else (
    echo Found existing config\config.yaml file
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
