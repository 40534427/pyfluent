#!/usr/bin/env bash
# T4a: tension-only membrane, eb = 0.05 * ea, reinforced vent ring 0.04 m, 60 ms
set -e
cd "$(dirname "$0")"

K=${1:-input/Parachute_F28.k}
OUT=${2:-results_rerun}

python3 src/run_parachute.py \
  --k "$K" \
  --nx 16 --ny 28 --nz 16 \
  --endtime 0.060 --tssfac 0.8 \
  --tension-only-membrane \
  --eb-frac 0.05 \
  --vent-radius 0.04 \
  --vtk-every 0.01 \
  --outdir "$OUT"
