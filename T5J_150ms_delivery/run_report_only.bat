@echo off
setlocal
cd /d "%~dp0"

set "PYEXE=%~dp0bin\run_parachute.exe"
set "SCRIPT="

if exist "%PYEXE%" goto launcher_ready
where python >nul 2>nul
if errorlevel 1 goto no_launcher
set "PYEXE=python"
set "SCRIPT="%~dp0src\run_parachute.py""
goto launcher_ready

:no_launcher
echo [ERROR] bin\run_parachute.exe was not found.
echo         Python was not found either. Restore the complete package.
pause
exit /b 1

:launcher_ready
if not exist "results\history.csv" goto no_results
if not exist "results\line_force.csv" goto no_results

"%PYEXE%" %SCRIPT% --report-only --outdir "results"

set "EXIT_CODE=%ERRORLEVEL%"
if not "%EXIT_CODE%"=="0" goto report_failed
echo.
echo Report regenerated: results\calculation_report.html
pause
exit /b 0

:no_results
echo [ERROR] results\history.csv or results\line_force.csv is missing.
pause
exit /b 1

:report_failed
echo.
echo [ERROR] Report generation failed with exit code %EXIT_CODE%.
pause
exit /b %EXIT_CODE%
