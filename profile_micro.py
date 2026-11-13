"""Micro-profile: fluid residual phases + structure force phases."""
import sys, time
sys.path.insert(0, "/workspace/T5J_150ms_delivery/src")
import numpy as np
from aleparachute import load_model, auto_cylinder_grid, fluid_geometry, Simulation, Options

model = load_model("/workspace/run_300ms/prof.k")
y0, y1, r, cx, cz = fluid_geometry(model)
grid = auto_cylinder_grid(y0, y1 + 0.4, 0.5, 30, 40, 30, cx, cz)
opt = Options(endtime=0.15, cfl=0.5, tssfac=0.8, constant_vel=220, bend_scale=1.0,
              bend_damp=0.0, pleak=0.1, struct_damping=100.0, struct_damping_vmax=30.0,
              eb_frac=0.05, vent_radius=0.006, vent_ring_E_factor=0.0,
              vent_ring_A_factor=2.0, membrane_tension_only=True, contact=False,
              vtk_every=0.0, checkpoint_every=0.0, max_steps=3, verbose=False,
              outdir="/tmp/prof_out")
sim = Simulation(model, grid, opt)
f = sim.fluid; g = grid

# warm up
for _ in range(2):
    f.step(3.8e-6)

def bench(fn, n=30, label=""):
    t0 = time.perf_counter()
    for _ in range(n):
        fn()
    dt = (time.perf_counter() - t0) / n * 1000
    print(f"  {label:<34}{dt:8.2f} ms")
    return dt

print("FLUID residual() phases:")
bench(f.residual, 20, "residual total")
bench(lambda: f.primitive(), 20, "  primitive()")
U = f.U; bnd = f._bnd
UL = U[g.owner]
bench(lambda: f._ghost_states(UL[bnd], g.n[bnd], g.bc[bnd]), 20, "  ghost states")
bench(lambda: U[g.owner], 20, "  gather U[owner]")
bench(lambda: U[g.neigh[f._nb0 if hasattr(f,'_nb0') else g.neigh>=0]], 20, "  gather U[neigh interior]")

print("\nFLUID step total:")
bench(lambda: f.step(3.8e-6), 20, "fluid.step (2x residual)")
bench(lambda: f.stable_dt(), 50, "fluid.stable_dt")

st = sim.ssolver
st.update_kinematics()
print("\nSTRUCTURE phases:")
bench(lambda: st.update_kinematics(), 20, "update_kinematics")
bench(lambda: st.internal_forces(), 20, "internal_forces total")
ff = np.zeros_like(sim.struct.x)
bench(lambda: st._quad_membrane_forces(ff), 20, "  quad membrane")
bench(lambda: st._bending_forces(ff), 20, "  bending hinges")
bench(lambda: st.step(3.8e-6, 0.0, None, 1.0), 20, "ssolver.step total")

print("\nCOUPLING:")
bench(lambda: sim.coupler.force(sim.t, 3.8e-6), 20, "coupler.force")
fc = np.zeros_like(sim.struct.x)
bench(lambda: sim.coupler.transfer(fc, 3.8e-6), 20, "coupler.transfer")
print("ncell", grid.ncell, "faces", grid.owner.size, "nodes", sim.struct.nnode,
      "tris", sim.struct.tris.shape[0], "quads", sim.struct.quads.shape[0])
