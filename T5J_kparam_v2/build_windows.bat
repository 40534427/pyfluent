@echo off
chcp 65001 >nul
rem ============================================================
rem  T5J make_kfile.exe 一键打包脚本（Windows）
rem  用法：双击本文件，或在 cmd 里运行
rem  前提：已安装 Python 3.10+ 和 pip
rem ============================================================
cd /d "%~dp0src"
echo [1/3] Installing pyinstaller ...
pip install pyinstaller --quiet
echo [2/3] Building make_kfile.exe ...
pyinstaller --onefile --name make_kfile ^
  --add-data "paramk\_template.pkb.gz;paramk" ^
  --distpath .. --workpath build --specpath build ^
  paramk\generator.py
echo [3/3] Cleaning ...
rmdir /s /q build
del /q make_kfile.spec
echo.
echo === Done === make_kfile.exe is next to this script.
pause
