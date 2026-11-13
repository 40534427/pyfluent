"""Benchmark harness: run N steps of the T5J case with a given source tree.

usage: run_bench.py SRC_DIR OUT_JSON [--steps N] [--implicit 0|1] [--fixed-dt X]
"""
import sys, os, time, json, dataclasses
import argparse
import numpy as np

ap = argparse.ArgumentParser()
ap.add_argument("src")
ap.add_argument("out")
ap.add_argument("--steps", type=int, default=400)
ap.add_argument("--implicit", type=int, default=1)
ap.add_argument("--fixed-dt", type=float, default=0.0)
args = ap.parse_args()
sys.path.insert(0, args.src)
from aleparachute import (load_model, auto_cylinder_grid, fluid_geometry,
                          Simulation, Options)

K = os.environ.get("BENCH_K", "/workspace/bench/deck.k")
model = load_model(K)
y0, y1, r, cx, cz = fluid_geometry(model)
grid = auto_cylinder_grid(y0, y1 + 0.4, 0.5, 30, 40, 30, cx, cz)
kw = dict(endtime=0.30, cfl=0.5, tssfac=0.8, constant_vel=220,
          bend_scale=1.0, bend_damp=0.0, pleak=0.1,
          struct_damping=100.0, struct_damping_vmax=30.0, eb_frac=0.05,
          vent_radius=0.006, vent_ring_E_factor=0.0, vent_ring_A_factor=2.0,
          membrane_tension_only=True, contact=False,
          vtk_every=0.0, checkpoint_every=0.0, max_steps=args.steps,
          verbose=False, outdir="/tmp/bench_" + str(os.getpid()),
          fsi_implicit=bool(args.implicit))
names = {f.name for f in dataclasses.fields(Options)}
opt = Options(**{k: v for k, v in kw.items() if k in names})
sim = Simulation(model, grid, opt)
if args.fixed_dt > 0:
    opt.tssfac = 1.0
    sim.stable_dt = lambda: args.fixed_dt

t0 = time.perf_counter()
res = sim.run()
wall = time.perf_counter() - t0
n = max(res["steps"], 1)
h = res["history"][-1]
out = dict(src=args.src, steps=n, wall=wall, ms_per_step=wall / n * 1e3,
           t_end=h["time"], dt_last=h["dt"], dt_mean=h["time"] / n,
           drag=h["coupling_drag"], R=h["canopy_radius"], area=h["canopy_area"],
           vmax=h["struct_vmax"], umax=h["u_max"], p_max=h["p_max"],
           Tc=h["line_tension_max"], fsi=float(h["fsi_dt"]),
           implicit=args.implicit, fixed_dt=args.fixed_dt,
           traj=[[r0["time"], r0["coupling_drag"], r0["canopy_radius"],
                  r0["canopy_area"]] for r0 in res["history"]])
json.dump(out, open(args.out, "w"), indent=1)
print(f"{os.path.basename(os.path.dirname(args.src) or args.src):<10} "
      f"impl={args.implicit} fixed={args.fixed_dt:.0e} steps={n} "
      f"{out['ms_per_step']:.1f}ms/step t={out['t_end']*1e3:.2f}ms "
      f"dt={out['dt_mean']:.2e} drag={out['drag']:.1f}N R={out['R']*1e3:.2f}mm "
      f"A={out['area']*1e4:.1f}cm2 vmax={out['vmax']:.1f} fsi_dt={out['fsi']:.2e}")
