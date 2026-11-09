#!/bin/bash
# Auto-finalize after the 0->200ms run exits.
set -u
R=/workspace/run_200ms_v3/results
D=/workspace/run_200ms_v3/delivery
Z=/workspace/T5J_200ms_delivery.zip
LOG=/workspace/run_200ms_v3/finalize.log
exec > >(tee -a "$LOG") 2>&1

echo "[$(date '+F %T')] watcher: waiting for solver to exit"
while pgrep -f "[r]un_parachute.py" >/dev/null 2>&1; do sleep 30; done
echo "[$(date '+F %T')] solver exited"

sleep 3
if [ ! -f "$R/state_0000_structure.vtk" ]; then
  echo "WARN: no state_0000_structure.vtk; measurement may fail"
fi

echo "[$(date '+F %T')] vent measurement"
python3 /workspace/measure_vent.py "$R" > "$R/vent_measurement.txt" 2>&1 || echo "measure failed"

echo "[$(date '+F %T')] report"
(cd /workspace/ale_parachute && python3 run_parachute.py \
  --k /workspace/run_200ms_v3/kinput_match/Parachute_match.k \
  --report-only --outdir "$R" >/workspace/run_200ms_v3/report.log 2>&1) || echo "report failed"

echo "[$(date '+F %T')] build delivery"
rm -rf "$D"; mkdir -p "$D/results" "$D/kinput" "$D/src" "$D/bin"
cp -r /workspace/ale_parachute/aleparachute "$D/src/"
cp /workspace/ale_parachute/run_parachute.py "$D/src/" 2>/dev/null
cp /workspace/ale_parachute/requirements.txt "$D/src/" 2>/dev/null
cp /workspace/run_200ms_v3/kinput_match/Parachute_match.k "$D/kinput/Parachute_0903_reconstructed.k"
cp -r "$R"/. "$D/results/"
echo "This package was recomputed from t=0 because the original K file and\n150ms checkpoint were lost with a sandbox reset. The input K was rebuilt\nfrom kparam templates (cone_angle=29.28 deg, line_length=1.51 m)." > "$D/kinput/README_reconstructed.txt"
echo "bin" > "$D/bin/README.txt"

echo "[$(date '+F %T')] zip"
rm -f "$Z"
(cd "$D" && zip -rq "$Z" .)
unzip -tq "$Z" && echo "zip integrity OK"
ls -lh "$Z"

echo "[$(date '+F %T')] http"
pkill -f "http.server 8766" 2>/dev/null
cd /workspace && setsid nohup python3 -m http.server 8766 --directory /workspace >/dev/null 2>&1 &
sleep 2
curl -sI http://127.0.0.1:8766/T5J_200ms_delivery.zip | head -1
echo "[$(date '+F %T')] DONE"
