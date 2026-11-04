#!/usr/bin/env bash
# T5IJ: 三向对比 —— 阻尼对伞力的影响
# 共用配置: R=0.5m, 下游 +0.4m, PLEAK=0.1, eb_frac=0.05, bend_scale=1, 恒定 220 m/s, 50 ms
set -e
# T5E 基线（无阻尼）
python3 src/run_parachute.py --k input/Parachute_F28.k \
  --nx 30 --ny 40 --nz 30 --domain-radius 0.5 --y1-extension 0.4 \
  --endtime 0.050 --tssfac 0.8 \
  --tension-only-membrane --eb-frac 0.05 --vent-radius 0.04 \
  --constant-vel 220 --bend-scale 1 --bend-damp 0 --pleak 0.1 \
  --struct-damping 0 --outdir results/T5E

# T5I plain 100/s 阻尼
python3 src/run_parachute.py --k input/Parachute_F28.k \
  --nx 30 --ny 40 --nz 30 --domain-radius 0.5 --y1-extension 0.4 \
  --endtime 0.050 --tssfac 0.8 \
  --tension-only-membrane --eb-frac 0.05 --vent-radius 0.04 \
  --constant-vel 220 --bend-scale 1 --bend-damp 0 --pleak 0.1 \
  --struct-damping 100 --outdir results/T5I

# T5J smart 阻尼 100/s + vmax 门限 30 m/s
python3 src/run_parachute.py --k input/Parachute_F28.k \
  --nx 30 --ny 40 --nz 30 --domain-radius 0.5 --y1-extension 0.4 \
  --endtime 0.050 --tssfac 0.8 \
  --tension-only-membrane --eb-frac 0.05 --vent-radius 0.04 \
  --constant-vel 220 --bend-scale 1 --bend-damp 0 --pleak 0.1 \
  --struct-damping 100 --struct-damping-vmax 30 --outdir results/T5J
