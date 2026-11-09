#!/bin/bash
cd /workspace/ale_parachute || exit 1
exec python3 -u run_parachute.py \
  --k /workspace/run_200ms_v3/kinput_match/Parachute_match.k \
  --nx 30 --ny 40 --nz 30 --domain-radius 0.5 --y1-extension 0.4 \
  --endtime 0.20 \
  --tssfac 0.8 --cfl 0.5 \
  --constant-vel 220 \
  --bend-scale 1 --bend-damp 0 \
  --pleak 0.1 \
  --struct-damping 100 --struct-damping-vmax 30 \
  --eb-frac 0.05 \
  --vent-radius 0.006 --vent-ring-E-factor 0 --vent-ring-A-factor 2 \
  --tension-only-membrane \
  --no-contact \
  --vtk-every 0.005 --checkpoint-every 0.005 \
  --max-steps 400000 \
  --outdir /workspace/run_200ms_v3/results
