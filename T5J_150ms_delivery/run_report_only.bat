@echo off
REM ============================================================
REM  仅根据 results\history.csv / line_force.csv 重新生成计算报告
REM  不重新计算；用于报告排版调整或结果复核
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

%PYEXE% src\run_parachute.py --k kinput\Parachute_0903.k ^
  --report-only --generate-report --outdir results

echo.
echo 报告已重新生成: results\calculation_report.html
pause
