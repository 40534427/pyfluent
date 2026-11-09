#!/bin/bash
# Finalize the 150 ms delivery: wait for run end, measure vent, report,
# copy results, write README, zip and verify.
set -u
RES=/workspace/run_150ms_final/results
DEL=/workspace/T5J_150ms_delivery

# 1) wait for completion
for i in $(seq 1 400); do
  grep -q "ALL DONE resume150" /workspace/run_150ms_final/resume150.log && break
  if ! ps aux | grep -q "[r]un_parachute"; then
    echo "solver died before ALL DONE"; tail -5 /workspace/run_150ms_final/resume150.log; exit 1
  fi
  sleep 60
done
echo "[finalize] run finished at $(date -u +%H:%M:%S)"

cd /workspace
# 2) measure vent on final structure state
python3 measure_vent.py "$RES" > "$RES/vent_measurement.txt" 2>&1 || echo "[finalize] vent measure failed"
tail -8 "$RES/vent_measurement.txt"

# 3) regenerate report from full history
python3 run_parachute.py --k /workspace/run_150ms_vent/Parachute_0903.k \
  --report-only --generate-report --outdir "$RES" || echo "[finalize] report failed"

# 4) copy results into delivery
mkdir -p "$DEL/results"
cp "$RES"/history.csv "$RES"/line_force.csv "$RES"/run_meta.json \
   "$RES"/calculation_report.html "$RES"/vent_measurement.txt "$DEL/results/" 2>/dev/null
# VTK states: keep every state (they are the animation frames)
for f in "$RES"/state_*_fluid.vtk "$RES"/state_*_structure.vtk \
         "$RES"/final_fluid.vtk "$RES"/final_structure.vtk; do
  [ -f "$f" ] && cp "$f" "$DEL/results/"
done
echo "[finalize] results copied: $(ls "$DEL/results" | wc -l) files, $(du -sh "$DEL/results" | cut -f1)"

# 5) README
python3 - <<'EOF'
import csv, json, os
RES='/workspace/run_150ms_final/results'
DEL='/workspace/T5J_150ms_delivery'
rows=list(csv.DictReader(open(RES+'/history.csv')))
mx=max(rows,key=lambda r: float(r['coupling_drag']))
f=rows[-1]
meta=json.load(open(RES+'/run_meta.json'))
vent=''
vp=RES+'/vent_measurement.txt'
if os.path.exists(vp):
    for ln in open(vp):
        if 'vent' in ln.lower() or 'ratio' in ln.lower(): vent+=ln
peak=float(mx['coupling_drag']); tp=float(mx['time'])
Rpk=float(mx['canopy_radius']); Rf=float(f['canopy_radius'])
ratio_pk=float(mx.get('vent_ratio',0) or 0)
readme=f"""# T5J 减速伞 150 ms 充气展开 ALE 流固耦合计算交付包

## 1. 结果摘要（Parachute_0903.k 原始 K 文件，恒定来流 220 m/s）

| 项目 | 数值 |
|---|---|
| 计算终了时间 | {float(f['time'])*1000:.1f} ms（步数 {f['step']}） |
| 气动阻力峰载 | {peak:.1f} N @ t = {tp*1000:.1f} ms |
| 峰载时伞衣最大投影半径 | {Rpk*1000:.1f} mm |
| 终态伞衣最大投影半径 | {Rf*1000:.1f} mm |
| 顶孔直径（终态） | 见 results/vent_measurement.txt |
| 顶孔/投影径比值（终态） | 见 results/vent_measurement.txt |
| 伞绳总数 | 16 根 × 10 段 |

注：本交付包为原始 K 文件基线算例（质量缩放 mass_scale = 1.0）。
顶孔刚性环：--vent-radius 0.006（半径 6 mm 刚性环，径向投影约束）。

## 2. 目录说明

- `kinput/Parachute_0903.k` —— LS-DYNA 关键字文件（53 MB，15024 节点 / 13056 伞衣壳 + 160 伞绳梁 + ALE 流体）
- `src/` —— 求解器源码（aleparachute 包 + run_parachute.py + 绘图脚本）
- `bin/` —— 可选的 Windows 可执行文件放置目录（用 src/build_windows_exe.bat 构建）
- `results/` —— 全部计算结果
  - `history.csv` 每 5 ms 一行的全局历史（阻力、伞衣半径、压力、线张力等）
  - `line_force.csv` 16 根伞绳逐时刻张力
  - `state_*.vtk` 每 5 ms 流体/结构状态（Paraview 可视化）
  - `final_*.vtk` 终态
  - `calculation_report.html` 计算报告（工况、网格、求解设置、曲线图）
  - `run_meta.json` 运行元数据（参数、CPU、墙钟）
  - `vent_measurement.txt` 顶孔量测

## 3. Windows 一键运行

1. `run_parachute.bat` 全新计算（约 3.2 h @ 3 核 Xeon）
2. `run_resume.bat` 从 results/checkpoint.npz 断点续算
3. `run_report_only.bat` 仅重新生成报告

系统有 Python 时自动使用 Python（依赖 numpy/scipy/matplotlib），
否则回退 bin/run_parachute.exe（先用 src/build_windows_exe.bat 构建）。

## 4. 关键计算设置

- 流域：圆柱半径 0.5 m（消除阻塞），30×40×30，下游 +0.4 m
- 气体：ρ0=1.18 kg/m³，p0=100 kPa，Ma∞=0.639，动压 28.6 kPa
- 耦合：CLLS 罚函数，omega=0.2，cdamp=1.0，pleak=0.1
- 结构：仅受拉膜（tension-only），EB=0.05·EA，smart 阻尼 100 1/s（vmax 门限 30 m/s）
- 伞衣壳 THEORY=5 / BWC=2，沙漏 IHQ=1 qh=0.1
- 顶孔 6 mm 刚性环（E_factor=0 → 径向投影约束）
"""
open(DEL+'/README.md','w').write(readme)
print('[finalize] README written')
EOF

# 6) zip and verify
cd /workspace/T5J_150ms_delivery
rm -f /workspace/T5J_150ms_delivery.zip
zip -rq /workspace/T5J_150ms_delivery.zip .
echo "[finalize] zip: $(du -sh /workspace/T5J_150ms_delivery.zip | cut -f1), $(unzip -l /workspace/T5J_150ms_delivery.zip | tail -1)"
unzip -t /workspace/T5J_150ms_delivery.zip > /dev/null && echo "[finalize] zip integrity OK" || echo "[finalize] ZIP CORRUPT"
echo "ALL DONE finalize $(date -u +%H:%M:%S)"
