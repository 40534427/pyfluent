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
        dist, cel = self.tree.query(x)
        h = self.cell_size[cel]
        d = 0.6 * h
        dp, cp = self.tree.query(x + d[:, None] * nrm)
        dm, cm = self.tree.query(x - d[:, None] * nrm)
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
    def force(self, t: float) -> np.ndarray:
        st = self.st.st
        f = np.zeros((st.nnode, 3))
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
        ubar = 0.5 * (u[cp] + u[cm])
        rc = 0.5 * (rho[cp] * c[cp] + rho[cm] * c[cm])
        A = st.nodal_area[act]
        nrm = st.nodal_normal[act]

        vn = np.einsum("ij,ij->i", st.v[act] - ubar, nrm)
        dfac = self.cdamp * rc * vn
        fn = (pm - pp) - dfac                             # scalar traction
        an = A[:, None] * nrm
        fdamp = -dfac[:, None] * an                       # damping part
        srcp = pp[:, None] * an - 0.5 * fdamp
        srcm = -pm[:, None] * an - 0.5 * fdamp

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
        rho, u, p, c = self.fluid.primitive()

        ncell = self.fluid.g.ncell
        inv_vol = 1.0 / self.fluid.g.vol
        mom = np.zeros((ncell, 3))
        work = np.zeros(ncell)
        for k in range(3):
            mom[:, k] = (np.bincount(cp, weights=sp[:, k], minlength=ncell)
                         + np.bincount(cm, weights=sm[:, k], minlength=ncell))
            mom[:, k] *= dt * inv_vol
        work = (np.bincount(cp, weights=np.einsum("ij,ij->i", sp, u[cp]),
                            minlength=ncell)
                + np.bincount(cm, weights=np.einsum("ij,ij->i", sm, u[cm]),
                              minlength=ncell)) * dt * inv_vol
        self.fluid.U[:, 1:4] += mom
        self.fluid.U[:, 4] += work
        self.fluid._enforce(self.fluid.U)

    def drag(self, f_struct: np.ndarray, axis: int = 1) -> float:
        act = np.nonzero(self._active)[0]
        if act.size == 0:
            return 0.0
        return float(np.sum(f_struct[act, axis]))
