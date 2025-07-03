@echo off
:: stop.bat - Stop the Lichess Events Discord Bot on Windows
:: This script finds and terminates the Python process for the bot

echo Stopping Lichess Events Discord Bot...

:: Enable delayed expansion for variables in loops
setlocal enabledelayedexpansion

:: Look for python processes running the bot
for /f "tokens=1" %%p in ('wmic process where "commandline like '%%src.bot%%' and name like '%%python%%'" get processid 2^>nul ^| findstr /r "[0-9]"') do (
    echo Found bot process with PID: %%p
    echo Terminating process...
    taskkill /pid %%p /f
    if !errorlevel! equ 0 (
        echo Bot stopped successfully.
    ) else (
        echo Failed to stop the bot. Please check Task Manager.
    )
    goto :found
)

echo No running bot process found.
goto :eof

:found
exit /b 0
