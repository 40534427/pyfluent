@echo off
REM ============================================================
REM  可选：重新构建单文件版 run_parachute.exe
REM  交付包已包含原生启动器和免安装运行库，正常使用无需执行本脚本。
REM  为兼容 Windows 7，请使用 64 位 Python 3.8 构建。
REM ============================================================
setlocal
cd /d "%~dp0"

python -c "import sys; assert sys.version_info[:2] == (3, 8), 'need Python 3.8'; assert sys.maxsize > 2**32, 'need 64-bit Python'"
if errorlevel 1 (
    echo [错误] 请使用 64 位 Python 3.8，以保证 Windows 7 兼容性。
    pause
    exit /b 1
)

echo [1/3] 安装 Win7 兼容的构建依赖 ...
python -m pip install pyinstaller==5.13.2 numpy==1.24.4 scipy==1.10.1 matplotlib==3.7.5 psutil==6.0.0 importlib_resources==6.4.5 zipp==3.20.2
if errorlevel 1 (
    echo 依赖安装失败，请检查 Python/pip 和网络。
    pause
    exit /b 1
)

echo [2/3] 构建 EXE (PyInstaller, 单文件模式) ...
python -m PyInstaller --clean --noupx --onefile --console --name run_parachute --collect-all matplotlib run_parachute.py
if errorlevel 1 (
    echo EXE 构建失败。
    pause
    exit /b 1
)

echo [3/3] 完成：dist\run_parachute.exe
echo      可复制到交付包 bin\ 目录替换随包启动器。
pause
