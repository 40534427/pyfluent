#!/usr/bin/env bash
# T5: constant 220 m/s inflow + edge-hinge bending stiffness, 80 ms
set -e
cd "$(dirname "$0")"

K=${1:-input/Parachute_F28.k}
OUT=${2:-results_rerun}

python3 src/run_parachute.py \
  --k "$K" \
  --nx 16 --ny 28 --nz 16 \
  --endtime 0.080 --tssfac 0.8 \
  --tension-only-membrane \
  --eb-frac 0.05 \
  --vent-radius 0.04 \
  --constant-vel 220 \
  --bend-scale 1.0 \
  --bend-damp 0.0 \
  --vtk-every 0.01 \
  --outdir "$OUT"
