#!/usr/bin/env bash
# T5E: R=0.5 m, +0.4 m downstream extension, PLEAK=0.1, 50 ms
set -e
python3 src/run_parachute.py --k input/Parachute_F28.k \
  --nx 30 --ny 40 --nz 30 --domain-radius 0.5 --y1-extension 0.4 \
  --endtime 0.050 --tssfac 0.8 \
  --tension-only-membrane --eb-frac 0.05 --vent-radius 0.04 \
  --constant-vel 220 --bend-scale 1 --bend-damp 0 \
  --pleak 0.1 --vtk-every 0.01 --outdir results_rerun
