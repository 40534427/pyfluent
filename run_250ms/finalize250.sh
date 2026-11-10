#!/bin/bash
# T5J 250 ms: measure -> report -> 3-view -> delivery zip -> standalone HTML.
RES=/workspace/run_250ms/results
DIR=/workspace/run_250ms
DELIV=$DIR/delivery
LOG=$DIR/finalize.log
exec > "$LOG" 2>&1
set -x
echo "[$(date '+%F %T')] finalize start"

# 1. vent (apex hole) measurement
python3 /workspace/measure_vent.py "$RES" > "$RES/vent_measurement.txt" 2>&1 || true

# 2. calculation report from existing outputs
(cd /workspace/ale_parachute && timeout 1800 python3 run_parachute.py \
  --k "$DIR/Parachute_0903_origcards.k" \
  --report-only --outdir "$RES") || true

# 3. canopy 3-view of the final frame
if [ -f "$RES/final_structure.vtk" ]; then
  python3 /workspace/run_300ms/render3view.py "$RES/final_structure.vtk" \
    /workspace/T5J_canopy_3view_t250ms.png \
    "T5J Parachute Canopy 3-View - t = 250 ms" || true
  cp -f /workspace/T5J_canopy_3view_t250ms.png "$RES/" 2>/dev/null || true
fi

# 4. delivery package
rm -rf "$DELIV"
mkdir -p "$DELIV/results" "$DELIV/kinput" "$DELIV/src"
cp -f "$RES/history.csv" "$RES/line_force.csv" "$RES/run_meta.json" \
      "$RES/vent_measurement.txt" "$RES/calculation_report.html" \
      "$DELIV/results/" 2>/dev/null
cp -r "$RES/figures" "$DELIV/results/" 2>/dev/null
cp -f "$RES/final_structure.vtk" "$RES/final_fluid.vtk" "$DELIV/results/" 2>/dev/null
gzip -c "$RES/checkpoint.npz" > "$DELIV/results/checkpoint.npz.gz" 2>/dev/null
cp -f /workspace/T5J_canopy_3view_t250ms.png "$DELIV/results/" 2>/dev/null
cp -r /workspace/ale_parachute/aleparachute "$DELIV/src/" 2>/dev/null
cp -f /workspace/ale_parachute/run_parachute.py \
      /workspace/ale_parachute/requirements.txt "$DELIV/src/" 2>/dev/null
gzip -c "$DIR/Parachute_0903_origcards.k" > "$DELIV/kinput/Parachute_0903_origcards.k.gz"

python3 - << 'PYEOF'
import csv, os
RES = "/workspace/run_250ms/results"
rows = list(csv.DictReader(open(f"{RES}/history.csv")))
last = rows[-1]
peak = max(rows, key=lambda r: float(r["coupling_drag"]))
v = open(f"{RES}/vent_measurement.txt").read().strip() if os.path.exists(f"{RES}/vent_measurement.txt") else ""
body = f"""# T5J 减速伞 250 ms 充气展开 ALE 流固耦合计算交付包

## 结果摘要

| 项目 | 数值 |
|---|---|
| 计算终了时间 | {float(last['time'])*1000:.1f} ms（累计步数 {int(float(last['step']))}） |
| 终态伞衣投影半径 / 直径 | {float(last['canopy_radius'])*1000:.1f} mm / {float(last['canopy_radius'])*2000:.1f} mm |
| 终态气动阻力 | {float(last['coupling_drag']):.1f} N |
| 全程阻力峰载 | {float(peak['coupling_drag']):.1f} N @ t = {float(peak['time'])*1000:.1f} ms |
| 终态伞绳最大张力 | {float(last['line_tension_max']):.1f} N |

{v}

## 目录

- `results/` — history.csv, line_force.csv, calculation_report.html(+figures),
  vent_measurement.txt, 终态 VTK, checkpoint.npz.gz, 三视图 PNG
- `kinput/` — LS-DYNA 关键字文件（gz 压缩）
- `src/` — 求解器源码

## 续算

```bash
gzip -dc results/checkpoint.npz.gz > results/checkpoint.npz
python3 src/run_parachute.py --k <K文件> --restart results/checkpoint.npz --endtime 0.30 ...
```
"""
open("/workspace/run_250ms/delivery/README.md", "w").write(body)
print("README ok")
PYEOF

rm -f /workspace/T5J_250ms_delivery.zip
(cd "$DELIV" && zip -rq /workspace/T5J_250ms_delivery.zip .)
unzip -tq /workspace/T5J_250ms_delivery.zip && echo "zip integrity OK"
gzip -c /workspace/T5J_250ms_delivery.zip > /workspace/T5J_250ms_delivery.zip.gz
ls -lh /workspace/T5J_250ms_delivery.zip /workspace/T5J_250ms_delivery.zip.gz

# 5. standalone HTML report + its figure folder
if [ -f "$RES/calculation_report.html" ]; then
  cp -f "$RES/calculation_report.html" /workspace/T5J_250ms_report.html
  rm -rf /workspace/T5J_250ms_figures
  cp -r "$RES/figures" /workspace/T5J_250ms_figures 2>/dev/null
  sed -i 's#figures/#T5J_250ms_figures/#g' /workspace/T5J_250ms_report.html
  echo "standalone report: /workspace/T5J_250ms_report.html + T5J_250ms_figures/"
fi

# 6. commit the light deliverables (no LFS-suffixed names)
cd /workspace
git add T5J_250ms_report.html T5J_canopy_3view_t250ms.png T5J_250ms_delivery.zip.gz \
        run_250ms/delivery/README.md run_250ms/results/history.csv \
        run_250ms/results/line_force.csv run_250ms/results/vent_measurement.txt \
        run_250ms/results/calculation_report.html >/dev/null 2>&1
git -c user.name="trae-agent" -c user.email="agent@local" \
  commit -qm "250ms delivery: report, 3-view, zip.gz, tables" >/dev/null 2>&1

echo "[$(date '+%F %T')] FINALIZE DONE"
echo "===250MS_DELIVERY_READY==="
