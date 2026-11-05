@echo off
setlocal
cd /d "%~dp0"
rem ============================================================
rem Run the ALE solver on the generated K file (T5J settings)
rem Generated from params.json by make_kfile.exe - do not edit.
rem ============================================================
set "SOLVER=%~dp0run_parachute.exe"
set "KFILE=%~dp0Parachute_generated.k"
if not exist "%SOLVER%" goto :nosolver
"%SOLVER%" --k "%KFILE%" --outdir results --mesh auto --nx 30 --ny 40 --nz 30 --domain-radius 0.5 --y1-extension 0.4 --cfl 0.5 --omega 0.2 --cdamp 1.0 --fsi-mach-cap 0.3 --constant-vel 220.0 --endtime 0.05 --vtk-every 0.005 --tssfac 0.8 --vent-radius 0.04 --bend-scale 1 --bend-damp 0 --struct-damping 100 --struct-damping-vmax 30 --eb-frac 0.05 --tension-only-membrane --no-contact --generate-report
if errorlevel 1 goto :failed
echo.
echo === Done === Report: results\calculation_report.html
pause
exit /b 0
:nosolver
echo [ERROR] run_parachute.exe not found next to this script.
echo Copy run_parachute.exe from the T5J delivery package here.
pause
exit /b 1
:failed
echo [ERROR] Solver exited with an error. See messages above.
pause
exit /b 1
