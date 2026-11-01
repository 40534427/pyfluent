"""Lagrangian fabric canopy and suspension lines.

* Canopy  : 4-node quads of the K file are split into two constant-strain
  membrane triangles.  Stresses come from a plane-stress orthotropic
  constitutive law built from ``*MAT_FABRIC`` (EA / EB / PRBA / GAB).
  A total-Lagrangian (Green strain) formulation is used so that large
  inflation deformations are handled correctly.
* Lines   : 2-node cables from ``*ELEMENT_BEAM`` (Hughes-Liu section, here
  represented as tension-capable trusses with ``*MAT_PLASTIC_KINEMATIC``
  elastic data).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np

from .mesh import Structure


class StructureSolver:
    def __init__(self, st: Structure, damping: float = 0.0,
                 tension_only: bool = True, hg_qh: float = 0.1,
                 hg_damp: float = 0.5, alt_floor: float = 0.1):
        self.st = st
        self.damping = damping
        self.tension_only = tension_only
        self.hg_qh = float(hg_qh)
        self.hg_damp = float(hg_damp)
        self.alt_floor = float(alt_floor)
        self._build_reference()

    # ------------------------------------------------------------------ setup
    def _build_reference(self) -> None:
        st = self.st
        x0 = st.x
        t0 = st.tris[:, 0]
        e1 = x0[st.tris[:, 1]] - x0[t0]
        e2 = x0[st.tris[:, 2]] - x0[t0]
        nrm = np.cross(e1, e2)
        nrm /= np.maximum(np.linalg.norm(nrm, axis=1, keepdims=True), 1e-30)
        ex = e1 / np.maximum(np.linalg.norm(e1, axis=1, keepdims=True), 1e-30)
        ey = np.cross(nrm, ex)

        # local 2x2 reference matrix: columns = edge vectors in (ex, ey)
        X = np.empty((st.tris.shape[0], 2, 2))
        X[:, :, 0] = np.stack([np.einsum("ij,ij->i", e1, ex),
                              np.einsum("ij,ij->i", e1, ey)], axis=1)
        X[:, :, 1] = np.stack([np.einsum("ij,ij->i", e2, ex),
                              np.einsum("ij,ij->i", e2, ey)], axis=1)
        det = X[:, 0, 0] * X[:, 1, 1] - X[:, 0, 1] * X[:, 1, 0]
        det = np.where(np.abs(det) < 1e-20, 1e-20, det)
        Xinv = np.empty_like(X)
        Xinv[:, 0, 0] = X[:, 1, 1] / det
        Xinv[:, 0, 1] = -X[:, 0, 1] / det
        Xinv[:, 1, 0] = -X[:, 1, 0] / det
        Xinv[:, 1, 1] = X[:, 0, 0] / det
        self.Xinv = Xinv
        self.tex = ex
        self.tey = ey

        st.tri_area0[st.tri_area0 <= 0] = 1e-14
        self.vol0 = st.tri_area0 * st.tri_thk
        # smallest altitude of every triangle: the explicit stability limit of
        # a CST membrane is governed by the altitude, not by the edge length
        a = st.tri_area0
        e0, e1, e2 = st.tri_edge0[:, 0], st.tri_edge0[:, 1], st.tri_edge0[:, 2]
        self.alt0 = np.min(np.stack([2.0 * a / np.maximum(e2, 1e-30),
                                     2.0 * a / np.maximum(e0, 1e-30),
                                     2.0 * a / np.maximum(e1, 1e-30)], axis=1),
                           axis=1)
        self.alt_cur = self.alt0.copy()

        # constitutive matrix (plane stress, orthotropic)
        ea = st.tri_ea
        eb = st.tri_eb
        nu12 = st.tri_nu
        nu21 = nu12 * eb / np.maximum(ea, 1e-12)
        den = np.maximum(1.0 - nu12 * nu21, 1e-9)
        self.C11 = ea / den
        self.C22 = eb / den
        self.C12 = nu21 * ea / den
        self.C66 = st.tri_g

        # cable stiffness and optional axial damping
        st.beam_L0 = np.maximum(st.beam_L0, 1e-12)
        self.beam_k = st.beam_E * st.beam_area / st.beam_L0
        self.beam_damp = 2.0 * self.damping * np.sqrt(self.beam_k * st.beam_mass)

        # ---- hourglass control of the quad "flap" mode -----------------------
        # each *ELEMENT_SHELL quad of the deck is split into two triangles, so
        # the quad out-of-plane flap mode (x0-x1+x2-x3) carries no membrane
        # strain and is a zero energy mode.  The deck asks for hourglass
        # control (*CONTROL_HOURGLASS qh = 0.1), reproduced here with a
        # bending-like penalty of stiffness qh*D/A_quad, D = E t^3/12(1-nu^2),
        # plus a viscous term that damps the flapping.
        nq = st.quads.shape[0]
        self.nq = nq
        self.quad_area0 = None
        self.hg_k = None
        if nq:
            nt = st.tris.shape[0]
            aq = st.tri_area0[:nt // 2] + st.tri_area0[nt // 2:]
            aq = np.maximum(aq, 1e-14)
            t = np.mean(st.tri_thk)
            e = np.mean(st.tri_ea[:nt // 2]) if nt > 1 else np.mean(st.tri_ea)
            nu = float(np.mean(st.tri_nu))
            D = e * t ** 3 / (12.0 * max(1.0 - nu * nu, 1e-6))
            self.quad_area0 = aq
            self.hg_k = np.maximum(self.hg_qh * D / aq, 0.0)
            qm = np.mean(st.mass[st.quads], axis=1)
            self.hg_c = 2.0 * self.hg_damp * np.sqrt(self.hg_k * qm)

    # ------------------------------------------------------------- kinematics
    def update_kinematics(self) -> None:
        st = self.st
        p0 = st.x[st.tris[:, 0]]
        p1 = st.x[st.tris[:, 1]]
        p2 = st.x[st.tris[:, 2]]
        nrm = np.cross(p1 - p0, p2 - p0)
        a = 0.5 * np.linalg.norm(nrm, axis=1)
        nrm /= np.maximum(np.linalg.norm(nrm, axis=1, keepdims=True), 1e-30)
        st.tri_area = a
        st.tri_normal = nrm
        L1 = np.linalg.norm(p1 - p0, axis=1)
        L2 = np.linalg.norm(p2 - p1, axis=1)
        L3 = np.linalg.norm(p0 - p2, axis=1)
        self.alt_cur = np.min(np.stack([2.0 * a / np.maximum(L2, 1e-30),
                                        2.0 * a / np.maximum(L3, 1e-30),
                                        2.0 * a / np.maximum(L1, 1e-30)], axis=1),
                              axis=1)

        na = np.zeros(st.nnode)
        nn = np.zeros((st.nnode, 3))
        contrib_a = np.repeat(a / 3.0, 3)
        np.add.at(na, st.tris.ravel(), contrib_a)
        for k in range(3):
            contrib_n = np.repeat(nrm[:, k] * a / 3.0, 3)
            np.add.at(nn[:, k], st.tris.ravel(), contrib_n)
        st.nodal_area = na
        ln = np.linalg.norm(nn, axis=1)
        st.nodal_normal = nn / np.maximum(ln[:, None], 1e-30)
        # coherence = |sum A n| / sum A ; 1 for a smooth patch, -> 0 on a
        # fold where the surrounding triangles have opposite normals
        st.nodal_coherence = ln / np.maximum(na, 1e-30)

    # ----------------------------------------------------------------- forces
    def internal_forces(self) -> np.ndarray:
        st = self.st
        f = np.zeros((st.nnode, 3))

        t0 = st.tris[:, 0]
        d2 = st.x[st.tris[:, 1]] - st.x[t0]
        d3 = st.x[st.tris[:, 2]] - st.x[t0]
        xm = np.stack([d2, d3], axis=2)                      # (Nt,3,2)

        # local 2D edge vectors
        Xc = np.empty((st.tris.shape[0], 2, 2))
        Xc[:, :, 0] = np.stack([np.einsum("ij,ij->i", d2, self.tex),
                               np.einsum("ij,ij->i", d2, self.tey)], axis=1)
        Xc[:, :, 1] = np.stack([np.einsum("ij,ij->i", d3, self.tex),
                               np.einsum("ij,ij->i", d3, self.tey)], axis=1)
        F = np.einsum("nij,njk->nik", Xc, self.Xinv)          # (Nt,2,2)

        FtF = np.einsum("nji,njk->nik", F, F)
        E = 0.5 * (FtF - np.eye(2)[None])
        S11 = self.C11 * E[:, 0, 0] + self.C12 * E[:, 1, 1]
        S22 = self.C12 * E[:, 0, 0] + self.C22 * E[:, 1, 1]
        S12 = 2.0 * self.C66 * E[:, 0, 1]
        S = np.stack([np.stack([S11, S12], axis=1),
                      np.stack([S12, S22], axis=1)], axis=1)

        P = np.einsum("nij,njk->nik", F, S)                   # first PK stress

        # in-plane nodal tractions, then mapped back to the global frame
        t2 = np.einsum("nij,nj->ni", P, self.Xinv[:, 0, :])   # dN2/dX
        t3 = np.einsum("nij,nj->ni", P, self.Xinv[:, 1, :])   # dN3/dX
        scale = -self.vol0
        f2 = scale[:, None] * (t2[:, 0, None] * self.tex + t2[:, 1, None] * self.tey)
        f3 = scale[:, None] * (t3[:, 0, None] * self.tex + t3[:, 1, None] * self.tey)
        f1 = -(f2 + f3)

        for k in range(3):
            np.add.at(f[:, k], st.tris[:, 0], f1[:, k])
            np.add.at(f[:, k], st.tris[:, 1], f2[:, k])
            np.add.at(f[:, k], st.tris[:, 2], f3[:, k])

        # ---- cable (truss) forces ----------------------------------------
        if st.beams.size:
            i = st.beams[:, 0]
            j = st.beams[:, 1]
            d = st.x[j] - st.x[i]
            L = np.maximum(np.linalg.norm(d, axis=1), 1e-12)
            nv = d / L[:, None]
            ext = L - st.beam_L0
            if self.tension_only:
                ext = np.maximum(ext, 0.0)
            fmag = self.beam_k * ext
            dv = np.einsum("ij,ij->i", st.v[j] - st.v[i], nv)
            fmag += self.beam_damp * dv
            fvec = fmag[:, None] * nv
            for k in range(3):
                np.add.at(f[:, k], i, fvec[:, k])
                np.add.at(f[:, k], j, -fvec[:, k])

        # ---- quad flap (hourglass) control ---------------------------------
        if self.hg_k is not None and self.hg_k.size:
            q = st.quads
            xq = st.x[q]                                   # (Nq,4,3)
            vq = st.v[q]
            nq = (np.cross(xq[:, 1] - xq[:, 0], xq[:, 2] - xq[:, 0])
                  + np.cross(xq[:, 2] - xq[:, 0], xq[:, 3] - xq[:, 0]))
            nq /= np.maximum(np.linalg.norm(nq, axis=1, keepdims=True), 1e-30)
            s = np.einsum("ij,ij->i",
                          xq[:, 0] - xq[:, 1] + xq[:, 2] - xq[:, 3], nq)
            sd = np.einsum("ij,ij->i",
                           vq[:, 0] - vq[:, 1] + vq[:, 2] - vq[:, 3], nq)
            fmag = -(self.hg_k * s + self.hg_c * sd)
            g = np.array([1.0, -1.0, 1.0, -1.0])
            fq = (fmag[:, None] * g[None, :])[:, :, None] * nq[:, None, :]
            fqt = fq.reshape(-1, 3)
            for k in range(3):
                np.add.at(f[:, k], q.ravel(), fqt[:, k])
        return f

    # -------------------------------------------------------------- boundary
    def apply_constraints(self, f: np.ndarray) -> None:
        st = self.st
        if st.fixed.size:
            f[st.fixed] = 0.0
            st.v[st.fixed] = 0.0

    def set_driven_velocity(self, t: float, curves: dict, scale: float = 1.0) -> None:
        st = self.st
        if st.driven.size == 0:
            return
        for dof, lcid, ids in _group_driven(st):
            a, o = curves[lcid]
            val = float(np.interp(t, a, o)) * scale
            st.v[ids, dof - 1] = val

    # ----------------------------------------------------------------- step
    def step(self, dt: float, t: float = 0.0, curves: Optional[dict] = None,
             scale: float = 1.0, f_ext: Optional[np.ndarray] = None) -> None:
        st = self.st
        if curves is not None:
            self.set_driven_velocity(t, curves, scale)
        self.update_kinematics()
        f = self.internal_forces()
        if f_ext is not None:
            f = f + f_ext
        self.apply_constraints(f)
        st.f = f
        acc = f / st.mass[:, None]
        st.v += dt * acc
        self.apply_constraints(st.f)
        st.x += dt * st.v
        if st.driven.size and curves is not None:
            self.set_driven_velocity(t + dt, curves, scale)

    def add_force(self, f: np.ndarray) -> None:
        self.st.f += f

    # ------------------------------------------------------------ properties
    def stable_dt(self) -> float:
        st = self.st
        # *MAT_FABRIC EA/EB are elastic moduli [Pa]; the membrane stiffness
        # per unit width is EA*t, so the wave speed is sqrt(EA/rho)
        c = float(np.sqrt(np.max(st.tri_ea / st.tri_rho)))
        h0 = float(self.alt0.min()) if self.alt0.size else 1e-3
        hc = float(self.alt_cur.min()) if self.alt_cur.size else h0
        # a crumpled triangle can shrink without bound; keep a floor so that a
        # single collapsed element cannot stall the whole explicit integration
        hc = max(hc, self.alt_floor * h0)
        h = min(h0, hc)
        dt_s = h / max(c, 1e-9)
        if self.hg_k is not None and self.hg_k.size:
            kmax = float(np.max(self.hg_k))
            mmin = float(np.min(self.st.mass[self.st.quads]))
            if kmax > 0.0:
                dt_s = min(dt_s, 0.9 * np.sqrt(mmin / kmax))
        if st.beams.size:
            k = float(np.max(self.beam_k))
            m = float(np.min(st.beam_mass))
            dt_b = 0.9 * np.sqrt(m / max(k, 1e-12))
            dt_s = min(dt_s, dt_b)
        return dt_s


def _group_driven(st):
    """Yield (dof, lcid, node ids) with identical prescribed motion."""
    key = {}
    for k in range(st.driven.size):
        key.setdefault((int(st.driven_dof[k]), int(st.driven_curve[k]),
                        float(st.driven_sf[k])), []).append(int(st.driven[k]))
    for (dof, lcid, sf), ids in key.items():
        yield dof, lcid, np.asarray(ids, dtype=np.int64)
