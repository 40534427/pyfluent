@echo off
REM ============================================================
REM  T5J 减速伞 150 ms 充气展开 ALE 流固耦合算例 - 一键计算
REM  优先使用 bin\run_parachute.exe 和随包运行库，无需安装 Python
REM  结果输出到 results\，报告为 results\calculation_report.html
REM ============================================================
setlocal
cd /d "%~dp0"
set "PYEXE=%~dp0bin\run_parachute.exe"
set "SCRIPT="
if not exist "%PYEXE%" (
    where python >nul 2>nul
    if errorlevel 1 (
        echo [错误] 未找到 bin\run_parachute.exe，也未找到 python
        pause
        exit /b 1
    )
    set "PYEXE=python"
    set SCRIPT="%~dp0src\run_parachute.py"
)

if not exist kinput\Parachute_0903.k (
    echo [错误] 缺少输入文件 kinput\Parachute_0903.k
    echo        请将原始 LS-DYNA K 文件放入 kinput 目录后重新运行。
    pause
    exit /b 1
)
if not exist results mkdir results
"%PYEXE%" %SCRIPT% --k kinput\Parachute_0903.k ^
  --nx 30 --ny 40 --nz 30 --domain-radius 0.5 --y1-extension 0.4 ^
  --endtime 0.150 --tssfac 0.8 --cfl 0.5 --constant-vel 220 ^
  --bend-scale 1 --bend-damp 0 --pleak 0.1 ^
  --struct-damping 100 --struct-damping-vmax 30 ^
  --eb-frac 0.05 --vent-radius 0.006 --vent-ring-E-factor 0 --vent-ring-A-factor 2 ^
  --tension-only-membrane --no-contact ^
  --vtk-every 0.005 --checkpoint-every 0.005 ^
  --generate-report --outdir results

echo.
echo 计算完成。报告: results\calculation_report.html
pause
