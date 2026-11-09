#!/bin/bash
# Finalize T5J 300ms: measure -> report -> 3-view -> package -> standalone HTML
RES=/workspace/run_300ms/results
DELIV=/workspace/run_300ms/delivery
ZIP=/workspace/T5J_300ms_delivery.zip
LOG=/workspace/run_300ms/finalize.log
exec > "$LOG" 2>&1
set -x

echo "[$(date '+%F %T')] finalize start"

# 1. vent measurement
python3 /workspace/measure_vent.py "$RES" > "$RES/vent_measurement.txt" 2>&1 || true

# 2. calculation report (report-only)
(cd /workspace/ale_parachute && timeout 900 python3 run_parachute.py \
  --k /workspace/run_300ms/Parachute_0903_origcards.k \
  --report-only --outdir "$RES" ) || true

# 3. 3-view at final frame
FINAL_VTK=$(ls "$RES"/state_*structure.vtk 2>/dev/null | grep -v state_0000 | sort | tail -1)
if [ -n "$FINAL_VTK" ]; then
  TVAL=$(python3 -c "import numpy as np; d=np.load('$RES/checkpoint.npz'); print('%.0f'%(float(d['t'])*1000))" 2>/dev/null || echo "final")
  python3 /workspace/run_300ms/render3view.py "$FINAL_VTK" \
    "/workspace/T5J_canopy_3view_t${TVAL}ms.png" \
    "T5J Parachute Canopy 3-View - t = ${TVAL} ms" || true
  cp "/workspace/T5J_canopy_3view_t${TVAL}ms.png" "$RES/" 2>/dev/null || true
fi

# 4. delivery package
rm -rf "$DELIV"; mkdir -p "$DELIV/results" "$DELIV/kinput" "$DELIV/src"
cp -r /workspace/ale_parachute/aleparachute "$DELIV/src/" 2>/dev/null
cp /workspace/ale_parachute/run_parachute.py /workspace/ale_parachute/requirements.txt "$DELIV/src/" 2>/dev/null
cp -r "$RES"/* "$DELIV/results/" 2>/dev/null
cp /workspace/run_300ms/Parachute_0903_origcards.k "$DELIV/kinput/" 2>/dev/null

python3 - << 'PYEOF'
import csv, os
RES="/workspace/run_300ms/results"; DELIV="/workspace/run_300ms/delivery"
try:
    rows=list(csv.DictReader(open(f"{RES}/history.csv")))
    mx=max(rows,key=lambda r:float(r['coupling_drag'])); f=rows[-1]
    peak=float(mx['coupling_drag']); tp=float(mx['time']); Rf=float(f['canopy_radius'])
    vtxt=open(f"{RES}/vent_measurement.txt").read() if os.path.exists(f"{RES}/vent_measurement.txt") else ""
    body=f"""# T5J 减速伞 300 ms 充气展开 ALE 流固耦合计算交付包

> 本包从 t=5 ms 检查点续算至 300 ms。

## 结果摘要

| 项目 | 数值 |
|---|---|
| 计算终了时间 | {float(f['time'])*1000:.1f} ms（步数 {int(float(f['step']))}） |
| 全程气动阻力峰载 | {peak:.1f} N @ t = {tp*1000:.1f} ms |
| 终态伞衣投影直径 | {Rf*2*1000:.1f} mm |

{vtxt.strip()}

## 目录
- kinput/Parachute_match.k  LS-DYNA 关键字文件
- src/  求解器源码
- results/  history.csv, line_force.csv, checkpoint.npz, state_*.vtk, calculation_report.html(+figures), vent_measurement.txt, 三视图 PNG
"""
    open(f"{DELIV}/README.md","w").write(body)
except Exception as e:
    print("README failed:", e)
PYEOF

rm -f "$ZIP"
(cd "$DELIV" && zip -rq "$ZIP" .)
unzip -tq "$ZIP" && echo "zip integrity OK"
ls -lh "$ZIP"

# 5. standalone HTML report at workspace root
if [ -f "$RES/calculation_report.html" ]; then
  cp "$RES/calculation_report.html" /workspace/T5J_300ms_report.html
  rm -rf /workspace/T5J_300ms_report_assets
  mkdir -p /workspace/T5J_300ms_report_assets
  cp -r "$RES/figures" /workspace/T5J_300ms_report_assets/ 2>/dev/null
  cp -r "$RES/data"    /workspace/T5J_300ms_report_assets/ 2>/dev/null
  echo "standalone report: /workspace/T5J_300ms_report.html (+ T5J_300ms_report_assets/)"
fi

echo "[$(date '+%F %T')] FINALIZE DONE"
echo "===300MS_DELIVERY_READY==="
