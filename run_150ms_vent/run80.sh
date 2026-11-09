#!/bin/bash
# 80 ms extension of the revised (corrected) parachute case.
# Resumes from the 20 ms checkpoint of run20_rev, keeps the same solver flags.
# Loop with checkpoint resume so it survives process restarts.
cd /workspace/ale_parachute
for i in $(seq 1 80); do
  EXTRA=""
  if [ -f /workspace/run80_rev/checkpoint.npz ]; then
    EXTRA="--restart /workspace/run80_rev/checkpoint.npz"
  elif [ -f /workspace/run20_rev/checkpoint.npz ]; then
    EXTRA="--restart /workspace/run20_rev/checkpoint.npz"
  fi
  echo "=== rev80 segment $i $(date -u +%H:%M:%S) ==="
  python3 run_parachute.py \
    --k /workspace/run_150ms_vent/Parachute_0903_rev.k --nx 30 --ny 40 --nz 30 \
    --domain-radius 0.5 --y1-extension 0.4 --endtime 0.08 --tssfac 0.8 \
    --cfl 0.5 --mass-scale 5 --constant-vel 220 --bend-scale 1 --bend-damp 0 \
    --pleak 0.1 --struct-damping 100 --struct-damping-vmax 30 \
    --eb-frac 0.05 --vent-radius 0.006 --vent-ring-E-factor 0 --vent-ring-A-factor 2 \
    --tension-only-membrane --no-contact --max-steps 1000000 \
    --vtk-every 0.005 --checkpoint-every 0.005 \
    --outdir /workspace/run80_rev $EXTRA || exit 1
  LAST=$(tail -1 /workspace/run80_rev/history.csv)
  T=$(echo "$LAST" | cut -d, -f1)
  echo "rev80 segment $i done, t=$T"
  awk -v t="$T" 'BEGIN{exit !(t>=0.0799)}' && break
done
echo "ALL DONE rev80 $(date -u +%H:%M:%S)"
