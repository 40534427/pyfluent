#!/usr/bin/env bash
# Reproduce the 80 ms constant-220 m/s inflation with the corrected
# non-reflecting ghost state and the edge-hinge bending stiffness.
set -euo pipefail
cd "$(dirname "$0")"

python3 src/run_parachute.py \
  --k input/Parachute_F28.k \
  --nx 16 --ny 28 --nz 16 \
  --endtime 0.080 --tssfac 0.8 \
  --tension-only-membrane --eb-frac 0.05 --vent-radius 0.04 \
  --constant-vel 220 --bend-scale 1 --bend-damp 0 \
  --vtk-every 0.01 --outdir results_rerun
