=======================================================================
  减速伞 ALE 流固耦合仿真 —— 50ms 计算结果交付包
  (参数来源：/workspace/kparam/params.json + Parachute_F28.k 原始卡)
=======================================================================

一、目录结构
-----------------------------------------------------------------------
T5J_50ms_final/
├── input/
│   └── Parachute_F28.k          LS-DYNA 原始 K 文件 (伞衣/伞绳/流域)
├── results/                     ★ 核心：全部计算结果
│   ├── history.csv              201 条诊断记录 (t=0~0.05s, 步长自动)
│   ├── line_force.csv           逐伞绳张力时程 (16 根 × 时间)
│   ├── final_fluid.vtk          最终时刻流场 VTK (t=0.05s)
│   ├── final_structure.vtk      最终时刻结构 VTK (t=0.05s)
│   ├── states/                  各时刻中间态 VTK (vtk_every=0.01s)
│   │   ├── state_0000_fluid.vtk / state_0000_structure.vtk   (t=0ms)
│   │   ├── state_0010_*.vtk                                    (t=10ms)
│   │   ├── state_0020_*.vtk                                    (t=20ms)
│   │   ├── state_0030_*.vtk                                    (t=30ms)
│   │   ├── state_0040_*.vtk                                    (t=40ms)
│   │   └── state_0050_*.vtk                                    (t=50ms)
│   ├── figures/                 9 张计算结果图 (PNG)
│   │   ├── anchor_force_time.png                 伞绳汇聚点力时程
│   │   ├── canopy_area_radius_time.png           伞衣投影面积/半径时程
│   │   ├── canopy_drag_time.png                  伞衣阻力时程
│   │   ├── canopy_shape_evolution.png            伞衣形态演化 (多时刻叠合)
│   │   ├── canopy_shape_side_evolution.png       伞衣侧视演化
│   │   ├── field_pressure.png                    最终时刻压力场云图
│   │   ├── field_velocity.png                    最终时刻速度场云图
│   │   ├── line_tension_per_line.png             16 根伞绳张力对比
│   │   └── struct_vmax_time.png                  结构节点最大速度时程
│   ├── data/                    所有曲线 .dat 原始数据 (同 .csv)
│   └── calculation_report.html  自动生成的计算报告 (浏览器打开)
├── src/paramk/                  参数化 K 文件生成器 (纯标准库 Python)
│   ├── generator.py             python -m paramk.generator 读取 params.json
│   └── _template.pkb.gz         内嵌网格模板 (伞衣 15024 节点 / 13056 壳)
└── docs/
    ├── params.json              79 参数 / 10 分组 (全中文注释)
    └── run_solver.bat           Windows 一键运行脚本
=======================================================================

二、计算工况参数
-----------------------------------------------------------------------
【伞衣（*MAT_FABRIC，kg-m-s）】
  幅数 n_gores = 16（拓扑固定）
  纬向带 n_weft_bands = 10（拓扑固定）
  锥角 cone_angle = 29.28°（折叠外轮廓基准）
  膜厚 t = 0.9 mm
  密度 ρ = 533.77 kg/m³
  经向模量 EA = 4.309e7 Pa
  纬向模量 EB = 0.05·EA = 2.1545e6 Pa（运行时 --eb-frac 0.05 覆盖 K 文件 eb=0）
  泊松比 PRBA = 0.14
  本构 = 仅受拉膜（tension-only-membrane 运行时生效）

【伞绳（16 根 × 10 段梁 = 160 个 *ELEMENT_BEAM）】
  长度 L = 1.5124 m
  截面积 A = 5e-5 m²（等效正方形边长 ts=tt=√A=0.00707 m）
  密度 ρ = 1200 kg/m³
  弹性模量 E = 2e9 Pa
  屈服应力 SIGY = 1e9 Pa

【来流 & 空气物性】
  来流速度 Vy = 220 m/s（恒速 --constant-vel 220）
  空气密度 ρ_air = 1.18 kg/m³
  环境压力 P = 100 kPa（EOS e0 = P/(γ-1) = 250 kJ/kg）
  比热比 γ = 1.4
  声速 c₀ = √(γP/ρ) ≈ 344 m/s
  马赫数 Ma = Vy/c₀ ≈ 0.64

【流域（auto 笛卡尔网格）】
  圆柱半径 R = 0.5 m（override K 文件内置 0.2348 m，消除伞衣阻塞）
  上游 y0 = -0.8996 m，下游 y1 = 0.5675 m（+0.4 m 延长尾流发展空间）
  网格 30 × 40 × 30 = 36000 单元 (实际有效流体单元 ~28640)

【求解器运行参数（ALEPARACHUTE）】
  耦合 = 罚函数 CLLS（CTYPE=11，DIREC=2，PFAC=0.1，PLEAK=0.1，ILEAK=2）
  FSI 声阻抗阻尼 cdamp = 1.0
  FSI 罚耦合欠松弛 omega = 0.2
  FSI 注入流场速度增量马赫数上限 = 0.3
  结构时间步缩放 TSSFAC = 0.8（初始 dt ≈ 3.81e-6 s）
  结构智能阻尼 struct_damping = 100 1/s + struct_damping_vmax = 30 m/s
      （节点速度 > 30 m/s 时阻尼关闭；< 18 m/s 时阻尼全开，之间平滑门控）
  弯曲边铰 bend_scale = 1（物理板弯曲刚度 D = E t³/12/(1-ν²)）、bend_damp = 0
  顶部通气孔加强环 vent_radius = 0.04 m
  自接触 = 关闭（--no-contact，加速计算）
  计算终止时间 endtime = 0.05 s (50 ms)
  VTK 中间态输出间隔 vtk_every = 0.01 s（5 个中间态 + 最终态）

【网格规模】
  结构节点 = 15169
  伞衣四边形壳单元 = 13056
  伞绳梁单元 = 160
  流体单元（auto 笛卡尔）= 28640
  运行总步数 ≈ 39900

三、查看方法
-----------------------------------------------------------------------
【看图表】 浏览器打开 results/calculation_report.html
  （该 HTML 引用同目录 figures/ 和 data/，请整体移动）

【看 VTK】 用 ParaView / VisIt / VTK Viewer 打开 results/final_*.vtk
  states/ 下的 VTK 可做动画（Reader: VTK Legacy File，时间序列）

【看原始数据】 直接用 Excel/记事本打开 results/history.csv 或 results/line_force.csv

四、参数化 K 文件生成
-----------------------------------------------------------------------
如果需要修改计算参数，编辑 docs/params.json 中的 "值" 字段，然后：

  Windows:  make_kfile.exe --params docs/params.json --output Parachute_custom.k
  Linux:    python3 -m src.paramk.generator --params docs/params.json --output Parachute_custom.k

生成的 .k 文件可直接给 LS-DYNA 或 ALEPARACHUTE 求解器使用。

五、备注
-----------------------------------------------------------------------
本交付包的计算结果来自与 params.json 默认参数完全一致的工况
（原始 Parachute_F28.k + run_T5E.sh 参数组合），
已端到端验证：history.csv 201 条记录覆盖 t=0→0.05s 完整过程，
结构状态始终有限（无 NaN/inf），伞衣从折叠态逐步展开到稳态开口。
=======================================================================
