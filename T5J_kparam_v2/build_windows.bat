@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"

rem -----------------------------------------------------------------
rem  T5J make_kfile.exe  -- one-click PyInstaller build for Windows
rem  Usage: double-click, or run in cmd
rem -----------------------------------------------------------------

echo ============================================================
echo   T5J make_kfile.exe  Build (Windows)
echo ============================================================

rem ---- [0] find a REAL python --------------------------------------
set "PYEXE="

rem --- Strategy A: py launcher is the most reliable ---------------
rem     python.org installer ALWAYS registers "py" even without PATH.
where py >nul 2>&1
if not errorlevel 1 (
    echo   [A] Trying py launcher (python.org registered) ...
    for /f "delims=" %%i in ('py -3 -c "import sys; sys.stdout.write(sys.executable)" 2^>nul') do (
        if exist "%%i" set "PYEXE=%%i"
    )
)

rem --- Strategy B: filter PATH entries, skip WindowsApps store stub
if not defined PYEXE (
    echo   [B] Searching PATH (skipping WindowsApps) ...
    for /f "delims=" %%i in ('where python 2^>nul') do (
        set "CAND=%%i"
        if /i not "!CAND:WindowsApps=!"=="!CAND!" (
            echo     skip stub: !CAND!
        ) else (
            if exist "!CAND!" if not defined PYEXE set "PYEXE=!CAND!"
        )
    )
)

rem --- Strategy C: probe common install paths ----------------------
if not defined PYEXE (
    echo   [C] Probing well-known install paths ...
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

rem --- Strategy D: read registry InstallPath ----------------------
if not defined PYEXE (
    echo   [D] Reading registry ...
    for %%k in (
        "HKCU\SOFTWARE\Python\PythonCore"
        "HKLM\SOFTWARE\Python\PythonCore"
    ) do (
        for /f "delims=" %%v in ('reg query %%k /s /f InstallPath 2^>nul ^| findstr /i "InstallPath"') do (
            for /f "tokens=2,* delims==" %%a in ("%%v") do (
                set "p=%%b"
                set "p=!p:"=!"
                if exist "!p!python.exe" if not defined PYEXE set "PYEXE=!p!python.exe"
            )
        )
    )
)

rem --- not found? --------------------------------------------------
if not defined PYEXE (
    echo.
    echo ================================================================
    echo   [ERROR] Real Python was not located.
    echo ================================================================
    echo.
    echo   On your machine it is very likely at:
    echo   C:\Users\%USERNAME%\AppData\Local\Programs\Python\Python314\python.exe
    echo.
    echo   Please do one of the following:
    echo.
    echo   1) Open cmd and run:
    echo        py -3 -m pip install pyinstaller
    echo        py -3 -m PyInstaller --onefile --name make_kfile ^
    echo           --add-data "paramk\_template.pkb.gz;paramk" ^
    echo           --distpath .. --workpath build --specpath build ^
    echo           paramk\generator.py
    echo.
    echo   2) Or re-run the python.org installer and TICK:
    echo        "Add Python to PATH" at the bottom of the first page.
    echo.
    echo ================================================================
    pause
    exit /b 1
)

echo [OK] python = %PYEXE%
"%PYEXE%" --version

rem ---- [1] ensure pyinstaller -------------------------------------
echo.
echo [1/3] Checking pyinstaller ...
"%PYEXE%" -c "import PyInstaller" 2>nul
if errorlevel 1 (
    echo   Installing via python -m pip ...
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

rem ---- [3] clean up -----------------------------------------------
echo.
echo [3/3] Cleaning ...
if exist build rmdir /s /q build

cd /d "%~dp0"
if not exist make_kfile.exe (
    echo [ERROR] make_kfile.exe not produced. See build output above.
    pause
    exit /b 1
)

for %%A in ("make_kfile.exe") do (
    echo.
    echo ============================================================
    echo   DONE !
    echo   make_kfile.exe path:
    echo     %~dp0make_kfile.exe
    echo   Size: %%~zA bytes
    echo ============================================================
)
pause
exit /b 0
