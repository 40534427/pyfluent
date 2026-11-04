# 减速伞展开数值计算 —— T5J 智能阻尼算例交付包

## 目录结构
```
T5J_smart_damping_report/
├── src/                      源码 (aleparachute 包 + run_parachute.py)
├── input/                    输入文件 Parachute_F28.k
├── results/                  计算结果与报告
│   ├── calculation_report.html   ★ 计算报告（浏览器打开）
│   ├── history.csv               完整时程历史
│   ├── line_force.csv            逐伞绳张力时程
│   ├── state_*_fluid.vtk         各时刻流场 VTK
│   ├── state_*_structure.vtk     各时刻结构 VTK
│   ├── figures/                  所有图片 + 动画 MP4
│   └── data/                     所有曲线 .dat 原始数据
└── build/                    Windows EXE 构建工具链
    ├── build_windows_exe.bat     一键构建 run_parachute.exe
    ├── run_parachute.spec        PyInstaller 规格文件
    ├── run_T5J_report.bat        一键运行 T5J + 报告
    └── requirements.txt          Python 依赖
```

## 算例配置 (T5J)
- 流域: 圆柱 R=0.5 m, 下游延长 +0.4 m, 网格 30×40×30 (28640 单元)
- 来流: 恒定 220 m/s, 50 ms
- 结构: *MAT_FABRIC 膜 + 16 根伞绳, bend_scale=1 (物理板刚度)
- 材料: EA=4.309e7 Pa, EB=0.05·EA, PRBA=0.14, t=0.9 mm
- 阻尼: struct_damping=100 1/s + struct_damping_vmax=30 m/s (智能门控)
- FSI: 罚函数耦合, PLEAK=0.1, cdamp=1.0, tssfac=0.8

## 计算报告包含
a) 工况条件（流域/网格/求解器/材料）
b) 伞绳力/汇聚点受力时程曲线 + .dat 原始数据
c) 伞衣形态演化、速度/压力流场云图、应力/应变云图 + 动画
d) CPU 型号/核数/基频 + 计算用时

## 快速开始
**查看报告**: 用浏览器打开 `results/calculation_report.html`

**重新运行 (Python)**:
```bash
cd src
pip install -r requirements.txt
python run_parachute.py --k ../input/Parachute_F28.k \
  --nx 30 --ny 40 --nz 30 --domain-radius 0.5 --y1-extension 0.4 \
  --endtime 0.050 --tssfac 0.8 --tension-only-membrane --eb-frac 0.05 \
  --vent-radius 0.04 --constant-vel 220 --bend-scale 1 --bend-damp 0 \
  --pleak 0.1 --struct-damping 100 --struct-damping-vmax 30 \
  --vtk-every 0.005 --generate-report --outdir ../results
```

**构建 Windows EXE**: 见 `build/README_build_exe.txt`
