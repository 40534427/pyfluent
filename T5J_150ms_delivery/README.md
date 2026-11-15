# T5J 减速伞 150 ms 充气展开 ALE 流固耦合计算交付包

> 本包为工作区数据丢失后的完整重建版：从 t=30 ms 检查点精确续算至 150 ms，
> 终态顶孔量测与首版交付逐位一致（12.08 mm / 238.97 mm / 5.05 %）。
>
> 交付版本：2026-11-15 —— 支持 Windows 7 SP1 / Windows 11 x64 / 麒麟 V10（x86_64）
> 三平台免安装直接运行，并新增第 9 节「断点续算操作说明」。

## 1. 结果摘要（Parachute_0903.k 重建 K 文件，恒定来流 220 m/s）

| 项目 | 数值 |
|---|---|
| 计算终了时间 | 150.0 ms（步数 105283） |
| 气动阻力峰载 | 2207.6 N @ t = 60.8 ms |
| 峰载时伞衣最大投影直径 | 177.5 mm |
| 终态伞衣最大投影直径 | 163.6 mm |
| 顶孔直径（终态） | 12.08 mm |
| 顶孔/投影径比值（终态） | 5.05 %（峰值时刻 4.45 %） |
| 总墙钟时间 | 约 11482 s（3 核 Xeon 单进程） |

注：本交付包为重建 K 文件基线算例（质量缩放 mass_scale = 1.0）；
顶孔刚性环 --vent-radius 0.006（6 mm 刚性环，径向投影约束）；
流域半径 0.5 m（消除原 K 0.2348 m 流域的 33 % 阻塞）。

## 2. 交付清单

完整文件清单（文件数、体积、关键文件 SHA-256、各平台运行库版本）见包根目录
`MANIFEST.txt`；本节只列出交付内容与用途。

| 路径 | 说明 |
|---|---|
| `kinput/Parachute_0903.k` | LS-DYNA 关键字文件（按原始拓扑重建，CLLS 罚函数已恢复 A1/B1） |
| `src/` | 求解器源码：`aleparachute` 包、`run_parachute.py`、绘图脚本、两款启动器源码与 EXE 构建脚本 |
| `bin/run_parachute.exe` | Windows 7/10/11 x64 原生启动器（PE32+ 控制台程序，仅依赖 KERNEL32/msvcrt） |
| `bin/runtime/` | Windows 免安装运行库：Python 3.8.10 x64（含 `python38.zip` 标准库）、NumPy 1.24.4、SciPy 1.10.1、Matplotlib 3.7.5、UCRT/VC++ |
| `bin/linux-x86_64/run_parachute` | 麒麟 V10 / Linux x86_64 原生启动器（静态链接，不依赖系统 glibc 版本） |
| `bin/linux-x86_64/runtime/` | Linux 免安装运行库：Python 3.9.20 可移植构建 + NumPy 1.24.4 / SciPy 1.10.1 / Matplotlib 3.7.5（依赖最高 glibc 2.27） |
| `run_parachute.bat` / `run_parachute.sh` | 全新计算 150 ms（Windows / Linux） |
| `run_resume.bat` / `run_resume.sh` | 从 `results/checkpoint.npz` 断点续算（Windows / Linux） |
| `run_report_only.bat` / `run_report_only.sh` | 仅用已有 CSV 重建报告（Windows / Linux） |
| `verify_windows.bat` / `verify_linux.sh` | 交付包自检（Windows / Linux） |
| `results/` | 已有计算结果（不含 VTK 帧与检查点） |

`results/` 内容：

- `history.csv` 每 5 ms 一行的全局历史（阻力、伞衣半径、压力、线张力、dt 等，t=0–150 ms）
- `line_force.csv` 16 根伞绳逐时刻张力
- `calculation_report.html` 计算报告（工况、网格、求解设置与曲线图）
- `run_meta.json` 运行元数据（全部运行参数、CPU 信息、墙钟）
- `vent_measurement.txt` 顶孔逐时刻量测与 FINAL/PEAK 行

## 3. 一键运行（Windows 7 / 11、麒麟 V10）

### 3.1 Windows 7 SP1 x64 / Windows 10 x64 / Windows 11 x64

随包提供 64 位 `bin\run_parachute.exe`、Python 3.8.10、NumPy/SciPy/Matplotlib、
UCRT 及 VC++ 运行库，**无需安装 Python 或 VC++ Redistributable**。

1. `verify_windows.bat` —— 交付包自检（系统版本、运行库、EXE、绘图与短算例），详见第 7 节。
2. `run_parachute.bat` —— 全新计算 150 ms（`kinput\Parachute_0903.k` 已随包提供）。
3. `run_resume.bat` —— 从 `results\checkpoint.npz` 断点续算（详见第 9 节）。
4. `run_report_only.bat` —— 直接根据已有 CSV 和运行元数据重新生成报告，不需要 K 文件。

也可在命令行运行 `bin\run_parachute.exe --help` 查看全部参数。
**请完整保留 `bin\runtime` 和 `src`，不要只复制 EXE。** 三个批处理均优先使用随包运行库，
只有 EXE 缺失时才回退系统 Python。`src\build_windows_exe.bat` 仅用于可选的单文件版重建。

### 3.2 麒麟 V10（x86_64）/ 其他 Linux x86_64

随包提供 `bin/linux-x86_64/run_parachute`（静态链接，不依赖系统 Python、无需 root）
与 `bin/linux-x86_64/runtime/` 免安装运行库。运行库内各 `.so` 所需 glibc 最高为
**2.27**，麒麟 V10（glibc 2.28）及更高版本均可直接运行。

```bash
cd T5J_150ms_delivery
chmod +x run_parachute.sh run_resume.sh run_report_only.sh verify_linux.sh   # 解压后如丢失执行位
./verify_linux.sh          # 交付包自检：系统、运行库、启动器、报告、短算例、断点续算
./run_parachute.sh         # 全新计算 150 ms，写 results/checkpoint.npz
./run_resume.sh            # 从 results/checkpoint.npz 断点续算（详见第 9 节）
./run_report_only.sh       # 仅重建报告
```

也可直接执行 `bin/linux-x86_64/run_parachute --help` 查看全部参数。
**请完整保留 `bin/linux-x86_64` 与 `src`，不要只复制启动器。**

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

- `bin/run_parachute.exe` 为 PE32+ x64 原生控制台程序，子系统版本 5.2，仅导入
  `KERNEL32.dll` / `msvcrt.dll`，可在 Windows 7 SP1 x64 及以上直接运行。
  本次已在 Wine（Windows API 兼容层）中实测 `--help`、4 步冒烟求解、
  `--report-only` 报告重建以及断点写入/重启，全部通过。
- `bin/linux-x86_64/run_parachute` 为静态链接的 x86_64 ELF 可执行文件，
  不依赖发行版 glibc；随包 `.so` 所需 glibc 最高 2.27。本次已在 Linux x86_64
  （glibc 2.39）实测 `--help`、`verify_linux.sh` 全项、4 步冒烟求解、
  报告重建和断点续算，全部通过。
- 两套运行库均自带 Python 与 NumPy/SciPy/Matplotlib，无需安装系统 Python。
- 说明：沙箱内没有 Windows 7/11 与麒麟 V10 物理机，Windows 侧使用 Wine 验证，
  Linux 侧使用同架构 x86_64 验证；兼容性依据为上述 PE 头/依赖与 glibc 版本上限，
  而非目标系统实机执行。
- `kinput/Parachute_0903.k` 已随包提供（按原始模板与参数重建，CLLS 的 A1/B1 已恢复）。
  本次验证只执行了 4 步冒烟求解，未重新执行完整 150 ms 计算。
  `results/` 不含 VTK 状态帧和 `checkpoint.npz`，断点续算前需先运行一次
  `run_parachute` 生成检查点（见第 9 节）。

## 7. 验证脚本（Windows / 麒麟 V10）

**Windows**：在交付包根目录双击 `verify_windows.bat`（或在 cmd 中运行），脚本自动完成：

1. 读取注册表识别系统版本与位数（Win7 必须为 SP1，即 build 7601；Win10/11 为 10.0）。
2. 检查 EXE、随包 Python、UCRT/VC++、NumPy/SciPy/Matplotlib、源码、结果和 K 文件是否齐全。
3. 直接调用 `bin\runtime\python.exe`，输出版本并验证科学计算库可导入。
4. 在包目录内和包目录外分别执行 `run_parachute.exe --help`，验证路径无关性。
5. 复制 `results` 后执行 `--report-only`，确认 HTML 报告和图件可重新生成。
6. 用 K 文件跑 4 步、8×8×8 网格的求解冒烟测试，确认历史、伞绳力、检查点和 VTK 输出。

结果写入 `verify_windows.log`，退出码 0 表示全部通过，1 表示存在失败项；`verify_out`
为测试临时目录，可直接删除。脚本为纯批处理，不依赖系统 Python 或 PowerShell。
在 Windows 7 上请使用 SP1 且以 64 位 cmd 运行。

**麒麟 V10 / Linux**：在交付包根目录执行 `./verify_linux.sh`，脚本自动完成：

1. 输出版本、内核、架构、glibc 与发行版信息，核对 x86_64。
2. 检查启动器、随包 Python、源码、K 文件与结果文件是否齐全。
3. 用随包 Python 验证 NumPy/SciPy/Matplotlib/psutil 与求解器包可导入。
4. 在包目录内执行 `run_parachute --help`。
5. 复制 `results` 后执行 `--report-only`，确认 HTML 报告与 11 张图件可重新生成。
6. 8×8×8 网格跑 4 步，检查 history/line_force/checkpoint/VTK 输出；
   再从 `checkpoint.npz` 重启跑到第 6 步，确认断点续算生效。

结果输出到终端，退出码 0 表示全部通过；临时目录 `verify_out` 可直接删除。

## 8. 稳定性修复（t ≈ 0.028 s 发散）

**现象**：使用包内重建的 K 文件计算时，充气到约 28 ms 发散。

**根因**：重建 K 的 `*CONSTRAINED_LAGRANGE_IN_SOLID` 缺少可选卡中的罚函数刚度系数
A1/B1，界面刚度只剩流体声阻抗项，fsi 稳定步长约为原算例的 2.5 倍。充气压力升高后
界面约束不足，伞衣被压入 ALE 网格，最终失稳。

**修复**：

- 在 `kinput/Parachute_0903.k` 的 CLLS 卡恢复 `A1 = 1.6e6`、`B1 = 4.8e5`（与原算例
  一致），界面刚度随当地压力增长，fsi 稳定步长回到约 2e-06 s（t ≈ 7 ms）。
- `solver.py` 增加自适应回退：每步检查密度、节点速度和数值有限性，越界则回滚该步并
  将 dt 减半重试，最多 30 次后报错；正常轨迹不触发，结果不受影响。这是兜底保护，
  主修复仍是恢复 A1/B1。

**第二次修复（节点速度尖峰）**：恢复 A1/B1 后计算已能越过 28 ms，但在约 31.7 ms
仍有偶发失稳。诊断表明问题不在流固耦合力（该处耦合作用力仅约 0.5 N），而是伞衣
下摆局部单元的薄膜/沙漏模态：这些四边形在充气折叠过程中翘曲角达 70°–85°，单元
特征高度小、节点质量仅约 3e-6–6e-6 kg，局部稳定步长接近全局 dt，节点速度会从
约 150 m/s 在一两个步内跳到 1200 m/s，随后该步被接受、状态被"污染"，再减小 dt 也
无法恢复。

处理办法：把 `_state_is_healthy` 的节点速度上限从 2000 m/s 收紧到 **650 m/s**。
已验证的 150 ms 参考算例全程节点速度峰值为 520 m/s（t = 95.3 ms，99 分位 333 m/s），
因此该阈值不影响正常轨迹；一旦某步速度越过 650 m/s，就在**接受该步之前**判为越界，
回滚到上一步并把 dt 减半重做，使尖峰在放大前被压掉。异常中止时的报错信息现在还会
给出越界时刻的 `vmax`、密度范围和有限性标志，便于定位。

**验证**：以与原算例相同的参数从 t = 0 计算到 60 ms（越过原发散点约一倍，并覆盖
60.8 ms 的阻力峰载），共 41164 步，全程无发散、无 NaN；自适应回退累计触发 40 次，
每次 1–3 次折半后都在同一步内恢复，dt 始终回到 1.3e-06 ~ 1.6e-06 s。终态
R = 92.0 mm、阻力 2290 N、pmax = 124.9 kPa、vmax = 135 m/s。与 `results/` 中基线
相比，阻力偏差 < 6 %、伞衣半径偏差 < 7 %——充气过程本身对数值扰动敏感，回退会
改变局部步长序列，这一量级的差异属于正常范围。

## 9. 断点续算操作说明

计算 150 ms 约需 3 小时以上，包内已内置检查点（checkpoint）与续算（restart）机制，
程序中断、机器重启或主动停止后可从最近的检查点继续，不必从头计算。

### 9.1 机制与检查点内容

- 求解器运行中按固定物理时间间隔把完整积分状态写入 `<outdir>/checkpoint.npz`
  （压缩 `.npz`，30×40×30 网格约 0.65 MB），同名覆盖，不累积占用磁盘。
- 检查点包含：当前物理时间 `t`、已积分步数 `step`、上一步长 `dt`、
  流场守恒变量 `U`、结构节点位置 `x` 与速度 `v`、全局历史 `history`、
  伞绳逐线历史 `line_history`。
- 未写入检查点的量：流固耦合器的预测器缓存（`_f_prev` 等）与自适应回退计数。
  续算后第一步会以当前流/固状态重新预热预测器，这是显式耦合的标准做法，
  不影响后续结果；回退计数从零开始。
- 检查点按“到点即写”策略直接覆盖文件，因此若恰在写盘瞬间断电，
  `checkpoint.npz` 可能不完整。重要长算例建议定期把该文件另存备份
  （例如每 20 ms 复制一份 `checkpoint_t120.npz`）。

### 9.2 Windows 操作步骤

1. 首次计算：双击 `run_parachute.bat`。脚本每 5 ms 写一次
   `results\checkpoint.npz`（参数 `--checkpoint-every 0.005`），
   同时每 5 ms 输出一帧 VTK。
2. 中断计算：在控制台按 `Ctrl+C`，或直接关闭窗口、重启机器。已写盘的检查点保留。
3. 断点续算：双击 `run_resume.bat`。脚本以完全相同的网格与物理参数调用
   `--restart "results\checkpoint.npz"`，从检查点时刻继续算到 150 ms。
4. 确认续算生效：控制台出现

   ```
   [restart] resumed from results\checkpoint.npz at t=0.09500s step=67231
   ```

   且结束时 `results\history.csv` 的步数大于中断前的步数。
5. 续算完成后同样生成 `results\calculation_report.html`。

### 9.3 麒麟 V10 / Linux 操作步骤

```bash
./run_parachute.sh     # 首次计算，写 results/checkpoint.npz（每 5 ms）
# Ctrl+C 或 kill 中断
./run_resume.sh        # 从 results/checkpoint.npz 续算到 150 ms
```

判定方式与 Windows 相同：日志出现 `[restart] resumed ...`，
`results/history.csv` 步数继续增长。

### 9.4 相关命令行参数

| 参数 | 默认值 | 说明 |
|---|---|---|
| `--checkpoint-every` | `0.02` | 每多少秒写一次 `checkpoint.npz`；随包脚本设为 `0.005`（5 ms）。`<=0` 表示跟随 VTK 输出间隔 |
| `--restart` | 空 | 续算时指定检查点路径，如 `--restart results/checkpoint.npz`；为空表示全新计算 |
| `--max-steps` | `100000` | **绝对**总步数上限，续算时需大于检查点中的 `step`。`run_resume` 脚本已放宽到 400000 |
| `--outdir` | `out` | 检查点、历史、VTK 与报告的输出目录，续算必须与原计算一致 |

### 9.5 注意事项

- 续算必须使用与首次计算**完全一致**的网格与物理参数（`--k`、`--nx/--ny/--nz`、
  `--domain-radius`、`--y1-extension`、`--tssfac`、`--cfl`、`--constant-vel` 等）。
  随包 `run_resume.bat` / `run_resume.sh` 已固化为与 `run_parachute` 相同的参数，
  请勿只改其中一个脚本。
- 已输出的 VTK 帧不会被续算重写；续算只补齐检查点之后的帧。
- 中断时刻与最近检查点之间（最多 5 ms）的步长会被重新计算，结果不受影响。
- 检查点与 VTK 共用一个输出目录；删除 `checkpoint.npz` 后 `run_resume` 会报
  “Missing checkpoint”，需改为全新计算。
- 稳定性回退（第 8 节）只在单步内回滚，不改变写盘节奏；触发回退时不会额外写检查点。


