#!/usr/bin/env bash
# Re-run T5J with VTK state output every 5 ms for report figures/video
set -e
cd /workspace/ale_parachute
mkdir -p out/T5J_states
exec python3 run_parachute.py \
  --k /workspace/T5IJ_damping_compare_50ms/input/Parachute_F28.k \
  --nx 30 --ny 40 --nz 30 --domain-radius 0.5 --y1-extension 0.4 \
  --endtime 0.050 --tssfac 0.8 \
  --tension-only-membrane --eb-frac 0.05 --vent-radius 0.04 \
  --constant-vel 220 --bend-scale 1 --bend-damp 0 --pleak 0.1 \
  --struct-damping 100 --struct-damping-vmax 30 \
  --vtk-every 0.005 \
  --outdir out/T5J_states
