@echo off
REM ============================================================
REM  T5J delivery package verification
REM  Target : Windows 7 SP1 x64 / Windows 10 x64 / Windows 11 x64
REM  Usage  : double-click, or run "verify_windows.bat" in cmd
REM  Output : verify_windows.log (full log), verify_out\ (scratch)
REM  Exit   : 0 = all checks passed, 1 = one or more checks failed
REM ============================================================
setlocal EnableExtensions EnableDelayedExpansion

set "ROOT=%~dp0"
if "%ROOT:~-1%"=="\" set "ROOT=%ROOT:~0,-1%"
cd /d "%ROOT%"
set "LOG=%ROOT%\verify_windows.log"
set "WORK=%ROOT%\verify_out"
set /a PASS=0
set /a FAIL=0
set "OSNAME=unknown"

if not exist "%WORK%" mkdir "%WORK%" >nul 2>&1
> "%LOG%" echo T5J delivery package verification
>>"%LOG%" echo Started : %DATE% %TIME%
>>"%LOG%" echo Computer: %COMPUTERNAME%   User: %USERNAME%
>>"%LOG%" echo Root    : %ROOT%
>>"%LOG%" echo.

echo ============================================================
echo  T5J delivery package verification
echo  Root: %ROOT%
echo  Log : %LOG%
echo ============================================================
echo.

REM ------------------------------------------------------------
REM 1. operating system + architecture
REM ------------------------------------------------------------
call :say "1. Operating system"
set "CURVER=0.0"
set "BUILD=0"
for /f "tokens=2,*" %%A in ('reg query "HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion" /v CurrentVersion 2^>nul ^| findstr "CurrentVersion"') do set "CURVER=%%B"
for /f "tokens=2,*" %%A in ('reg query "HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion" /v CurrentBuildNumber 2^>nul ^| findstr "CurrentBuildNumber"') do set "BUILD=%%B"
set "MAJ=!CURVER:~0,2!"
if "!MAJ!"=="10" (
    set "MAJ=10"
    set "MIN=!CURVER:~3!"
) else (
    set "MIN=!CURVER:~2!"
    set "MAJ=!CURVER:~0,1!"
)
call :say "  reported version !CURVER!, build !BUILD!"

if /i "!MAJ!"=="6" if /i "!MIN!"=="1" goto :os_win7
if /i "!MAJ!"=="10" goto :os_win10
call :bad "unsupported OS version !CURVER! build !BUILD! (need Win7 SP1 or Win10/11 x64)"
set "OSNAME=unsupported"
goto :os_arch

:os_win7
if !BUILD! GEQ 7601 (
    call :ok "Windows 7 SP1 detected"
    set "OSNAME=Windows 7 SP1 x64"
) else (
    call :bad "Windows 7 build !BUILD! is older than SP1 (7601)"
    set "OSNAME=Windows 7 (no SP1)"
)
goto :os_arch

:os_win10
if !BUILD! GEQ 22000 (
    call :ok "Windows 11 detected (build !BUILD!)"
    set "OSNAME=Windows 11 x64"
) else (
    call :ok "Windows 10 detected (build !BUILD!, supported)"
    set "OSNAME=Windows 10 x64"
)
goto :os_arch

:os_arch
if /i "%PROCESSOR_ARCHITECTURE%"=="AMD64" (
    call :ok "64-bit Windows (AMD64)"
) else (
    call :bad "not a 64-bit process (PROCESSOR_ARCHITECTURE=%PROCESSOR_ARCHITECTURE%)"
)
if /i "!OSNAME!"=="unknown" set "OSNAME=Windows (unknown edition) x64"

REM ------------------------------------------------------------
REM 2. package layout
REM ------------------------------------------------------------
call :blank
call :say "2. Package layout"
if exist "%ROOT%\README.md" (call :ok "found README.md") else (call :bad "missing README.md")
call :need "bin\run_parachute.exe"
call :need "bin\runtime\python.exe"
call :need "bin\runtime\python38.dll"
call :need "bin\runtime\ucrtbase.dll"
call :need "bin\runtime\msvcp140.dll"
call :need "bin\runtime\vcruntime140.dll"
call :need "bin\runtime\api-ms-win-crt-runtime-l1-1-0.dll"
call :need "bin\runtime\Lib\site-packages\numpy\__init__.py"
call :need "bin\runtime\Lib\site-packages\scipy\__init__.py"
call :need "bin\runtime\Lib\site-packages\matplotlib\__init__.py"
call :need "src\run_parachute.py"
call :need "src\aleparachute\__init__.py"
call :need "results\history.csv"
call :need "results\calculation_report.html"
call :need "kinput\Parachute_0903.k"

REM ------------------------------------------------------------
REM 3. bundled Python runtime
REM ------------------------------------------------------------
call :blank
call :say "3. Bundled Python runtime"
"%ROOT%\bin\runtime\python.exe" -c "import sys, numpy, scipy, matplotlib; print('python', sys.version.split()[0], '64bit', sys.maxsize > 2**32); print('numpy', numpy.__version__, 'scipy', scipy.__version__, 'matplotlib', matplotlib.__version__)" > "%WORK%\runtime.txt" 2>&1
if errorlevel 1 (
    call :bad "python.exe failed to start, see verify_out\runtime.txt"
) else (
    call :ok "python.exe started"
)
type "%WORK%\runtime.txt" >> "%LOG%" 2>nul
findstr /c:"64bit True" "%WORK%\runtime.txt" >nul 2>&1
if errorlevel 1 (call :bad "runtime is not 64-bit") else (call :ok "runtime is 64-bit")
findstr /c:"numpy" "%WORK%\runtime.txt" >nul 2>&1
if errorlevel 1 (call :bad "numpy/scipy/matplotlib import failed") else (call :ok "numpy/scipy/matplotlib import OK")

REM ------------------------------------------------------------
REM 4. launcher startup
REM ------------------------------------------------------------
call :blank
call :say "4. Launcher startup (bin\run_parachute.exe --help)"
"%ROOT%\bin\run_parachute.exe" --help > "%WORK%\help.txt" 2>&1
if errorlevel 1 (
    call :bad "run_parachute.exe --help returned an error"
) else (
    call :ok "run_parachute.exe --help returned 0"
)
findstr /c:"--report-only" "%WORK%\help.txt" >nul 2>&1
if errorlevel 1 (call :bad "help text is incomplete") else (call :ok "help text contains the solver options")

call :blank
call :say "5. Launcher started from another directory"
pushd "%TEMP%"
"%ROOT%\bin\run_parachute.exe" --help >nul 2>&1
set "RC=!errorlevel!"
popd
cd /d "%ROOT%"
if !RC! EQU 0 (
    call :ok "launcher resolves the package root from its own path"
) else (
    call :bad "launcher failed outside the package directory (exit !RC!)"
)

REM ------------------------------------------------------------
REM 6. report + plotting chain (no solver)
REM ------------------------------------------------------------
call :blank
call :say "6. Report and plotting chain (--report-only)"
if exist "%WORK%\report" rd /s /q "%WORK%\report"
xcopy "%ROOT%\results" "%WORK%\report" /e /i /q /y >nul 2>&1
if not exist "%WORK%\report\history.csv" (
    call :bad "could not copy results into verify_out\report"
) else (
    call :ok "existing results copied to verify_out\report"
)
"%ROOT%\bin\run_parachute.exe" --report-only --outdir "%WORK%\report" > "%WORK%\report.log" 2>&1
if errorlevel 1 (
    call :bad "--report-only returned an error, see verify_out\report.log"
) else (
    call :ok "--report-only returned 0"
)
if exist "%WORK%\report\calculation_report.html" (
    call :ok "calculation_report.html regenerated"
) else (
    call :bad "calculation_report.html was not regenerated"
)
set /a FIG=0
for /f "delims=" %%F in ('dir /b "%WORK%\report\figures\*.png" 2^>nul') do set /a FIG+=1
if !FIG! GEQ 5 (
    call :ok "!FIG! PNG figures regenerated"
) else (
    call :bad "only !FIG! PNG figures regenerated (expected at least 5)"
)

REM ------------------------------------------------------------
REM 7. solver smoke test (4 steps, 8x8x8 grid)
REM ------------------------------------------------------------
call :blank
call :say "7. Solver smoke test (4 steps, 8x8x8 grid, endtime 0.1 ms)"
if not exist "%ROOT%\kinput\Parachute_0903.k" (
    call :bad "kinput\Parachute_0903.k not found, solver test skipped"
) else (
    if exist "%WORK%\solve" rd /s /q "%WORK%\solve"
    "%ROOT%\bin\run_parachute.exe" --k "%ROOT%\kinput\Parachute_0903.k" --nx 8 --ny 8 --nz 8 --domain-radius 0.5 --endtime 0.0001 --max-steps 4 --outdir "%WORK%\solve" --quiet > "%WORK%\solve.log" 2>&1
    if errorlevel 1 (
        call :bad "solver returned an error, see verify_out\solve.log"
    ) else (
        call :ok "solver returned 0"
    )
    findstr /c:"done:" "%WORK%\solve.log" >nul 2>&1
    if errorlevel 1 (call :bad "solver did not report completion") else (call :ok "solver reported completion")
    if exist "%WORK%\solve\history.csv" (call :ok "history.csv written") else (call :bad "history.csv missing")
    if exist "%WORK%\solve\line_force.csv" (call :ok "line_force.csv written") else (call :bad "line_force.csv missing")
    if exist "%WORK%\solve\checkpoint.npz" (call :ok "checkpoint.npz written") else (call :bad "checkpoint.npz missing")
    if exist "%WORK%\solve\final_structure.vtk" (call :ok "final_structure.vtk written") else (call :bad "final_structure.vtk missing")
)

REM ------------------------------------------------------------
REM summary
REM ------------------------------------------------------------
call :blank
call :say "============================================================"
if !FAIL! GTR 0 (
    call :say "RESULT: FAIL   (passed !PASS!, failed !FAIL!)"
) else (
    call :say "RESULT: PASS   (passed !PASS!, failed 0)"
)
call :say "OS    : !OSNAME!"
call :say "Log   : %LOG%"
call :say "============================================================"
>>"%LOG%" echo.
>>"%LOG%" echo Finished: %DATE% %TIME%
>>"%LOG%" echo RESULT=!OSNAME! PASS=!PASS! FAIL=!FAIL!

if /i "%T5J_NOPAUSE%"=="1" goto :finish
pause

:finish
if !FAIL! GTR 0 exit /b 1
exit /b 0

REM ------------------------------------------------------------
REM helpers
REM ------------------------------------------------------------
:blank
echo.
>>"%LOG%" echo.
goto :eof

:say
echo %~1
>>"%LOG%" echo %~1
goto :eof

:ok
set /a PASS+=1
echo   [PASS] %~1
>>"%LOG%" echo   [PASS] %~1
goto :eof

:bad
set /a FAIL+=1
echo   [FAIL] %~1
>>"%LOG%" echo   [FAIL] %~1
goto :eof

:need
if exist "%ROOT%\%~1" (
    call :ok "found %~1"
) else (
    call :bad "missing %~1"
)
goto :eof
