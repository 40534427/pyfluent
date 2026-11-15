#!/bin/sh
# 全新计算 150 ms（麒麟 V10 / 其他 Linux x86_64）
set -e
cd "$(dirname "$0")"

EXE="bin/linux-x86_64/run_parachute"
if [ ! -x "$EXE" ]; then
    echo "[ERROR] $EXE not found or not executable."
    echo "        Restore the complete package (bin/linux-x86_64)."
    exit 1
fi
if [ ! -f "kinput/Parachute_0903.k" ]; then
    echo "[ERROR] Missing input: kinput/Parachute_0903.k"
    exit 1
fi
mkdir -p results

"$EXE" --k "kinput/Parachute_0903.k" \
  --nx 30 --ny 40 --nz 30 --domain-radius 0.5 --y1-extension 0.4 \
  --endtime 0.150 --tssfac 0.8 --cfl 0.5 --constant-vel 220 \
  --bend-scale 1 --bend-damp 0 --pleak 0.1 \
  --struct-damping 100 --struct-damping-vmax 30 \
  --eb-frac 0.05 --vent-radius 0.006 --vent-ring-E-factor 0 --vent-ring-A-factor 2 \
  --tension-only-membrane --no-contact \
  --vtk-every 0.005 --checkpoint-every 0.005 \
  --generate-report --outdir "results"

echo
echo "Calculation completed."
echo "Report: results/calculation_report.html"
