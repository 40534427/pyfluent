@echo off
REM ============================================================
REM  运行 T5J 算例（smart 阻尼 + 自动生成计算报告）
REM  使用前请先运行 build_windows_exe.bat 生成 run_parachute.exe
REM ============================================================
set EXE=dist\run_parachute.exe
if not exist %EXE% (
    echo 未找到 %EXE%，请先运行 build_windows_exe.bat 构建。
    pause
    exit /b 1
)

%EXE% --k Parachute_F28.k ^
  --nx 30 --ny 40 --nz 30 --domain-radius 0.5 --y1-extension 0.4 ^
  --endtime 0.050 --tssfac 0.8 ^
  --tension-only-membrane --eb-frac 0.05 --vent-radius 0.04 ^
  --constant-vel 220 --bend-scale 1 --bend-damp 0 --pleak 0.1 ^
  --struct-damping 100 --struct-damping-vmax 30 ^
  --vtk-every 0.005 --generate-report --outdir out\T5J

echo.
echo 计算完成，报告位于 out\T5J\calculation_report.html
pause
