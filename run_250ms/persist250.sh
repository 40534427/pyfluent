#!/bin/bash
# Persist the live checkpoint + tables into git every few minutes so a sandbox
# reset costs at most one interval of compute.
DIR=/workspace/run_250ms
RES=$DIR/results
BK=$DIR/backup
LOG=$DIR/persist.log
mkdir -p "$BK"
cd /workspace || exit 1

while :; do
  if [ -f "$RES/checkpoint.npz" ]; then
    gzip -c "$RES/checkpoint.npz" > "$BK/checkpoint.npz.gz.tmp" \
      && mv "$BK/checkpoint.npz.gz.tmp" "$BK/checkpoint.npz.gz"
    cp -f "$RES/history.csv" "$BK/history.csv" 2>/dev/null
    cp -f "$RES/line_force.csv" "$BK/line_force.csv" 2>/dev/null
    cp -f "$RES/run_meta.json" "$BK/run_meta.json" 2>/dev/null
    T=$(python3 -c "import numpy as np;print('%.1f'%(float(np.load('$RES/checkpoint.npz')['t'])*1000))" 2>/dev/null || echo "?")
    git add run_250ms/backup >/dev/null 2>&1
    git -c user.name="trae-agent" -c user.email="agent@local" \
      commit -qm "250ms ckpt t=${T}ms $(date '+%m-%d %H:%M')" >/dev/null 2>&1
    echo "[$(date '+%F %T')] persisted t=${T} ms" >> "$LOG"
  fi
  if [ -f "$DIR/run250.done" ] && ! ps aux | grep -q "[r]un_parachute"; then
    echo "[$(date '+%F %T')] run finished, persist loop exits" >> "$LOG"
    exit 0
  fi
  sleep 180
done
