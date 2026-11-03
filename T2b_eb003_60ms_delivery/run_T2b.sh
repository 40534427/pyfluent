#!/usr/bin/env bash
# T2b 工况复现脚本：eb_stab = 0.003*ea，无结构阻尼，60 ms
# 用法：  bash run_T2b.sh          （在任意目录执行均可）
set -e
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUT="${1:-$HERE/results_rerun}"
mkdir -p "$OUT"

OMP_NUM_THREADS=1 python3 -u "$HERE/src/run_parachute.py" \
  --k "$HERE/input/Parachute_F28.k" \
  --nx 16 --ny 28 --nz 16 \
  --endtime 0.060 \
  --tssfac 0.8 \
  --eb-stab-frac 0.003 \
  --outdir "$OUT"

echo "done -> $OUT"
