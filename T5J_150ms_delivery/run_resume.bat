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
if not exist "kinput\Parachute_0903.k" goto no_input
if not exist "results\checkpoint.npz" goto no_checkpoint

"%PYEXE%" %SCRIPT% --k "kinput\Parachute_0903.k" ^
  --nx 30 --ny 40 --nz 30 --domain-radius 0.5 --y1-extension 0.4 ^
  --endtime 0.150 --tssfac 0.8 --cfl 0.5 --constant-vel 220 ^
  --bend-scale 1 --bend-damp 0 --pleak 0.1 ^
  --struct-damping 100 --struct-damping-vmax 30 ^
  --eb-frac 0.05 --vent-radius 0.006 --vent-ring-E-factor 0 --vent-ring-A-factor 2 ^
  --tension-only-membrane --no-contact ^
  --vtk-every 0.005 --checkpoint-every 0.005 --max-steps 400000 ^
  --restart "results\checkpoint.npz" ^
  --generate-report --outdir "results"

set "EXIT_CODE=%ERRORLEVEL%"
if not "%EXIT_CODE%"=="0" goto solver_failed
echo.
echo Resume calculation completed.
echo Report: results\calculation_report.html
pause
exit /b 0

:no_input
echo [ERROR] Missing input: kinput\Parachute_0903.k
pause
exit /b 1

:no_checkpoint
echo [ERROR] Missing results\checkpoint.npz
echo         Run run_parachute.bat first to create a checkpoint.
pause
exit /b 1

:solver_failed
echo.
echo [ERROR] Solver failed with exit code %EXIT_CODE%.
pause
exit /b %EXIT_CODE%
