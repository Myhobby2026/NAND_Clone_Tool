@echo off
:: NAND Flash Clone Tool - Launcher
:: =================================
setlocal

cd /d "%~dp0"

:: Activate virtual environment if it exists
if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
)

:: Launch the application
python main.py %*

endlocal
