#!/bin/sh
# 用已有 CSV 和运行元数据重新生成报告（麒麟 V10 / 其他 Linux x86_64）
set -e
cd "$(dirname "$0")"

EXE="bin/linux-x86_64/run_parachute"
if [ ! -x "$EXE" ]; then
    echo "[ERROR] $EXE not found or not executable."
    exit 1
fi
if [ ! -f "results/history.csv" ] || [ ! -f "results/line_force.csv" ]; then
    echo "[ERROR] results/history.csv or results/line_force.csv is missing."
    exit 1
fi

"$EXE" --report-only --outdir "results"

echo
echo "Report regenerated: results/calculation_report.html"
