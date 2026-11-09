#!/bin/bash
# Resume the original 150 ms baseline run from the t=0.03 checkpoint.
# Regenerates VTK states / history / line_force / checkpoints to t=0.15.
cd /workspace/ale_parachute
for i in $(seq 1 40); do
  EXTRA=""
  if [ -f /workspace/run_150ms_final/results/checkpoint_t0.03_backup.npz ]; then
    EXTRA="--restart /workspace/run_150ms_final/results/checkpoint_t0.03_backup.npz"
    # pick the newest rolling checkpoint if present
    NEW=$(ls -t /workspace/run_150ms_final/results/checkpoint.npz 2>/dev/null | head -1)
    if [ -n "$NEW" ]; then
      T=$(python3 -c "import numpy as np;print('%.4f'%np.load('$NEW',allow_pickle=True)['t'])" 2>/dev/null)
      awk -v t="$T" 'BEGIN{exit !(t>0.0301)}' && EXTRA="--restart $NEW"
    fi
  fi
  echo "=== resume150 segment $i $(date -u +%H:%M:%S) ==="
  python3 run_parachute.py \
    --k /workspace/run_150ms_vent/Parachute_0903.k --nx 30 --ny 40 --nz 30 \
    --domain-radius 0.5 --y1-extension 0.4 --endtime 0.15 --tssfac 0.8 --cfl 0.5 \
    --constant-vel 220 --bend-scale 1 --bend-damp 0 --pleak 0.1 \
    --struct-damping 100 --struct-damping-vmax 30 --eb-frac 0.05 \
    --vent-radius 0.006 --vent-ring-E-factor 0 --vent-ring-A-factor 2 \
    --tension-only-membrane --no-contact \
    --vtk-every 0.005 --checkpoint-every 0.005 \
    --max-steps 400000 --outdir /workspace/run_150ms_final/results $EXTRA || exit 1
  T=$(python3 -c "
import csv
rows=list(csv.DictReader(open('/workspace/run_150ms_final/results/history.csv')))
print(rows[-1]['time'])" 2>/dev/null)
  echo "resume150 segment $i done, t=$T"
  awk -v t="$T" 'BEGIN{exit !(t>=0.1499)}' && break
done
echo "ALL DONE resume150 $(date -u +%H:%M:%S)"
