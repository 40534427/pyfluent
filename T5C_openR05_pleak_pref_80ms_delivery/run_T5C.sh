#!/usr/bin/env bash
# T5C: enlarged cylindrical domain (R=0.5 m), fabric leakage on, unified pref
set -e
python3 src/run_parachute.py --k input/Parachute_F28.k \
  --nx 30 --ny 28 --nz 30 --domain-radius 0.5 \
  --endtime 0.080 --tssfac 0.8 \
  --tension-only-membrane --eb-frac 0.05 --vent-radius 0.04 \
  --constant-vel 220 --bend-scale 1 --bend-damp 0 \
  --pleak 0.5 --vtk-every 0.01 --outdir results_rerun
