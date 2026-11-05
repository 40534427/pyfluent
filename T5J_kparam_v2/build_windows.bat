@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"

rem -----------------------------------------------------------------
rem  T5J make_kfile.exe  -- one-click PyInstaller build for Windows
rem  Usage: double-click, or run in cmd
rem  Prereq: Python 3.10+ installed and "python" on PATH
rem -----------------------------------------------------------------

echo ============================================================
echo   T5J make_kfile.exe  Build (Windows)
echo ============================================================

rem ---- [0] locate python ------------------------------------------
set "PYEXE="
for /f "delims=" %%i in ('where python 2^>nul') do (
    if not defined PYEXE set "PYEXE=%%i"
)
if not defined PYEXE (
    echo.
    echo [ERROR] python not found on PATH.
    echo Please install Python 3.10+ and check "Add to PATH" during install.
    echo Download: https://www.python.org/downloads/
    pause
    exit /b 1
)
echo [OK] python = %PYEXE%

rem ---- [1] ensure pyinstaller ------------------------------------
echo.
echo [1/3] Checking pyinstaller ...
"%PYEXE%" -c "import PyInstaller" 2>nul
if errorlevel 1 (
    echo   Not installed. Installing via python -m pip ...
    "%PYEXE%" -m pip install --upgrade pip --quiet
    if errorlevel 1 (
        echo [ERROR] pip install failed. Check network / firewall.
        pause
        exit /b 1
    )
    "%PYEXE%" -m pip install pyinstaller --quiet
    if errorlevel 1 (
        echo [ERROR] pyinstaller install failed.
        pause
        exit /b 1
    )
) else (
    echo   Already installed.
)

rem ---- [2] build --------------------------------------------------
echo.
echo [2/3] Building make_kfile.exe ...
cd "%~dp0src"

"%PYEXE%" -m PyInstaller --onefile --name make_kfile ^
  --add-data "paramk\_template.pkb.gz;paramk" ^
  --distpath .. --workpath build --specpath build ^
  paramk\generator.py
if errorlevel 1 (
    echo [ERROR] PyInstaller failed. See messages above.
    cd /d "%~dp0"
    pause
    exit /b 1
)

rem ---- [3] clean up build artifacts ------------------------------
echo.
echo [3/3] Cleaning ...
if exist build rmdir /s /q build

rem ---- done -------------------------------------------------------
cd /d "%~dp0"
if not exist make_kfile.exe (
    echo.
    echo [ERROR] make_kfile.exe was not produced. Check the build output above.
    pause
    exit /b 1
)

echo.
echo ============================================================
echo   DONE !
echo   make_kfile.exe is in this folder:
echo   %~dp0make_kfile.exe
echo   Size:
dir /b make_kfile.exe
echo ============================================================
pause
exit /b 0
