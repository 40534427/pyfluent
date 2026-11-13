"""FSI stable-dt analysis with the real (impedance) stiffness branch."""
import sys
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
c = sim.coupler

def report(tag):
    c.force(sim.t, 1e-6)
    st = sim.struct
    act = np.nonzero(c._active)[0]
    A = st.nodal_area[act]; cp, cm = c._cp[act], c._cm[act]
    h = 0.5 * (c.cell_size[cp] + c.cell_size[cm])
    rho, u, p, cc = sim.fluid.primitive()
    ubar = 0.5 * (u[cp] + u[cm])
    uspeed = np.linalg.norm(st.v[act] - ubar, axis=1)
    rc = 0.5 * (rho[cp] * (cc[cp] + uspeed) + rho[cm] * (cc[cm] + uspeed))
    k = rc * A / h
    m = st.mass[act]
    dtn = 0.9 * np.sqrt(m / k)
    q = np.percentile(dtn, [0, 1, 5, 50, 95])
    print(f"{tag}: code fsi_dt={c.fsi_dt:.3e} (m_min={m.min():.2e}, k_max={k.max():.3e})")
    print(f"   per-node dt p0={q[0]:.3e} p1={q[1]:.3e} p5={q[2]:.3e} p50={q[3]:.3e} p95={q[4]:.3e}")
    print(f"   gain from per-node dt: {q[0]/c.fsi_dt:.2f}x ; from p1 floor: {q[1]/c.fsi_dt:.2f}x")
    print(f"   struct dt={sim.ssolver.stable_dt():.3e} fluid dt={sim.fluid.stable_dt():.3e}")

report("t=0")
for i in range(400):
    dt = sim.stable_dt() * 0.8
    f = c.force(sim.t, dt)
    sim.ssolver.step(dt, sim.t, None, 1.0, f_ext=f)
    c.transfer(f, dt)
    sim.fluid.set_drive(sim.driven_cells, sim.pm["dof"], 220.0)
    sim.fluid.step(dt)
    sim.t += dt; sim.step_count += 1
report("t≈1.5ms")
