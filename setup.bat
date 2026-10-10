@echo off
:: NAND Flash Clone Tool - Windows Setup Script
:: ==============================================
:: Run this script once to set up the Python virtual environment.

echo.
echo  ┌─────────────────────────────────────────────────────┐
echo  │         NAND Flash Clone Tool - Setup               │
echo  └─────────────────────────────────────────────────────┘
echo.

:: Check Python version
python --version 2>NUL
if errorlevel 1 (
    echo  [ERROR] Python not found. Install Python 3.10+ from python.org
    pause
    exit /b 1
)

:: Create virtual environment
echo  [1/4] Creating virtual environment...
python -m venv venv
if errorlevel 1 (
    echo  [ERROR] Failed to create virtual environment
    pause
    exit /b 1
)

:: Activate venv
echo  [2/4] Activating virtual environment...
call venv\Scripts\activate.bat

:: Upgrade pip
echo  [3/4] Upgrading pip...
python -m pip install --upgrade pip --quiet

:: Install dependencies
echo  [4/4] Installing dependencies...
pip install -r requirements.txt
if errorlevel 1 (
    echo  [ERROR] Failed to install dependencies
    pause
    exit /b 1
)

echo.
echo  ┌─────────────────────────────────────────────────────┐
echo  │  Setup complete! Run launch.bat to start the tool.  │
echo  └─────────────────────────────────────────────────────┘
echo.
pause
