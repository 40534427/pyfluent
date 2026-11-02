"""Penalty based fluid-structure coupling (Lagrange in solid).

The K file couples the canopy (``*SET_PART_LIST 2``) to the ALE air
(``*SET_PART_LIST 11``) with

``*CONSTRAINED_LAGRANGE_IN_SOLID``  PFAC = 0.1, CTYPE = 11, ILEAK = 2,
                                    A1 = 1.6e6, B1 = 4.8e5.

Because the deck contains a single ALE material, the fabric is a *porous
interface embedded in one gas*.  The traction on a fabric node is therefore
the pressure jump between the two fluid cells that straddle the surface

    f_node = A_node * [ (p_minus - p_plus) - PFAC * rho c * (v - u_avg)·n ] n

with ``n`` the node normal (``plus`` = side the normal points to).  Only the
pressure *perturbation* ``p - p0`` enters, exactly like ``*CONTROL_ALE
PREF``: the undisturbed ambient state then carries no load, so a uniform
flow cannot inject spurious momentum dipoles into the fluid.  The opposite
momentum sources are returned to both straddling cells (``+p_plus A n`` to
the plus cell, ``-p_minus A n`` to the minus cell) which keeps total
momentum and energy exactly balanced.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.spatial import cKDTree

from .fluid import ALEFluid
from .structure import StructureSolver


@dataclass
class CouplingStats:
    force: np.ndarray = None
    drag: float = 0.0
    nodes_active: int = 0


class PenaltyCoupler:
    def __init__(self, fluid: ALEFluid, struct: StructureSolver, model,
                 enabled: bool = True):
        self.fluid = fluid
        self.st = struct
        self.st_enabled = enabled
        c = model.coupling
        self.pfac = float(c.get("pfac", 0.1))
        self.start = float(c.get("start", 0.0))
        self.end = float(c.get("end", 1e10))
        self.direc = int(c.get("direc", 2))
        self.fric = float(c.get("fric", 0.0))
        # under-relaxation of the exchanged traction: the explicit (added mass
        # driven) fluid-structure iteration is only conditionally stable when
        # the fabric mass is small compared with the fluid mass of a cell.
        self.omega = float(c.get("omega", 0.2))
        # acoustic impedance coefficient of the penalty damping.  PFAC of the
        # K file only scales the penalty *stiffness*; the impedance term is
        # taken at full strength (cdamp = 1) which is the physical value for
        # a light shell immersed in the ALE grid.
        self.cdamp = float(c.get("cdamp", 1.0))
        # a node sitting on a fold has an ill defined surface normal, so the
        # two sampling cells can end up on the same side of the fabric and
        # produce a spurious pressure jump.  Such nodes are excluded.
        self.coh_min = float(c.get("coherence_min", 0.5))
        # LS-DYNA CLLS penalty stiffness parameters.  The deck stores
        # A1 = 1.6e6, B1 = 4.8e5 on the ``*CONSTRAINED_LAGRANGE_IN_SOLID``
        # card and the interface stiffness grows with the local *pressure*:
        #   k = PFAC (A1 + B1 p)        (p = dynamic pressure perturbation)
        # A high-pressure pocket therefore produces a stiffer interface, which
        # is what keeps the fabric from being pushed through the ALE grid.
        self.a1 = float(c.get("a1", 0.0))
        self.b1 = float(c.get("b1", 0.0))
        self.a2 = float(c.get("a2", 0.0))
        self.b2 = float(c.get("b2", 0.0))
        self.nquad = int(c.get("nquad", 2))
        # LS-DYNA leakage control (ILEAK/PLEAK).  With a Lagrangian surface
        # embedded in a coarse ALE grid, mass is artificially trapped on the
        # wrong side of the interface and the pressure difference runs away
        # (a sealed folded canopy inside a driven cylinder behaves like a
        # balloon).  ILEAK = 2 switches on the leakage control of the deck:
        # air passes through the coupling interface with the leak velocity
        #   u_leak = PLEAK * (p_minus - p_plus) / (rho c)
        # which relaxes the jump without touching the penalty force itself.
        self.ileak = int(c.get("ileak", 0))
        self.pleak = float(c.get("pleak", 0.1))
        # per-step mass-leak cap, as a fraction of the donor-cell mass shared
        # by the sampling nodes.  ILEAK = 2 with PLEAK = 0.1 already limits the
        # leak velocity to ~0.1 (p_minus - p_plus)/(rho c), so the cap is only
        # a numerical safeguard against driving a donor cell negative; the
        # default 1.0 (i.e. at most the donor mass itself) leaves the deck's
        # leakage model untouched.
        self.leak_cap = float(c.get("leak_cap", 1.0))
        # hard cap of the pressure *perturbation* (p - p_ref) that enters the
        # coupling traction, in Pa.  With a light, bend-free membrane hit by
        # a constant full-speed stream the air trapped between the canopy and
        # the domain wall gets compressed to several MPa (the stagnation
        # pressure is only ~30 kPa); without a cap the penalty force grows
        # without bound and the step diverges.  ``None`` disables the cap.
        self.p_cap = c.get("p_cap", None)
        if self.p_cap is not None:
            self.p_cap = float(self.p_cap)
        self.k_fsi = 0.0
        self.fsi_dt = float("inf")
        self.impedance = 0.0
        self._dt = 0.0
        # cap of the momentum source expressed as a local Mach number.  A
        # coarse ALE cell collects the reaction of many fabric nodes; without
        # the cap the cell velocity can exceed the sound speed, the Riemann
        # solver then sees supersonic states and the pressure runs away.  The
        # same factor is applied to the momentum and to the work so that the
        # source stays thermodynamically consistent.
        self.mach_cap = float(c.get("fsi_mach_cap", 0.3))

        self.tree = cKDTree(fluid.g.center)
        self.cell_size = np.cbrt(fluid.g.vol)
        self.pref = float(fluid.gas.pressure(np.array([fluid.gas.rho0]),
                                             np.array([fluid.gas.e0]))[0])
        n = struct.st.nnode
        self._cell = np.full(n, -1, dtype=np.int64)      # nearest cell
        self._cp = np.full(n, -1, dtype=np.int64)        # cell on + normal
        self._cm = np.full(n, -1, dtype=np.int64)        # cell on - normal
        self._srcp = np.zeros((n, 3))                    # force on + cell
        self._srcm = np.zeros((n, 3))                    # force on - cell
        self._f_prev = np.zeros((n, 3))
        self._srcp_prev = np.zeros((n, 3))
        self._srcm_prev = np.zeros((n, 3))
        self._active = np.zeros(n, dtype=bool)
        self.nodes_active = 0
        self._x_ref = None
        self._refresh_targets()

    # --------------------------------------------------------------- mapping
    def _refresh_targets(self) -> None:
        st = self.st.st
        if st.nodal_area.size == 0:
            return
        sel = np.nonzero(st.nodal_area > 0.0)[0]
        if sel.size == 0:
            return
        x = st.x[sel]
        nrm = st.nodal_normal[sel]
        # guard: skip nodes that have flown out of the domain or become
        # non-finite (an unstable step can push a light fabric node to inf)
        finite = np.all(np.isfinite(x), axis=1) & np.all(np.isfinite(nrm), axis=1)
        if not finite.all():
            sel = sel[finite]
            x = x[finite]
            nrm = nrm[finite]
        if sel.size == 0:
            self._active[:] = False
            self.nodes_active = 0
            return
        ncell = self.fluid.g.ncell
        dist, cel = self.tree.query(x)
        cel = np.clip(cel, 0, ncell - 1)
        h = self.cell_size[cel]
        d = 0.6 * h
        dp, cp = self.tree.query(x + d[:, None] * nrm)
        dm, cm = self.tree.query(x - d[:, None] * nrm)
        cp = np.clip(cp, 0, ncell - 1)
        cm = np.clip(cm, 0, ncell - 1)
        ok = ((dist <= 1.5 * h) & (dp <= 1.5 * h) & (dm <= 1.5 * h)
              & (cp != cm) & (st.nodal_coherence[sel] > self.coh_min))
        self._cell[:] = -1
        self._cp[:] = -1
        self._cm[:] = -1
        self._cell[sel] = cel
        self._cp[sel] = cp
        self._cm[sel] = cm
        self._active[:] = False
        self._active[sel[ok]] = True
        self.nodes_active = int(self._active.sum())
        self._x_ref = x.copy()

    def _maybe_refresh(self) -> None:
        """Re-locate the sampling cells only when the fabric has moved enough.

        The nearest-cell search is the dominant cost of the coupling, while a
        node crossing a cell boundary changes the sampled pressure only mildly;
        one refresh per quarter cell of motion is accurate enough.
        """
        st = self.st.st
        if self._x_ref is None:
            self._refresh_targets()
            return
        sel = np.nonzero(st.nodal_area > 0.0)[0]
        if sel.size == 0:
            return
        move = float(np.max(np.linalg.norm(st.x[sel] - self._x_ref, axis=1)))
        if move > 0.25 * float(np.min(self.cell_size)):
            self._refresh_targets()

    # ----------------------------------------------------------------- force
    def force(self, t: float, dt: float = 0.0) -> np.ndarray:
        st = self.st.st
        self._dt = float(dt) if dt > 0.0 else 0.0
        f = np.zeros((st.nnode, 3))
        self.k_fsi = 0.0
        self.fsi_dt = float("inf")
        self.impedance = 0.0
        self._srcp[:] = 0.0
        self._srcm[:] = 0.0
        if not self.st_enabled:
            self._f_prev[:] = 0.0
            self._srcp_prev[:] = 0.0
            self._srcm_prev[:] = 0.0
            return f
        self._maybe_refresh()
        if not (self.start <= t <= self.end):
            self._f_prev[:] = 0.0
            self._srcp_prev[:] = 0.0
            self._srcm_prev[:] = 0.0
            return f
        act = np.nonzero(self._active)[0]
        if act.size == 0:
            self._f_prev[:] = 0.0
            self._srcp_prev[:] = 0.0
            self._srcm_prev[:] = 0.0
            return f

        cp = self._cp[act]
        cm = self._cm[act]
        rho, u, p, c = self.fluid.primitive()
        pp = p[cp] - self.pref
        pm = p[cm] - self.pref
        # cap the pressure perturbation so a trapped pocket of air between
        # the canopy and the domain wall cannot drive the penalty traction to
        # the MPa range and blow the (bend-free, light) membrane apart.
        if self.p_cap is not None:
            pp = np.clip(pp, -self.p_cap, self.p_cap)
            pm = np.clip(pm, -self.p_cap, self.p_cap)
        ubar = 0.5 * (u[cp] + u[cm])
        # local acoustic impedance: rho (c + |u_rel|).  It is the quantity
        # that changes with the inflation speed and therefore changes the
        # penalty damping and the FSI stiffness of the interface.
        urel = st.v[act] - ubar
        uspeed = np.linalg.norm(urel, axis=1)
        rc = 0.5 * (rho[cp] * (c[cp] + uspeed)
                    + rho[cm] * (c[cm] + uspeed))
        A = st.nodal_area[act]
        nrm = st.nodal_normal[act]

        # LS-DYNA CLLS interface stiffness and its explicit stable dt:
        #   k = PFAC (A1 + B1 p),  p = local dynamic pressure perturbation.
        h = np.maximum(0.5 * (self.cell_size[cp] + self.cell_size[cm]), 1e-12)
        pbar = np.maximum(0.5 * (pp + pm), 0.0)
        k_node = (self.pfac * (self.a1 + self.b1 * pbar) * A / h
                  if (self.a1 + self.b1) > 0.0 else rc * A / h)
        k_node = np.maximum(k_node, 0.0)
        self.k_fsi = float(np.max(k_node)) if k_node.size else 0.0
        self.impedance = float(np.mean(rc)) if rc.size else 0.0
        m_node = float(np.min(st.mass[act])) if act.size else 1.0
        self.fsi_dt = (0.9 * float(np.sqrt(max(m_node, 1e-18)
                                            / max(self.k_fsi, 1e-30)))
                       if self.k_fsi > 0.0 else float("inf"))

        # normal relative velocity: nodal part and fluid part are separated so
        # that the *nodal* part can be treated implicitly.  A fabric node is
        # extremely light (m ~ 5e-6 kg) compared with the interface force it
        # carries, so the explicit update of the acoustic impedance term
        #   F = A [ (p_m - p_p) - rho c (v_n - u_n) ]
        # is unconditionally unstable.  Solving for v_n^{n+1} gives the
        # standard semi-implicit (added-damping) traction
        #   F = A [ dp - D (v_n^n - u_n) ] / (1 + A D dt / m)
        # which reduces to a velocity-relaxation for large A D dt / m and
        # therefore cannot inject energy.  The pressure part is scaled by the
        # same factor so that Newton's third law (fluid reaction = -f_node)
        # holds exactly for the *applied* force.
        vn_node = np.einsum("ij,ij->i", st.v[act], nrm)
        vn_fluid = np.einsum("ij,ij->i", ubar, nrm)
        d = self.cdamp * rc
        dp = pm - pp
        corr = d * (vn_node - vn_fluid)
        den = np.ones_like(A)
        if self._dt > 0.0:
            m = np.maximum(st.mass[act], 1e-18)
            den = 1.0 + A * d * self._dt / m
        fn = (dp - corr) / den                             # scalar traction
        an = A[:, None] * nrm
        dsrc = (0.5 * corr / den)[:, None] * an           # damping reaction
        srcp = (pp / den)[:, None] * an + dsrc
        srcm = (-pm / den)[:, None] * an + dsrc

        w = self.omega
        f_act = w * (fn[:, None] * an) + (1.0 - w) * self._f_prev[act]
        sp = w * srcp + (1.0 - w) * self._srcp_prev[act]
        sm = w * srcm + (1.0 - w) * self._srcm_prev[act]
        self._f_prev[:] = 0.0
        self._srcp_prev[:] = 0.0
        self._srcm_prev[:] = 0.0
        self._f_prev[act] = f_act
        self._srcp_prev[act] = sp
        self._srcm_prev[act] = sm
        f[act] = f_act
        self._srcp[act] = sp
        self._srcm[act] = sm
        return f

    # ------------------------------------------------------------------ source
    def transfer(self, f_struct: np.ndarray, dt: float) -> None:
        """Return the opposite momentum / work source to the fluid cells."""
        act = np.nonzero(self._active)[0]
        if act.size == 0 or dt <= 0.0:
            return
        cp = self._cp[act]
        cm = self._cm[act]
        sp = self._srcp[act]
        sm = self._srcm[act]
        A = self.st.st.nodal_area[act]
        rho, u, p, c = self.fluid.primitive()

        ncell = self.fluid.g.ncell
        inv_vol = 1.0 / self.fluid.g.vol
        mom = np.zeros((ncell, 3))
        for k in range(3):
            mom[:, k] = (np.bincount(cp, weights=sp[:, k], minlength=ncell)
                         + np.bincount(cm, weights=sm[:, k], minlength=ncell))
        mom *= (dt * inv_vol)[:, None]
        work = (np.bincount(cp, weights=np.einsum("ij,ij->i", sp, u[cp]),
                            minlength=ncell)
                + np.bincount(cm, weights=np.einsum("ij,ij->i", sm, u[cm]),
                              minlength=ncell)) * dt * inv_vol

        # Mach cap of the source.  On a coarse ALE grid one control volume
        # carries the reaction of many fabric nodes, so the momentum fed back
        # in one step can push the cell above the local sound speed.  The
        # Riemann solver then sees supersonic states and the pressure runs
        # away (pmax ~ 26 q).  Limiting the *added* velocity to a fraction of
        # the local speed of sound keeps the update in the regime where the
        # Godunov flux is still dissipative.  The work source is scaled by the
        # same factor so that the injected energy stays consistent with the
        # injected momentum (both vanish together for a zero-velocity jump).
        if self.mach_cap > 0.0:
            rho_c = np.maximum(rho, 1e-30)
            c_c = np.maximum(c, 1e-30)
            du = np.linalg.norm(mom, axis=1) / rho_c
            fac = np.minimum(1.0, self.mach_cap * c_c / np.maximum(du, 1e-30))
            mom *= fac[:, None]
            work *= fac
        self.fluid.U[:, 1:4] += mom
        self.fluid.U[:, 4] += work

        # ---- leakage control (ILEAK / PLEAK) --------------------------------
        # Air crosses the interface towards the low pressure side.  Mass,
        # momentum and total energy are moved together (the donor state is
        # taken from the upwind cell), so the transfer is conservative.
        if self.ileak > 0 and self.pleak > 0.0:
            rf = 0.5 * (rho[cp] + rho[cm])
            cf = 0.5 * (c[cp] + c[cm])
            uleak = self.pleak * (p[cm] - p[cp]) / np.maximum(rf * cf, 1e-30)
            dm = rf * uleak * A * dt                 # > 0: minus -> plus
            # no control volume may lose more than 10 % of its mass in one
            # step, shared between the nodes that sample it
            cntp = np.maximum(np.bincount(cp, minlength=ncell), 1)
            cntm = np.maximum(np.bincount(cm, minlength=ncell), 1)
            vol = self.fluid.g.vol
            shared = np.minimum(rho[cp] * vol[cp] / cntp[cp],
                                rho[cm] * vol[cm] / cntm[cm])
            cap = self.leak_cap * shared
            dm = np.clip(dm, -cap, cap)
            donor = np.where(dm > 0.0, cm, cp)       # upwind cell state
            ud = u[donor]
            ed = self.fluid.U[donor, 4] / np.maximum(rho[donor], 1e-30)
            mc = (np.bincount(cp, weights=dm, minlength=ncell)
                  - np.bincount(cm, weights=dm, minlength=ncell))
            for k in range(3):
                self.fluid.U[:, 1 + k] += (
                    np.bincount(cp, weights=dm * ud[:, k], minlength=ncell)
                    - np.bincount(cm, weights=dm * ud[:, k], minlength=ncell))
            me = (np.bincount(cp, weights=dm * ed, minlength=ncell)
                  - np.bincount(cm, weights=dm * ed, minlength=ncell))
            self.fluid.U[:, 0] += mc
            self.fluid.U[:, 4] += me

        self.fluid._enforce(self.fluid.U)
        self.cap_pressure()

    def cap_pressure(self) -> None:
        """Pressure relief valve.

        The coupling-force cap (``p_cap`` on ``pp``/``pm``) limits the
        traction on the fabric, but the fluid itself can still be compressed
        to tens of MPa by the inflating canopy (the stagnation pressure is
        only ~30 kPa).  Here we remove the excess internal energy from every
        cell whose pressure exceeds ``p_ref + p_cap``; the removed energy
        represents air escaping through the porous fabric.  This keeps both
        the fluid pressure and the resulting time step bounded.  Must be
        called both inside :meth:`transfer` (before the Riemann step) and
        again after the fluid step, since the Riemann solver can move
        high-pressure fluid into neighbouring cells.
        """
        if self.p_cap is None:
            return
        rho, u, p, c = self.fluid.primitive()
        p_max = self.pref + self.p_cap
        over = np.nonzero(p > p_max)[0]
        if over.size == 0:
            return
        gas = self.fluid.gas
        vol = self.fluid.g.vol[over]
        Uo = self.fluid.U[over]
        ke = 0.5 * np.sum(Uo[:, 1:4] ** 2, axis=1) \
            / np.maximum(Uo[:, 0], 1e-30) * vol
        a = gas.c4 + gas.c5 * (rho[over] / gas.rho0 - 1.0)
        e_int_max = p_max / np.maximum(a, 1e-30)
        self.fluid.U[over, 4] = np.minimum(Uo[:, 4], e_int_max * vol + ke)

    def drag(self, f_struct: np.ndarray, axis: int = 1) -> float:
        act = np.nonzero(self._active)[0]
        if act.size == 0:
            return 0.0
        return float(np.sum(f_struct[act, axis]))
