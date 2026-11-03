# T2b 工况交付包（eb_stab = 0.003·ea，60 ms）

F28 降落伞开伞动力学 ALE 流固耦合算例。本包为该工况的**输入文件、计算结果与执行程序**的完整归档。

## 1. 工况参数

| 项目 | 取值 |
|---|---|
| K 文件 | `input/Parachute_F28.k`（LS-DYNA 原始模型） |
| 网格 | nx=16, ny=28, nz=16（流体背景网格） |
| 终止时间 | 60 ms |
| 时间步安全系数 tssfac | 0.8 |
| **eb_stab（膜稳定化模量）** | **0.003 · ea**（ea = 4.309e7 Pa → eb_stab ≈ 129 kPa） |
| 耦合罚刚度系数 pfac | 0.1（K 文件默认） |
| 结构阻尼 struct_damping | 0（无） |
| 泄漏系数 pleak | 0.1（K 文件默认） |

## 2. 关键结果（t = 60 ms）

| 指标 | 数值 |
|---|---|
| 伞衣半径 R | **0.2103 m**（目标 0.20 m） |
| 真实膜面积 | 0.3587 m² |
| 膜面积 / 投影面积 πR² | **2.58** |
| 锚点合力（终态） | 3911 N |
| 锚点合力峰值 | 4415 N @ 54.6 ms |
| 锚点力峰-峰值（末 20 ms） | 2232 N |
| 流体压力峰值 | 116.4 kPa |
| 结构速度峰值 | 1842 m/s（无 15 km/s 级数值尖峰） |
| 总步数 / 墙钟 | 38794 步 / 3208 s |

## 3. 目录结构

```
T2b_eb003_60ms_delivery/
├── README.md                 本说明
├── run_T2b.sh                复现脚本（可直接执行）
├── input/
│   └── Parachute_F28.k       输入文件
├── results/                  计算结果（本次运行产出）
│   ├── history.csv           时程：时间/步数/压力/半径/受力等 27 列
│   ├── line_force.csv        伞绳受力：16 根单绳逐时程
│   ├── final_fluid.vtk       终态流场
│   ├── final_structure.vtk   终态伞衣结构
│   └── run.log               运行日志
├── src/                      执行程序（Python 3，无外部编译依赖）
│   ├── run_parachute.py      驱动脚本 / 命令行入口
│   └── aleparachute/         求解器源码
│       ├── kfile.py          K 文件解析
│       ├── mesh.py           网格与膜单元（含 eb_stab 逻辑）
│       ├── fluid.py          ALE 流体求解（入流驱动 + ghost 边界）
│       ├── structure.py      膜结构求解（BT 壳 + 阻尼）
│       ├── coupling.py       CLLS 罚耦合（k_node / 泄漏）
│       ├── contact.py        自接触检测
│       ├── vtkio.py          VTK 输出
│       └── solver.py         时间推进与耦合装配
└── figures/                  结果曲线
```

## 4. 复现方式

依赖：Python 3 + numpy（可选 matplotlib 用于画图）。

```bash
bash run_T2b.sh                    # 结果写入 results_rerun/
bash run_T2b.sh /path/to/myout     # 指定输出目录
```

或手动执行等价命令：

```bash
cd src && OMP_NUM_THREADS=1 python3 -u run_parachute.py \
  --k ../input/Parachute_F28.k \
  --nx 16 --ny 28 --nz 16 --endtime 0.060 --tssfac 0.8 \
  --eb-stab-frac 0.003 --outdir ../results_rerun
```

## 5. 数据文件列定义

`history.csv`（逗号分隔，首行为列名）：

`time, step, fluid_mass, fluid_energy, fluid_kinetic, fluid_internal, p_max, p_min, u_max, canopy_radius, canopy_y, canopy_area, struct_kinetic, struct_vmax, coupling_drag, line_tension_max, line_tension_sum, line_anchor_force, contact_force_max, contact_pairs, contact_penetration, fsi_stiffness, fsi_impedance, fsi_dt, dt_fluid, dt_struct, dt_contact, dt`

`line_force.csv`：`time, line_1 ... line_16`（每根伞绳的张力，N，共 16 根）。

## 6. 说明

- `eb_stab` 的作用：原模型膜单元 b 向杨氏模量为 0，BT 单元在该方向无刚度，detJ→0 会导致发散。将其下限锁定为 `0.003·ea` 可提供面内稳定刚度，同时不显著阻碍充气（0.005·ea 会使 R 偏小约 12%）。
- 本工况未加结构阻尼。对比试验表明 `struct_damping=200` 可进一步压低锚点力振荡，但会使 R 从 0.210 降到 0.167 m。
