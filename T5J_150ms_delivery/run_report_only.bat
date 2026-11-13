@echo off
REM ============================================================
REM  仅根据 results\history.csv / line_force.csv 重新生成计算报告
REM  不重新计算；用于报告排版调整或结果复核
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

"%PYEXE%" %SCRIPT% --report-only --outdir results

echo.
echo 报告已重新生成: results\calculation_report.html
pause
