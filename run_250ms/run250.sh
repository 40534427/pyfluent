#!/bin/bash
# T5J parachute: resumable run to 250 ms, git-backed checkpoints.
# Idempotent: safe to re-run after a sandbox reset (restores from git backup).
DIR=/workspace/run_250ms
RES=$DIR/results
BK=$DIR/backup
LOG=$DIR/run250.log
mkdir -p "$RES" "$BK"
cd /workspace/ale_parachute || exit 1

# --- restore the newest git-backed checkpoint if the working copy is gone
if [ ! -f "$RES/checkpoint.npz" ] && [ -f "$BK/checkpoint.npz.gz" ]; then
  gzip -dc "$BK/checkpoint.npz.gz" > "$RES/checkpoint.npz"
  cp -f "$BK/history.csv" "$RES/history.csv" 2>/dev/null
  cp -f "$BK/line_force.csv" "$RES/line_force.csv" 2>/dev/null
  echo "[$(date '+%F %T')] restored checkpoint from git backup" >> "$LOG"
fi

cur_t() {
  python3 - "$RES/checkpoint.npz" <<'PY'
import os, sys
import numpy as np
p = sys.argv[1]
print("%.6f" % float(np.load(p)["t"]) if os.path.exists(p) else "0.000000")
PY
}

attempt=0
while :; do
  attempt=$((attempt + 1))
  T=$(cur_t)
  echo "[$(date '+%F %T')] attempt $attempt, t=$T s" >> "$LOG"
  if python3 -c "import sys; sys.exit(0 if float('$T') >= 0.2499 else 1)"; then
    echo "[$(date '+%F %T')] target reached: t=$T s" >> "$LOG"
    break
  fi
  RESTART=""
  [ -f "$RES/checkpoint.npz" ] && RESTART="--restart $RES/checkpoint.npz"
  python3 -u run_parachute.py \
    --k "$DIR/Parachute_0903_origcards.k" \
    --nx 30 --ny 40 --nz 30 --domain-radius 0.5 --y1-extension 0.4 \
    --endtime 0.25 --tssfac 0.8 --cfl 0.5 --constant-vel 220 \
    --bend-scale 1 --bend-damp 0 --pleak 0.1 \
    --struct-damping 100 --struct-damping-vmax 30 --eb-frac 0.05 \
    --vent-radius 0.006 --vent-ring-E-factor 0 --vent-ring-A-factor 2 \
    --tension-only-membrane --no-contact \
    --vtk-every 0.01 --checkpoint-every 0.001 --max-steps 400000 \
    $RESTART --outdir "$RES" >> "$LOG" 2>&1
  T=$(cur_t)
  echo "[$(date '+%F %T')] solver exited at t=$T s" >> "$LOG"
  if python3 -c "import sys; sys.exit(0 if float('$T') >= 0.2499 else 1)"; then break; fi
  if [ "$attempt" -ge 40 ]; then
    echo "[$(date '+%F %T')] giving up after $attempt attempts" >> "$LOG"
    exit 1
  fi
  sleep 10
done

touch "$DIR/run250.done"
bash "$DIR/finalize250.sh"
