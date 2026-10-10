@echo off
:: NAND Flash Clone Tool - PyInstaller Build Script
:: ==================================================
:: Creates a standalone Windows .exe

echo.
echo  Building NAND Flash Clone Tool executable...
echo.

cd /d "%~dp0"
if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
)

pip install pyinstaller --quiet

pyinstaller ^
    --onefile ^
    --windowed ^
    --name "NANDFlashCloneTool" ^
    --icon "assets\icon.ico" ^
    --add-data "src;src" ^
    --add-data "assets;assets" ^
    --hidden-import "PyQt6.QtCore" ^
    --hidden-import "PyQt6.QtWidgets" ^
    --hidden-import "PyQt6.QtGui" ^
    --hidden-import "serial" ^
    --hidden-import "serial.tools.list_ports" ^
    main.py

echo.
if exist "dist\NANDFlashCloneTool.exe" (
    echo  Build successful: dist\NANDFlashCloneTool.exe
) else (
    echo  Build failed. Check output above.
)
echo.
pause
