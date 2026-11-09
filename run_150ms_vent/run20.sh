#!/bin/bash
# 20 ms short comparison case.  Usage: run20.sh <tag> <kfile> <mass-scale>
set -u
TAG=$1; K=$2; MS=$3
OUT=/workspace/run20_$TAG
mkdir -p "$OUT"
cd /workspace/ale_parachute
for i in $(seq 1 30); do
  EXTRA=""
  if [ -f "$OUT/checkpoint.npz" ]; then
    EXTRA="--restart $OUT/checkpoint.npz"
  fi
  echo "=== $TAG segment $i $(date -u +%H:%M:%S) ==="
  python3 run_parachute.py \
    --k "$K" --nx 30 --ny 40 --nz 30 \
    --domain-radius 0.5 --y1-extension 0.4 --endtime 0.02 --tssfac 0.8 \
    --vtk-every 0.005 --checkpoint-every 0.005 --cfl 0.5 --constant-vel 220 \
    --mass-scale "$MS" \
    --bend-scale 1 --bend-damp 0 --pleak 0.1 --struct-damping 100 \
    --struct-damping-vmax 30 --eb-frac 0.05 --vent-radius 0.006 \
    --vent-ring-E-factor 0 --vent-ring-A-factor 2 --tension-only-membrane \
    --no-contact --max-steps 120000 --quiet \
    --outdir "$OUT" $EXTRA
  rc=$?
  LAST=$(tail -1 "$OUT/history.csv" 2>/dev/null)
  T=$(echo "$LAST" | cut -d, -f1)
  echo "segment $i rc=$rc t=$T"
  awk -v t="${T:-0}" 'BEGIN{exit !(t>=0.0199)}' && break
  if [ $rc -ne 0 ] && [ -z "$EXTRA" ]; then
    echo "hard failure without checkpoint, aborting"
    break
  fi
done
echo "ALL DONE $TAG $(date -u +%H:%M:%S)"
