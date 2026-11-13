@echo off
REM ============================================================
REM  一键构建 Windows 可执行文件 run_parachute.exe
REM  在 Windows 上双击运行，或在 cmd 中执行本脚本
REM ============================================================
echo [1/3] 安装依赖 ...
pip install pyinstaller numpy scipy matplotlib psutil
if errorlevel 1 (
    echo 依赖安装失败，请检查 Python/pip 是否可用。
    pause
    exit /b 1
)

echo [2/3] 构建 EXE (PyInstaller, 单文件模式) ...
pyinstaller --clean run_parachute.spec
if errorlevel 1 (
    echo EXE 构建失败。
    pause
    exit /b 1
)

echo [3/3] 完成。可执行文件位于 dist\run_parachute.exe
echo.
echo 运行示例：
echo   dist\run_parachute.exe --k Parachute_F28.k --nx 30 --ny 40 --nz 30 ^
echo       --domain-radius 0.5 --y1-extension 0.4 --endtime 0.050 --tssfac 0.8 ^
echo       --tension-only-membrane --eb-frac 0.05 --vent-radius 0.04 ^
echo       --constant-vel 220 --bend-scale 1 --bend-damp 0 --pleak 0.1 ^
echo       --struct-damping 100 --struct-damping-vmax 30 ^
echo       --vtk-every 0.005 --generate-report --outdir out
pause
