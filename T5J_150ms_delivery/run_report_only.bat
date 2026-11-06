@echo off
setlocal
set EXE=%~dp0run_parachute.exe
set KFILE=%~dp0Parachute_0903.k
"%EXE%" --k "%KFILE%" --outdir "%~dp0results" --mesh auto --nx 30 --ny 40 --nz 30 --domain-radius 0.5 --y1-extension 0.4 --endtime 0.150 --vtk-every 0.005 --cfl 0.5 --tssfac 0.8 --constant-vel 220.0 --bend-scale 1 --bend-damp 0 --pleak 0.1 --struct-damping 100 --struct-damping-vmax 30 --eb-frac 0.05 --vent-radius 0.04 --tension-only-membrane --no-contact --max-steps 400000 --report-only
echo.
echo Done. Open results\calculation_report.html in a browser.
pause
