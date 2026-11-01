"""Lagrangian fabric canopy and suspension lines.

Shell theory
------------
The K file selects

    *SECTION_SHELL  secid 11  ELFORM = 5   (Belytschko-Tsay membrane)
    *CONTROL_SHELL  THEORY = 5             (same formulation for all quads)
                    BWC    = 2             (plain Belytschko-Tsay, i.e. *no*
                                           Belytschko-Wong-Chiang warping
                                           stiffness is added)

THEORY = 5 is reproduced here as a four-node, one-point integrated,
co-rotational Belytschko-Tsay **membrane**:

* the element frame follows the current geometry, so rigid rotations
  (including large out-of-plane rotations of a folding canopy) produce no
  strain;
* the in-plane strain is evaluated at the element centre with the standard
  bilinear B-operator;
* the two in-plane hourglass modes (the ``xi*eta`` mode) are controlled by
  ``*CONTROL_HOURGLASS IHQ = 1 / QH = 0.1`` with a viscous + stiffness term;
* the transverse "w" mode is *not* given a bending stiffness: BWC = 2 means
  the Belytschko-Wong-Chiang warping stiffness is switched off.  Only the
  hourglass stabilisation of that zero-energy mode is retained, exactly as
  the shell element needs to remain non-singular.

BWC = 1 would switch on the B-W-C warping stiffness (``bwc`` is therefore a
real switch in this implementation); the deck's BWC = 2 leaves it off.

Suspension lines are 2-node tension-only trusses built from
``*ELEMENT_BEAM`` (Hughes-Liu section, ``*MAT_PLASTIC_KINEMATIC`` elastic
data).  They are grouped into the 16 physical lines so that the tension of
the bottom (anchor) segment of every line can be reported, which is the
quantity plotted in the reference presentation.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np

from .mesh import Structure


class StructureSolver:
    def __init__(self, st: Structure, damping: float = 0.0,
                 tension_only: bool = True, hg_qh: float = 0.1,
                 hg_damp: float = 0.5, alt_floor: float = 0.1,
                 theory: int = 5, bwc: int = 2, ihq: int = 1):
        self.st = st
        self.damping = damping
        self.tension_only = tension_only
        self.hg_qh = float(hg_qh)
        self.hg_damp = float(hg_damp)
        self.alt_floor = float(alt_floor)
        self.theory = int(theory)
        self.bwc = int(bwc)
        self.ihq = int(ihq)
        self._build_reference()
        self._build_lines()

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

        self.use_quads = st.quads.shape[0] > 0
        if self.use_quads:
            self._build_quad_reference()
        else:
            self.nq = 0
            self.hg_k = None

    # -------------------------------------------------------------- quad shell
    def _build_quad_reference(self) -> None:
        """Reference frame, B-operator and hourglass data of the BT membrane."""
        st = self.st
        q = st.quads
        nq = q.shape[0]
        self.nq = nq
        nt = st.tris.shape[0]
        p0 = st.x[q]

        e1, e2, n0 = self._quad_frame(p0)
        rel = p0 - p0[:, 0:1]
        xi = np.einsum("qij,qj->qi", rel, e1)
        et = np.einsum("qij,qj->qi", rel, e2)
        self.qX = np.stack([xi, et], axis=2)                 # reference local
        self.q_e1_ref = e1
        self.q_e2_ref = e2
        self.q_n0 = n0

        # Jacobian of the bilinear map at the centre (xi = eta = 0)
        dxi = np.array([-1.0, 1.0, 1.0, -1.0]) * 0.25
        det_ = np.array([-1.0, -1.0, 1.0, 1.0]) * 0.25
        J = np.empty((nq, 2, 2))
        J[:, 0, 0] = np.einsum("qi,i->q", xi, dxi)          # d(x)/d(xi)
        J[:, 0, 1] = np.einsum("qi,i->q", et, dxi)          # d(y)/d(xi)
        J[:, 1, 0] = np.einsum("qi,i->q", xi, det_)         # d(x)/d(eta)
        J[:, 1, 1] = np.einsum("qi,i->q", et, det_)         # d(y)/d(eta)
        detJ = J[:, 0, 0] * J[:, 1, 1] - J[:, 0, 1] * J[:, 1, 0]
        detJ = np.where(np.abs(detJ) < 1e-20, 1e-20, detJ)
        Ji = np.empty_like(J)
        Ji[:, 0, 0] = J[:, 1, 1] / detJ
        Ji[:, 0, 1] = -J[:, 0, 1] / detJ
        Ji[:, 1, 0] = -J[:, 1, 0] / detJ
        Ji[:, 1, 1] = J[:, 0, 0] / detJ
        B = np.empty((nq, 4, 2))
        B[:, :, 0] = Ji[:, 0, 0, None] * dxi[None, :] + Ji[:, 0, 1, None] * det_[None, :]
        B[:, :, 1] = Ji[:, 1, 0, None] * dxi[None, :] + Ji[:, 1, 1, None] * det_[None, :]
        self.qB0 = B                                         # (Nq,4,2)
        self.q_detJ0 = detJ

        diag1 = p0[:, 2] - p0[:, 0]
        diag2 = p0[:, 3] - p0[:, 1]
        a0 = 0.5 * np.linalg.norm(np.cross(diag1, diag2), axis=1)
        a0 = np.maximum(a0, 1e-14)
        self.q_area0 = a0

        # per-quad material data (quad i corresponds to triangle i)
        self.q_thk = st.tri_thk[:nq]
        self.q_C11 = self.C11[:nq]
        self.q_C22 = self.C22[:nq]
        self.q_C12 = self.C12[:nq]
        self.q_C66 = self.C66[:nq]
        self.q_ea = st.tri_ea[:nq]
        self.q_rho = st.tri_rho[:nq]
        self.q_mass = 0.25 * np.sum(st.mass[q], axis=1)

        # ---- IHQ = 1 hourglass control -------------------------------------
        # in-plane: one xi*eta pattern (h = 1/2 [1,-1,1,-1]) for each of the
        # two in-plane components; generalised stiffness qh * E * t.
        self.q_khg = np.maximum(self.hg_qh * self.q_C11 * self.q_thk, 1e-12)
        self.q_chg = 2.0 * self.hg_damp * np.sqrt(self.q_khg * self.q_mass)
        self.h_pattern = np.array([0.5, -0.5, 0.5, -0.5])

        # transverse w-mode: LS-DYNA keeps the hourglass stabilisation of the
        # zero-energy thickness mode.  BWC = 2 selects plain B-T and therefore
        # adds *no* Belytschko-Wong-Chiang warping stiffness; BWC = 1 would.
        t = float(np.mean(self.q_thk))
        e = float(np.mean(self.q_C11))
        nu = float(np.mean(st.tri_nu))
        D = e * t ** 3 / (12.0 * max(1.0 - nu * nu, 1e-6))
        k_w = self.hg_qh * D / a0
        if self.bwc <= 1:
            k_w = k_w + D / a0          # B-W-C warping stiffness switched on
        self.q_kw = np.maximum(k_w, 0.0)
        self.q_cw = 2.0 * self.hg_damp * np.sqrt(self.q_kw * self.q_mass)
        self.q_warp_angle = 0.0          # diagnostic, degrees

        # CST-like altitude of a quad (smallest distance between opposite
        # edges) used for the explicit time step
        edge = np.stack([np.linalg.norm(p0[:, k] - p0[:, (k + 1) % 4], axis=1)
                         for k in range(4)], axis=1)
        self.q_alt0 = 2.0 * a0 / np.maximum(edge.max(axis=1), 1e-30)

    @staticmethod
    def _quad_frame(p: np.ndarray):
        """Co-rotational frame: x along side 0-1, z along the two diagonals."""
        e1 = p[:, 1] - p[:, 0]
        e1 = e1 / np.maximum(np.linalg.norm(e1, axis=1, keepdims=True), 1e-30)
        n = np.cross(p[:, 2] - p[:, 0], p[:, 3] - p[:, 1])
        n = n / np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-30)
        e2 = np.cross(n, e1)
        e2 = e2 / np.maximum(np.linalg.norm(e2, axis=1, keepdims=True), 1e-30)
        return e1, e2, n

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
        if self.use_quads:
            self._quad_membrane_forces(f)
        else:
            self._cst_membrane_forces(f)

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
        return f

    # ---- Belytschko-Tsay membrane (THEORY = 5) -----------------------------
    def _quad_membrane_forces(self, f: np.ndarray) -> None:
        st = self.st
        q = st.quads
        p = st.x[q]                                         # (Nq,4,3)
        v = st.v[q]
        e1, e2, nrm = self._quad_frame(p)
        rel = p - p[:, 0:1]
        xc = np.stack([np.einsum("qij,qj->qi", rel, e1),
                       np.einsum("qij,qj->qi", rel, e2)], axis=2)
        vc = np.stack([np.einsum("qij,qj->qi", v, e1),
                       np.einsum("qij,qj->qi", v, e2)], axis=2)
        d = xc - self.qX                                   # co-rotational

        # F = I + d u / d X with the reference B-operator
        F = np.einsum("nia,nib->nab", d, self.qB0)
        F[:, 0, 0] += 1.0
        F[:, 1, 1] += 1.0
        FtF = np.einsum("nji,njk->nik", F, F)
        E = 0.5 * (FtF - np.eye(2)[None])
        S11 = self.q_C11 * E[:, 0, 0] + self.q_C12 * E[:, 1, 1]
        S22 = self.q_C12 * E[:, 0, 0] + self.q_C22 * E[:, 1, 1]
        S12 = 2.0 * self.q_C66 * E[:, 0, 1]
        S = np.stack([np.stack([S11, S12], axis=1),
                      np.stack([S12, S22], axis=1)], axis=1)
        P = np.einsum("nij,njk->nik", F, S)

        # nodal forces in the local frame, -t0 A0 P B
        fl = -np.einsum("n,n,nab,nib->nia", self.q_thk, self.q_area0,
                        P, self.qB0)

        # ---- in-plane hourglass (IHQ = 1) --------------------------------
        h = self.h_pattern
        qh_d = np.einsum("i,qia->qa", h, d)
        qh_v = np.einsum("i,qia->qa", h, vc)
        fh = -(self.q_khg[:, None] * qh_d + self.q_chg[:, None] * qh_v)
        fl += h[None, :, None] * fh[:, None, :]

        # map local (e1,e2) forces back to global
        fq = fl[:, :, 0, None] * e1[:, None, :] + fl[:, :, 1, None] * e2[:, None, :]
        fqt = fq.reshape(-1, 3)
        for k in range(3):
            np.add.at(f[:, k], q.ravel(), fqt[:, k])

        # ---- transverse w-mode hourglass ---------------------------------
        s = np.einsum("ij,ij->i", p[:, 0] - p[:, 1] + p[:, 2] - p[:, 3], nrm)
        sd = np.einsum("ij,ij->i", v[:, 0] - v[:, 1] + v[:, 2] - v[:, 3], nrm)
        fmag = -(self.q_kw * s + self.q_cw * sd)
        g = np.array([1.0, -1.0, 1.0, -1.0])
        fw = (fmag[:, None] * g[None, :])[:, :, None] * nrm[:, None, :]
        fwt = fw.reshape(-1, 3)
        for k in range(3):
            np.add.at(f[:, k], q.ravel(), fwt[:, k])

        self.q_warp_angle = float(np.degrees(np.max(np.abs(s) /
                                                    np.maximum(self.q_alt0, 1e-30))))

    # ---- constant-strain-triangle fallback --------------------------------
    def _cst_membrane_forces(self, f: np.ndarray) -> None:
        st = self.st
        t0 = st.tris[:, 0]
        d2 = st.x[st.tris[:, 1]] - st.x[t0]
        d3 = st.x[st.tris[:, 2]] - st.x[t0]

        Xc = np.empty((st.tris.shape[0], 2, 2))
        Xc[:, :, 0] = np.stack([np.einsum("ij,ij->i", d2, self.tex),
                                np.einsum("ij,ij->i", d2, self.tey)], axis=1)
        Xc[:, :, 1] = np.stack([np.einsum("ij,ij->i", d3, self.tex),
                                np.einsum("ij,ij->i", d3, self.tey)], axis=1)
        F = np.einsum("nij,njk->nik", Xc, self.Xinv)

        FtF = np.einsum("nji,njk->nik", F, F)
        E = 0.5 * (FtF - np.eye(2)[None])
        S11 = self.C11 * E[:, 0, 0] + self.C12 * E[:, 1, 1]
        S22 = self.C12 * E[:, 0, 0] + self.C22 * E[:, 1, 1]
        S12 = 2.0 * self.C66 * E[:, 0, 1]
        S = np.stack([np.stack([S11, S12], axis=1),
                      np.stack([S12, S22], axis=1)], axis=1)
        P = np.einsum("nij,njk->nik", F, S)

        t2 = np.einsum("nij,nj->ni", P, self.Xinv[:, 0, :])
        t3 = np.einsum("nij,nj->ni", P, self.Xinv[:, 1, :])
        scale = -self.vol0
        f2 = scale[:, None] * (t2[:, 0, None] * self.tex + t2[:, 1, None] * self.tey)
        f3 = scale[:, None] * (t3[:, 0, None] * self.tex + t3[:, 1, None] * self.tey)
        f1 = -(f2 + f3)

        for k in range(3):
            np.add.at(f[:, k], st.tris[:, 0], f1[:, k])
            np.add.at(f[:, k], st.tris[:, 1], f2[:, k])
            np.add.at(f[:, k], st.tris[:, 2], f3[:, k])

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

    # ------------------------------------------------------------ line forces
    def beam_tension(self) -> np.ndarray:
        """Axial tension carried by every suspension-line element [N].

        Only the elastic (tension-only) part is returned, so the value is the
        actual force in the cable rather than the damping contribution.
        """
        st = self.st
        if st.beams.size == 0:
            return np.zeros(0)
        d = st.x[st.beams[:, 1]] - st.x[st.beams[:, 0]]
        L = np.maximum(np.linalg.norm(d, axis=1), 1e-12)
        ext = L - st.beam_L0
        if self.tension_only:
            ext = np.maximum(ext, 0.0)
        return self.beam_k * ext

    def beam_anchor_force(self) -> float:
        """Magnitude of the resultant line force acting on the fixed nodes."""
        st = self.st
        if st.beams.size == 0 or st.fixed.size == 0:
            return 0.0
        d = st.x[st.beams[:, 1]] - st.x[st.beams[:, 0]]
        L = np.maximum(np.linalg.norm(d, axis=1), 1e-12)
        t = self.beam_tension()
        fvec = (t / L)[:, None] * d
        fb = np.zeros_like(st.x)
        for k in range(3):
            np.add.at(fb[:, k], st.beams[:, 0], fvec[:, k])
            np.add.at(fb[:, k], st.beams[:, 1], -fvec[:, k])
        return float(np.linalg.norm(fb[st.fixed].sum(axis=0)))

    # ------------------------------------------------------- per-line tension
    def _build_lines(self) -> None:
        """Split the beam mesh into the physical suspension lines.

        Each line is the connected chain of beam elements between the canopy
        attachment and the common fixed anchor.  The *anchor* segment (the one
        touching the fixed end) carries the whole line load and is the
        quantity plotted in the reference presentation.
        """
        st = self.st
        self.line_anchor_beam = np.zeros(0, dtype=np.int64)
        self.line_count = 0
        self._line_beams = []
        if st.beams.size == 0:
            return
        from scipy.sparse import coo_matrix
        from scipy.sparse.csgraph import connected_components

        i = st.beams[:, 0]
        j = st.beams[:, 1]
        nb = st.beams.shape[0]
        nn = st.nnode
        fs = np.zeros(nn, dtype=bool)
        if st.fixed.size:
            fs[st.fixed] = True

        if fs.any():
            # all 16 lines meet at the common anchor node; removing the fixed
            # nodes from the graph splits them into the physical lines again
            keep = ~(fs[i] | fs[j])
            g = coo_matrix((np.ones(int(keep.sum())), (i[keep], j[keep])),
                           shape=(nn, nn)).tocsr()
            _, labels = connected_components(g, directed=False)
            blab = np.where(fs[i], labels[j], np.where(fs[j], labels[i], labels[i]))
            valid = (blab >= 0) & (blab < nn)
            comps = np.unique(blab[valid])
            anchor = []
            line_beams = []
            for c in comps:
                members = np.nonzero(valid & (blab == c))[0]
                if members.size == 0:
                    continue
                touch = members[fs[i[members]] | fs[j[members]]]
                sel = touch[0] if touch.size else members[0]
                anchor.append(sel)
                line_beams.append(members)
        else:
            g = coo_matrix((np.ones(nb), (i, j), ), shape=(nn, nn)).tocsr()
            ncomp, labels = connected_components(g, directed=False)
            anchor, line_beams = [], []
            for c in range(ncomp):
                members = np.nonzero(labels[i] == c)[0]
                if members.size == 0:
                    continue
                ymin = np.minimum(st.x[i[members], 1], st.x[j[members], 1])
                anchor.append(members[np.argmin(ymin)])
                line_beams.append(members)

        self.line_anchor_beam = np.asarray(anchor, dtype=np.int64)
        self.line_count = self.line_anchor_beam.size
        self._line_beams = line_beams

    def line_tension(self) -> np.ndarray:
        """Tension [N] of the anchor segment of every suspension line."""
        if self.line_anchor_beam.size == 0:
            return np.zeros(0)
        return self.beam_tension()[self.line_anchor_beam]

    def line_max_tension(self) -> np.ndarray:
        """Largest tension anywhere along every suspension line."""
        if self.line_anchor_beam.size == 0:
            return np.zeros(0)
        t = self.beam_tension()
        return np.asarray([t[b].max() if b.size else 0.0
                           for b in self._line_beams])

    # ------------------------------------------------------------ properties
    def stable_dt(self) -> float:
        st = self.st
        # *MAT_FABRIC EA is [Pa]; the membrane wave speed is sqrt(EA/rho)
        c = float(np.sqrt(np.max(st.tri_ea / st.tri_rho)))
        dt_s = np.inf
        if self.use_quads:
            h0 = float(self.q_alt0.min())
            hc = h0
            dt_q = hc / max(c, 1e-9)
            m_hg = float(np.min(self.q_mass))
            k_hg = float(np.max(self.q_khg))
            dt_hg = 0.9 * 2.0 * np.sqrt(m_hg / max(k_hg, 1e-12))
            dt_s = min(dt_q, dt_hg)
            if self.q_kw.size and float(np.max(self.q_kw)) > 0.0:
                k_w = float(np.max(self.q_kw))
                dt_w = 0.9 * 2.0 * np.sqrt(m_hg / max(k_w, 1e-12))
                dt_s = min(dt_s, dt_w)
        else:
            h0 = float(self.alt0.min()) if self.alt0.size else 1e-3
            hc = float(self.alt_cur.min()) if self.alt_cur.size else h0
            hc = max(hc, self.alt_floor * h0)
            dt_s = min(h0, hc) / max(c, 1e-9)
        if st.beams.size:
            k = float(np.max(self.beam_k))
            m = float(np.min(st.beam_mass))
            dt_b = 0.9 * np.sqrt(m / max(k, 1e-12))
            dt_s = min(dt_s, dt_b)
        return float(dt_s)


def _group_driven(st):
    """Yield (dof, lcid, node ids) with identical prescribed motion."""
    key = {}
    for k in range(st.driven.size):
        key.setdefault((int(st.driven_dof[k]), int(st.driven_curve[k]),
                        float(st.driven_sf[k])), []).append(int(st.driven[k]))
    for (dof, lcid, sf), ids in key.items():
        yield dof, lcid, np.asarray(ids, dtype=np.int64)
