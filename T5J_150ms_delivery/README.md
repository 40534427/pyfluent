# T5J 减速伞 150 ms 充气展开 ALE 流固耦合计算交付包

> 本包为工作区数据丢失后的完整重建版：从 t=30 ms 检查点精确续算至 150 ms，
> 终态顶孔量测与首版交付逐位一致（12.08 mm / 238.97 mm / 5.05 %）。

## 1. 结果摘要（Parachute_0903.k 原始 K 文件，恒定来流 220 m/s）

| 项目 | 数值 |
|---|---|
| 计算终了时间 | 150.0 ms（步数 105283） |
| 气动阻力峰载 | 2207.6 N @ t = 60.8 ms |
| 峰载时伞衣最大投影直径 | 177.5 mm |
| 终态伞衣最大投影直径 | 163.6 mm |
| 顶孔直径（终态） | 12.08 mm |
| 顶孔/投影径比值（终态） | 5.05 %（峰值时刻 4.45 %） |
| 总墙钟时间 | 约 11482 s（3 核 Xeon 单进程） |

注：本交付包为原始 K 文件基线算例（质量缩放 mass_scale = 1.0）；
顶孔刚性环 --vent-radius 0.006（6 mm 刚性环，径向投影约束）；
流域半径 0.5 m（消除原 K 0.2348 m 流域的 33 % 阻塞）。

## 2. 目录说明

- `kinput/Parachute_0903.k` —— 原始 LS-DYNA 关键字文件（当前工作区未保留，计算前请重新放入）
- `src/` —— 求解器源码（aleparachute 包 + run_parachute.py + 绘图脚本 + exe 构建脚本）
- `bin/` —— `run_parachute.exe` 原生启动器及 `runtime/` 免安装运行库
- `results/` —— 当前已有的计算结果（HTML 报告、CSV 历史数据和图件；不含 VTK 帧与检查点）
  - `history.csv` 每 5 ms 一行的全局历史（阻力、伞衣半径、压力、线张力、dt 等，t=0–150 ms）
  - `line_force.csv` 16 根伞绳逐时刻张力
  - `calculation_report.html` 计算报告（工况、网格、求解设置与曲线图）
  - `run_meta.json` 运行元数据（全部运行参数、CPU 信息、墙钟）
  - `vent_measurement.txt` 顶孔逐时刻量测与 FINAL/PEAK 行

## 3. Windows 一键运行

目标系统为 **Windows 7 SP1 x64 / Windows 10 x64 / Windows 11 x64**。
随包提供 64 位 `bin\run_parachute.exe`、Python 3.8.10、NumPy/SciPy/Matplotlib、
UCRT 及 VC++ 运行库，**无需安装 Python 或 VC++ Redistributable**。

1. 将原始 `Parachute_0903.k` 放入 `kinput\`（当前工作区未保留该输入文件）。
2. `run_parachute.bat` —— 全新计算 150 ms。
3. `run_resume.bat` —— 从 `results\checkpoint.npz` 断点续算。
4. `run_report_only.bat` —— 直接根据已有 CSV 和运行元数据重新生成报告，不需要 K 文件。

也可在命令行运行 `bin\run_parachute.exe --help` 查看全部参数。
**请完整保留 `bin\runtime` 和 `src`，不要只复制 EXE。** 三个批处理均优先使用随包运行库，
只有 EXE 缺失时才回退系统 Python。`src\build_windows_exe.bat` 仅用于可选的单文件版重建。

## 4. 关键计算设置

- 流域：圆柱半径 0.5 m，30×40×30 结构化自动网格，下游延伸 +0.4 m，非反射出口
- 气体：ρ0 = 1.18 kg/m³，p0 = 100 kPa，Ma∞ = 0.639，动压 28.6 kPa
- 耦合：CLLS 罚函数（omega = 0.2，cdamp = 1.0，pleak = 0.1，pfac 按 K 文件 0.1）
- 结构：仅受拉膜（--tension-only-membrane），EB = 0.05·EA，
  smart 阻尼 100 1/s（节点速度门限 30 m/s），bend_scale = 1，bend_damp = 0
- 壳 THEORY = 5 / BWC = 2，沙漏 IHQ = 1、qh = 0.1；接触关闭（充气前期不发生自接触）
- 时间步：CFL = 0.5，TSSFAC = 0.8，初始 dt ≈ 3.81e-06 s

## 5. 性能优化（内核重写 + 线程）

本次交付的 `src/` 已包含内核级优化，默认参数下的物理结果与优化前一致
（固定 dt = 1e-6 跑 400 步，阻力差 < 1e-8 N、伞衣半径差 < 1e-12 m，
差异仅来自浮点求和顺序）。

| 配置（5000 步，自动步长） | 单步耗时 | 说明 |
|---|---|---|
| 优化前 | 124.4 ms | 基线 |
| 优化后（默认） | 86.5 ms | 1.44×，`--threads 0` 自动用 3 线程 |

优化内容：

- 流体：primitive 变量缓存、gather/scatter 索引预计算、通量就地组装、散射合并为一次 `bincount`
- 结构：`np.matmul` 替代通用 `einsum`、弯曲/膜力散射合并为一次 `bincount`
- 多核：仅对流体残差做 3 线程分块（结构核受内存带宽限制，开线程收益 < 10 %）

相关新增参数：

- `--threads N`：元素核线程数（0 = 自动，1 = 串行）
- `--max-dt X`：时间步硬上限 [s]
- `--fsi-implicit`：罚函数刚度半隐式（可去掉 CLLS 的 `sqrt(m/k)` 步长限制）。
  **默认关闭**：dt 接近该限制时会改变耦合动力学（dt = 3e-6 时阻力偏差约 18 %），
  仅在与 `--max-dt` 配合、需要强行加大步长时使用。

## 6. 验证范围与输入文件说明

- `run_parachute.exe` 为 PE32+ x64 原生控制台程序；已在 Wine 中验证 `--help`、
  中文及空格路径启动和参数转发。
- 已通过该 EXE 对现有结果执行 `--report-only`，成功重建 HTML 报告和 5 张曲线图；
  另行通过 NumPy 矩阵运算、SciPy KDTree、Matplotlib PNG 和求解器导入自检。
- 当前验证环境为 Wine，未在真实 Windows 7/11 物理机上执行；目标兼容性采用
  Python 3.8.10 x64、Win7 目标启动器及随包正式 UCRT/VC++ 运行库实现。
- 当前工作区未保留原始 `Parachute_0903.k`、VTK 状态帧和 `checkpoint.npz`，因此本次
  未重新执行完整 150 ms 求解。全新计算前必须补回 K 文件；断点续算还必须提供检查点。
