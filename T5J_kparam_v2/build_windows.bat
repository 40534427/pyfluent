@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"

rem -----------------------------------------------------------------
rem  T5J make_kfile.exe  -- one-click PyInstaller build for Windows
rem  Usage: double-click, or run in cmd
rem  Prereq: real Python 3.10+ installed (NOT the Microsoft Store stub)
rem -----------------------------------------------------------------

echo ============================================================
echo   T5J make_kfile.exe  Build (Windows)
echo ============================================================

rem ---- [0] find a REAL python --------------------------------------
rem Strategy:
rem   1) try every "python" on PATH, skip WindowsApps stubs
rem   2) probe well-known install paths (python.org installer)
rem   3) probe registry (py launcher registered python)
rem   4) if still nothing, print a clear install guide

set "PYEXE="

rem --- 1a. iterate "where python", skip WindowsApps ---------------
for /f "delims=" %%i in ('where python 2^>nul') do (
    set "CAND=%%i"
    if /i not "!CAND:WindowsApps=!"=="!CAND!" (
        echo   [SKIP] WindowsApps stub: !CAND!
    ) else (
        if /i not "!CAND:store=!"=="!CAND!" (
            echo   [SKIP] store-related: !CAND!
        ) else (
            if not defined PYEXE (
                if exist "!CAND!" set "PYEXE=!CAND!"
            )
        )
    )
)

rem --- 1b. also try py launcher (python.org installs register "py")-
if not defined PYEXE (
    where py >nul 2>&1
    if not errorlevel 1 (
        for /f "delims=" %%i in ('py -3 -c "import sys; print(sys.executable)" 2^>nul') do (
            set "PYEXE=%%i"
        )
    )
)

rem --- 2. probe well-known install paths ---------------------------
if not defined PYEXE (
    for %%d in (
        "%LOCALAPPDATA%\Programs\Python\Python314\python.exe"
        "%LOCALAPPDATA%\Programs\Python\Python313\python.exe"
        "%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
        "%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
        "%LOCALAPPDATA%\Programs\Python\Python310\python.exe"
        "%PROGRAMFILES%\Python314\python.exe"
        "%PROGRAMFILES%\Python313\python.exe"
        "%PROGRAMFILES%\Python312\python.exe"
        "%PROGRAMFILES%\Python311\python.exe"
        "%PROGRAMFILES%\Python310\python.exe"
        "%PROGRAMFILES%\Python\Python314\python.exe"
        "%PROGRAMFILES%\Python\Python313\python.exe"
        "%PROGRAMFILES%\Python\Python312\python.exe"
        "%PROGRAMFILES%\Python\Python311\python.exe"
        "%PROGRAMFILES%\Python\Python310\python.exe"
        "%PROGRAMFILES(x86)%\Python314\python.exe"
        "%PROGRAMFILES(x86)%\Python313\python.exe"
        "%PROGRAMFILES(x86)%\Python312\python.exe"
        "%PROGRAMFILES(x86)%\Python311\python.exe"
        "%PROGRAMFILES(x86)%\Python310\python.exe"
        "%USERPROFILE%\scoop\apps\python\current\python.exe"
        "C:\Python314\python.exe"
        "C:\Python313\python.exe"
        "C:\Python312\python.exe"
        "C:\Python311\python.exe"
        "C:\Python310\python.exe"
    ) do (
        if exist %%d if not defined PYEXE set "PYEXE=%%~d"
    )
)

rem --- 3. probe registry ------------------------------------------
if not defined PYEXE (
    for %%k in (
        "HKLM\SOFTWARE\Python\PythonCore"
        "HKCU\SOFTWARE\Python\PythonCore"
    ) do (
        for /f "delims=" %%v in ('reg query %%k /s /f python.exe 2^>nul ^| findstr /i "InstallPath"') do (
            rem "InstallPath"="C:\Python312\"  -> append python.exe
            for /f "tokens=2,* delims==" %%a in ("%%v") do (
                set "p=%%b"
                set "p=!p:"=!"
                if exist "!p!python.exe" if not defined PYEXE set "PYEXE=!p!python.exe"
            )
        )
    )
)

rem --- 4. still nothing? ------------------------------------------
if not defined PYEXE (
    echo.
    echo ================================================================
    echo   [ERROR] Real Python not found on this system.
    echo ================================================================
    echo.
    echo   The "python" you have on PATH is the Microsoft Store stub -
    echo   it just opens the Store instead of actually running Python.
    echo.
    echo   Please install Python properly:
    echo.
    echo     1) Go to  https://www.python.org/downloads/
    echo        (NOT the Microsoft Store version)
    echo     2) Run the installer
    echo        - IMPORTANT: tick "Add Python to PATH" at the bottom
    echo        - Click "Install Now"
    echo     3) Re-run this build script
    echo.
    echo   Alternative: open cmd and type "where python" - none of the
    echo   results should contain "WindowsApps".
    echo.
    echo ================================================================
    pause
    exit /b 1
)

echo [OK] python = %PYEXE%
"%PYEXE%" --version

rem ---- [1] make sure pip + pyinstaller are available ---------------
echo.
echo [1/3] Checking pyinstaller ...
"%PYEXE%" -c "import PyInstaller" 2>nul
if errorlevel 1 (
    echo   Installing pyinstaller via python -m pip ...
    "%PYEXE%" -m pip install --upgrade pip
    if errorlevel 1 (
        echo [ERROR] pip failed. Check network.
        pause
        exit /b 1
    )
    "%PYEXE%" -m pip install pyinstaller
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

rem ---- [3] clean up ------------------------------------------------
echo.
echo [3/3] Cleaning ...
if exist build rmdir /s /q build

cd /d "%~dp0"
if not exist make_kfile.exe (
    echo.
    echo [ERROR] make_kfile.exe not produced. See build output above.
    pause
    exit /b 1
)

for %%A in ("make_kfile.exe") do (
    echo.
    echo ============================================================
    echo   DONE !
    echo   make_kfile.exe is in:
    echo     %~dp0
    echo   Size: %%~zA bytes
    echo ============================================================
)
pause
exit /b 0
