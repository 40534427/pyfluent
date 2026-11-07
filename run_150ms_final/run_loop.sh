#!/bin/bash
# 150 ms parachute inflation run with automatic checkpoint resume.
# Rigid vent ring (E-factor 0) at design radius 6 mm.
cd /workspace/ale_parachute
for i in $(seq 1 40); do
  EXTRA=""
  if [ -f /workspace/run_150ms_final/results/checkpoint.npz ]; then
    EXTRA="--restart /workspace/run_150ms_final/results/checkpoint.npz"
  fi
  echo "=== segment $i $(date -u +%H:%M:%S) ==="
  python3 run_parachute.py \
    --k /workspace/run_150ms_vent/Parachute_0903.k --nx 30 --ny 40 --nz 30 \
    --domain-radius 0.5 --y1-extension 0.4 --endtime 0.15 --tssfac 0.8 \
    --vtk-every 0.005 --checkpoint-every 0.005 --cfl 0.5 --constant-vel 220 \
    --bend-scale 1 --bend-damp 0 --pleak 0.1 --struct-damping 100 \
    --struct-damping-vmax 30 --eb-frac 0.05 --vent-radius 0.006 \
    --vent-ring-E-factor 0 --vent-ring-A-factor 2 --tension-only-membrane \
    --no-contact --max-steps 400000 --quiet \
    --outdir /workspace/run_150ms_final/results $EXTRA || exit 1
  LAST=$(tail -1 /workspace/run_150ms_final/results/history.csv)
  T=$(echo "$LAST" | cut -d, -f1)
  echo "segment $i done, t=$T"
  awk -v t="$T" 'BEGIN{exit !(t>=0.1499)}' && break
done
echo "ALL DONE $(date -u +%H:%M:%S)"
