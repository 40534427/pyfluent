#!/usr/bin/env bash
# ============================================================
#  打包 T5J 智能阻尼算例 + 自动计算报告
#  产物: /workspace/T5J_smart_damping_report.tar.gz
# ============================================================
set -e

SRC=/workspace/ale_parachute
OUT=$SRC/out/T5J_states
PKG=/workspace/T5J_smart_damping_report
rm -rf "$PKG"
mkdir -p "$PKG"/{src,input,results,build}

# ---- 1. 源码 ----
cp -r "$SRC"/aleparachute "$PKG"/src/
cp "$SRC"/run_parachute.py "$PKG"/src/
cp "$SRC"/plot_force_area.py "$PKG"/src/ 2>/dev/null || true
cp "$SRC"/requirements.txt "$PKG"/src/
echo "源码已复制"

# ---- 2. 输入文件 ----
cp /workspace/T5IJ_damping_compare_50ms/input/Parachute_F28.k "$PKG"/input/
echo "输入文件已复制 (Parachute_F28.k)"

# ---- 3. 计算结果 + 报告产物 ----
cp "$OUT"/history.csv "$PKG"/results/
cp "$OUT"/line_force.csv "$PKG"/results/
cp "$OUT"/calculation_report.html "$PKG"/results/ 2>/dev/null || true
# state VTK files (every 5 ms + final)
for f in "$OUT"/state_*_fluid.vtk "$OUT"/state_*_structure.vtk \
         "$OUT"/final_fluid.vtk "$OUT"/final_structure.vtk; do
    [ -f "$f" ] && cp "$f" "$PKG"/results/
done
# figures + data tables
[ -d "$OUT"/figures ] && cp -r "$OUT"/figures "$PKG"/results/
[ -d "$OUT"/data ] && cp -r "$OUT"/data "$PKG"/results/
echo "结果与报告已复制"

# ---- 4. Windows EXE 构建工具链 ----
cp "$SRC"/run_parachute.spec "$PKG"/build/
cp "$SRC"/build_windows_exe.bat "$PKG"/build/
cp "$SRC"/run_T5J_report.bat "$PKG"/build/
cp "$SRC"/requirements.txt "$PKG"/build/
cat > "$PKG"/build/README_build_exe.txt << 'EOF'
Windows 可执行文件构建说明
==========================

本包提供完整的 PyInstaller 构建工具链，在 Windows 上一键生成 run_parachute.exe：

1. 安装 Python 3.10+ (https://www.python.org)
2. 双击 build_windows_exe.bat
   - 自动安装 pyinstaller + numpy/scipy/matplotlib/psutil
   - 自动构建 dist/run_parachute.exe (单文件)
3. 双击 run_T5J_report.bat 运行 T5J 算例并生成报告

或手动构建：
   pip install pyinstaller numpy scipy matplotlib psutil
   pyinstaller run_parachute.spec

运行生成的 EXE：
   dist\run_parachute.exe --k Parachute_F28.k [options] --generate-report --outdir out
EOF
echo "EXE 构建工具链已复制"

# ---- 5. 顶层 README ----
cat > "$PKG"/README.md << 'EOF'
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
EOF
echo "README 已生成"

# ---- 6. 打包 ----
cd /workspace
tar -czf T5J_smart_damping_report.tar.gz T5J_smart_damping_report
echo "============================================"
echo "打包完成: /workspace/T5J_smart_damping_report.tar.gz"
du -sh /workspace/T5J_smart_damping_report.tar.gz
echo "============================================"
