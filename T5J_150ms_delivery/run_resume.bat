@echo off
REM ============================================================
REM  T5J 算例断点续算：从 results\checkpoint.npz 恢复并算到 150 ms
REM  如中途再次中断，重新运行本脚本即可（每 5 ms 自动保存检查点）
REM ============================================================
setlocal
set PYEXE=
where python >nul 2>nul && set PYEXE=python
if not defined PYEXE (
    if exist bin\run_parachute.exe set PYEXE=bin\run_parachute.exe
)
if not defined PYEXE (
    echo [错误] 未找到 python，也未找到 bin\run_parachute.exe
    pause
    exit /b 1
)
if not exist results\checkpoint.npz (
    echo [错误] 未找到 results\checkpoint.npz，请先运行 run_parachute.bat
    pause
    exit /b 1
)

%PYEXE% src\run_parachute.py --k kinput\Parachute_0903.k ^
  --nx 30 --ny 40 --nz 30 --domain-radius 0.5 --y1-extension 0.4 ^
  --endtime 0.150 --tssfac 0.8 --cfl 0.5 --constant-vel 220 ^
  --bend-scale 1 --bend-damp 0 --pleak 0.1 ^
  --struct-damping 100 --struct-damping-vmax 30 ^
  --eb-frac 0.05 --vent-radius 0.006 --vent-ring-E-factor 0 --vent-ring-A-factor 2 ^
  --tension-only-membrane --no-contact ^
  --vtk-every 0.005 --checkpoint-every 0.005 --max-steps 400000 ^
  --restart results\checkpoint.npz ^
  --generate-report --outdir results

echo.
echo 续算完成。报告: results\calculation_report.html
pause
