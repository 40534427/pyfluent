# T4a 工况交付包（60 ms）

ALE / 罚函数耦合降落伞充气求解器，T4 方案第一组：膜松弛纤维 + 顶孔加强环。

## 工况定义

| 参数 | 值 | 说明 |
|---|---|---|
| 网格 | nx=16, ny=28, nz=16 | 自动圆柱 ALE 网格，5824 单元 |
| 终止时间 | 0.060 s | 固定步长 dt≈1.95e-6 s（后期），17427 步 |
| tssfac | 0.8 | 显式安全系数 |
| 膜本构 | `--tension-only-membrane` | 松弛纤维：受压方向应力置零（*MAT_FABRIC 语义） |
| 环向模量 | `--eb-frac 0.05` | eb = 0.05·ea（替代旧 eb_stab=0.003·ea） |
| 顶孔约束 | `--vent-radius 0.04` | 顶孔节点串接 tension-only 加强环，L0=2π·0.04/16≈0.0157 m，初始松弛 |
| 流固耦合 | 默认 CLLS | pfac=0.1，ileak 默认，无额外阻尼 |

## 复现

```bash
bash run_T4a.sh                  # 结果写入 results_rerun/
# 或指定输入/输出
bash run_T4a.sh input/Parachute_F28.k out_60ms
```

依赖：Python 3、numpy、scipy、matplotlib。源码在 `src/`（`run_parachute.py` + `aleparachute/`）。

## 结果

| 指标 | 数值 |
|---|---|
| 锚点合力峰值 | 2876 N @ 43.5 ms |
| 锚点合力 50–60 ms 均值 | 2152 N |
| 锚点合力末值 | 2463 N |
| 伞衣平均半径 R | 0.107 m |
| 顶孔半径 | 0.054 m（目标 0.04，环梁被拉伸约 34%） |
| 伞衣高度 h | 0.207 m |
| h/R | 1.53（未完全展开） |
| 膜面积 | 0.135 m² |

对比旧工况 T2b（eb_stab=0.003·ea，无顶孔约束）：峰值 4415 N、50–60 ms 均值 3858 N、R=0.210 m、顶孔 0.145 m。
T4a 把峰值压低约 35%，顶孔受控，但充气显著滞后（60 ms 仍为长筒/环状，h/R=1.53）。

## 交付内容

- `input/Parachute_F28.k` — 原始 LS-DYNA 关键词文件
- `results/history.csv` — 逐步诊断（时间、R、高度、压强、锚点合力、膜面积等）
- `results/line_force.csv` — 16 条伞绳底端张力时间历程
- `results/final_structure.vtk` / `final_fluid.vtk` — 终态结构/流场
- `results/state_*_structure.vtk` — 每 10 ms 的伞衣状态帧（用于变形渲染）
- `results/run.log` — 完整求解日志
- `figures/canopy_deform_T4a_eb005_vent04_60ms.png` — 侧视+俯视变形过程图
- `figures/T4a_anchor_force_area.png` — 锚点合力与膜面积曲线
- `src/` — 求解器与绘图脚本（`plot_canopy_deform.py` 可直接重绘变形图）

## 备注

- 顶孔加强环为 tension-only 弹性索，仅提供环向约束、不承受压力；目标半径 0.04 m 是初始松弛长度，实际孔径随膜拉伸增大。
- 本工况的力峰值已接近 2500 N 上限，但展开度明显不足；后续建议先延长到 80–100 ms 观察是否继续充气，或把顶孔目标半径降到 0.03 m 并提高环梁刚度。
