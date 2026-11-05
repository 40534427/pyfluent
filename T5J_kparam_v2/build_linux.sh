#!/bin/bash
# T5J make_kfile 一键打包脚本（Linux / macOS）
set -e
cd "$(dirname "$0")/src"
echo "[1/3] Installing pyinstaller ..."
pip install pyinstaller --quiet
echo "[2/3] Building make_kfile ..."
pyinstaller --onefile --name make_kfile \
  --add-data "paramk/_template.pkb.gz:paramk" \
  --distpath .. --workpath build --specpath build \
  paramk/generator.py
echo "[3/3] Cleaning ..."
rm -rf build make_kfile.spec
echo ""
echo "=== Done ==="
