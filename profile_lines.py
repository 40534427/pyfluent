"""Line-level timing of the two dominant kernels."""
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
N = 20

def T(fn, n=N):
    t0 = time.perf_counter()
    for _ in range(n):
        fn()
    return (time.perf_counter() - t0) / n * 1000

print("== FLUID residual body ==")
U = f.U
rho, u, p, c = f.primitive()
UL = U[g.owner]
UR = np.empty_like(UL); UR[~f._is_b] = U[g.neigh[~f._is_b]]
ghost = T(lambda: f._ghost_states(UL[f._bnd], g.n[f._bnd], g.bc[f._bnd]))
pL = p[g.owner]
rhoR = UR[:, 0]; uR = UR[:, 1:4] / rhoR[:, None]
pR = f.gas.pressure(rhoR, UR[:, 4] - 0.5*np.sum(UR[:, 1:4]**2, axis=1)/rhoR)
cR = f.gas.sound_speed(rhoR, pR)
uL = u[g.owner]
FL = T(lambda: f._flux_normal(UL, uL, pL, g.n))
FR = T(lambda: f._flux_normal(UR, uR, pR, g.n))
lam = np.maximum(np.abs(np.einsum("ij,ij->i", uL, g.n)) + c[g.owner],
                 np.abs(np.einsum("ij,ij->i", uR, g.n)) + cR)
flux = 0.5*(FL+FR) - 0.5*lam[:, None]*(UR-UL)
flux *= g.area[:, None]
nc = g.ncell
mask = ~f._is_b

def bincounts():
    d = np.empty_like(U)
    for k in range(5):
        d[:, k] = (-np.bincount(g.owner, weights=flux[:, k], minlength=nc)
                   + np.bincount(g.neigh[mask], weights=flux[mask, k], minlength=nc))
        d[:, k] *= f._invV
    return d

print(f"  ghost                {ghost:6.2f} ms")
print(f"  flux L               {FL:6.2f} ms")
print(f"  flux R               {FR:6.2f} ms")
print(f"  bincount x10         {T(bincounts):6.2f} ms")
print(f"  residual total       {T(f.residual):6.2f} ms")

print("\n== STRUCT quad membrane ==")
st = sim.ssolver; s = sim.struct
st.update_kinematics()
q = s.quads; p4 = s.x[q]; v4 = s.v[q]
e1, e2, nrm = st._quad_frame(p4)
rel = p4 - p4[:, 0:1]
xc = np.stack([np.einsum("qij,qj->qi", rel, e1), np.einsum("qij,qj->qi", rel, e2)], axis=2)
d = xc - st.qX
F = np.einsum("nia,nib->nab", d, st.qB0); F[:, 0, 0] += 1; F[:, 1, 1] += 1
FtF = np.einsum("nji,njk->nik", F, F)
E = 0.5*(FtF - np.eye(2)[None])
S = np.stack([np.stack([np.zeros(len(q)), np.zeros(len(q))], axis=1)]*2, axis=1)
P = np.einsum("nij,njk->nik", F, S)
fl = np.zeros((len(q), 4, 2))
print(f"  quad_frame           {T(lambda: st._quad_frame(p4)):6.2f} ms")
print(f"  F=einsum(d,B0)       {T(lambda: np.einsum('nia,nib->nab', d, st.qB0)):6.2f} ms")
print(f"  P=einsum(F,S)        {T(lambda: np.einsum('nij,njk->nik', F, S)):6.2f} ms")
print(f"  fl 4-operand einsum  {T(lambda: np.einsum('n,n,nab,nib->nia', st.q_thk, st.q_area0, P, st.qB0)):6.2f} ms")
fqt = np.random.rand(len(q)*4, 3)
fake = np.zeros((s.nnode, 3)); idx = q.ravel()
print(f"  np.add.at x3         {T(lambda: [np.add.at(fake[:, k], idx, fqt[:, k]) for k in range(3)]):6.2f} ms")
print(f"  bincount x3 equiv    {T(lambda: [np.bincount(idx, weights=fqt[:, k], minlength=s.nnode) for k in range(3)]):6.2f} ms")
print(f"  quad membrane total  {T(lambda: st._quad_membrane_forces(np.zeros_like(s.x))):6.2f} ms")
print(f"  bending total        {T(lambda: st._bending_forces(np.zeros_like(s.x))):6.2f} ms")
print(f"  update_kinematics    {T(st.update_kinematics):6.2f} ms")
print(f"  internal_forces      {T(st.internal_forces):6.2f} ms")
