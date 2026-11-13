"""Per-phase wall-clock profile of one solver step (no output I/O)."""
import sys, os, time
sys.path.insert(0, "/workspace/T5J_150ms_delivery/src")
import numpy as np
from aleparachute import load_model, auto_cylinder_grid, fluid_geometry, Simulation, Options

K = "/workspace/run_300ms/prof.k"
model = load_model(K)
y0, y1, r, cx, cz = fluid_geometry(model)
grid = auto_cylinder_grid(y0, y1 + 0.4, 0.5, 30, 40, 30, cx, cz)
opt = Options(endtime=0.15, cfl=0.5, tssfac=0.8, constant_vel=220,
              bend_scale=1.0, bend_damp=0.0, pleak=0.1,
              struct_damping=100.0, struct_damping_vmax=30.0,
              eb_frac=0.05, vent_radius=0.006, vent_ring_E_factor=0.0,
              vent_ring_A_factor=2.0, membrane_tension_only=True,
              contact=False, vtk_every=0.0, checkpoint_every=0.0,
              max_steps=80, verbose=False, outdir="/tmp/prof_out")
sim = Simulation(model, grid, opt)

stats = {}
def wrap(obj, name, label):
    fn = getattr(obj, name)
    def w(*a, **k):
        t0 = time.perf_counter()
        try:
            return fn(*a, **k)
        finally:
            stats[label] = stats.get(label, 0.0) + time.perf_counter() - t0
    setattr(obj, name, w)

wrap(sim.coupler, "force", "1 coupler.force")
wrap(sim.coupler, "transfer", "2 coupler.transfer")
wrap(sim.coupler, "cap_pressure", "3 coupler.cap_pressure")
wrap(sim.ssolver, "step", "4 structure step")
wrap(sim.fluid, "step", "5 fluid step")
wrap(sim.fluid, "set_drive", "6 fluid drive")
wrap(sim, "stable_dt", "7 stable_dt")
wrap(sim, "diagnostics", "8 diagnostics")
wrap(sim, "write_state", "9 write_state")

t0 = time.perf_counter()
res = sim.run()
wall = time.perf_counter() - t0
n = max(res["steps"], 1)
print(f"\nsteps={res['steps']}  wall={wall:.2f}s  per-step={wall/n*1000:.1f} ms")
print(f"{'phase':<24}{'total s':>10}{'ms/step':>10}{'share':>8}")
for k in sorted(stats):
    print(f"{k:<24}{stats[k]:>10.2f}{stats[k]/n*1000:>10.2f}{stats[k]/wall*100:>7.1f}%")
other = wall - sum(stats.values())
print(f"{'(loop overhead)':<24}{other:>10.2f}{other/n*1000:>10.2f}{other/wall*100:>7.1f}%")
